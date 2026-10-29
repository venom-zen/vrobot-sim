"""Kernel, snapshot and creation-time configuration validation tests."""

from __future__ import annotations

import dataclasses
import math

import pytest
from conftest import ASSERT_TOL, DT_S, V_MAX_MPS, make_spec, obstacle_at
from vrobot_sim.dispatcher import FcfsDispatcher
from vrobot_sim.maps import load_map
from vrobot_sim.maps.demo import DEMO_MAP_ID
from vrobot_sim.maps.minimal import MINIMAL_MAP_ID
from vrobot_sim.obstacle_field import Obstacle
from vrobot_sim.robot import ChassisConfig, EStopReason, RobotStatus
from vrobot_sim.scenario import Scenario, ScenarioValidationError
from vrobot_sim.simulation import Simulation
from vrobot_sim.snapshots import RobotSnapshot, TickSnapshot

PATH = ("N01", "N02", "N03")


def _scenario(**overrides) -> Scenario:
    base = {
        "map_id": MINIMAL_MAP_ID,
        "dt_s": DT_S,
        "robots": (make_spec(robot_id="R1", path=PATH),),
        "obstacles": (),
    }
    base.update(overrides)
    return Scenario(**base)


def _run(sim: Simulation, ticks: int) -> list[TickSnapshot]:
    return [sim.step() for _ in range(ticks)]


def test_one_step_advances_the_clock_by_exactly_dt_and_moves_every_robot_once():
    sim = Simulation.create(_scenario(dt_s=0.05))
    first = sim.step()
    assert first.tick_index == 0
    assert first.sim_time_s == pytest.approx(0.05, abs=ASSERT_TOL)

    previous = first
    for _ in range(40):
        current = sim.step()
        assert current.tick_index == previous.tick_index + 1
        assert current.sim_time_s - previous.sim_time_s == pytest.approx(0.05, abs=ASSERT_TOL)
        moved = current.robots[0].x_m - previous.robots[0].x_m
        assert moved == pytest.approx(current.robots[0].v_mps * 0.05, abs=ASSERT_TOL)
        previous = current


def test_snapshot_carries_every_declared_field_and_no_zone_occupancy():
    sim = Simulation.create(
        _scenario(
            robots=(
                make_spec(robot_id="R2", path=PATH, start_node_id="N01"),
                make_spec(robot_id="R10", path=("N02", "N03"), start_node_id="N02"),
            )
        )
    )
    snapshot = sim.step()
    assert [item.robot_id for item in snapshot.robots] == ["R10", "R2"]
    assert [field.name for field in dataclasses.fields(TickSnapshot)] == [
        "tick_index",
        "sim_time_s",
        "robots",
        "zones",
    ]
    assert snapshot.zones == ()
    assert [field.name for field in dataclasses.fields(RobotSnapshot)] == [
        "robot_id",
        "x_m",
        "y_m",
        "theta_rad",
        "v_mps",
        "omega_radps",
        "status",
        "estop_reason",
    ]
    for robot_snapshot in snapshot.robots:
        assert robot_snapshot.status is RobotStatus.MOVING
        assert isinstance(robot_snapshot.theta_rad, float)


def test_snapshots_are_immutable():
    sim = Simulation.create(_scenario())
    snapshot = sim.step()
    with pytest.raises(dataclasses.FrozenInstanceError):
        snapshot.tick_index = 99  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        snapshot.robots[0].v_mps = 9.0  # type: ignore[misc]


def test_the_same_scenario_twice_produces_identical_snapshot_sequences():
    scenario = _scenario(
        robots=(
            make_spec(robot_id="R1", path=PATH),
            make_spec(robot_id="R2", path=("N02", "N03"), start_node_id="N02", start_tick=1),
        ),
        obstacles=(obstacle_at(5.0, 0.0),),
    )
    first = _run(Simulation.create(scenario), 500)
    second = _run(Simulation.create(scenario), 500)
    assert first == second
    assert len(first) == 500


def test_stepping_keeps_returning_snapshots_after_every_robot_has_finished():
    sim = Simulation.create(_scenario(robots=(make_spec(robot_id="R1", path=("N01", "N02")),)))
    for _ in range(4000):
        snapshot = sim.step()
        if snapshot.robots[0].status is RobotStatus.ARRIVED:
            break
    held = [(snapshot.robots[0].x_m, snapshot.robots[0].v_mps, snapshot.robots[0].status)]
    for _ in range(25):
        snapshot = sim.step()
        assert snapshot.robots[0].status is RobotStatus.ARRIVED
        assert snapshot.robots[0].v_mps == 0.0
    assert held == [(10.0, 0.0, RobotStatus.ARRIVED)]


