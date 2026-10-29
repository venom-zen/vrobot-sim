# Implementation Plan: Mutex Scheduling

## Overview

本计划把 `design.md` 的路权互斥、车车避让、快照区状态和 demo 扩展拆成 5 个功能阶段，并在阶段
边界设置 Checkpoint。实现顺序是：先建立地图派生索引与快照字段，再实现路权协议和 FCFS 调度器，
随后接入机器人状态机、车车避让与仿真装配，最后补集成场景、回归与基准。

关键决策：调度器只通过 `rights` 协议和区状态读取契约接入；默认 `Simulation.create` 保持无路权
门禁，`Simulation.create_scheduled` 才启用调度；等待中的机器人保留已持有区，切换段时按
make-before-break 释放；10 车场景使用 demo 的 10 个不同起始节点，任意两个起始节点中心距大于
0.70 m。`design.md` 是行为与 AC 的唯一来源，本计划不新增或改写 AC。

## Tasks

- [✅] 1. Phase 1: 地图与快照基础
  - [✅] 1.1 增加边到区的派生索引
    - Modify `src/vrobot_sim/map_model.py` to add read-only `edge_zones` to `TopologyMap`
    - Derive `edge_zones` from `zones` in `build_topology_map`; keep existing map validation and
      build-error semantics unchanged
    - _Design: Proposed Solution / Data Model_
  - [✅] 1.2 增加 ZoneSnapshot 与 TickSnapshot.zones
    - Modify `src/vrobot_sim/snapshots.py` with a frozen `ZoneSnapshot` carrying `zone_id`,
      `capacity`, `holder_robot_ids` and `waiting_robot_ids`
    - Add `zones: tuple[ZoneSnapshot, ...] = ()` to `TickSnapshot`; keep the existing fields and
      default behavior
    - _Design: Proposed Solution / Data Model_
  - [✅] 1.3 扩展 demo 地图到 10 个可起始节点
    - Modify `src/vrobot_sim/maps/demo.py` to add at least three nodes and connecting edges;
      each new node must be startable
    - Preserve the N01-N03 triangle, Z01-Z05 and map id `demo`; ensure any two of the 10
      startable nodes are more than 0.70 m apart
    - Keep node spacing a demo scenario constraint rather than a global map-build rejection
    - _Acceptance: AC-scale-ten-robots-scheduled, AC-scale-ten-robots-default,
      AC-scale-no-initial-overlap_
    - _Design: Decision Record / DR-scale-demo-map-extension_
  - [✅] 1.4 补地图与快照基础测试
    - Update `tests/test_map_model.py` to assert `edge_zones` matches the zone member lists and
      demo has at least 10 startable nodes with pairwise spacing greater than 0.70 m
    - Update `tests/test_simulation.py` to assert `TickSnapshot.zones` defaults to `()` and the
      declared field list includes `zones`
    - _Acceptance: AC-snapshot-zones-default, AC-scale-no-initial-overlap_
    - _Design: Testing_

