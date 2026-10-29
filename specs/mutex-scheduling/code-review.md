# Code Review

## Review Manifest

- **Review kind**: spec-backed
- **Mode**: Closure Review
- **Mode reason**: 用户选择修复 CR-001–CR-004 后按闭环复核；修复范围仅测试、docstring 与死声明，公共契约、数据模型和架构边界未变；比较上一轮被评审快照 `sha256:6de480…` 与当前快照 `sha256:cbe8c1…`。
- **Closure round**: 1
- **Report language**: 中文（用户请求语言）
- **Target / scope**: `specs/mutex-scheduling` 的完整交付实现，即工作区相对 `HEAD` 的全部改动：15 个已跟踪文件（+578/−70）、新增模块 `dispatcher.py`/`rights.py` 与测试 `test_dispatcher.py`/`test_mutex_scheduling.py`；需求范围以 `design.md` 的全部 AC 与设计契约为准，不由 diff 缩小。
- **Base / comparison**: 基线 `56646f81772812d4d52820799272f70c7d54af84`（`main`，也是 merge-base）；比较端点为当前工作树（staged 为空、unstaged 15 文件、untracked 8 文件）。
- **Spec source**: `specs/mutex-scheduling/design.md`
- **Standards sources**: `AGENTS.md`（根目录唯一项目指导：分层、依赖方向、不可变数据、零运行时依赖）；`pyproject.toml`（`testpaths`、`pythonpath=["src"]`）；仓库无 ruff/mypy/lint 配置。
- **Languages / rules**: Python 3.11+（运行 3.13.9）；加载 `rules/common.md`、`rules/spec.md`、`rules/validation.md`、`rules/findings.md`；仓库无 Python 语言专项规则文件。
- **Input revisions**:
  - `specs/mutex-scheduling/design.md`: `sha256:c19876a6469ffa9345a3b2468c80dcfd9bfa5e71fecd6cffabb585eb63d1a6f9`
  - `specs/mutex-scheduling/tasks.md`: `sha256:5a7c62be4307f42fc51b7e4b8ce02a66e9bb288c3a0253b5e203b42f18325a56`
  - `specs/mutex-scheduling/exec-evidence.md`: `sha256:0d445fd61ebc00801d5e772588054a3cf158d0697b3daa87f05d22e0e4437901`
  - `AGENTS.md`: `sha256:3d7f3e9b019782def7b8eec730e0e84d39ca016c77072761531d72feedb7c97e`
  - `pyproject.toml`: `sha256:4f683192e811115584101da882ce7d3b84efadac4c014e39e1aa754d8054483b`
- **Snapshot evidence**: `review-manifest.mjs` 记录 unstaged diff 15 文件（+578/−70）、staged 与 committed diff 为空、8 个 untracked 文件内容纳入快照。
- **Manifest command / Diff fingerprint**: `node "C:/Users/wenlong.chen/.claude/skills/code-review/scripts/review-manifest.mjs" --exclude specs/mutex-scheduling/code-review.md --exclude specs/mutex-scheduling/exec-evidence.md` → `sha256:cbe8c18d510f4b9ebe3131aea9da65775c44c08f14370361dcbea792b14e81ac`
- **Review artifacts excluded**: `specs/mutex-scheduling/code-review.md`、`specs/mutex-scheduling/exec-evidence.md`
- **Discovery Package**:
  - `map_model.build_topology_map` → 只读 `TopologyMap.edge_zones`（`_edge_zones_by_id` 从 `zones` 反查）
  - `snapshots.ZoneSnapshot`；`TickSnapshot.zones: tuple[ZoneSnapshot, ...] = ()`
  - `rights.GrantOutcome`、`RightOfWayArbiter.request_right/release_right`
  - `dispatcher.FcfsDispatcher` 同时实现 `CommandSource`/`RightOfWayArbiter`/`ZoneStateProvider`（`ScheduledDispatcher`）；`_Request`、`_grant_pending`、`_is_first_in_every_queue`、`_waiting_for`、`read_zone_state`；`dispatch` = 授予 → `start_tick` 下发路径 → 对全部 `E_STOP` 下发 `RESUME`
  - `robot.Robot`：`_arbiter`、`_holding_zone_ids`、`_pending_request`、`_peer_circles`；`_begin_segment_entry`/`_apply_pending_request`/`_enter_segment`/`_release_all_zones`/`_wait_at_entrance`/`_holding_status`；`tick(tick_index)` 与 `set_peer_circles`
  - `safety.SafetyMonitor.check(..., reference_v_mps, peers)`：`circles = (*obstacles, *peers)`，相交兜底与前瞻共用
  - `simulation.Simulation.create_scheduled`；`step()` = tick 起始圆集合 → dispatch → 逐车 tick → 区状态读取 → 快照
  - demo 地图 10 节点/11 边、Z01–Z05；测试映射见覆盖表
