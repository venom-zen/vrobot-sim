"""Integration tests for right-of-way mutex, deadlock exposure and peer avoidance."""

from __future__ import annotations

import math

from conftest import DT_S, make_spec, obstacle_at

from vrobot_sim.dispatcher import FcfsDispatcher
from vrobot_sim.map_model import (
    EdgeDirection,
    MapCriticalZone,
    MapEdge,
    MapNode,
    build_topology_map,
)
from vrobot_sim.maps.demo import DEMO_MAP_ID
from vrobot_sim.robot import EStopReason, RobotStatus
from vrobot_sim.scenario import Scenario
from vrobot_sim.simulation import Simulation
from vrobot_sim.snapshots import TickSnapshot


def _spec(robot_id: str, path: tuple[str, ...], theta: float = 0.0, start_tick: int = 0):
    return make_spec(
        robot_id=robot_id,
        path=path,
        start_node_id=path[0],
        start_theta_rad=theta,
        start_tick=start_tick,
    )


def _scenario(specs, obstacles=()) -> Scenario:
    return Scenario(map_id=DEMO_MAP_ID, dt_s=DT_S, robots=tuple(specs), obstacles=tuple(obstacles))


def _zone(snapshot: TickSnapshot, zone_id: str):
    return next(zone for zone in snapshot.zones if zone.zone_id == zone_id)


def _run_until(sim: Simulation, predicate, max_ticks: int, message: str) -> TickSnapshot:
    for _ in range(max_ticks):
        snapshot = sim.step()
        if predicate(snapshot):
            return snapshot
    raise AssertionError(message)


def _all_arrived(snapshot: TickSnapshot) -> bool:
    return all(item.status is RobotStatus.ARRIVED for item in snapshot.robots)


def _statuses(snapshot: TickSnapshot) -> dict[str, RobotStatus]:
    return {item.robot_id: item.status for item in snapshot.robots}


def _assert_capacity_respected(snapshot: TickSnapshot) -> None:
    for zone in snapshot.zones:
        assert len(zone.holder_robot_ids) <= zone.capacity


# --- 5.1 Right-of-way mutex -------------------------------------------------


def test_two_robots_contending_for_one_zone_leave_one_waiting_then_both_arrive():
    sim = Simulation.create_scheduled(
        _scenario(
            (
                _spec("R1", ("N06", "N07"), theta=math.pi / 2.0),
                _spec("R9", ("N05", "N06"), theta=math.pi),
            )
        )
    )
    first = sim.step()
    assert _statuses(first) == {"R1": RobotStatus.WAITING_RIGHT, "R9": RobotStatus.WAITING_RIGHT}

    granted = sim.step()
    _assert_capacity_respected(granted)
    assert _statuses(granted) == {"R1": RobotStatus.HOLDING_ZONE, "R9": RobotStatus.WAITING_RIGHT}
    zone = _zone(granted, "Z05")
    assert zone.holder_robot_ids == ("R1",)
    assert zone.waiting_robot_ids == ("R9",)
    waiting = next(item for item in granted.robots if item.robot_id == "R9")
    assert waiting.v_mps == 0.0
    assert (waiting.x_m, waiting.y_m) == (20.0, 16.0), "the waiter stays at the entrance node"

    last = _run_until(sim, _all_arrived, 2000, "both robots must finish after the zone changes hands")
    assert all(zone.holder_robot_ids == () for zone in last.zones)


def test_the_ring_releases_the_first_zone_only_when_the_second_is_granted():
    sim = Simulation.create_scheduled(
        _scenario(
            (
                _spec("R1", ("N01", "N02", "N03")),
                _spec("R2", ("N03", "N01", "N02"), theta=math.atan2(-15.0, -10.0)),
            )
        )
    )

    held = _run_until(
        sim,
        lambda snapshot: _statuses(snapshot)["R2"] is RobotStatus.WAITING_RIGHT
        and (snapshot.tick_index > 1),
        2000,
        "R2 must wait at N01 for Z01",
    )
    _assert_capacity_respected(held)
    assert _statuses(held)["R2"] is RobotStatus.WAITING_RIGHT
    assert (held.robots[1].x_m, held.robots[1].y_m) == (0.0, 0.0)
    # Make-before-break: the waiter still owns the zone of the segment it left...
    assert _zone(held, "Z03").holder_robot_ids == ("R2",)
    # ...and the holder of the contested zone keeps it until its own switch.
    assert _zone(held, "Z01").holder_robot_ids == ("R1",)
    assert _zone(held, "Z01").waiting_robot_ids == ("R2",)

    last = _run_until(sim, _all_arrived, 2500, "the ring scenario must finish under the dispatcher")
    assert all(zone.holder_robot_ids == () and zone.waiting_robot_ids == () for zone in last.zones)


