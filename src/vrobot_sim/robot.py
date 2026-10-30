"""Robot runtime object, status transitions and command intake boundary."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Protocol, Sequence, runtime_checkable

from vrobot_sim.controller import Controller
from vrobot_sim.kinematics import Pose, advance_pose, normalize_theta
from vrobot_sim.map_model import EdgeDirection, SegmentGeometry, TopologyMap
from vrobot_sim.obstacle_field import Obstacle, ObstacleField
from vrobot_sim.rights import GrantOutcome, RightOfWayArbiter

if TYPE_CHECKING:
    # The monitor is injected by the simulation so that safety can keep reading the reason
    # enum declared here, which keeps the per-tick call graph free of an import cycle.
    from vrobot_sim.safety import SafetyMonitor


class RobotStatus(Enum):
    """Frozen six-member set shared by the three Now items.

    ``WAITING_RIGHT`` marks a robot stopped at an entrance without the right of way;
    ``HOLDING_ZONE`` marks a robot that holds at least one critical zone. Both are only
    produced for robots with an injected arbiter.
    """

    IDLE = "idle"
    MOVING = "moving"
    E_STOP = "e_stop"
    ARRIVED = "arrived"
    WAITING_RIGHT = "waiting_right"
    HOLDING_ZONE = "holding_zone"


class EStopReason(Enum):
    """Which e-stop branch ended the motion; ``NONE`` outside an e-stop."""

    NONE = "none"
    SAFETY_DISTANCE = "safety_distance"
    OVERLAP = "overlap"


class CommandKind(Enum):
    ASSIGN_PATH = "assign_path"
    RESUME = "resume"


class CommandRejection(Enum):
    INVALID_STATE = "invalid_state"
    PATH_UNAVAILABLE = "path_unavailable"
    TARGET_MISMATCH = "target_mismatch"
    MALFORMED_PAYLOAD = "malformed_payload"


@dataclass(frozen=True)
class ChassisConfig:
    """Physical limits for one chassis. Limit ranges are validated at simulation creation."""

    v_max_mps: float = 1.5
    a_max_mps2: float = 0.8
    decel_max_mps2: float = 1.5
    omega_max_radps: float = 1.2
    body_radius_m: float = 0.35
    turn_align_tolerance_rad: float = 0.02
    arrival_tolerance_m: float = 0.02


@dataclass(frozen=True)
class RobotSpec:
    robot_id: str
    chassis: ChassisConfig
    vehicle_class: str
    start_node_id: str
    start_theta_rad: float
    planned_node_path: tuple[str, ...]
    start_tick: int = 0


@dataclass(frozen=True)
class MotionCommand:
    """Payload of IF-PROTO-robot-command-intake. The robot only reads the payload."""

    kind: CommandKind
    robot_id: str
    node_path: tuple[str, ...] = ()


@dataclass(frozen=True)
class CommandResult:
    """Accept or reject answer, listing every path violation at once when rejected."""

    accepted: bool
    rejection: CommandRejection | None = None
    violations: tuple[str, ...] = ()


class Robot:
    """One simulated AMR: pose, speed and status, advanced safety then control then integration."""

    def __init__(
        self,
        spec: RobotSpec,
        topology_map: TopologyMap,
        dt: float,
        safety_monitor: SafetyMonitor,
        obstacles: ObstacleField,
        arbiter: RightOfWayArbiter | None = None,
    ):
        self.spec = spec
        self.dt = dt
        self.pose = Pose(*_node_position(topology_map, spec.start_node_id), normalize_theta(spec.start_theta_rad))
        self.v_mps = 0.0
        self.omega_radps = 0.0
        self.status = RobotStatus.IDLE
        self.estop_reason = EStopReason.NONE
        self.path_node_ids: tuple[str, ...] = ()
        self.path_edge_ids: tuple[str, ...] = ()
        self.segment_index = 0
        self.segment_remaining_m = 0.0
        self.turn_remaining_rad = 0.0
        self.current_node_id = spec.start_node_id

        self._map = topology_map
        self._controller = Controller(spec.chassis, dt)
        self._safety = safety_monitor
        self._obstacles = obstacles
        self._arbiter = arbiter
        self._holding_zone_ids: set[str] = set()
        # One pending application for the segment the robot is trying to enter.
        self._pending_request: tuple[int, tuple[str, ...]] | None = None
        # The other robots' circles as captured at the start of the current tick.
        self._peer_circles: tuple[Obstacle, ...] = ()

    @property
    def robot_id(self) -> str:
        return self.spec.robot_id

    @property
    def holding_zone_ids(self) -> tuple[str, ...]:
        """The zones this robot holds, ordered by identifier."""
        return tuple(sorted(self._holding_zone_ids))

    def set_peer_circles(self, circles: Sequence[Obstacle]) -> None:
        """Fix this tick's peer input; the caller excludes this robot from the set."""
        self._peer_circles = tuple(circles)

    def receive(self, command: MotionCommand) -> CommandResult:
        if command.robot_id != self.robot_id:
            return CommandResult(
                accepted=False,
                rejection=CommandRejection.TARGET_MISMATCH,
                violations=(f"command targets {command.robot_id} but this robot is {self.robot_id}",),
            )
        if command.kind is CommandKind.ASSIGN_PATH:
            return self._intake_assign_path(command.node_path)
        return self._intake_resume(command.node_path)

    def tick(self, tick_index: int = 0) -> None:
        """Advance one step: rights gate, hazard judgement, control and integration."""
        if self.status in (RobotStatus.IDLE, RobotStatus.ARRIVED) or not self.path_node_ids:
            return

        if self._pending_request is not None:
            if not self._apply_pending_request(tick_index):
                self._wait_at_entrance()
                return

        segment = self._segment(self.segment_index)
        request = self._safety.check(
            self, self._obstacles.active(), segment, self.dt, peers=self._peer_circles
        )

        if request is EStopReason.OVERLAP:
            self.status = RobotStatus.E_STOP
            self.estop_reason = EStopReason.OVERLAP
            self.v_mps = 0.0
            self.omega_radps = 0.0
            return
        if request is EStopReason.SAFETY_DISTANCE:
            self.status = RobotStatus.E_STOP
            self.estop_reason = EStopReason.SAFETY_DISTANCE
            self._brake_to_halt(segment)
            return
        if self.status is RobotStatus.E_STOP:
            # The hazard cleared but this robot is still braking. Recovery stays a command,
            # so it never restarts motion here even when the path ahead is empty.
            self._brake_to_halt(segment)
            return

        if self.turn_remaining_rad != 0.0:
            self._turn_step(segment)
            return

        self._linear_step(segment, tick_index)

    def _intake_assign_path(self, node_path: Sequence[str]) -> CommandResult:
        if self.status not in (RobotStatus.IDLE, RobotStatus.ARRIVED):
            return _invalid_state("ASSIGN_PATH", self.status)
        violations = self._validate_path(node_path)
        if violations:
            return CommandResult(
                accepted=False,
                rejection=CommandRejection.PATH_UNAVAILABLE,
                violations=tuple(violations),
            )
        self._start_path(tuple(node_path))
        return CommandResult(accepted=True)

    def _intake_resume(self, node_path: Sequence[str]) -> CommandResult:
        if self.status is not RobotStatus.E_STOP:
            return _invalid_state("RESUME", self.status)
        if node_path:
            return CommandResult(
                accepted=False,
                rejection=CommandRejection.MALFORMED_PAYLOAD,
                violations=(f"RESUME must not carry a node path, got {list(node_path)}",),
            )
        segment = self._segment(self.segment_index)
        request = self._safety.check(
            self,
            self._obstacles.active(),
            segment,
            self.dt,
            reference_v_mps=self.spec.chassis.v_max_mps,
            peers=self._peer_circles,
        )
        if request is not EStopReason.NONE:
            # Still unsafe: a legal transition that leaves the pose untouched.
            self.estop_reason = request
            return CommandResult(accepted=True)
        self.status = self._holding_status()
        self.estop_reason = EStopReason.NONE
        return CommandResult(accepted=True)

    def _validate_path(self, node_path: Sequence[str]) -> list[str]:
        violations: list[str] = []
        known_ids = {node.node_id for node in self._map.nodes}
        if len(node_path) < 2:
            violations.append(f"node path must name at least two nodes, got {list(node_path)}")
        if node_path and node_path[0] != self.current_node_id:
            violations.append(f"path starts at {node_path[0]} while the robot stands on {self.current_node_id}")
        for node_id in node_path:
            if node_id not in known_ids:
                violations.append(f"node {node_id} is not in map {self._map.map_id}")
        for from_id, to_id in zip(node_path, node_path[1:]):
            if from_id not in known_ids or to_id not in known_ids:
                continue
            if self._map.edge_by_node_pair.get((from_id, to_id)) is not None:
                continue
            reverse = self._map.edge_by_node_pair.get((to_id, from_id))
            if reverse is not None and reverse.direction is EdgeDirection.FWD:
                violations.append(
                    f"edge {reverse.edge_id} is one-way {reverse.from_node_id}->{reverse.to_node_id}"
                    f" and cannot be travelled {from_id}->{to_id}"
                )
            else:
                violations.append(f"no edge connects node pair {(from_id, to_id)}")
        return violations

    def _start_path(self, node_path: tuple[str, ...]) -> None:
        self.path_node_ids = node_path
        self.path_edge_ids = tuple(
            self._map.edge_by_node_pair[pair].edge_id for pair in zip(node_path, node_path[1:])
        )
        self.segment_index = 0
        self.current_node_id = node_path[0]
        self.estop_reason = EStopReason.NONE
        # The first application is made by the first tick, not here: a grant can only
        # be settled in a dispatch phase, so nothing is lost by asking a moment later.
        self._begin_segment_entry(0)

    def _aim_at_segment(self, segment_index: int) -> None:
        """Enter the turning sub-phase, or start the linear one when already aligned."""
        segment = self._segment(segment_index)
        deviation = normalize_theta(segment.heading_rad - self.pose.theta)
        self.turn_remaining_rad = 0.0 if abs(deviation) <= self.spec.chassis.turn_align_tolerance_rad else deviation
        # Remaining length is set once the turn lands on the segment direction.
        self.segment_remaining_m = segment.length_m if self.turn_remaining_rad == 0.0 else 0.0

    def _turn_step(self, segment: SegmentGeometry) -> None:
        target = self._controller.turn_step(self.turn_remaining_rad)
        self.v_mps = 0.0
        self.omega_radps = target.omega_radps
        self.pose = advance_pose(self.pose, 0.0, target.omega_radps, self.dt, segment.heading_rad)
        self.turn_remaining_rad = normalize_theta(segment.heading_rad - self.pose.theta)
        # A deadbeat step can land exactly on the heading outside the tolerance test; the
        # turn is over then too, and the segment length must be restored in the same tick.
        if not target.aligned and self.turn_remaining_rad != 0.0:
            return
        # Alignment completion sets theta to the exact segment direction in the same tick.
        self.pose = Pose(self.pose.x, self.pose.y, normalize_theta(segment.heading_rad))
        self.turn_remaining_rad = 0.0
        self.segment_remaining_m = segment.length_m

    def _linear_step(self, segment: SegmentGeometry, tick_index: int) -> None:
        heading = normalize_theta(segment.heading_rad)
        self.omega_radps = 0.0
        self.v_mps = self._controller.linear_step(self.v_mps, self.segment_remaining_m)
        self.pose = advance_pose(self.pose, self.v_mps, 0.0, self.dt, heading)
        self.segment_remaining_m -= self.v_mps * self.dt
        if self._controller.segment_finished(self.segment_remaining_m, self.v_mps):
            self._finish_segment(segment, heading, tick_index)

    def _finish_segment(self, segment: SegmentGeometry, heading: float, tick_index: int) -> None:
        # Discretisation leaves the robot a fraction of a metre off the node; landing on the
        # node is what keeps the centroid on the next segment's centerline as the model asks.
        node_x, node_y = _node_position(self._map, segment.to_node_id)
        self.pose = Pose(node_x, node_y, heading)
        self.segment_remaining_m = 0.0
        self.current_node_id = segment.to_node_id
        if self.segment_index >= len(self.path_node_ids) - 2:
            self._release_all_zones()
            self.v_mps = 0.0
            self.omega_radps = 0.0
            self.status = RobotStatus.ARRIVED
            return
        self._begin_segment_entry(self.segment_index + 1)
        if self._pending_request is not None:
            # The switch moment is also the moment the application is filed.
            if not self._apply_pending_request(tick_index):
                self._wait_at_entrance()

    def _brake_to_halt(self, segment: SegmentGeometry) -> None:
        self.omega_radps = 0.0
        self.v_mps = self._controller.estop_step(self.v_mps)
        if self.v_mps <= 0.0:
            return
        self.pose = advance_pose(self.pose, self.v_mps, 0.0, self.dt, normalize_theta(segment.heading_rad))
        self.segment_remaining_m = max(0.0, self.segment_remaining_m - self.v_mps * self.dt)

    def _segment(self, segment_index: int) -> SegmentGeometry:
        from_id = self.path_node_ids[segment_index]
        to_id = self.path_node_ids[segment_index + 1]
        return self._map.segment_geometry(from_id, to_id)

    def _zone_ids_of_segment(self, segment_index: int) -> tuple[str, ...]:
        return self._map.edge_zones.get(self.path_edge_ids[segment_index], ())

    def _begin_segment_entry(self, segment_index: int) -> None:
        """Enter the segment when no unheld zone is involved; otherwise queue at its entrance."""
        required = tuple(
            sorted(set(self._zone_ids_of_segment(segment_index)) - self._holding_zone_ids)
        )
        if self._arbiter is None or not required:
            self._enter_segment(segment_index)
            return
        self._pending_request = (segment_index, required)
        self._wait_at_entrance()

    def _apply_pending_request(self, tick_index: int) -> bool:
        """Repeat the pending application; a grant switches segments and lets the tick go on."""
        segment_index, zone_ids = self._pending_request
        outcome = self._arbiter.request_right(self.robot_id, segment_index, zone_ids, tick_index)
        if outcome is not GrantOutcome.GRANTED:
            return False
        self._holding_zone_ids.update(zone_ids)
        self._pending_request = None
        self._enter_segment(segment_index)
        return True

    def _enter_segment(self, segment_index: int) -> None:
        """Make-before-break: release zones that do not cover the new segment, then aim at it."""
        target = set(self._zone_ids_of_segment(segment_index))
        stale = self._holding_zone_ids - target
        if stale:
            self._arbiter.release_right(self.robot_id, tuple(sorted(stale)))
            self._holding_zone_ids -= stale
        self.segment_index = segment_index
        self._aim_at_segment(segment_index)
        self.status = self._holding_status()

    def _release_all_zones(self) -> None:
        if not self._holding_zone_ids:
            return
        self._arbiter.release_right(self.robot_id, tuple(sorted(self._holding_zone_ids)))
        self._holding_zone_ids.clear()

    def _wait_at_entrance(self) -> None:
        self.status = RobotStatus.WAITING_RIGHT
        self.v_mps = 0.0
        self.omega_radps = 0.0

    def _holding_status(self) -> RobotStatus:
        return RobotStatus.HOLDING_ZONE if self._holding_zone_ids else RobotStatus.MOVING


