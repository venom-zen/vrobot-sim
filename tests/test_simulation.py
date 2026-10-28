"""Kernel, snapshot and creation-time configuration validation tests."""

from __future__ import annotations

import dataclasses

import pytest
from conftest import ASSERT_TOL, DT_S, V_MAX_MPS, make_spec, obstacle_at
from vrobot_sim.maps.minimal import MINIMAL_MAP_ID
from vrobot_sim.obstacle_field import Obstacle
from vrobot_sim.robot import ChassisConfig, RobotStatus
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
                make_spec(robot_id="R10", path=PATH, start_node_id="N01"),
            )
        )
    )
    snapshot = sim.step()
    assert [item.robot_id for item in snapshot.robots] == ["R10", "R2"]
    assert [field.name for field in dataclasses.fields(TickSnapshot)] == ["tick_index", "sim_time_s", "robots"]
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
        robots=(make_spec(robot_id="R1", path=PATH), make_spec(robot_id="R2", path=("N01", "N02"), start_tick=1)),
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
                make_spec(robot_id="R2", path=("N01", "N02"), start_tick=1),
            )
        )
    )
    _run(sim, 60)
    assert sim.obstacles.register(obstacle_at(4.0, 0.0)).accepted

    stopped = []
    for _ in range(400):
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
        _scenario(robots=(make_spec(robot_id="R1", path=PATH), make_spec(robot_id="R2", path=("N01", "N02"))))
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