- **Reused facts**: 同会话 `exec-evidence.md` 的验证结果在修复前快照上有效并已复用；修复后重跑了全部命令（见 Validation evidence），旧 fingerprint `sha256:6de480…` 仅对应修复前快照。
- **Historical findings**: CR-001–CR-004（Full Review 第 0 轮，4 条 open minor），本轮复核为 resolved，原 Issue/Evidence/Closure test 保留。
- **Validation environment**: `D:\Workspace\python\VirtualRobot`，Windows 10 (10.0.19041)，`.venv` CPython 3.13.9，pytest 9.2.0，零运行时第三方依赖。
- **Validation evidence**:
  - `.venv/Scripts/python.exe -m pytest tests -q`: 168 passed in 0.91s
  - `.venv/Scripts/python.exe -m pytest tests/test_dispatcher.py tests/test_mutex_scheduling.py -q`: 24 passed（含新增的 CR-001/CR-002 Closure tests）
  - `.venv/Scripts/python.exe -m pytest tests/test_benchmark.py -q -s`: 1 passed；`bench: robots=10 steps=1000 dt=0.02s average=0.0601ms p95=0.0951ms average_below_dt=True`
  - `.venv/Scripts/python.exe -m compileall -q src tests`: 通过
  - `git diff --check`: 干净（仅 CRLF 提示）
  - Closure mutation probes（临时内存改写，未落盘）：CR-001 将 `_waiting_for` 改为仅按 `robot_id` 排序 → `waiting_robot_ids == ('R10','R2')`、holder `('R10',)`；CR-002 从 peer 集合移除 `(0,15)` 的圆 → 后车 2500 tick 内无 `E_STOP`，直接 `ARRIVED` 于 (0,15)
  - AST 未使用导入扫描（排除 `__future__`）：无命中；`dispatcher.py` 中 `.key`/`def key` 计数为 0
- **Scope notes**:
  - `review.md` 是设计评审产物，本报告不继承其 findings，也不改写设计或任务状态。
  - 执行基线中的用户改动（`AGENTS.md`、`projects/virtual-robot/backlog.md`、`docs/`）不属于本项交付；仅按 `AGENTS.md` 的既有约定核对实现。
  - 同一机器人在 `ARRIVED` 后再次受理第二条路径不在本 spec 的支持流程内；`FcfsDispatcher` 的申请键按"每车一条路径"设计，该场景未纳入覆盖（属后续重规划能力）。
  - 基准耗时仅观测，不构成通过门槛。
  - `exec-evidence.md` 保留 spec-exec 时的原始执行记录（fingerprint `6de480…`、166 tests）；修复后的当前快照与验证以本报告为准。

## Results

- **Quality Result**: Pass
- **Spec Result**: Pass
- **Overall Result**: Pass
- **Merge readiness**: Go
- **Summary**: 27 条 AC 全部满足，`rights`/`dispatcher`/`robot`/`safety`/`simulation`/`snapshots`/`map_model`/demo 的实现与设计契约一致；4 条 minor 已全部修复并经 Closure Review 复核为 resolved；168 项测试、基准、编译与 diff 检查通过。

## Spec Coverage