@runtime_checkable
class CommandSource(Protocol):
    """Producer side of IF-PROTO-robot-command-intake."""

    def dispatch(self, tick_index: int, robots: Sequence[Robot]) -> None: ...


class PassthroughCommandSource:
    """Built-in source: hands each robot its planned_node_path at its start_tick."""

    def __init__(self, specs: Sequence[RobotSpec]):
        by_tick: dict[int, list[tuple[str, tuple[str, ...]]]] = {}
        for spec in specs:
            by_tick.setdefault(spec.start_tick, []).append((spec.robot_id, spec.planned_node_path))
        self._by_tick = {tick: sorted(items) for tick, items in by_tick.items()}

    def dispatch(self, tick_index: int, robots: Sequence[Robot]) -> None:
        targets = {robot.robot_id: robot for robot in robots}
        for robot_id, node_path in self._by_tick.get(tick_index, ()):
            targets[robot_id].receive(
                MotionCommand(kind=CommandKind.ASSIGN_PATH, robot_id=robot_id, node_path=node_path)
            )


def _invalid_state(command_name: str, status: RobotStatus) -> CommandResult:
    return CommandResult(
        accepted=False,
        rejection=CommandRejection.INVALID_STATE,
        violations=(f"{command_name} is not accepted in {status.name}",),
    )


def _node_position(topology_map: TopologyMap, node_id: str) -> tuple[float, float]:
    node = topology_map.node(node_id)
    return node.x, node.y
