# Code Review

## Review Manifest

- **Review kind**: spec-backed
- **Mode**: Closure Review
- **Mode reason**: Round 1。仅处置第 0 轮的 8 条 findings，未新增需求，架构边界与数据模型归属未变。CR-006 确实加宽了公开接收契约（新增 `TARGET_MISMATCH`、`MALFORMED_PAYLOAD` 两个拒绝成员），CR-007 的决定写回了 design.md 的状态机 Guard，因此把 Closure scope 从"历史项 + 直接调用方"扩展到：4 个被改源文件全文、指令接收契约的全部生产者/消费者、地图构建校验与派生索引的一致性。未受影响模块沿用第 0 轮已核实的结论，并按复用条件复跑全量验证。
- **Closure round**: 1
- **Report language**: 中文（用户请求语言）；命令、路径、代码符号、AC ID 与状态枚举保持原文。
- **Target / scope**: 当前工作区 `D:\Workspace\python\VirtualRobot` 的目标版本，即 `WI-sim-kinematics` 的完整交付：`src/vrobot_sim/`（10 个模块 + `maps/` 两张内置地图）、`tests/`（9 个测试文件 + conftest，共 126 项，含本轮新增 5 项）、`pyproject.toml`、`AGENTS.md`、`specs/sim-kinematics/{tasks.md,exec-evidence.md,benchmark-notes.md}`。验收范围是整个 spec 的 43 条 AC 与关键设计契约，不以 tasks.md 的进度或 Phase 划分缩小。
- **Base / comparison**: 无法确定 VCS 基线。工作区不是 git 仓库（`git status` → `not a git repository`），执行基线由 `exec-evidence.md` 以目录快照文字记录：开始时无任何代码，只有 5 份文档。因此本评审不产生 diff，而是把全部交付文件当作新增内容完整读取，回归归因限制记入 Scope notes。
- **Spec source**: `specs/sim-kinematics/design.md`（含 11 条 Decision Record、3 条 IF-PROTO 契约、16 行状态机表、43 条 AC）
- **Standards sources**: `AGENTS.md`（本次交付新增，根目录，适用全部路径）；`pyproject.toml`（`requires-python>=3.11`、`dev` 依赖组、`pythonpath`）；仓库内无 formatter/lint/type-check 配置，无历史代码惯例可继承。
- **Languages / rules**: Python 3.13.9（`.venv`）。已加载 `rules/common.md`、`rules/spec.md`、`rules/validation.md`、`rules/findings.md`；无 Java/Go 实现，不加载语言规则；Python 无专用规则文件，按 common + 项目规范继续。
- **Input revisions**（本轮实际读取内容 SHA-256，修复后快照）：
  - `specs/sim-kinematics/design.md` — `bbcfb4db7a08b94770e528506f4d9aa4095547908ef58dc02abe20404a398ab4`（较第 0 轮 `c5ad49a0…` 变化：按 CR-007 决定补入恢复 Guard 段落与状态机 RESUME 行，AC 文本未改）
  - `specs/sim-kinematics/tasks.md` — `4e59f2edd7a4c2dc5ebdd8eb5d188339c6ba03ba733f4e6d21109e556904d8fa`（未变）
  - `specs/sim-kinematics/exec-evidence.md` — `dec085d39442a66e3e9ceed933479e12b1948c9fc1cb00e9f46d54db5cf4f9d1`（未变，由 spec-exec 流程维护）
  - 实现快照覆盖 `src/`、`tests/`、`pyproject.toml`、`AGENTS.md`
- **Snapshot evidence**: 读取命令 `find src tests pyproject.toml AGENTS.md -type f \( -name '*.py' -o -name '*.toml' -o -name '*.md' \) | sort | xargs cat | sha256sum`；无 staged/unstaged/untracked 概念（非 git 工作区），全部文件均已直接读取。修复前核对快照为 `f4039ab6…`（与第 0 轮一致），修改后为 `f088dd9f…`。
- **Manifest command / Diff fingerprint**: `review-manifest.mjs` 需要 `git rev-parse HEAD`，本工作区不可运行 → 等效快照为上述自算哈希，当前值 `sha256:f088dd9fd45837c79836436c92bd8c5c11927d7f729583a6840c6d198863f8b4`（第 0 轮为 `sha256:f4039ab6af5b76b11fd212b0362e36a202c7ffa158602a06279edbec36b7f080`）。
- **Review artifacts excluded**: `specs/sim-kinematics/code-review.md`（本报告，不在快照路径集内，写入不会使快照失效）、`specs/sim-kinematics/exec-evidence.md`（同理，非 `.py`/`.toml`，且未参与自算哈希）。
- **Discovery Package**:
  - 运行时依赖图（grep + import 实测，无环）：叶子 `map_model`/`kinematics`/`obstacle_field`；`controller` 仅 `TYPE_CHECKING` 引用 `robot.ChassisConfig`；`robot → controller, kinematics, map_model, obstacle_field`（`safety` 仅 `TYPE_CHECKING`）；`safety → robot`；`snapshots → robot`；`scenario → map_model, maps, obstacle_field, robot`；`simulation` 顶层装配；`maps → map_model`。
  - 每 tick 调用链：`Simulation.step`（simulation.py:54）→ `CommandSource.dispatch` → `Robot.tick`（robot.py:134）→ `SafetyMonitor.check`（safety.py:19）→ `Controller.linear_step`/`turn_step`/`estop_step`（controller.py:26/45/38）→ `advance_pose`（kinematics.py:23）→ `RobotSnapshot.from_robot`（snapshots.py:27）。
  - 校验三处“先全量校验再一次生效”：`build_topology_map`（map_model.py:224）、`Scenario.validate`+`Simulation.create`（scenario.py:42 / simulation.py:33）、`ObstacleField.register`（obstacle_field.py:40）。
  - 规则出处：AGENTS.md:24-40（零依赖、依赖方向、不可变、结构化拒绝、内置地图 ID、无真实时钟/CLI）。