| Requirement | Implementation | Evidence | Status | Finding / gap |
|-------------|----------------|----------|--------|---------------|
| AC-rights-single-holder | `dispatcher._grant_pending` 容量检查；`_holders` 集合 | `test_two_robots_contending_for_one_zone_leave_one_waiting_then_both_arrive`；`test_a_request_is_queued_until_the_next_dispatch_grants_it` | satisfied | — |
| AC-rights-fcfs-same-tick | `_Request.arrival_order = (arrival_tick, robot_id)`；`sorted` | `test_same_tick_requests_grant_the_lexicographically_first_robot`（R10 < R2） | satisfied | — |
| AC-rights-fcfs-arrival | 同上，arrival_tick 优先 | `test_an_earlier_application_wins_over_a_smaller_robot_id`；ring 交棒 | satisfied | — |
| AC-rights-atomic-multi-zone | `_is_first_in_every_queue` + 全组容量 | `test_a_multi_zone_request_is_granted_atomically_or_not_at_all`；`test_a_multi_zone_edge_is_granted_as_one_group` | satisfied | — |
| AC-rights-capacity | 每区 `len(holders) < capacity` | `test_capacity_two_admits_two_holders_and_queues_the_third_until_a_release`；`test_a_capacity_two_zone_admits_two_holders_and_queues_the_third` | satisfied | — |
| AC-rights-release-make-before-break | `robot._enter_segment`：先授予后释放 `held - target` | `test_a_waiting_robot_keeps_its_zone_until_the_switch_tick`；ring 场景 | satisfied | — |
| AC-rights-hold-while-waiting | `_begin_segment_entry` 排队不清空 `_holding_zone_ids` | `test_the_ring_releases_the_first_zone_only_when_the_second_is_granted`（Z03 持有 + Z01 等待） | satisfied | — |
| AC-rights-holding-status | `_holding_status` → `HOLDING_ZONE` | `test_a_first_segment_application_queues_at_the_start_node_until_granted`；多区/ring 快照 | satisfied | — |
| AC-rights-waiting-status | `_wait_at_entrance` 置 v/ω=0 | `test_two_robots...`（v=0、入口位姿）；`test_a_first_segment...` | satisfied | — |
| AC-deadlock-ring-forms | 三车首段互斥 + make-before-break | `test_three_robots_form_a_persistent_ring_wait_on_the_demo_triangle` | satisfied | — |
| AC-deadlock-persists | 无超时/抢占；`_wait_at_entrance` 不动位姿 | 同一测试后续 300 tick 全量快照比对 | satisfied | — |
| AC-peers-rear-end | `safety.check` 合并 `peers` 的两步判定 | `test_a_follower_stops_behind_a_blocked_leader_and_both_resume`；`test_a_follower_approaching_a_stopped_leader_stops_before_touching` | satisfied | — |
| AC-peers-auto-resume | `dispatch` 对全部 `E_STOP` 下发 `RESUME` | 上述 follower 测试（前车驶离后后车自行前进 >1 m） | satisfied | — |
| AC-peers-resume-blocked | `_intake_resume` 不安全时保持 E_STOP | follower 测试连续 100 tick 位姿/状态不变 | satisfied | — |
| AC-peers-tick-start-poses | `Simulation.step` 推进前采集全部机器人圆；`tick`/`_intake_resume` 读取同一集合 | 顺序无关测试；IDLE/WAITING/E_STOP/ARRIVED 对端均有断言（`test_an_arrived_robot_still_blocks_the_follower_behind_it`） | satisfied | — |
| AC-peers-order-independent | 起始圆集合 + 快照排序 + 请求排序 | `test_swapping_robot_order_leaves_the_snapshot_sequence_unchanged`；`test_swapping_robot_order_keeps_the_head_on_sequence_identical` | satisfied | — |
| AC-peers-initial-overlap | 相交兜底先于行驶 | `test_initial_overlap_keeps_the_starting_robot_in_e_stop`；`test_a_robot_starting_inside_another_robot_stops_with_overlap` | satisfied | — |
| AC-status-estop-over-holding | 急停不释放区；状态置 E_STOP | `test_a_holding_robot_shows_e_stop_and_returns_to_holding_zone`；`test_an_e_stop_while_holding_keeps_the_zone_and_reports_e_stop` | satisfied | — |
| AC-status-holding-after-resume | `_intake_resume` 成功 → `_holding_status()` | 同一测试；`test_a_resumed_robot_returns_to_holding_zone_and_releases_on_arrival` | satisfied | — |
| AC-snapshot-zone-detail | `read_zone_state` 覆盖全部区；holders 按 id、waiters 按 `(arrival_tick, robot_id)` | `test_zone_state_covers_every_zone_in_identifier_order`；`test_waiters_are_ordered_by_arrival_tick_before_robot_id`；snapshot 字段与顺序断言 | satisfied | — |
| AC-snapshot-zones-default | `TickSnapshot.zones` 默认 `()`；默认入口不注入 provider | `test_snapshot_carries_every_declared_field_and_no_zone_occupancy`；`test_the_default_entry_never_produces_zone_states...` | satisfied | — |
| AC-compat-default-create | `create` 保持 `PassthroughCommandSource`、无 arbiter | 上述默认入口测试 + `test_only_the_four_produced_states_ever_appear` | satisfied | — |
| AC-compat-scheduled-create | `create_scheduled` 默认 `FcfsDispatcher` 并三处注入 | `test_create_scheduled_publishes_zone_state_and_finishes_the_ring`；10 车 scheduled | satisfied | — |
| AC-contract-arbiter-swap | 三契约注入；`zones` 来自被装配实现 | `test_an_injected_dispatcher_produces_the_same_snapshot_sequence`（1500 tick 逐快照相等） | satisfied | — |
| AC-scale-ten-robots-scheduled | demo 10 节点；10 车环线路径 | `test_ten_robots_arrive_under_create_scheduled`（4000 tick 内全部 ARRIVED，区状态清空） | satisfied | — |
| AC-scale-ten-robots-default | 同上，无门禁 | `test_ten_robots_arrive_under_the_default_entry` | satisfied | — |
| AC-scale-no-initial-overlap | 10 节点两两 >0.70 m；首 tick 无 OVERLAP | `test_ten_robots_start_without_any_overlap_e_stop`；`test_demo_map_has_ten_startable_nodes_more_than_a_body_diameter_apart` | satisfied | — |
| IF-PROTO-right-of-way-arbitration | `rights.py` 协议；重复申请保留原 `arrival_tick`；释放未持有区无操作 | `test_repeating_a_request_keeps_one_entry_and_the_original_arrival_tick`；`test_releasing_an_unheld_zone_is_a_no_op...` | satisfied | — |
| IF-PROTO-zone-state-read | `read_zone_state` 无入参、全量区、只读幂等 | `test_zone_state_covers_every_zone_in_identifier_order`；`minimal` 地图返回 `()` | satisfied | — |
| DR-rights-grant-in-dispatch | 授予只在 `dispatch` 结算；申请最早下一 tick 生效 | `test_a_request_is_queued_until_the_next_dispatch_grants_it`；机器人首 tick 排队 | satisfied | — |
| Data model：`edge_zones` 单一来源、只读 | `build_topology_map` 内派生 + `MappingProxyType` | `test_edge_zones_inverts_the_zone_member_lists`；`test_derived_indexes_are_read_only` | satisfied | — |
| Error Handling：`minimal` 无区时 `create_scheduled` 只下发与恢复 | `required` 为空直接进入；`zones == ()` | 本轮只读探查：minimal scheduled 单车 3000 tick 内 `ARRIVED`、`zones=()`、无 WAITING/HOLDING | satisfied | 无套件内专用断言（行为已探查） |
| DR-scale-demo-map-extension | demo 保留 id/三角环/5 区，新增 N08–N10/E08–E11 | `test_the_demo_map_passes_build_and_creation_validation`（10/11/5）；`test_the_ring_legs_belong_to_mutually_exclusive_zones_with_a_shared_branch_edge`；`test_demo_map_has_ten_startable_nodes_more_than_a_body_diameter_apart` | satisfied | — |

