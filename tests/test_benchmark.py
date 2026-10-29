"""Optional benchmark: single-step cost of the demo scenario at ten robots.

Every robot starts on its own node, so each step runs the full peer judging path. The
assertions here only prove the measurement exists; speed numbers never gate a build, because
host load makes a threshold assertion flaky. Current numbers are recorded in
specs/mutex-scheduling/exec-evidence.md; specs/sim-kinematics/benchmark-notes.md holds the
earlier run of this measurement before peer judging was enabled.
"""

from __future__ import annotations

import time

from conftest import DT_S, make_spec, obstacle_at

from vrobot_sim.maps.demo import DEMO_MAP_ID
from vrobot_sim.scenario import Scenario
from vrobot_sim.simulation import Simulation

STEP_COUNT = 1000
# Ten distinct start nodes, pairwise more than 0.70 m apart, so every step judges peers
# without an initial overlap e-stop.
ROBOT_PATHS = (
    ("N01", "N08"),
    ("N02", "N03"),
    ("N03", "N01"),
    ("N04", "N02"),
    ("N05", "N04"),
    ("N06", "N05"),
    ("N07", "N06"),
    ("N08", "N10"),
    ("N09", "N07"),
    ("N10", "N09"),
)
FIXED_OBSTACLES = (obstacle_at(10.0, 8.0, 0.3, "B1"), obstacle_at(18.0, 6.0, 0.25, "B2"), obstacle_at(5.0, 3.0, 0.2, "B3"))


def _scenario() -> Scenario:
    specs = tuple(
        make_spec(robot_id=f"B{index:02d}", path=path, start_node_id=path[0], start_theta_rad=0.0)
        for index, path in enumerate(ROBOT_PATHS, start=1)
    )
    return Scenario(map_id=DEMO_MAP_ID, dt_s=DT_S, robots=specs, obstacles=FIXED_OBSTACLES)


def test_ten_robot_demo_bench_reports_average_and_p95_step_cost():
    sim = Simulation.create(_scenario())
    for _ in range(50):
        sim.step()

    step_costs_ns = []
    for _ in range(STEP_COUNT):
        started = time.perf_counter_ns()
        snapshot = sim.step()
        step_costs_ns.append(time.perf_counter_ns() - started)
        assert len(snapshot.robots) == len(ROBOT_PATHS)

    ordered = sorted(step_costs_ns)
    average_ms = sum(step_costs_ns) / len(step_costs_ns) / 1e6
    p95_ms = ordered[int(0.95 * len(ordered))] / 1e6
    average_below_dt = average_ms < DT_S * 1000.0

    assert len(step_costs_ns) == STEP_COUNT
    assert average_ms > 0.0 and p95_ms > 0.0
    assert p95_ms >= average_ms
    print(
        f"bench: robots={len(ROBOT_PATHS)} steps={STEP_COUNT} dt={DT_S}s "
        f"average={average_ms:.4f}ms p95={p95_ms:.4f}ms average_below_dt={average_below_dt}"
    )