- **Reused facts**: `exec-evidence.md` 记录的 AC→测试映射与静态核查（零第三方依赖、无 Non-Goal 关键词、无空白符问题）在本轮同一快照下复算一致，作为定位起点；结论以本轮重跑与逐文件读取为准。
- **Historical findings**: None（无历史 `code-review.md`；同目录 `review.md` 是 `design-review` 报告，只作设计层背景，不构成代码评审历史）。
- **Validation environment**: 执行目录 `D:\Workspace\python\VirtualRobot`；`.venv` 内 CPython 3.13.9；`pytest 9.2.0`（唯一开发依赖）；`src` 经 `pythonpath` 导入，未安装包；无网络、无数据库、无外部服务参与。
- **Validation evidence**:
  - `.venv/Scripts/python.exe -m pytest tests -q` → **126 passed in 0.28s**（修复后新快照重跑；第 0 轮 121 passed，新增 5 项用例：CR-001 两条、CR-002 一条、CR-006 两条）。
  - `.venv/Scripts/python.exe -m compileall -q src tests` → **passed**（项目未配置 linter/类型检查器，`dev` 依赖按 design.md 只允许 `pytest`，故未新增工具）。
  - AST 导入门（排除 `TYPE_CHECKING`）：`map_model`/`kinematics`/`obstacle_field` 无包内运行时导入；`controller` 仅类型引用 `robot`；`robot` 运行时不导入 `safety`；`safety`、`snapshots` 运行时导入 `robot` 枚举 → 与 CR-008 改写后的 AGENTS.md 条目一致，无导入环。
  - stdlib-only 审计（grep 全量 import）→ 仅 `__future__/math/dataclasses/enum/types/typing`，**零第三方运行时依赖成立**；行尾空白/Tab、Non-Goal 关键词（`zone_occup|right_of_way|http|websocket|argparse|random|time.time|sleep`）均零命中。
  - 原反例逐条复跑（结论见 Closure 表）：CR-001 的 `BOTH`+反向 `FWD`；CR-002 的重合节点；CR-004 的迟注册距离在 dt 0.02 与 0.05 两种触发位置；CR-006 的错寻址与带路径 RESUME。
  - 反证检查：CR-001 修复后，两条方向相反的 `FWD` 边（合法形状）仍构建成功且索引为 `{('A','B'):E01, ('B','A'):E02}`，未被过度拒绝；`load_map("minimal")` 与 `load_map("demo")` 仍可构建。
- **Scope notes**:
  1. 无 VCS 基线 → 无法用 diff 区分“本次改动”与“既有代码”；因开始时无代码，全部交付物按新增处理，归因限制如实记录。
  2. 浏览器可视化、通信层、多车路权、50 台规模等 design.md Non-Goals 未评审也不应存在；关键词扫描确认无残留。
  3. `review-manifest.mjs` 与工作区 `--check` 类 git 检查不可用，已按 validation 规则以等效内容哈希替代；不因此判定 Blocked（不阻断正确性判断）。
  4. `exec-evidence.md` 第 1–7 条解释性决定中，第 4 条（恢复判定参考速度）已按 CR-007 决定升格为 design.md 条文；第 2、3 条（段末吸附节点、弧线+下限剖面）经行为核查与设计前提自洽，未单独立项。
  5. 热路径每 tick 重建 `SegmentGeometry`、`ObstacleField.active()` 与快照排序，`TopologyMap.node/edge` 为线性查找：10 台实测 0.053 ms/步（dt 的 0.26%），50 台规模按线性外推仍有余量，不构成 finding，作为 `WI-scale-50-robots` 输入。
  6. 本轮修复范围外的遗留观察：`tests/test_benchmark.py:31` 长 130 字符，超出其余文件的 ≤120 习惯。项目未配置 formatter 也无成文行长规则，按 common 规则"工具未配置不等于代码违规"，只作风格提示。
  7. CR-005 的残留说明：逐 tick 输出相等与集合包含判定都可失败，但"成员边存在"这条正向行受构建期校验保护，无法在已建成的地图上造反例；真正可失败的证据是同批的负向用例（成员边缺失 → `MapBuildError`）。
  8. `tasks.md` Overview 仍写"16 行转移"，design.md 状态机因 CR-006 决定新增一行（现 17 行）。计数与 checkbox 由 spec-exec / spec-plan 维护，评审未改，需要同步时由对应流程处理。

## Results

- **Quality Result**: Pass
- **Spec Result**: Pass
- **Overall Result**: Pass
- **Merge readiness**: Go
- **Summary**: 第 0 轮的 8 条 findings 全部以反例复跑证明根因消除（见 Closure 表），无参与计算的 open/reopened 项。43 条 AC 全部 satisfied，两条此前 `unsatisfied` 的行（`AC-map-parallel-edge-reject`、IF-PROTO-robot-command-intake）已修复并各带新用例；反证检查确认修复没有过度拒绝合法地图形状。适用的必需验证（`pytest tests -q` 126 passed、`compileall`、导入图与依赖/Non-Goal 审计）在同一新快照上有有效证据。剩余限制如实记录：无 VCS 基线使 diff 类检查以内容哈希替代；项目按设计只允许 `pytest` 作为开发依赖，故无 linter/类型检查器可复用。

## Spec Coverage