def test_a_registered_obstacle_is_visible_to_every_robot_from_the_next_tick():
    sim = Simulation.create(
        _scenario(
            robots=(
                make_spec(robot_id="R1", path=("N01", "N02")),
                make_spec(
                    robot_id="R2",
                    path=("N02", "N01"),
                    start_node_id="N02",
                    start_theta_rad=math.pi,
                    start_tick=1,
                ),
            )
        )
    )
    _run(sim, 60)
    assert sim.obstacles.register(obstacle_at(4.0, 0.0)).accepted

    stopped = []
    for _ in range(900):
        snapshot = sim.step()
        stopped = [item.status for item in snapshot.robots]
        if all(item is RobotStatus.E_STOP for item in stopped):
            break
    assert stopped == [RobotStatus.E_STOP, RobotStatus.E_STOP]


@pytest.mark.parametrize("bad_dt", [0.0, -0.01, 0.050001, 1.0])
def test_invalid_dt_fails_creation_and_names_the_field_and_range(bad_dt):
    with pytest.raises(ScenarioValidationError) as excinfo:
        Simulation.create(_scenario(dt_s=bad_dt))
    message = str(excinfo.value)
    assert "dt_s" in message
    assert "(0.0, 0.05]" in message


def test_unknown_map_id_fails_creation_and_lists_the_two_legal_values():
    with pytest.raises(ScenarioValidationError) as excinfo:
        Simulation.create(_scenario(map_id="warehouse-3"))
    message = str(excinfo.value)
    assert "map_id='warehouse-3'" in message
    assert "'demo'" in message and "'minimal'" in message


def test_turn_tolerance_above_the_angular_limit_fails_creation_with_both_values():
    chassis = ChassisConfig(turn_align_tolerance_rad=0.05)
    spec = make_spec(robot_id="R7", path=PATH, chassis=chassis)
    with pytest.raises(ScenarioValidationError) as excinfo:
        Simulation.create(_scenario(dt_s=0.02, robots=(spec,)))
    message = str(excinfo.value)
    assert "R7" in message
    assert "turn_align_tolerance_rad=0.05" in message
    assert "omega_max_radps=1.2" in message
    assert "0.02" in message


def test_creation_lists_every_violation_instead_of_only_the_first():
    with pytest.raises(ScenarioValidationError) as excinfo:
        Simulation.create(
            _scenario(
                dt_s=0.5,
                robots=(
                    make_spec(robot_id="R1", path=("N01",)),
                    make_spec(robot_id="R1", start_node_id="GHOST", path=("GHOST", "N02"), vehicle_class="TITAN"),
                ),
                obstacles=(Obstacle("O1", 1.0, 1.0, 0.0),),
            )
        )
    violations = excinfo.value.violations
    assert len(violations) >= 6
    assert any("dt_s" in item for item in violations)
    assert any("duplicate robot id R1" in item for item in violations)
    assert any("start_node_id=GHOST" in item for item in violations)
    assert any("TITAN" in item for item in violations)
    assert any("O1" in item for item in violations)
    assert any("fewer than two nodes" in item for item in violations)


def test_creation_builds_the_whole_robot_set_before_the_first_step():
    sim = Simulation.create(
        _scenario(
            robots=(
                make_spec(robot_id="R1", path=PATH),
                make_spec(
                    robot_id="R2",
                    path=("N02", "N03"),
                    start_node_id="N02",
                    start_theta_rad=math.pi / 2.0,
                ),
            )
        )
    )
    snapshot = sim.step()
    assert [item.robot_id for item in snapshot.robots] == ["R1", "R2"]
    assert all(item.status is RobotStatus.MOVING for item in snapshot.robots)
    assert snapshot.robots[0].v_mps == snapshot.robots[1].v_mps > 0.0


def test_default_cruise_speed_reaches_the_configured_limit_in_the_kernel():
    sim = Simulation.create(_scenario())
    peak = 0.0
    for _ in range(400):
        snapshot = sim.step()
        peak = max(peak, snapshot.robots[0].v_mps)
    assert peak == pytest.approx(V_MAX_MPS, abs=ASSERT_TOL)


def test_a_follower_approaching_a_stopped_leader_stops_before_touching():
    sim = Simulation.create(
        Scenario(
            map_id=DEMO_MAP_ID,
            dt_s=DT_S,
            robots=(
                make_spec(robot_id="R1", path=("N01", "N02")),
                make_spec(
                    robot_id="R2",
                    path=("N08", "N01", "N02"),
                    start_node_id="N08",
                    start_theta_rad=-math.pi / 2.0,
                ),
            ),
            obstacles=(obstacle_at(10.0, 0.0),),
        )
    )
    leader = follower = None
    for _ in range(1600):
        snapshot = sim.step()
        leader, follower = snapshot.robots
        if follower.status is RobotStatus.E_STOP and follower.v_mps == 0.0:
            break

    assert leader.status is RobotStatus.E_STOP, "the leader is held by the static obstacle"
    assert follower.status is RobotStatus.E_STOP
    assert follower.estop_reason is EStopReason.SAFETY_DISTANCE
    gap = math.hypot(leader.x_m - follower.x_m, leader.y_m - follower.y_m)
    assert gap >= 2.0 * 0.35, "the two body circles must not intersect"