def test_a_multi_zone_edge_is_granted_as_one_group():
    sim = Simulation.create_scheduled(
        _scenario(
            (
                _spec("R05", ("N06", "N07"), theta=math.pi / 2.0),
                _spec("R1", ("N04", "N05"), theta=-math.pi / 2.0),
            )
        )
    )
    first = sim.step()
    granted = sim.step()

    assert _statuses(first) == {"R05": RobotStatus.WAITING_RIGHT, "R1": RobotStatus.WAITING_RIGHT}
    assert _statuses(granted)["R05"] is RobotStatus.HOLDING_ZONE
    zone_04 = _zone(granted, "Z04")
    zone_05 = _zone(granted, "Z05")
    assert zone_05.holder_robot_ids == ("R05",)
    assert zone_04.holder_robot_ids == ()
    assert zone_04.waiting_robot_ids == ("R1",), "a multi-zone application appears in every queue"
    assert zone_05.waiting_robot_ids == ("R1",)
    assert _statuses(granted)["R1"] is RobotStatus.WAITING_RIGHT
    assert (granted.robots[1].x_m, granted.robots[1].y_m) == (20.0, 12.0)

    last = _run_until(sim, _all_arrived, 2500, "R1 must get both zones once R05 finishes")
    assert all(zone.holder_robot_ids == () for zone in last.zones)


def test_a_capacity_two_zone_admits_two_holders_and_queues_the_third():
    wide_map = build_topology_map(
        "wide_corridor",
        (MapNode("N01", 0.0, 0.0), MapNode("N02", 20.0, 0.0)),
        (MapEdge("E01", "N01", "N02", EdgeDirection.BOTH),),
        (MapCriticalZone("Z01", "wide corridor", ("E01",), capacity=2),),
    )
    dispatcher = FcfsDispatcher((), wide_map)
    for robot_id in ("R1", "R2", "R3"):
        dispatcher.request_right(robot_id, 0, ("Z01",), 0)
    dispatcher.dispatch(1, ())

    zone = dispatcher.read_zone_state()[0]
    assert zone.capacity == 2
    assert zone.holder_robot_ids == ("R1", "R2")
    assert zone.waiting_robot_ids == ("R3",)

    dispatcher.release_right("R1", ("Z01",))
    dispatcher.dispatch(2, ())
    zone = dispatcher.read_zone_state()[0]
    assert zone.holder_robot_ids == ("R2", "R3")
    assert zone.waiting_robot_ids == ()


# --- 5.2 Deadlock exposure --------------------------------------------------


def _ring_specs():
    return (
        _spec("R1", ("N01", "N02", "N03")),
        _spec("R2", ("N02", "N03", "N01"), theta=math.atan2(15.0, -10.0)),
        _spec("R3", ("N03", "N01", "N02"), theta=math.atan2(-15.0, -10.0)),
    )


def _ring_formed(snapshot: TickSnapshot) -> bool:
    if len(snapshot.robots) != 3:
        return False
    positions = {item.robot_id: (item.x_m, item.y_m) for item in snapshot.robots}
    return (
        all(item.status is RobotStatus.WAITING_RIGHT for item in snapshot.robots)
        and positions["R1"] == (20.0, 0.0)
        and positions["R2"] == (10.0, 15.0)
        and positions["R3"] == (0.0, 0.0)
    )


