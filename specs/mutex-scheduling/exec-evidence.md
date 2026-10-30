# Execution Evidence

- **Execution baseline**: `HEAD 56646f8 (main)`; target scope is the implementation of
  `specs/mutex-scheduling/tasks.md`. Pre-existing user changes kept intact and not part of this
  work: modified `AGENTS.md` (rights/dispatcher structure and dependency rules) and
  `projects/virtual-robot/backlog.md`; untracked `docs/`, `specs/mutex-scheduling/design.md`,
  `specs/mutex-scheduling/tasks.md`, `specs/mutex-scheduling/review.md`.
- **Input revisions**:
  - `specs/mutex-scheduling/design.md`: `sha256:c19876a6469ffa9345a3b2468c80dcfd9bfa5e71fecd6cffabb585eb63d1a6f9`
  - `AGENTS.md`: `sha256:3d7f3e9b019782def7b8eec730e0e84d39ca016c77072761531d72feedb7c97e`
  - `pyproject.toml`: `sha256:4f683192e811115584101da882ce7d3b84efadac4c014e39e1aa754d8054483b`
- **Validation environment**: repo root `D:\Workspace\python\VirtualRobot`, Windows 10
  (10.0.19041), Python 3.13.9 in `.venv`, pytest 9.2.0, no runtime third-party dependencies
  (test extras: colorama, iniconfig, packaging, pluggy, Pygments).
- **Manifest command**: `node "C:/Users/wenlong.chen/.claude/skills/code-review/scripts/review-manifest.mjs" --exclude specs/mutex-scheduling/code-review.md --exclude specs/mutex-scheduling/exec-evidence.md`
- **Diff fingerprint**: `sha256:6de480062eee374cc164e0364915b8c58e0414686490d678ac216b4cb7586807`
- **Validation**:
  - `.venv/Scripts/python.exe -m pytest tests -q`: passed — 166 passed in 0.87s
  - `.venv/Scripts/python.exe -m pytest tests/test_benchmark.py -q`: passed —
    `bench: robots=10 steps=1000 dt=0.02s average=0.0624ms p95=0.1013ms average_below_dt=True`
    (observation only; not a gate)
  - `.venv/Scripts/python.exe -m compileall -q src tests`: passed
  - `git diff --check`: clean (only CRLF line-ending notices from Git)
  - Dependency-direction review: `rights.py` has no package imports; `robot.py` imports
    `SafetyMonitor` only under `TYPE_CHECKING`; `snapshots.py` imports the shared enums from
    `robot.py`; `dispatcher.py` and `simulation.py` sit at the top layer
  - Acceptance-criteria evidence:
    - `AC-rights-single-holder`, `AC-rights-fcfs-same-tick`, `AC-rights-fcfs-arrival`,
      `AC-rights-atomic-multi-zone`, `AC-rights-capacity`, `AC-snapshot-zone-detail`:
      `tests/test_dispatcher.py`, `tests/test_mutex_scheduling.py` (contention, ring handoff,
      multi-zone group, capacity-2 zone state)
    - `AC-rights-release-make-before-break`, `AC-rights-hold-while-waiting`,
      `AC-rights-holding-status`, `AC-rights-waiting-status`: `tests/test_robot.py`,
      `tests/test_mutex_scheduling.py` ring cases
    - `AC-deadlock-ring-forms`, `AC-deadlock-persists`:
      `test_three_robots_form_a_persistent_ring_wait_on_the_demo_triangle`
    - `AC-peers-rear-end`, `AC-peers-auto-resume`, `AC-peers-resume-blocked`,
      `AC-status-estop-over-holding`, `AC-status-holding-after-resume`:
      `tests/test_mutex_scheduling.py` follower and holding-robot cases
    - `AC-peers-tick-start-poses`, `AC-peers-order-independent`,
      `AC-peers-initial-overlap`: `tests/test_safety.py`, `tests/test_simulation.py`,
      `tests/test_mutex_scheduling.py` head-on/initial-overlap cases
    - `AC-compat-default-create`, `AC-compat-scheduled-create`, `AC-contract-arbiter-swap`,
      `AC-snapshot-zones-default`: `tests/test_simulation.py`
    - `AC-scale-ten-robots-scheduled`, `AC-scale-ten-robots-default`,
      `AC-scale-no-initial-overlap`: `tests/test_mutex_scheduling.py` scale cases,
      `tests/test_map_model.py` spacing case
  - Note: `Robot._turn_step` was fixed during execution so a deadbeat turn step that lands
    exactly on the segment heading starts the linear phase in the same tick; the regression is
    covered by
    `tests/test_robot.py::test_a_turn_that_lands_exactly_on_the_heading_keeps_the_next_segment_length`.