## Findings

### CR-001: 快照等待队列的跨到达 tick 排序缺少直接断言

- **Basis**: quality
- **Severity**: minor
- **Status**: resolved
- **Origin**: full-review
- **Rule / requirement sources**: `AC-snapshot-zone-detail`（等待者按 `(arrival_tick, robot_id)` 升序）；`design.md` §Testing（排序规则）；common 规则"测试有效性"
- **Location**: `src/vrobot_sim/dispatcher.py:132-138`（`_waiting_for`）；`tests/test_dispatcher.py:59-81,139-149`
- **Issue**: 现有全部 `waiting_robot_ids` 断言要么只有一个等待者，要么两个等待者的 `arrival_tick` 相同（如 R10/R2 同为 5），只能证明 `robot_id` 次序；若实现退化为仅按 `robot_id` 排序，测试仍会通过。
- **Evidence**: 断言清单见上述行号；本轮只读探查：`R2@5`、`R10@9` 时 `waiting_robot_ids == ('R2','R10')`，dispatch 后授予 R2——当前实现正确。
- **Impact**: 覆盖缺口，不改变当前行为；后续重构可能无提示地破坏 AC 明确要求的跨 tick 排序。
- **Recommendation**: 增加一条调度器测试：先 `request_right("R2", …, 5)`，再 `request_right("R10", …, 9)`，断言等待列表为 `("R2","R10")`，dispatch 后持有人为 `("R2",)`。
- **Closure test**: 上述新测试在 `_waiting_for` 改为仅按 `robot_id` 排序时必须失败。
- **Related findings**: None