def test_three_robots_form_a_persistent_ring_wait_on_the_demo_triangle():
    sim = Simulation.create_scheduled(_scenario(_ring_specs()))
    formed = _run_until(sim, _ring_formed, 2000, "the three robots must form the ring wait")

    assert _zone(formed, "Z01").holder_robot_ids == ("R1",)
    assert _zone(formed, "Z01").waiting_robot_ids == ("R3",)
    assert _zone(formed, "Z02").holder_robot_ids == ("R2",)
    assert _zone(formed, "Z02").waiting_robot_ids == ("R1",)
    assert _zone(formed, "Z03").holder_robot_ids == ("R3",)
    assert _zone(formed, "Z03").waiting_robot_ids == ("R2",)

    for _ in range(300):
        snapshot = sim.step()
        assert snapshot.robots == formed.robots, "poses and statuses stay frozen"
        assert snapshot.zones == formed.zones, "the ring is not broken automatically"
    assert snapshot.tick_index == formed.tick_index + 300, "the simulation keeps advancing"


# --- 5.3 Peer avoidance -----------------------------------------------------


def test_a_follower_stops_behind_a_blocked_leader_and_both_resume():
    sim = Simulation.create_scheduled(
        _scenario(
            (
                _spec("R1", ("N01", "N08"), theta=math.pi / 2.0),
                _spec("R2", ("N02", "N01", "N08"), theta=math.pi),
            ),
            obstacles=(obstacle_at(0.0, 10.0),),
        )
    )
    stopped = _run_until(
        sim,
        lambda snapshot: all(item.status is RobotStatus.E_STOP for item in snapshot.robots)
        and snapshot.robots[1].v_mps == 0.0,
        2500,
        "the follower must stop behind the blocked leader",
    )
    leader, follower = stopped.robots
    assert follower.estop_reason is EStopReason.SAFETY_DISTANCE
    gap = math.hypot(leader.x_m - follower.x_m, leader.y_m - follower.y_m)
    assert gap >= 2.0 * 0.35, "the body circles must not intersect"

    # Blocked resume: the dispatcher keeps sending RESUME, nothing moves.
    for _ in range(100):
        snapshot = sim.step()
        assert snapshot.robots == stopped.robots

    assert sim.obstacles.deregister("OBS").accepted
    leader_arrived = _run_until(
        sim,
        lambda snapshot: _statuses(snapshot)["R1"] is RobotStatus.ARRIVED,
        1500,
        "the leader must resume and finish once the obstacle is gone",
    )
    assert leader_arrived.robots[1].y_m > follower.y_m + 1.0, "the follower restarts without a command"
    assert leader_arrived.robots[1].v_mps > 0.0


def test_an_arrived_robot_still_blocks_the_follower_behind_it():
    sim = Simulation.create_scheduled(
        _scenario(
            (
                _spec("R1", ("N01", "N08"), theta=math.pi / 2.0),
                _spec("R2", ("N02", "N01", "N08"), theta=math.pi),
            )
        )
    )
    _run_until(
        sim,
        lambda snapshot: _statuses(snapshot)["R1"] is RobotStatus.ARRIVED,
        2500,
        "the leader must park at N08",
    )
    stopped = _run_until(
        sim,
        lambda snapshot: _statuses(snapshot)["R2"] is RobotStatus.E_STOP
        and snapshot.robots[1].v_mps == 0.0,
        2500,
        "the follower must stop behind the parked leader",
    )
    leader, follower = stopped.robots
    assert leader.status is RobotStatus.ARRIVED
    assert (leader.x_m, leader.y_m) == (0.0, 15.0), "the leader keeps its goal pose"
    assert follower.estop_reason is EStopReason.SAFETY_DISTANCE
    gap = math.hypot(leader.x_m - follower.x_m, leader.y_m - follower.y_m)
    assert gap >= 2.0 * 0.35, "the body circles must not intersect"

    for _ in range(50):
        snapshot = sim.step()
        assert snapshot.robots == stopped.robots, "the parked leader keeps blocking the follower"


def test_initial_overlap_keeps_the_starting_robot_in_e_stop():
    sim = Simulation.create_scheduled(
        _scenario(
            (
                _spec("R1", ("N08", "N10"), theta=math.pi / 2.0),
                _spec("R2", ("N08", "N10"), theta=math.pi / 2.0),
            )
        )
    )
    first = sim.step()
    assert {item.robot_id: (item.status, item.estop_reason) for item in first.robots} == {
        "R1": (RobotStatus.E_STOP, EStopReason.OVERLAP),
        "R2": (RobotStatus.E_STOP, EStopReason.OVERLAP),
    }
    for _ in range(100):
        snapshot = sim.step()
        assert all(item.status is RobotStatus.E_STOP for item in snapshot.robots)