def _demo_ring_scenario(robot_order=("R1", "R2")) -> Scenario:
    """Two robots whose ring paths force Z01 to change hands; both finish."""
    specs = {
        "R1": make_spec(robot_id="R1", path=("N01", "N02", "N03")),
        "R2": make_spec(
            robot_id="R2",
            path=("N03", "N01", "N02"),
            start_node_id="N03",
            start_theta_rad=math.atan2(-15.0, -10.0),
        ),
    }
    return Scenario(map_id=DEMO_MAP_ID, dt_s=DT_S, robots=tuple(specs[robot_id] for robot_id in robot_order))


def test_a_robot_starting_inside_another_robot_stops_with_overlap():
    sim = Simulation.create(
        _scenario(
            robots=(
                make_spec(robot_id="R1", path=("N01", "N02")),
                make_spec(robot_id="R2", path=("N01", "N02"), start_tick=10_000),
            )
        )
    )
    snapshot = sim.step()
    assert [(item.status, item.estop_reason) for item in snapshot.robots] == [
        (RobotStatus.E_STOP, EStopReason.OVERLAP),
        (RobotStatus.IDLE, EStopReason.NONE),
    ]


def test_swapping_robot_order_leaves_the_snapshot_sequence_unchanged():
    forward = _run(Simulation.create_scheduled(_demo_ring_scenario()), 2500)
    reversed_order = _run(Simulation.create_scheduled(_demo_ring_scenario(("R2", "R1"))), 2500)
    assert forward == reversed_order
    assert all(item.status is RobotStatus.ARRIVED for item in forward[-1].robots)


def test_the_default_entry_never_produces_zone_states_and_finishes_the_ring():
    sim = Simulation.create(_demo_ring_scenario())
    observed = set()
    snapshot = None
    for _ in range(2500):
        snapshot = sim.step()
        assert snapshot.zones == ()
        observed |= {item.status for item in snapshot.robots}
        if all(item.status is RobotStatus.ARRIVED for item in snapshot.robots):
            break
    assert observed <= {RobotStatus.IDLE, RobotStatus.MOVING, RobotStatus.E_STOP, RobotStatus.ARRIVED}
    assert all(item.status is RobotStatus.ARRIVED for item in snapshot.robots)


def test_create_scheduled_publishes_zone_state_and_finishes_the_ring():
    sim = Simulation.create_scheduled(_demo_ring_scenario())
    first = sim.step()
    assert [zone.zone_id for zone in first.zones] == ["Z01", "Z02", "Z03", "Z04", "Z05"]
    assert {item.robot_id: item.status for item in first.robots} == {
        "R1": RobotStatus.WAITING_RIGHT,
        "R2": RobotStatus.WAITING_RIGHT,
    }
    by_id = {zone.zone_id: zone for zone in first.zones}
    assert by_id["Z01"].waiting_robot_ids == ("R1",)
    assert by_id["Z03"].waiting_robot_ids == ("R2",)

    last = first
    for _ in range(2500):
        last = sim.step()
        if all(item.status is RobotStatus.ARRIVED for item in last.robots):
            break
    assert all(item.status is RobotStatus.ARRIVED for item in last.robots)
    assert all(zone.holder_robot_ids == () and zone.waiting_robot_ids == () for zone in last.zones)


class _DelegatingDispatcher:
    """A separate scheduler class that forwards the three contracts to the built-in one."""

    def __init__(self, specs, topology_map):
        self._inner = FcfsDispatcher(specs, topology_map)
        self.requests = 0

    def dispatch(self, tick_index, robots) -> None:
        self._inner.dispatch(tick_index, robots)

    def request_right(self, robot_id, segment_index, zone_ids, tick_index):
        self.requests += 1
        return self._inner.request_right(robot_id, segment_index, zone_ids, tick_index)

    def release_right(self, robot_id, zone_ids) -> None:
        self._inner.release_right(robot_id, zone_ids)

    def read_zone_state(self):
        return self._inner.read_zone_state()


def test_an_injected_dispatcher_produces_the_same_snapshot_sequence():
    scenario = _demo_ring_scenario()
    builtin = _run(Simulation.create_scheduled(scenario), 1500)
    replacement = _DelegatingDispatcher(scenario.robots, load_map(DEMO_MAP_ID))
    injected = _run(Simulation.create_scheduled(scenario, dispatcher=replacement), 1500)
    assert builtin == injected
    assert replacement.requests > 0