### CR-002: ARRIVED 前车作为车车判定输入缺少直接断言

- **Basis**: quality
- **Severity**: minor
- **Status**: resolved
- **Origin**: full-review
- **Rule / requirement sources**: `AC-peers-tick-start-poses`（明确列出 `IDLE`、`WAITING_RIGHT`、`ARRIVED`、`E_STOP`）；common 规则"测试有效性"
- **Location**: `src/vrobot_sim/simulation.py:74-81`；`tests/test_mutex_scheduling.py:217-252`；`tests/test_simulation.py:231-259`
- **Issue**: 现有断言覆盖 IDLE（同起点测试）、WAITING_RIGHT（10 车 R09/R07）、E_STOP（follower/leader），但没有一个场景断言一台 `ARRIVED` 机器人会挡住后车；实现无条件包含全部机器人，因此行为正确，但缺少防回归证据。
- **Evidence**: 本轮只读探查：R1 在 N08 `ARRIVED`，R2 沿 `N02→N01→N08` 接近后 `E_STOP`/`SAFETY_DISTANCE`，位姿 (0, 13.58)，中心距 1.422 m。
- **Impact**: 覆盖缺口；若后续按状态过滤 peer 集合，测试无法发现。
- **Recommendation**: 把上述探查固化为测试（无静态障碍，前车到达终点后保持 ARRIVED），断言后车 `E_STOP`、原因为 `SAFETY_DISTANCE` 且间距 ≥0.70 m。
- **Closure test**: 新增测试在 peer 集合排除 `ARRIVED` 机器人时失败。
- **Related findings**: None

### CR-003: 基准测试 docstring 指向已被取代的实测记录

- **Basis**: quality
- **Severity**: minor
- **Status**: resolved
- **Origin**: full-review
- **Rule / requirement sources**: 仓库"Durable Prose"约定（持久文本描述当前仓库事实）；`design.md` §Testing 基准项
- **Location**: `tests/test_benchmark.py:1-6`；`specs/sim-kinematics/benchmark-notes.md:3-5,28-31`
- **Issue**: `ROBOT_PATHS` 换成启用车车判定的 10 节点场景后，docstring 仍以现在时称耗时数字记录在 `specs/sim-kinematics/benchmark-notes.md`；该文件描述的是无 peer 判定、允许互相穿行的旧场景，当前数字只记录在本 spec 的 `exec-evidence.md`。
- **Evidence**: notes 第 3–5 行限定为 `WI-sim-kinematics`，第 28–31 行明确"本项不检测机器人之间的几何重叠"；benchmark 现已使用 `Simulation.create`（peer 判定生效）与新路径。
- **Impact**: 读者按 docstring 查到的数字与当前基准口径不符；不影响运行行为。
- **Recommendation**: 更新 notes 为本场景的实测数字，或改写 docstring 说明该 notes 为历史记录并给出当前数字的记录位置。
- **Closure test**: docstring/notes 对"当前基准场景与数字记录位置"的表述一致。
- **Related findings**: None