| Requirement | Implementation | Evidence | Status | Finding / gap |
|-------------|----------------|----------|--------|---------------|
| AC-kinematics-pose-integration | kinematics.py:23-37 `advance_pose`；robot.py:259/272/297 调用 | test_kinematics 直线/转向/θ 半开区间边界 5 组取值；test_robot 到达用例 | satisfied | None |
| AC-kinematics-no-cross-track-drift | kinematics.py:30-36（θ 钉在段方向）；robot.py:277-283 段末吸附节点 | test_kinematics::横向偏移恒为 0；test_integration_minimal::质心贴中心线（逐 tick <1e-12） | satisfied | None |
| AC-kinematics-segment-end-stop | controller.py:42 `segment_finished`；robot.py:268-290 | test_robot::段末归零后原地转向；test_controller::整段剖面 | satisfied | None |
| AC-kinematics-turn-no-overshoot | controller.py:45-59；robot.py:264-266 同 tick 吸附 θ | test_controller::剩余角恰等于容差、完整转向不过冲 | satisfied | None |
| AC-kinematics-first-turn-align | robot.py:247-253 `_aim_at_segment` | test_robot::初始航向不一致先转向（转向期间位移恒为 0） | satisfied | None |
| AC-kinematics-arrival | robot.py:283-287 | test_robot::到达并停止转向；test_integration_minimal::解析端点 (10.0, 5.0) | satisfied | None |
| AC-kinematics-linear-speed-bound | controller.py:34 `min(v_max, ...)` | test_integration_minimal::逐 tick；test_controller::巡航截断 | satisfied | None |
| AC-kinematics-linear-accel-bound | controller.py:33-36 | test_integration_minimal::逐 tick 上升量 ≤ a_max·dt | satisfied | None |
| AC-kinematics-normal-decel-bound | controller.py:36 下限 `v - a_max·dt` | test_integration_minimal::无障碍场景每步下降量；test_controller::剖面单调 | satisfied | None |
| AC-kinematics-estop-decel-bound | controller.py:38-40 `estop_step`；robot.py:292-298 | test_controller::estop_step；test_robot::每步上限；test_integration_estop::内核每步上限（仅此 AC 断言该性质，未并入其他 THEN） | satisfied | None |
| AC-kinematics-angular-speed-bound | controller.py:51-55 | test_integration_minimal::转向 tick 数=66 与 \|ω\|≤ω_max；test_controller::完整转向 | satisfied | None |
| AC-path-task-accept | robot.py:173-184, 236-245 | test_robot::受理即 MOVING 且 `path_edge_ids` 正确 | satisfied | None |
| AC-path-missing-edge-reject | robot.py:221-233 | test_robot::缺失节点对拒绝、状态与速度不变（错误含 `('N01', 'N03')`） | satisfied | None |
| AC-path-single-way-violation-reject | robot.py:226-231 | test_robot::逆行 E02；test_integration_demo::内核内被拒且保持 IDLE | satisfied | None |
| AC-path-unknown-node-reject | robot.py:218-220 | test_robot::错误含未知标识 `GHOST` | satisfied | None |
| AC-path-start-node-mismatch-reject | robot.py:216-217 | test_robot::错误含两侧标识且 `len(violations)==1` | satisfied | None |
| AC-estop-trigger-before-contact | safety.py:37-50 | test_safety::落在窗口内触发；test_integration_estop::预置障碍停住、原因 SAFETY_DISTANCE | satisfied | None |
| AC-estop-late-registration-overlap | robot.py:150-155 | test_robot::迟注册下一 tick 归零；test_integration_estop::行驶中/减速中两种时机；距离改到 0.45 后在 dt 0.02 与 0.05 两种触发位置都稳定改写为 OVERLAP | satisfied | CR-004 已闭合 |
| AC-estop-lateral-obstacle-no-trigger | safety.py:44-47 | test_safety::越门槛跳过 + 恰等于门槛的对照组仍触发 | satisfied | None |
| AC-estop-no-overlap | safety.py:30-33 严格相交 + 前瞻余量推导 | test_safety::dt 上限预置场景不出现 OVERLAP、两圆间隙 ≥ 半径和 | satisfied | None |
| AC-estop-stops-before-segment-end | safety.py:39-42 窗口在段末截断；robot.py:292-298 不动段位置 | test_robot::停在节点前且 `segment_index`/子阶段不变；test_integration_estop::同 | satisfied | None |
| AC-estop-straddling-obstacle-stops | safety.py:48-50 覆盖区间判定 | test_safety::10.05 m 障碍在 dt 0.02 与 0.05 下均停稳；test_integration_estop::本段计入 | satisfied | None |
| AC-estop-resume-continues-path | robot.py:186-203（Guard 已写入 design.md 状态机：按 `v_max_mps` 名义前瞻） | test_robot::注销后恢复走完；test_integration_estop::内核版本（断言未回起点）；本轮复跑 clean RESUME 仍被受理 | satisfied | CR-007 已按用户决定闭合（代码不变，口径入设计） |
| AC-estop-resume-still-unsafe | robot.py:195-201 | test_robot::位姿逐字段不变、原因保持 SAFETY_DISTANCE；test_integration_estop::同 | satisfied | CR-007 已按用户决定闭合 |
| AC-estop-resume-invalid-state | robot.py:187-189 + `_invalid_state` | test_robot::IDLE/MOVING/ARRIVED 参数化；test_integration_estop::经指令边界断言 INVALID_STATE | satisfied | None |
| AC-estop-reassign-rejected | robot.py:173-175 | test_robot::路径/位姿/速度不变；test_integration_estop::INVALID_STATE | satisfied | None |
| AC-estop-initial-overlap | robot.py:150-155（第一 tick） | test_robot::起始即相交；test_integration_estop::参数化 OVERLAP 分支 | satisfied | None |
| AC-state-unproduced-states | robot.py:20-32（6 成员）+ 转移实现 | test_robot::两张内置地图参数化，观测集合 ⊆ 四成员 | satisfied | None |
| AC-command-source-swap | robot.py:306-327；simulation.py:34 注入点 | test_robot::替身源逐 tick 输出完全相等 + 同一 `Robot` 类（恒真的模块身份断言已删除） | satisfied | CR-005 已闭合；"本体代码未修改"属流程约束，可失败部分只有输出相等 |
| AC-map-edge-attributes-complete | map_model.py:46-54；maps/{minimal,demo}.py | test_map_model::五项属性 + 距离代价等于派生长度（两张图参数化） | satisfied | None |
| AC-map-critical-zone-members-exist | map_model.py 的 `_check_zone_membership`（成员边必须存在） | test_map_model::成员集合包含判定 + 成员边缺失被拒；test_integration_demo::`Z09` 引用 `E404` → `MapBuildError` | satisfied | CR-005 的恒真断言已替换为可失败的集合判定 |
| AC-map-parallel-edge-reject | map_model.py:201-219 `_effective_pairs`+`_check_parallel_edges`；262-266 派生索引与校验同源 | test_map_model::同声明方向重复被拒、`BOTH`+反向 `FWD` 被拒（含 `('B','A')` 与两条边标识）、两条 `BOTH` 被拒；反证：反向两条 `FWD` 仍合法 | satisfied | CR-001 已闭合 |
| AC-map-invalid-edge-reject | map_model.py:160-164 | test_map_model::错误含 `E09` 与 `to_node_id=NOPE` | satisfied | None |
| AC-map-demo-ring-dependency | maps/demo.py:31-58 | test_map_model::环路 DFS + 环边互斥临界区；test_integration_demo::Z01/Z02/Z03 与共享边 E05 | satisfied | None |
| AC-sim-step-advances-fixed-dt | simulation.py:54-69 | test_simulation::首快照 dt、增量恒等 dt、位移等于本 tick v·dt | satisfied | None |
| AC-sim-deterministic | simulation.py:33-47；obstacle_field.py:67 排序 | test_simulation::两次运行 500 tick 快照逐字段相等 | satisfied | None |
| AC-sim-invalid-dt-reject | scenario.py:55-57 | test_simulation::四种非法 dt 参数化，含字段与范围 | satisfied | None |
| AC-sim-invalid-map-id-reject | scenario.py:50-52；simulation.py:36 | test_simulation::列出 `'demo'`/`'minimal'` | satisfied | None |
| AC-sim-invalid-turn-tolerance-reject | scenario.py:84-94 | test_simulation::含 robot_id 与两个比较值 | satisfied | None |
| AC-sim-snapshot-complete | snapshots.py:14-47 | test_simulation::字段名逐项比对（不含临界区占用字段）+ 冻结不可变 | satisfied | None |
| AC-obstacle-effective-next-tick | obstacle_field.py:40-61；robot.py:148 每 tick 读取 | test_simulation::两台机器人均因新障碍急停；test_robot/test_integration_estop::迟注册下一 tick 生效 | satisfied | None |
| AC-obstacle-invalid-radius-reject | obstacle_field.py:41-47 | test_safety::0/负值/6.0 三例拒绝且集合不变 | satisfied | None |
| AC-bench-step-cost-measured | tests/test_benchmark.py + benchmark-notes.md | 三次运行平均 0.0527–0.0567 ms、P95 0.0638–0.0770 ms，均标注小于 dt | satisfied | None |
| Goals：逐 tick 数值自检而非人工观察 | test_integration_minimal 全量逐 tick 断言 | 126 项通过 | satisfied | None |
| DR-motion-follow-model：质心恒在中心线、θ 吸附 | robot.py:264-283 | 横向偏移逐 tick <1e-12 | satisfied | None（段末吸附见 exec-evidence 决定 2） |
| DR-critical-zone-entity：不生成边到临界区反查索引 | map_model.py:262-274（仅两个派生索引） | grep 确认无反查结构 | satisfied | None |
| DR-robot-status-flat-enum-six：6 成员冻结、转向不是状态 | robot.py:20-32；robot.py:119/251 子阶段用剩余量表达 | test_robot::状态集合断言 | satisfied | None |
| DR-discrete-sim-clock：不读真实时间、无驱动循环 | simulation.py:30-31, 56 | src 内无 `time`/`sleep`（grep 零命中） | satisfied | None |
| IF-PROTO-robot-command-intake：载荷与受理门禁、同步结构化拒绝 | robot.py:131-141（寻址校验）、186-194（载荷形状校验）、robot.py:48-52 新增 `TARGET_MISMATCH`/`MALFORMED_PAYLOAD` | test_robot::错寻址被结构化拒绝且状态与路径不变；带路径 RESUME 被拒且随后 clean RESUME 仍可恢复；全部既有拒绝用例通过 | satisfied | CR-006 已闭合；design.md 状态机新增对应一行（见 Scope notes 8） |
| design.md Error Handling：地图构建期错误指出具体对象与字段、不产出半成品 | map_model.py:221-234 `_check_edge_lengths` + 既有校验族 | 本轮复跑：重合节点边 → `MapBuildError` 含 `E07` 与 `zero length`，原 `ZeroDivisionError` 路径不再可达 | satisfied | CR-002 已闭合 |
| IF-PROTO-obstacle-registration：拒绝时集合不变、注销未找到 | obstacle_field.py:40-65 | test_safety::集合不变 + NOT_FOUND | satisfied | None |
| IF-PROTO-sim-step-advance：创建输入 scenario、全终态后仍返回快照 | simulation.py:33-47, 54-69 | test_simulation::终态后连续 25 步仍返回快照 | satisfied | None（可选 `command_source` 参数为 swap 所必需，兼容） |
| Non-Goals 不越界（路权、可视化、路径规划、通信、角加速度、车间碰撞等） | 全模块 | grep 关键词零命中；未实现任何 Non-Goal 能力 | satisfied | None |

