"""Unit tests for the built-in dispatcher: queue order, grants, release and zone state."""

from __future__ import annotations

from conftest import make_obstacle_field, make_robot, make_spec, obstacle_at

from vrobot_sim.dispatcher import FcfsDispatcher, ScheduledDispatcher, ZoneStateProvider
from vrobot_sim.map_model import (
    EdgeDirection,
    MapCriticalZone,
    MapEdge,
    MapNode,
    build_topology_map,
)
from vrobot_sim.maps import load_map
from vrobot_sim.maps.demo import DEMO_MAP_ID
from vrobot_sim.maps.minimal import MINIMAL_MAP_ID
from vrobot_sim.rights import GrantOutcome, RightOfWayArbiter
from vrobot_sim.robot import CommandSource, EStopReason, RobotStatus
from vrobot_sim.snapshots import ZoneSnapshot

WIDE_CORRIDOR_MAP = build_topology_map(
    "wide_corridor",
    (MapNode("N01", 0.0, 0.0), MapNode("N02", 20.0, 0.0)),
    (MapEdge("E01", "N01", "N02", EdgeDirection.BOTH),),
    (MapCriticalZone("Z01", "wide corridor", ("E01",), capacity=2),),
)


def _dispatcher(map_id: str = DEMO_MAP_ID) -> FcfsDispatcher:
    return FcfsDispatcher((), load_map(map_id))


def _zone(dispatcher: FcfsDispatcher, zone_id: str) -> ZoneSnapshot:
    return next(item for item in dispatcher.read_zone_state() if item.zone_id == zone_id)


def test_the_dispatcher_fills_all_three_scheduled_roles():
    dispatcher = _dispatcher()
    assert isinstance(dispatcher, CommandSource)
    assert isinstance(dispatcher, RightOfWayArbiter)
    assert isinstance(dispatcher, ZoneStateProvider)
    assert isinstance(dispatcher, ScheduledDispatcher)


def test_a_request_is_queued_until_the_next_dispatch_grants_it():
    dispatcher = _dispatcher()
    dispatcher.dispatch(0, ())
    assert dispatcher.request_right("R1", 0, ("Z01",), 0) is GrantOutcome.QUEUED
    assert _zone(dispatcher, "Z01").holder_robot_ids == ()

    dispatcher.dispatch(1, ())
    assert dispatcher.request_right("R1", 0, ("Z01",), 1) is GrantOutcome.GRANTED
    assert _zone(dispatcher, "Z01").holder_robot_ids == ("R1",)
    assert _zone(dispatcher, "Z01").waiting_robot_ids == ()


def test_same_tick_requests_grant_the_lexicographically_first_robot():
    dispatcher = _dispatcher()
    dispatcher.dispatch(40, ())
    assert dispatcher.request_right("R2", 0, ("Z01",), 40) is GrantOutcome.QUEUED
    assert dispatcher.request_right("R10", 0, ("Z01",), 40) is GrantOutcome.QUEUED
    dispatcher.dispatch(41, ())

    assert dispatcher.request_right("R10", 0, ("Z01",), 41) is GrantOutcome.GRANTED
    assert dispatcher.request_right("R2", 0, ("Z01",), 41) is GrantOutcome.QUEUED
    zone = _zone(dispatcher, "Z01")
    assert zone.holder_robot_ids == ("R10",)
    assert zone.waiting_robot_ids == ("R2",)


def test_an_earlier_application_wins_over_a_smaller_robot_id():
    dispatcher = _dispatcher()
    assert dispatcher.request_right("R9", 0, ("Z01",), 100) is GrantOutcome.QUEUED
    assert dispatcher.request_right("R1", 0, ("Z01",), 101) is GrantOutcome.QUEUED
    dispatcher.dispatch(102, ())

    zone = _zone(dispatcher, "Z01")
    assert zone.holder_robot_ids == ("R9",)
    assert zone.waiting_robot_ids == ("R1",)


def test_waiters_are_ordered_by_arrival_tick_before_robot_id():
    dispatcher = _dispatcher()
    assert dispatcher.request_right("R2", 0, ("Z01",), 5) is GrantOutcome.QUEUED
    assert dispatcher.request_right("R10", 0, ("Z01",), 9) is GrantOutcome.QUEUED

    assert _zone(dispatcher, "Z01").waiting_robot_ids == ("R2", "R10")

    dispatcher.dispatch(10, ())
    zone = _zone(dispatcher, "Z01")
    assert zone.holder_robot_ids == ("R2",)
    assert zone.waiting_robot_ids == ("R10",)