### CR-004: 新增代码残留未使用声明

- **Basis**: quality
- **Severity**: minor
- **Status**: resolved
- **Origin**: full-review
- **Rule / requirement sources**: 仓库约定"最小实现"；common 规则可维护性
- **Location**: `src/vrobot_sim/dispatcher.py:41-43`（`_Request.key`）；`tests/test_dispatcher.py:5`（`import pytest`）
- **Issue**: `_Request.key` 属性没有任何调用方（`request_right` 在局部重复构造 `(robot_id, segment_index)`）；测试文件的 `pytest` 导入未被使用。两者都是新增代码中的死声明。
- **Evidence**: `grep -n "\.key" src/vrobot_sim/dispatcher.py` 无命中；AST 未使用导入扫描仅报出 `pytest@5`。
- **Impact**: 无行为影响；增加新模块的表面与阅读噪声，并暗示一条并不存在的键路径。
- **Recommendation**: 删除两处；或让 `request_right` 使用 `request.key`（若保留属性）。
- **Closure test**: 静态扫描不再报未使用声明，`pytest tests -q` 仍全部通过。
- **Related findings**: None

## Check Summary

| Check | Scope / sources | Evidence / findings |
|-------|-----------------|---------------------|
| Project and language conventions | `AGENTS.md`：叶子/中层/顶层依赖方向、`rights` 无包内导入、快照与地图只读、零第三方依赖、单 Simulation 调度状态 | 通过；`rights.py` 无包内导入，`robot.py` 仅在 `TYPE_CHECKING` 引用 `safety`，`MappingProxyType` 只读；死声明已删除（CR-004 resolved） |
| Correctness and regression | 全部 AC 与设计契约；默认/调度两个入口；既有套件回归 | 27 条 AC 全部 satisfied；无行为缺陷；CR-001–CR-004 均 resolved（证据见 Closure） |
| Validation | 全量 pytest、基准、compileall、`git diff --check`、Closure mutation probes | 168 passed；基准 1 passed（average 0.0601 ms）；编译与 diff 检查通过；mutation probes 证明两条新 Closure tests 有判别力 |

## Closure

| Finding | Result | Evidence |
|---------|--------|----------|
| CR-001 | resolved | 新增 `test_waiters_are_ordered_by_arrival_tick_before_robot_id`：`R2@5`、`R10@9` → `('R2','R10')`，dispatch 后 holder `('R2',)`；mutation probe 将 `_waiting_for` 改为仅按 `robot_id` 排序 → `('R10','R2')`、holder `('R10',)`，原 Closure test 按预期失败 |
| CR-002 | resolved | 新增 `test_an_arrived_robot_still_blocks_the_follower_behind_it`：前车 `ARRIVED` 于 (0,15)，后车 `E_STOP/SAFETY_DISTANCE`、间距 1.422 m，50 tick 内保持冻结；mutation probe 从 peer 集合移除 (0,15) 的圆 → 后车 2500 tick 内无 `E_STOP`，直接 `ARRIVED` 于 (0,15)，原 Closure test 按预期失败 |
| CR-003 | resolved | `tests/test_benchmark.py` docstring 现说明每步运行完整 peer 判定，当前数字记录在 `specs/mutex-scheduling/exec-evidence.md`，`specs/sim-kinematics/benchmark-notes.md` 为启用 peer 判定前的历史记录；基准测试通过 |
| CR-004 | resolved | 删除 `_Request.key` 与 `tests/test_dispatcher.py` 的 `import pytest`；AST 未使用导入扫描无命中，`dispatcher.py` 中 `.key`/`def key` 计数为 0；168 项测试通过 |

## Recommended Next Step

- **Suggested action**: 交付；无未闭合 findings。
- **Findings / decisions**: CR-001–CR-004 已全部修复并复核为 resolved，无需用户裁决。
- **Expected scope / validation**: 本轮仅测试、docstring 与死声明改动；168 passed、基准 1 passed、compileall 与 `git diff --check` 通过。
- **After remediation**: Closure Review（round 1）已完成；后续改动针对新快照重新评审。
- **Convergence note**: 无剩余 minor。