## Findings

### CR-001: 平行边构建期校验只看声明方向，`BOTH` 与反向 `FWD` 静默丢失一条边

- **Basis**: spec, quality
- **Severity**: major
- **Status**: resolved
- **Origin**: full-review
- **Rule / requirement sources**: AC-map-parallel-edge-reject；design.md Constraints and Indexes「一个有序节点对至多一条边。本项不支持平行边，构建期校验并报错」；DR-path-supplied-by-scenario「一个有序节点对唯一确定一条边」；Error Handling「同一有序节点对出现两条边」
- **Location**: `src/vrobot_sim/map_model.py:207-215`（`_check_parallel_edges` 只遍历 `edge.from_node_id→edge.to_node_id`）与 `src/vrobot_sim/map_model.py:245-249`（`BOTH` 边把反向有序对也写入索引）
- **Issue**: 一条 `BOTH` 边实际上占用两个有序节点对。若数据里再出现同节点对的反向 `FWD` 边（E01 A→B BOTH 与 E02 B→A FWD），声明方向互不相同，`_check_parallel_edges` 不报错；随后 `pair_index[(B, A)]` 先写入 E01、再被 E02 覆盖，索引静默丢掉一条边的可通行性。
- **Evidence**: 本轮反例脚本：`build_topology_map("t", nodes A/B, (E01 A→B BOTH, E02 B→A FWD))` 构建成功，`edge_by_node_pair` 为 `{('A','B'): 'E01', ('B','A'): 'E02}`，即 E01 的反向可通行性被丢弃且无任何违规项。对照 AC 原文：该输入确实是「在同一个有序节点对上放入两条边」（E01 使 B→A 合法，E02 也是 B→A），期望结果应为构建失败并指出该节点对。现有测试 `test_map_model.py:159` 只覆盖两条边声明方向相同的情形。
- **Impact**: 两张内置地图不受影响，但地图数据是 `WI-map-editor`/外部数据的唯一入口，`edge_by_node_pair` 又是 `Robot._validate_path`（robot.py:210-213）与派生长度的唯一真相源。静默覆盖会让受理的路径走到被丢弃的那条边（错误的临界区归属、错误的路宽等占位属性），且违反本 spec 明确要求构建失败的验收条款；错误只会在行驶行为里暴露，定位成本高。
- **Recommendation**: 把校验对象从「声明的有序对」改为「有效有序对集合」——`BOTH` 边同时登记正反向两个有序对，与所有边的声明对一起查重，命中即产出「哪两条边争用哪个有序对」的违规项（沿用现有 violations 汇总、一次生效的写法）。若判断 `BOTH`+反向 `FWD` 应在语义上合法，则必须先修订 design.md 的 Constraints 与 AC 口径（决定权在设计流程，不由实现单方面选择）。
- **Closure test**: 新增用例：以上面的两/三节点数据调用 `build_topology_map`，断言抛出 `MapBuildError` 且 `violations` 中包含争用的有序节点对与两条边标识；同时 `test_map_model.py:159` 原用例继续通过，内置两张地图 `load_map("minimal"/"demo")` 仍能构建。
- **Related findings**: None