- [✅] 2. Phase 2: 路权协议与调度器
  - [✅] 2.1 新增 rights 叶子模块
    - Create `src/vrobot_sim/rights.py` with `GrantOutcome` (`GRANTED`, `QUEUED`) and the
      `RightOfWayArbiter` protocol for request and release calls
    - Keep `rights` free of package imports and preserve the request/release payload semantics
      from the design
    - _Design: Proposed Solution / Architecture, Proposed Solution / Interfaces_
  - [✅] 2.2 实现 FcfsDispatcher 的申请、释放与区状态
    - Create `src/vrobot_sim/dispatcher.py` with `FcfsDispatcher`, taking the scenario robot
      specs and topology map in its constructor and keeping per-zone holder and wait state
    - Process ungranted requests in `(arrival_tick, robot_id)` order; grant a multi-zone request
      only when it is first in every requested queue and every zone has capacity
    - Keep repeated `(robot_id, segment_index)` requests idempotent, preserve the original
      `arrival_tick`, and make release of an unheld zone a no-op
    - Implement `read_zone_state` returning `ZoneSnapshot` values ordered by `zone_id`, holders
      by `robot_id`, and waiters by `(arrival_tick, robot_id)`
    - _Acceptance: AC-rights-single-holder, AC-rights-fcfs-same-tick, AC-rights-fcfs-arrival,
      AC-rights-atomic-multi-zone, AC-rights-capacity, AC-snapshot-zone-detail_
    - _Design: Proposed Solution / Components, Proposed Solution / Data Model_
  - [✅] 2.3 实现调度器指令源与自动恢复
    - Extend `FcfsDispatcher.dispatch` to send `ASSIGN_PATH` at each robot's `start_tick` and
      `RESUME` to every `E_STOP` robot
    - Implement the existing `CommandSource` protocol so the dispatcher can be passed to the
      simulation without changing robot command intake
    - _Acceptance: AC-peers-auto-resume, AC-compat-scheduled-create_
    - _Design: Proposed Solution / Components_
  - [✅] 2.4 补调度器单元测试
    - Add `tests/test_dispatcher.py` covering same-tick and cross-tick FCFS order, atomic
      multi-zone grants, capacity, release, idempotent requests, zone snapshot ordering, and
      automatic `RESUME` dispatch
    - _Acceptance: AC-rights-single-holder, AC-rights-fcfs-same-tick, AC-rights-fcfs-arrival,
      AC-rights-atomic-multi-zone, AC-rights-capacity, AC-snapshot-zone-detail,
      AC-peers-auto-resume_
    - _Design: Testing_

- [✅] 3. Phase 3: 机器人路权生命周期
  - [✅] 3.1 接入机器人路权持有与申请
    - Modify `src/vrobot_sim/robot.py` to accept an optional `RightOfWayArbiter` and track
      `holding_zone_ids` plus one pending request for the current segment
    - On the first segment or a segment switch, request the zones of the segment not already
      held; on grant, release zones not covering the new segment and switch; on `QUEUED`, stop
      at the entrance and keep held zones
    - _Acceptance: AC-rights-release-make-before-break, AC-rights-hold-while-waiting,
      AC-rights-holding-status, AC-rights-waiting-status_
    - _Design: Proposed Solution / State Machines, Proposed Solution / Components_
  - [✅] 3.2 补首段排队与状态优先级
    - Modify `src/vrobot_sim/robot.py` so a first-segment `QUEUED` result enters
      `WAITING_RIGHT`, sets v and omega to zero, and retains the request; repeat the same request
      every tick until granted
    - Apply the status priority `E_STOP` > `WAITING_RIGHT` > `HOLDING_ZONE` > `MOVING` while a
      robot holds zones
    - _Acceptance: AC-rights-waiting-status, AC-status-estop-over-holding,
      AC-status-holding-after-resume_
    - _Design: Proposed Solution / State Machines_
  - [✅] 3.3 补机器人状态机测试
    - Update `tests/test_robot.py` with first-segment queued, hold-while-waiting,
      release-on-switch, E_STOP-while-holding, and resume-to-holding scenarios
    - _Acceptance: AC-rights-release-make-before-break, AC-rights-hold-while-waiting,
      AC-rights-holding-status, AC-rights-waiting-status, AC-status-estop-over-holding,
      AC-status-holding-after-resume_
    - _Design: Testing_

