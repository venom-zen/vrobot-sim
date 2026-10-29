"""Discrete simulation clock: advance all robots one step and collect snapshots."""

from __future__ import annotations

from vrobot_sim.dispatcher import FcfsDispatcher, ScheduledDispatcher, ZoneStateProvider
from vrobot_sim.map_model import TopologyMap
from vrobot_sim.maps import BUILT_IN_MAP_IDS, load_map
from vrobot_sim.obstacle_field import Obstacle, ObstacleField
from vrobot_sim.rights import RightOfWayArbiter
from vrobot_sim.robot import CommandSource, PassthroughCommandSource, Robot
from vrobot_sim.safety import SafetyMonitor
from vrobot_sim.scenario import Scenario, ScenarioValidationError
from vrobot_sim.snapshots import RobotSnapshot, TickSnapshot


class Simulation:
    """One scenario's kernel. The clock only moves when the caller steps it."""

    def __init__(
        self,
        scenario: Scenario,
        topology_map: TopologyMap,
        obstacles: ObstacleField,
        command_source: CommandSource,
        arbiter: RightOfWayArbiter | None = None,
        zone_state_provider: ZoneStateProvider | None = None,
    ):
        self._scenario = scenario
        self._obstacles = obstacles
        self._command_source = command_source
        self._zone_state_provider = zone_state_provider
        self._robots = tuple(
            Robot(spec, topology_map, scenario.dt_s, SafetyMonitor(), obstacles, arbiter)
            for spec in scenario.robots
        )
        self._tick_index = 0
        self._sim_time_s = 0.0

    @staticmethod
    def create(scenario: Scenario, command_source: CommandSource | None = None) -> Simulation:
        """Validate first, then build. A rejected configuration never yields a half-built kernel."""
        topology_map = _validated_topology(scenario)
        return Simulation(
            scenario,
            topology_map,
            ObstacleField(scenario.obstacles),
            command_source if command_source is not None else PassthroughCommandSource(scenario.robots),
        )

    @staticmethod
    def create_scheduled(
        scenario: Scenario, dispatcher: ScheduledDispatcher | None = None
    ) -> Simulation:
        """Like ``create``, but one dispatcher supplies commands, arbitration and zone state."""
        topology_map = _validated_topology(scenario)
        scheduler = dispatcher if dispatcher is not None else FcfsDispatcher(scenario.robots, topology_map)
        return Simulation(
            scenario,
            topology_map,
            ObstacleField(scenario.obstacles),
            command_source=scheduler,
            arbiter=scheduler,
            zone_state_provider=scheduler,
        )

    @property
    def obstacles(self) -> ObstacleField:
        """The obstacle registration entry point of IF-PROTO-obstacle-registration."""
        return self._obstacles

    def step(self) -> TickSnapshot:
        """Advance the clock by dt: fix peer input, dispatch, move every robot, snapshot."""
        self._sim_time_s += self._scenario.dt_s
        circles = tuple(
            Obstacle(robot.robot_id, robot.pose.x, robot.pose.y, robot.spec.chassis.body_radius_m)
            for robot in self._robots
        )
        for robot in self._robots:
            robot.set_peer_circles(
                tuple(circle for circle in circles if circle.obstacle_id != robot.robot_id)
            )
        self._command_source.dispatch(self._tick_index, self._robots)
        for robot in self._robots:
            robot.tick(self._tick_index)
        # Zone state is read after the advance, so it reflects the tick-end occupancy.
        zones = self._zone_state_provider.read_zone_state() if self._zone_state_provider else ()
        snapshot = TickSnapshot(
            tick_index=self._tick_index,
            sim_time_s=self._sim_time_s,
            robots=tuple(
                RobotSnapshot.from_robot(robot)
                for robot in sorted(self._robots, key=lambda item: item.robot_id)
            ),
            zones=zones,
        )
        self._tick_index += 1
        return snapshot


def _validated_topology(scenario: Scenario) -> TopologyMap:
    """Load the built-in map and list every scenario violation before anything is built."""
    if scenario.map_id not in BUILT_IN_MAP_IDS:
        raise ScenarioValidationError(scenario.validate(None))
    topology_map = load_map(scenario.map_id)
    violations = scenario.validate(topology_map)
    if violations:
        raise ScenarioValidationError(violations)
    return topology_map