### CR-002: 坐标重合的节点通过构建，`segment_geometry` 抛未结构化的 ZeroDivisionError

- **Basis**: quality
- **Severity**: minor
- **Status**: resolved
- **Origin**: full-review
- **Rule / requirement sources**: design.md Error Handling「地图构建期错误…错误信息指出具体对象与字段，不产出半成品地图」；「以上错误都不产生部分写入」；common 规则「错误路径」
- **Location**: `src/vrobot_sim/map_model.py:218-221`（`_edge_length`）与 `src/vrobot_sim/map_model.py:136-141`（`unit_x=delta_x / length`）
- **Issue**: 两个不同 `node_id` 取相同坐标（占位范围 0–200 内合法）时，边长为 0 并通过构建期校验；首次按该边行驶或判定即 `delta_x / 0` 触发 `ZeroDivisionError`，异常既不带对象与字段，也绕过「先完整校验再一次生效」的边界。
- **Evidence**: 本轮反例：`build_topology_map("t2", (MapNode("A",0,0), MapNode("B",0,0)), (E01 A→B BOTH,))` 成功返回，`edge_length_m["E01"] == 0.0`；随后 `m.segment_geometry("A","B")` → `ZeroDivisionError: float division by zero`。
- **Impact**: 只在外部地图数据出错时触发（内置两张地图无此形状），但触发点是每 tick 必经的几何入口，表现为内核崩溃而不是可定位的构建失败，与 spec 的地图错误语义不一致。
- **Recommendation**: 在 `build_topology_map` 的同一批校验里增加「边长必须大于 0」并指出边标识（与现有数值范围检查同构），保持「先校验再一次生效」；不建议在 `segment_geometry` 里做防御性判断。
- **Closure test**: 构造重合节点的地图并断言 `MapBuildError.violations` 指出该边；`test_map_model` 其余用例与 121 项全量结果不退化。
- **Related findings**: None

### CR-003: 无人使用的几何方法与常量（`end_x`/`end_y`、`TURN_ALIGN_ALIGNMENT_RATIO_LIMIT`）