- [✅] 4. Phase 4: 车车避让与仿真装配
  - [✅] 4.1 扩展 safety 接收其他机器人圆
    - Modify `src/vrobot_sim/safety.py` to include peer robot circles in the existing overlap
      fallback, perpendicular skip, and coverage/lookahead checks
    - Keep the caller responsible for excluding the robot itself
    - _Acceptance: AC-peers-rear-end, AC-peers-tick-start-poses, AC-peers-initial-overlap_
    - _Design: Proposed Solution / Components, Proposed Solution / Key Mechanisms_
  - [✅] 4.2 增加 create_scheduled 与 tick 起始位姿采集
    - Modify `src/vrobot_sim/simulation.py` to add `Simulation.create_scheduled` with an optional
      dispatcher, defaulting to `FcfsDispatcher`
    - Inject the same dispatcher into every robot as arbiter and command source, and into the
      simulation as zone-state provider
    - Capture every robot's pose and body radius at tick start; pass the peer circles to every
      robot while excluding self; collect zone state through `IF-PROTO-zone-state-read` after
      robot advance
    - _Acceptance: AC-compat-scheduled-create, AC-contract-arbiter-swap,
      AC-peers-tick-start-poses, AC-snapshot-zone-detail_
    - _Design: Proposed Solution / Data Flow, Proposed Solution / Components_
  - [✅] 4.3 保持默认入口兼容
    - Modify `src/vrobot_sim/simulation.py` so `Simulation.create` keeps
      `PassthroughCommandSource` and no rights gate while peer avoidance remains active
    - Keep `TickSnapshot.zones` empty for the default entry; do not add creation-time rejection
      for overlapping start poses
    - _Acceptance: AC-compat-default-create, AC-snapshot-zones-default_
    - _Design: Proposed Solution / Data Flow, Error Handling_
  - [✅] 4.4 补安全与仿真契约测试
    - Update `tests/test_safety.py` and `tests/test_simulation.py` for peer circles, tick-start
      pose use, order independence, default and scheduled snapshot fields, and injected
      dispatcher consistency
    - Update the existing same-start cases in `tests/test_simulation.py` to distinct starts or
      assert `OVERLAP` E_STOP
    - _Acceptance: AC-peers-rear-end, AC-peers-order-independent, AC-peers-initial-overlap,
      AC-compat-default-create, AC-compat-scheduled-create, AC-snapshot-zone-detail,
      AC-snapshot-zones-default, AC-contract-arbiter-swap_
    - _Design: Testing_

- [✅] 5. Phase 5: 场景、死锁与规模
  - [✅] 5.1 增加路权互斥集成测试
    - Add `tests/test_mutex_scheduling.py` with two-robot contention, same-tick and cross-tick
      FCFS, atomic multi-zone, capacity, release, hold-while-waiting, and status scenarios
    - _Acceptance: AC-rights-single-holder, AC-rights-fcfs-same-tick, AC-rights-fcfs-arrival,
      AC-rights-atomic-multi-zone, AC-rights-capacity, AC-rights-release-make-before-break,
      AC-rights-hold-while-waiting, AC-rights-holding-status, AC-rights-waiting-status_
    - _Design: Testing_
  - [✅] 5.2 增加死锁场景测试
    - Add `tests/test_mutex_scheduling.py` cases for the demo triangle: three robots acquire
      their first ring edges, then wait head-to-tail, and keep poses and states unchanged while
      the simulation continues
    - _Acceptance: AC-deadlock-ring-forms, AC-deadlock-persists_
    - _Design: Testing_
  - [✅] 5.3 增加车车避让集成测试
    - Add `tests/test_mutex_scheduling.py` cases for rear-end stop, automatic resume after the
      leader leaves, blocked resume, initial overlap, tick-start poses, order independence, and
      E_STOP while holding a zone
    - _Acceptance: AC-peers-rear-end, AC-peers-auto-resume, AC-peers-resume-blocked,
      AC-peers-tick-start-poses, AC-peers-order-independent, AC-peers-initial-overlap,
      AC-status-estop-over-holding, AC-status-holding-after-resume_
    - _Design: Testing_
  - [✅] 5.4 增加 10 车规模场景测试
    - Add `tests/test_mutex_scheduling.py` scale cases using demo's 10 distinct start nodes with
      pairwise spacing greater than 0.70 m
    - Verify all 10 arrive under `create_scheduled` and under `Simulation.create`, and that the
      first tick has no `OVERLAP` E_STOP
    - _Acceptance: AC-scale-ten-robots-scheduled, AC-scale-ten-robots-default,
      AC-scale-no-initial-overlap_
    - _Design: Testing_
  - [✅] 5.5 更新既有回归与基准
    - Update `tests/test_integration_demo.py` node/edge counts and make R1/R2 use different
      starts; re-run `tests/test_simulation.py` so its updated same-start assertions stay green
    - Update `tests/test_benchmark.py` to use 10 distinct start nodes with pairwise spacing
      greater than 0.70 m and measure the step containing peer judging
    - _Acceptance: AC-peers-initial-overlap, AC-compat-default-create, AC-snapshot-zones-default_
    - _Design: Testing_