def test_a_holding_robot_shows_e_stop_and_returns_to_holding_zone():
    sim = Simulation.create_scheduled(
        _scenario((_spec("R1", ("N01", "N02")),), obstacles=(obstacle_at(10.0, 0.0),))
    )
    holding = _run_until(
        sim,
        lambda snapshot: snapshot.robots[0].status is RobotStatus.HOLDING_ZONE,
        10,
        "the first application must be granted",
    )
    assert _zone(holding, "Z01").holder_robot_ids == ("R1",)

    stopped = _run_until(
        sim,
        lambda snapshot: snapshot.robots[0].status is RobotStatus.E_STOP,
        2000,
        "the obstacle must stop the robot",
    )
    assert stopped.robots[0].estop_reason is EStopReason.SAFETY_DISTANCE
    assert _zone(stopped, "Z01").holder_robot_ids == ("R1",), "e-stop does not release the zone"

    assert sim.obstacles.deregister("OBS").accepted
    resumed = _run_until(
        sim,
        lambda snapshot: snapshot.robots[0].status is RobotStatus.HOLDING_ZONE,
        10,
        "the dispatcher must resume the robot on the next dispatch",
    )
    assert _zone(resumed, "Z01").holder_robot_ids == ("R1",)

    last = _run_until(
        sim,
        lambda snapshot: snapshot.robots[0].status is RobotStatus.ARRIVED,
        1500,
        "the robot must finish the remaining path",
    )
    assert _zone(last, "Z01").holder_robot_ids == ()


def test_swapping_robot_order_keeps_the_head_on_sequence_identical():
    robots = (
        _spec("R1", ("N01", "N02")),
        _spec("R2", ("N02", "N01"), theta=math.pi),
    )
    forward = Simulation.create(_scenario(robots))
    reversed_order = Simulation.create(_scenario(tuple(reversed(robots))))
    forward_run = [forward.step() for _ in range(400)]
    reversed_run = [reversed_order.step() for _ in range(400)]
    assert forward_run == reversed_run
    assert any(item.status is RobotStatus.E_STOP for item in forward_run[-1].robots)


# --- 5.4 Ten-robot scale ----------------------------------------------------

TEN_ROBOT_PATHS = (
    ("R01", ("N01", "N08"), math.pi / 2.0),
    ("R02", ("N02", "N03"), math.atan2(15.0, -10.0)),
    ("R03", ("N03", "N01"), math.atan2(-15.0, -10.0)),
    ("R04", ("N04", "N02"), -math.pi / 2.0),
    ("R05", ("N05", "N04"), -math.pi / 2.0),
    ("R06", ("N06", "N05"), 0.0),
    ("R07", ("N07", "N06"), -math.pi / 2.0),
    ("R08", ("N08", "N10"), math.pi / 2.0),
    ("R09", ("N09", "N07"), math.atan2(-5.0, 6.0)),
    ("R10", ("N10", "N09"), 0.0),
)


def _ten_robot_scenario() -> Scenario:
    return _scenario(tuple(_spec(robot_id, path, theta) for robot_id, path, theta in TEN_ROBOT_PATHS))


def test_ten_robots_start_without_any_overlap_e_stop():
    assert len({path[0] for _, path, _ in TEN_ROBOT_PATHS}) == 10
    for simulation in (Simulation.create(_ten_robot_scenario()), Simulation.create_scheduled(_ten_robot_scenario())):
        snapshot = simulation.step()
        assert len(snapshot.robots) == 10
        assert all(item.estop_reason is not EStopReason.OVERLAP for item in snapshot.robots)


def test_ten_robots_arrive_under_create_scheduled():
    sim = Simulation.create_scheduled(_ten_robot_scenario())
    last = _run_until(sim, _all_arrived, 4000, "all ten robots must arrive under the dispatcher")
    assert len(last.robots) == 10
    assert all(zone.holder_robot_ids == () and zone.waiting_robot_ids == () for zone in last.zones)


def test_ten_robots_arrive_under_the_default_entry():
    sim = Simulation.create(_ten_robot_scenario())
    last = _run_until(sim, _all_arrived, 4000, "all ten robots must arrive under the default entry")
    assert last.zones == ()
    assert all(item.estop_reason is EStopReason.NONE for item in last.robots)