- **Basis**: quality
- **Severity**: minor
- **Status**: resolved
- **Origin**: full-review
- **Rule / requirement sources**: common「为当前目标不需要的扩展预建抽象」；交付范围（tasks.md 未要求该入口）
- **Location**: `src/vrobot_sim/map_model.py:81-85`（`SegmentGeometry.end_x`/`end_y`）；`src/vrobot_sim/scenario.py:15`
- **Issue**: 两处定义在全仓库无引用。段末落点由 `robot._finish_segment` 直接读节点坐标（robot.py:266），`end_x/end_y` 提供的是另一条会引入浮点误差的算法路径；`TURN_ALIGN_ALIGNMENT_RATIO_LIMIT = 1.0` 未被使用，判定实际写在 `_validate_turn_tolerance` 里。
- **Evidence**: `grep -rn "end_x\|end_y\|TURN_ALIGN_ALIGNMENT_RATIO_LIMIT" src tests` 只命中定义本身（以及对应 `__pycache__` 编译产物）。
- **Impact**: 两份“段末在哪里”的表达会诱使后续改动只改一处；未使用的阈值常量容易被误认为已生效的校验口径。维护成本具体但不影响行为。
- **Recommendation**: 删除两个方法与该常量；若希望显式表达「容差/dt 不得超过 ω_max」的比值上限，就在 `_validate_turn_tolerance` 内用字面量或就近命名常量。
- **Closure test**: 再次全仓 grep 零命中，`pytest tests -q` 仍 121 通过。
- **Related findings**: None

### CR-004: 减速途中改写原因的用例把迟注册障碍放在 1 ulp 边界上

- **Basis**: quality
- **Severity**: minor
- **Status**: resolved
- **Origin**: full-review
- **Rule / requirement sources**: common「测试有效性：断言能在目标实现缺失或错误时失败」；AC-estop-late-registration-overlap（意图证据）
- **Location**: `tests/test_robot.py:317`（`obstacle_at(robot.pose.x + BODY_RADIUS_M + 0.2, ...)`）
- **Issue**: 注册距离恰好等于「车体半径 + 障碍半径」= 0.55，而 `safety.py:32` 用严格小于判定相交。是否触发取决于 `(p + 0.35) + 0.2 - p` 舍入到哪一侧，即依赖当次急停触发位置这个实现细节，而不是被测语义。
- **Evidence**: 本轮数值探针：threshold `0.2+0.35 = 0.55`；p=4.728119999999994 → dist=0.5499999999999998 → 触发 OVERLAP（当前用例因此通过）；p=2.7181 → dist=0.5500000000000003 → 不触发，原因会停留在 SAFETY_DISTANCE，断言失败。对照 `tests/test_integration_estop.py:158` 用 `+ BODY_RADIUS_M + 0.1`（0.45 < 0.55，对所有取样位置稳定成立）。
- **Impact**: 任何改动触发位置的因素（剖面、dt、参数默认值）都可能让这个用例假失败，或者反过来在实现真的丢掉原因改写时仍侥幸通过；同一语义在两个测试文件里表现不一致。
- **Recommendation**: 把该位置也改成明显落在接触范围内的距离（如 `+ BODY_RADIUS_M + 0.1`），与内核用例统一；不需要修改被测代码。
- **Closure test**: 该用例在不同 `pose.x` 触发位置下（例如把 dt 取 0.02/0.05 各跑一遍）都能稳定断言出 `EStopReason.OVERLAP`。
- **Related findings**: None

### CR-005: 无法失败的断言（模块身份、`is not None`）

- **Basis**: quality
- **Severity**: minor
- **Status**: resolved
- **Origin**: full-review
- **Rule / requirement sources**: common「测试有效性」；AC-command-source-swap、AC-map-critical-zone-members-exist
- **Location**: `tests/test_robot.py:367-368`；`tests/test_map_model.py:92`
- **Issue**: `advance_pose.__module__ == "vrobot_sim.kinematics"` 与 `Robot.tick.__module__ == "vrobot_sim.robot"` 只描述定义位置，无论指令源如何替换都为真，无法证明「本体代码路径未变」这一意图；`assert map_obj.edge(edge_id) is not None` 中 `TopologyMap.edge()` 缺失时抛 `KeyError`，永远不返回 `None`，断言恒真。
- **Evidence**: 代码即证：`map_model.py:119-123` 的 `edge()` 只 `return` 或 `raise KeyError`；两个 `__module__` 值是静态属性。
- **Impact**: 契约测试给人「本体变更会被抓到」的错觉，实际只有逐 tick 输出相等那半段在起作用；临界区成员存在性同理，靠异常而非断言失败。不阻断 AC 满足，属于误导性的证据强度标注。
- **Recommendation**: 删掉恒真断言，或改为可失败的形式：契约用例保留「逐 tick 输出完全相等」并在 docstring 写明「本体未改动」是流程约束（由 diff 审查承担），成员存在性改为 `{z.edge_ids} <= {e.edge_id for e in map.edges}` 集合判定。
- **Closure test**: 两处不再存在恒真断言，且 `pytest tests -q` 通过；故意把 `TopologyMap.edge` 改成返回 `None` 时（临时验证，不入库）相关用例应失败。
- **Related findings**: None

### CR-006: 指令接收边界不校验载荷形状与目标标识