def test_a_multi_zone_request_is_granted_atomically_or_not_at_all():
    dispatcher = _dispatcher()
    assert dispatcher.request_right("R5", 0, ("Z05",), 0) is GrantOutcome.QUEUED
    dispatcher.dispatch(1, ())
    assert _zone(dispatcher, "Z05").holder_robot_ids == ("R5",)

    assert dispatcher.request_right("R1", 0, ("Z04", "Z05"), 1) is GrantOutcome.QUEUED
    dispatcher.dispatch(2, ())
    assert _zone(dispatcher, "Z04").holder_robot_ids == ()
    assert _zone(dispatcher, "Z04").waiting_robot_ids == ("R1",)
    assert _zone(dispatcher, "Z05").holder_robot_ids == ("R5",)
    assert _zone(dispatcher, "Z05").waiting_robot_ids == ("R1",)

    dispatcher.release_right("R5", ("Z05",))
    dispatcher.dispatch(3, ())
    assert _zone(dispatcher, "Z04").holder_robot_ids == ("R1",)
    assert _zone(dispatcher, "Z05").holder_robot_ids == ("R1",)
    assert _zone(dispatcher, "Z05").waiting_robot_ids == ()


def test_capacity_two_admits_two_holders_and_queues_the_third_until_a_release():
    dispatcher = FcfsDispatcher((), WIDE_CORRIDOR_MAP)
    for robot_id in ("R1", "R2", "R3"):
        assert dispatcher.request_right(robot_id, 0, ("Z01",), 0) is GrantOutcome.QUEUED
    dispatcher.dispatch(1, ())

    zone = _zone(dispatcher, "Z01")
    assert zone.capacity == 2
    assert zone.holder_robot_ids == ("R1", "R2")
    assert zone.waiting_robot_ids == ("R3",)

    dispatcher.release_right("R1", ("Z01",))
    dispatcher.dispatch(2, ())
    zone = _zone(dispatcher, "Z01")
    assert zone.holder_robot_ids == ("R2", "R3")
    assert zone.waiting_robot_ids == ()


def test_releasing_an_unheld_zone_is_a_no_op_and_a_new_segment_is_a_new_application():
    dispatcher = _dispatcher()
    dispatcher.release_right("GHOST", ("Z01",))
    assert dispatcher.request_right("R1", 0, ("Z01",), 0) is GrantOutcome.QUEUED
    dispatcher.dispatch(1, ())
    assert _zone(dispatcher, "Z01").holder_robot_ids == ("R1",)

    dispatcher.release_right("R1", ("Z01",))
    dispatcher.release_right("R1", ("Z01",))
    assert _zone(dispatcher, "Z01").holder_robot_ids == ()
    assert dispatcher.request_right("R1", 0, ("Z01",), 5) is GrantOutcome.QUEUED

    assert dispatcher.request_right("R1", 1, ("Z01",), 5) is GrantOutcome.QUEUED
    dispatcher.dispatch(6, ())
    assert _zone(dispatcher, "Z01").holder_robot_ids == ("R1",)


def test_repeating_a_request_keeps_one_entry_and_the_original_arrival_tick():
    dispatcher = _dispatcher()
    dispatcher.request_right("R10", 0, ("Z01",), 5)
    dispatcher.request_right("R2", 0, ("Z01",), 5)
    dispatcher.request_right("R10", 0, ("Z01",), 9)
    dispatcher.request_right("R2", 0, ("Z01",), 5)

    zone = _zone(dispatcher, "Z01")
    assert zone.waiting_robot_ids == ("R10", "R2")
    assert zone.holder_robot_ids == ()


def test_zone_state_covers_every_zone_in_identifier_order():
    dispatcher = _dispatcher()
    state = dispatcher.read_zone_state()
    assert [item.zone_id for item in state] == ["Z01", "Z02", "Z03", "Z04", "Z05"]
    assert all(item.capacity == 1 for item in state)
    assert all(item.holder_robot_ids == () and item.waiting_robot_ids == () for item in state)

    assert _dispatcher(MINIMAL_MAP_ID).read_zone_state() == ()


def test_dispatch_assigns_paths_at_start_tick_and_resumes_e_stopped_robots():
    spec = make_spec(path=("N01", "N02", "N03"))
    obstacles = make_obstacle_field([obstacle_at(5.0, 0.0)])
    robot = make_robot(load_map(MINIMAL_MAP_ID), spec=spec, obstacles=obstacles)
    dispatcher = FcfsDispatcher((spec,), load_map(MINIMAL_MAP_ID))

    dispatcher.dispatch(0, (robot,))
    assert robot.status is RobotStatus.MOVING

    for _ in range(900):
        robot.tick()
    assert robot.status is RobotStatus.E_STOP
    assert robot.estop_reason is EStopReason.SAFETY_DISTANCE
    blocked_pose = (robot.pose.x, robot.pose.y)

    dispatcher.dispatch(1, (robot,))
    assert robot.status is RobotStatus.E_STOP, "a resume into a blocked path is refused"
    assert (robot.pose.x, robot.pose.y) == blocked_pose

    assert obstacles.deregister("OBS").accepted
    dispatcher.dispatch(2, (robot,))
    assert robot.status is RobotStatus.MOVING
    assert robot.estop_reason is EStopReason.NONE
