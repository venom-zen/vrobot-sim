"""Discrete simulation clock: advance all robots one step and collect snapshots."""

from __future__ import annotations

from vrobot_sim.map_model import TopologyMap
from vrobot_sim.maps import BUILT_IN_MAP_IDS, load_map
from vrobot_sim.obstacle_field import ObstacleField
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
    ):
        self._scenario = scenario
        self._obstacles = obstacles
        self._command_source = command_source
        self._robots = tuple(
            Robot(spec, topology_map, scenario.dt_s, SafetyMonitor(), obstacles) for spec in scenario.robots
        )
        self._tick_index = 0
        self._sim_time_s = 0.0

    @staticmethod
    def create(scenario: Scenario, command_source: CommandSource | None = None) -> Simulation:
        """Validate first, then build. A rejected configuration never yields a half-built kernel."""
        if scenario.map_id not in BUILT_IN_MAP_IDS:
            raise ScenarioValidationError(scenario.validate(None))
        topology_map = load_map(scenario.map_id)
        violations = scenario.validate(topology_map)
        if violations:
            raise ScenarioValidationError(violations)
        return Simulation(
            scenario,
            topology_map,
            ObstacleField(scenario.obstacles),
            command_source if command_source is not None else PassthroughCommandSource(scenario.robots),
        )

    @property
    def obstacles(self) -> ObstacleField:
        """The obstacle registration entry point of IF-PROTO-obstacle-registration."""
        return self._obstacles

    def step(self) -> TickSnapshot:
        """Advance the clock by dt, dispatch commands, then move every robot once."""
        self._sim_time_s += self._scenario.dt_s
        self._command_source.dispatch(self._tick_index, self._robots)
        for robot in self._robots:
            robot.tick()
        snapshot = TickSnapshot(
            tick_index=self._tick_index,
            sim_time_s=self._sim_time_s,
            robots=tuple(
                RobotSnapshot.from_robot(robot)
                for robot in sorted(self._robots, key=lambda item: item.robot_id)
            ),
        )
        self._tick_index += 1
        return snapshot