- **Basis**: spec, quality
- **Severity**: minor
- **Status**: resolved
- **Origin**: full-review
- **Rule / requirement sources**: design.md Data Model `[ADD] motion-command`「`robot_id` — 目标机器人；`node_path` — `ASSIGN_PATH` 时必填，`RESUME` 时必须为空」；IF-PROTO-robot-command-intake「同步返回受理结果…状态门禁」；common「输入信任边界」
- **Location**: `src/vrobot_sim/robot.py:129-132`（`receive` 未使用 `command.robot_id`）、`src/vrobot_sim/robot.py:178-195`（`_intake_resume` 完全忽略 `node_path`）
- **Issue**: 机器人只按调用对象本身决定行为，不核对指令寻址。`MotionCommand(robot_id="R2", ...)` 投给 R1 会被 R1 当作自己的路径受理；`RESUME` 带着非空 `node_path` 被静默接受（形状约束只写在文档里，没有实现也没有拒绝语义）。
- **Evidence**: 本轮反例：`r1.receive(MotionCommand(ASSIGN_PATH, "R2", ("N01","N02","N03")))` → `accepted=True`，R1 的 `path_node_ids` 变为 R2 的序列并进入 MOVING。代码层面 `receive` 从不读取 `command.robot_id`。
- **Impact**: 本项内置直通指令源按 robot_id 路由，所以现在没有可观察错误；但 `WI-pluggable-dispatcher`/`WI-mutex-scheduling` 会替换指令源，届时装错对象会静默改道，且 `robot_id` 与 `RESUME.node_path` 这两条已批准的载荷约束在边界上没有任何强制。
- **Recommendation**: 在 `receive` 入口加一条与既有 `CommandRejection` 同族的拒绝（如 `TARGET_MISMATCH`）并把「RESUME 必须为空路径」纳入同一结构化拒绝；或者明确决定这两条不属于本项强制范围，把设计文档的措辞从数据模型约束降级为生产者责任，避免下游误以为边界已校验。
- **Closure test**: 新增用例：把 `robot_id` 不匹配的 `ASSIGN_PATH` 投给机器人，断言被结构化拒绝且路径、位姿、速度不变；`RESUME` 携带非空 `node_path` 时得到确定的受理结果（拒绝或按文档忽略，二者都要有测试）。
- **Related findings**: None

### CR-007: 恢复判定使用 `v_max` 作参考速度，与每 tick 前瞻公式的字面口径不一致

- **Basis**: spec
- **Severity**: minor
- **Status**: resolved
- **Origin**: full-review
- **Rule / requirement sources**: design.md Key Mechanisms 前瞻安全距离「每个 tick 先算刹车距离 v²/(2·decel_max)，加上车体半径和位移余量 v·dt」；State Machines「`E_STOP` + `RESUME` 且前瞻安全距离成立 → `MOVING`」；AC-estop-resume-still-unsafe、AC-estop-resume-continues-path、AC-estop-no-overlap
- **Location**: `src/vrobot_sim/safety.py:25,35-37`（新增 `reference_v_mps`）与 `src/vrobot_sim/robot.py:182-192`（恢复时传入 `v_max_mps`）
- **Issue**: 按字面公式，静止机器人刹车距离为 0，前瞻窗口只剩车体半径，因此以 SAFETY_DISTANCE 停稳（实测停在障碍前 ≥ 车体半径 + 半步位移）后 RESUME 必判“安全”，机器人会起步再立即重新触发急停，形成走走停停；AC-estop-resume-still-unsafe 在字面口径下几乎不可达。实现改为以 `v_max` 判定，使该 AC 成立，但这会让恢复条件比每 tick 条件更保守。
- **Evidence**: `exec-evidence.md` 解释性决定第 4 条自述了这一偏离；本轮行为核查确认：默认参数下 SAFETY_DISTANCE 停稳点与障碍最近点之间恒留 `v·dt/2` 以上间隙（test_safety/test_integration_estop 的间隙断言即该余量的体现），故取当前速度判定恒为“安全”。
- **Impact**: 恢复语义是本项交给下游的三份契约之一（DR-estop-explicit-resume），行为差异会直接改变 `WI-mutex-scheduling` 构造“停过再起步”时的观察结果；实现本身自洽且有测试覆盖，但这是设计文字未钉死、由实现选择的口径，需要设计侧确认或补写。
- **Recommendation**: 请设计确认恢复判定使用“参考速度 = 该车 `v_max`”并把这句写进 Key Mechanisms / 状态机 Guard；若选择另一口径（例如按剩余段长的名义速度或引入显式“恢复安全裕度”参数），实现随之调整。
- **Closure test**: design.md 明文规定恢复判定的速度口径，且 `test_integration_estop::test_resume_into_a_blocked_path_keeps_the_e_stop_and_the_pose`、`test_after_the_obstacle_is_removed_the_robot_finishes_the_remaining_path` 与该口径一致通过。
- **Related findings**: None

### CR-008: AGENTS.md 的依赖方向陈述与实际导入图不符

- **Basis**: quality
- **Severity**: minor
- **Status**: resolved
- **Origin**: full-review
- **Rule / requirement sources**: common「项目规范优先关系以 common 为准」「规范符合性」；AGENTS.md:29-31；design.md Architecture 依赖图
- **Location**: `AGENTS.md:29-30`（「`controller`、`safety`、`robot` 只向上依赖它们；箭头不得反向」）
- **Issue**: 实际运行时 `safety → robot`（读取 `EStopReason`，safety.py:8）与 `snapshots → robot`（snapshots.py:8），相对设计图的 `robot → safety` 是反向。下一条 bullet 解释了注入做法，但第 29–30 行的规则本身按字面会把这两处判定为违规；`snapshots` 的同类关系未被提及。
- **Evidence**: 本轮依赖图审计结果；`robot.py:14-17` 仅在 `TYPE_CHECKING` 下引用 `SafetyMonitor`，因此运行时无环，但方向确实与设计图相反。
- **Impact**: 后续贡献者按 AGENTS.md 检查会误判现有代码违规，或反过来“修正”成真正的导入环；共享枚举单一归属这一关键约定也缺少清晰表述。
- **Recommendation**: 把规则改写为事实描述：枚举归属 `robot.py`；`safety`、`snapshots` 可依赖 `robot` 的枚举；`robot` 通过装配注入 `SafetyMonitor`，因此不得在运行时导入 `safety`。保留“箭头不得反向”只针对 `map_model/kinematics/obstacle_field` 这些叶子。
- **Closure test**: 按 AGENTS.md 逐条核对实际 import 图无冲突，且新读者能据此判断哪些反向导入是允许的。
- **Related findings**: None

## Check Summary

