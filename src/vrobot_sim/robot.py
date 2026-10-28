"""Robot runtime object, status transitions and command intake boundary."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Protocol, Sequence, runtime_checkable

from vrobot_sim.controller import Controller
from vrobot_sim.kinematics import Pose, advance_pose, normalize_theta
from vrobot_sim.map_model import EdgeDirection, SegmentGeometry, TopologyMap
from vrobot_sim.obstacle_field import ObstacleField

if TYPE_CHECKING:
    # The monitor is injected by the simulation so that safety can keep reading the reason
    # enum declared here, which keeps the per-tick call graph free of an import cycle.
    from vrobot_sim.safety import SafetyMonitor


class RobotStatus(Enum):
    """Frozen six-member set shared by the three Now items.

    ``WAITING_RIGHT`` and ``HOLDING_ZONE`` are declared here but never produced by this
    work item; their transitions belong to WI-mutex-scheduling.
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

    @property
    def robot_id(self) -> str:
        return self.spec.robot_id

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

    def tick(self) -> None:
        """Advance one step: hazard judgement, then control, then pose integration."""
        if self.status in (RobotStatus.IDLE, RobotStatus.ARRIVED) or not self.path_node_ids:
            return

        segment = self._segment(self.segment_index)
        request = self._safety.check(self, self._obstacles.active(), segment, self.dt)

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

        self._linear_step(segment)

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
        )
        if request is not EStopReason.NONE:
            # Still unsafe: a legal transition that leaves the pose untouched.
            self.estop_reason = request
            return CommandResult(accepted=True)
        self.status = RobotStatus.MOVING
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
        self.status = RobotStatus.MOVING
        self.estop_reason = EStopReason.NONE
        self._aim_at_segment(0)

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
        if not target.aligned:
            self.turn_remaining_rad = normalize_theta(segment.heading_rad - self.pose.theta)
            return
        # Alignment completion sets theta to the exact segment direction in the same tick.
        self.pose = Pose(self.pose.x, self.pose.y, normalize_theta(segment.heading_rad))
        self.turn_remaining_rad = 0.0
        self.segment_remaining_m = segment.length_m

    def _linear_step(self, segment: SegmentGeometry) -> None:
        heading = normalize_theta(segment.heading_rad)
        self.omega_radps = 0.0
        self.v_mps = self._controller.linear_step(self.v_mps, self.segment_remaining_m)
        self.pose = advance_pose(self.pose, self.v_mps, 0.0, self.dt, heading)
        self.segment_remaining_m -= self.v_mps * self.dt
        if self._controller.segment_finished(self.segment_remaining_m, self.v_mps):
            self._finish_segment(segment, heading)

    def _finish_segment(self, segment: SegmentGeometry, heading: float) -> None:
        # Discretisation leaves the robot a fraction of a metre off the node; landing on the
        # node is what keeps the centroid on the next segment's centerline as the model asks.
        node_x, node_y = _node_position(self._map, segment.to_node_id)
        self.pose = Pose(node_x, node_y, heading)
        self.segment_remaining_m = 0.0
        self.current_node_id = segment.to_node_id
        if self.segment_index >= len(self.path_node_ids) - 2:
            self.v_mps = 0.0
            self.omega_radps = 0.0
            self.status = RobotStatus.ARRIVED
            return
        self.segment_index += 1
        self._aim_at_segment(self.segment_index)

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