- [✅] 6. Checkpoint - Verify map and snapshot foundations
  - Run `.venv/Scripts/python.exe -m pytest tests/test_map_model.py tests/test_simulation.py -q`
  - Verify `AC-scale-no-initial-overlap` and `AC-snapshot-zones-default`
  - Pass when `edge_zones`, 10-node spacing, and default `zones` assertions pass; stop on failure,
    spec conflict, or missing dependency
  - _Acceptance: AC-scale-no-initial-overlap, AC-snapshot-zones-default_
  - _Design: Testing_

- [✅] 7. Checkpoint - Verify dispatcher core
  - Run `.venv/Scripts/python.exe -m pytest tests/test_dispatcher.py -q`
  - Verify `AC-rights-single-holder`, `AC-rights-fcfs-same-tick`, `AC-rights-fcfs-arrival`,
    `AC-rights-atomic-multi-zone`, `AC-rights-capacity`, and `AC-snapshot-zone-detail`
  - Pass when queue, grant, release, capacity, and zone snapshot ordering assertions pass; stop
    on failure, spec conflict, or missing dependency
  - _Acceptance: AC-rights-single-holder, AC-rights-fcfs-same-tick, AC-rights-fcfs-arrival,
    AC-rights-atomic-multi-zone, AC-rights-capacity, AC-snapshot-zone-detail_
  - _Design: Testing_

- [✅] 8. Checkpoint - Verify robot rights lifecycle
  - Run `.venv/Scripts/python.exe -m pytest tests/test_robot.py -q`
  - Verify hold/release, first-segment waiting, and status priority behavior
  - Pass when the referenced AC assertions pass; stop on failure, spec conflict, or missing
    dependency
  - _Acceptance: AC-rights-release-make-before-break, AC-rights-hold-while-waiting,
    AC-rights-holding-status, AC-rights-waiting-status, AC-status-estop-over-holding,
    AC-status-holding-after-resume_
  - _Design: Testing_

- [✅] 9. Checkpoint - Verify peer avoidance and simulation wiring
  - Run `.venv/Scripts/python.exe -m pytest tests/test_safety.py tests/test_simulation.py -q`
  - Verify peer safety, tick-start poses, order independence, snapshot fields, and default and
    scheduled creation
  - Pass when the referenced AC assertions pass; stop on failure, spec conflict, or missing
    dependency
  - _Acceptance: AC-peers-rear-end, AC-peers-order-independent, AC-compat-default-create,
    AC-compat-scheduled-create, AC-snapshot-zone-detail, AC-snapshot-zones-default,
    AC-contract-arbiter-swap_
  - _Design: Testing_

- [✅] 10. Checkpoint - Verify integration scenarios and full suite
  - Run `.venv/Scripts/python.exe -m pytest tests -q`
  - Run `.venv/Scripts/python.exe -m pytest tests/test_benchmark.py -q`
  - Verify deadlock persistence, 10-car completion under both entries, and no initial `OVERLAP`
    E_STOP
  - Pass when the full suite passes and the benchmark reports its measurement; speed numbers
    remain observation-only and never gate the build
  - _Acceptance: AC-deadlock-ring-forms, AC-deadlock-persists,
    AC-scale-ten-robots-scheduled, AC-scale-ten-robots-default, AC-scale-no-initial-overlap,
    AC-contract-arbiter-swap_
  - _Design: Testing_

## Notes

- Tasks marked with `*` may be skipped in MVP mode; this plan has no optional tasks because each
  phase supports the acceptance surface.
- Keep task numbering stable after execution begins.
- `design.md` is the source of truth; do not copy full AC text into this file or change AC
  behavior during implementation.