| Check | Scope / sources | Evidence / findings |
|-------|-----------------|---------------------|
| Project and language conventions | AGENTS.md:24-42、pyproject.toml、`dev` 依赖约束；无 linter/formatter 配置 | 零第三方运行时依赖成立（import 全量审计）；行尾空白/Tab 零命中；frozen dataclass + `MappingProxyType` 满足不可变；无 CLI/网络/真实时钟/事件日志等 Non-Goal 残留；AST 导入门与 AGENTS.md 改写后的条目一致。CR-003、CR-008 已闭合；范围外风格观察见 Scope notes 6 |
| Correctness and regression | 43 条 AC + 3 条 IF-PROTO + 17 行状态机逐条追踪；核心路径 safety/controller/robot/map_model | 单车完整任务、两种急停收尾、恢复、指令源替换、确定性、快照与三类配置拒绝均有行为证据；本轮额外覆盖错寻址拒绝、带路径 RESUME 拒绝、有效有序对查重与零长度边拒绝。8 条 findings 全部 resolved，反证检查确认合法地图形状未被过度拒绝 |
| Validation | `.venv` CPython 3.13.9 + pytest 9.2.0；126 项用例 | `pytest tests -q` 新快照重跑 **126 passed**；`compileall` 通过；`review-manifest.mjs` 因无 git 不可运行 → 以自算内容哈希固定快照（修复前 `f4039ab6…`、修复后 `f088dd9f…`）；linter/类型检查器项目未配置，未新增工具（记为限制，不判 Blocked） |

## Closure

| Finding | Result | Evidence |
|---------|--------|----------|
| CR-001 | resolved | 原反例复跑：`E01 A→B BOTH` + `E02 B→A FWD` → `MapBuildError("edges E01 and E02 share ordered node pair ('B', 'A')")`；两条 `BOTH` 同样被拒（两个有序对各一条）。反证：两条方向相反的 `FWD` 仍构建成功且索引完整；内置两张地图可构建；新用例 `test_both_edge_and_reverse_one_way_edge_competing_for_a_pair_are_rejected`、`test_two_both_edges_between_the_same_nodes_are_rejected` 通过。校验与 `pair_index` 现共用 `_effective_pairs` |
| CR-002 | resolved | 原反例复跑：`A(3,4)/B(3,4)` + `E07` → `MapBuildError('edge E07 has zero length: nodes A and B share coordinates')`，`ZeroDivisionError` 路径不再可达；新用例 `test_edge_between_coincident_nodes_fails_the_build_instead_of_dividing_by_zero` 通过 |
| CR-003 | resolved | `grep -rn "end_x\|end_y\|TURN_ALIGN_ALIGNMENT_RATIO_LIMIT" src tests --include=*.py` → 零命中（此前仅剩定义）；126 项用例通过，说明无隐藏消费者 |
| CR-004 | resolved | 距离改为 0.45 后，探针在 dt=0.02（触发位 4.7281）与 dt=0.05（触发位 4.7023）两种位置下都在迟注册的下一 tick 由 `SAFETY_DISTANCE` 改写为 `OVERLAP` 且 v 归零；用例随 126 项全量通过 |
| CR-005 | resolved | `tests` 内 `__module__` 断言零命中；成员存在性改为集合包含判定，正向行不再恒真；可失败的负向证据（成员边缺失 → `MapBuildError`）保留并通过。残留说明见 Scope notes 7 |
| CR-006 | resolved | 原反例复跑：把 `robot_id="R2"` 的 `ASSIGN_PATH` 投给 R1 → `CommandResult(accepted=False, rejection=TARGET_MISMATCH, violations=('command targets R2 but this robot is R1',))` 且 R1 路径与状态不变；`E_STOP` 中带 `node_path` 的 `RESUME` → `MALFORMED_PAYLOAD`，随后 clean `RESUME` 仍可受理并维持 `SAFETY_DISTANCE`。新增两个用例；内置直通源与全部既有契约用例未受影响（其载荷始终匹配自身 `robot_id`） |
| CR-007 | resolved | 用户决定批准"恢复判定按该车 `v_max_mps` 取名义前瞻"，已写回 `design.md` 的 Key Mechanisms 与状态机 RESUME 行（AC 文本未改，design.md 由 `c5ad49a0…` 变为 `bbcfb4db…`）；代码维持第 0 轮实现，行为与该条文一致（本轮复跑验证） |
| CR-008 | resolved | AGENTS.md:29-33 改为事实描述；AST 导入门复跑显示叶子模块无包内运行时导入、`robot` 运行时不导入 `safety`、`safety`/`snapshots` 运行时导入 `robot` 枚举，逐条比对无冲突且无导入环 |

## Recommended Next Step

- **Suggested action**: 交付继续。8 条 findings 全部闭合，Overall Result 为 Pass、Merge readiness 为 Go；无待处置项。
- **Findings / decisions**: 无 open/reopened。两项已生效的决定：CR-006 加宽了接收契约（两个新拒绝成员，design.md 状态机随之多一行），CR-007 的恢复 Guard 已升格为设计条文。
- **Expected scope / validation**: 本轮不再需要改动。若后续 `WI-mutex-scheduling` 追加指令类型或恢复语义，按 AGENTS.md 与 design.md 的 Versioning 条款处理，验证口径仍是 `pytest tests -q` + `compileall` + 内容哈希复算。
- **After remediation**: 若下一轮只修新发现的小问题且公共契约不变，走 Closure Review（round 2）；一旦地图数据模型、状态枚举或指令载荷形状发生变化，按 validation/findings 规则回到 Full Review。
- **交回其他流程的两件事**：(1) `tasks.md` Overview 仍写"16 行转移"，design.md 状态机现为 17 行，需由 spec-exec / spec-plan 同步计数；(2) `exec-evidence.md` 第 4 条解释性决定已由 CR-007 升格为设计条文，建议由 spec-exec 在下次更新时把该条改为指向设计正文，避免同一事实两处维护。
