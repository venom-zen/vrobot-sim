# Code Review

## Review Manifest

- **Review kind**: spec-backed
- **Mode**: Closure Review
- **Mode reason**: 用户对 CR-001…CR-004 全部选择 fix；修复只涉及这四条及其影响面，spec、基线、范围、公共契约与架构边界未变，因此执行 Closure Review。
- **Closure round**: 1
- **Report language**: 中文（用户请求语言，spec 与仓库文档均为中文）
- **Target / scope**: 整个 `specs/live-visualization` 交付：`src/vrobot_web/`（Python 服务端 + 静态前端）、`tests/vrobot_web/`、`pyproject.toml` 的 `web` extra 与 package-data、`AGENTS.md` 中与 Web 层相关的约定，以及 Round 1 的修复（`design.md` 依赖约束、多途经点表格、节拍单一来源、慢客户端测试）。范围覆盖 design.md 的全部 AC 与关键设计契约，不限于 diff。
- **Base / comparison**: `HEAD` = `08fc24bc837e012745b33b5476c7abe101aa081f`（分支 `feat/live-visualization`）；交付全部为未提交改动（工作区 vs HEAD）。
- **Spec source**: `specs/live-visualization/design.md`
- **Standards sources**: `AGENTS.md`（根目录，全部改动路径适用）、`CLAUDE.md`（用户级通用规范）、`pyproject.toml`（打包、依赖与 pytest 配置）；仓库未配置 formatter / linter / 类型检查工具。
- **Languages / rules**: Python 3.13（服务端与测试）、JavaScript / HTML / CSS（无构建步骤的静态前端）。加载 `common.md`、`spec.md`、`validation.md`、`findings.md`；仓库无 Java/Go 改动，未加载对应规则。
- **Input revisions**:
  - `specs/live-visualization/design.md` `sha256:78784be25249bf6c03805a2dffb72b7f35323e39d710bde28d46ee166d8a4865`
  - `specs/live-visualization/tasks.md` `sha256:f4f4f0a24986785848d0af1e7eef1c516272db9d3077d14435ff014504708def`
  - `specs/live-visualization/exec-evidence.md` `sha256:36f46a0bb98482cf19bbdf76e882fede7433fe977436fdec5df9774348d5c1fa`
  - `specs/live-visualization/review.md`（设计评审） `sha256:61021feecbdab34d0d70ab00ae8fbd23c077a1659f635b18e3f27a353106e18f`
  - `AGENTS.md` `sha256:409dfa872e2b6184fee80c10833bb642e11a408c51b92d71ee02f151d5c00a90`
  - `pyproject.toml` `sha256:b214d5eac2da62358ff95d0b176289200b4b30453c2a6d470b36ec5b0c616704`
  - 实现文件内容由本轮 Diff fingerprint 固定（`src/vrobot_web/`、`tests/vrobot_web/` 全部按完整内容读取）。
- **Snapshot evidence**: 目标 commit = HEAD `08fc24b`；committed diff 与 staged diff 为空；unstaged diff 为 4 个文件（`AGENTS.md`、`projects/virtual-robot/backlog.md`、`projects/virtual-robot/github-sync.json`、`pyproject.toml`）；untracked 为 `docs/github-projects-sync.md`、`specs/live-visualization/{design,tasks,review}.md`、`src/vrobot_web/*`、`tests/vrobot_web/*`（完整读取）。
- **Manifest command / Diff fingerprint**: `node <code-review-skill>/scripts/review-manifest.mjs --exclude specs/live-visualization/code-review.md --exclude specs/live-visualization/exec-evidence.md` → `sha256:5283b8fa43abf1a12571bfccf737e8a860883b2caa3d1ead13d4b9262bef7131`（Round 0 为 `sha256:7644bcaa…`；写报告前重新核对）。
- **Review artifacts excluded**: `specs/live-visualization/code-review.md`、`specs/live-visualization/exec-evidence.md`
- **Discovery Package**:
  - 入口与路由：`vrobot_web.app.create_app`（`app.py:35`）、`_lifespan`（`:29`）、`GET /api/map`（`:51`）、`PUT /api/scene`（`:58`）、`POST /api/control`（`:76`）、`WS /ws/state`（`:92`）、静态目录最后挂载（`:42`）；`vrobot_web.__main__.main`（`__main__.py:14`，`--port` only，`BIND_HOST=127.0.0.1`）。
  - 场景：`scene.resolve_scene`（`scene.py:59`）→ `_check_count`（`:94`）、`_check_identity`（`:99`）、`_check_anchors`（`:113`）、`_anchor_path`（`:132`）、`_adjacency`（`:154`）、`_shortest_path`（`:162`）、`_robot_spec`（`:186`）；`SCENE_DT_S`（`:22`）。
  - 推进与广播：`SimulationDriver`（`driver.py:53`）→ `apply_scene`（`:77`）、`reset`（`:83`）、`_replace_simulation`（`:91`）、`control/_start/_pause/_resume`（`:103-137`）、`_advance`（`:146`）、`subscribe/unsubscribe/_pump/_drop/shutdown`（`:173-210`）、`_status_text/_broadcast_status/_enqueue_tick`（`:214-228`）；默认节拍 `SCENE_DT_S`（`:17` 导入、`:56` 默认值）、`SEND_TIMEOUT_S`（`:20`）。
  - 序列化：`schemas.MapPayload.from_topology`（`schemas.py:42`）、`SnapshotPayload.from_tick`（`:95`）、`StatusFrame`（`:124`）、`TickFrame`（`:130`）。
  - 前端：`static/app.js`（表格与提交 `:113-315`、状态与重连 `:316-361`、Canvas 绘制 `:486` 起）、`static/index.html`、`static/style.css`。
  - 测试：`tests/vrobot_web/{conftest,test_scene,test_driver,test_api}.py`；内核与既有测试零改动。
  - 规则出处：`AGENTS.md` 的"约定"（内核零依赖、依赖方向、构建期一次校验、不读墙钟）与"命令"；`pyproject.toml` 的 optional-dependencies / package-data / pytest 配置。
- **Reused facts**: Round 1 在修复后的新快照上重跑了全量测试、Web 套件、屏蔽导入测试与浏览器复核；`--help`、真实 WebSocket 101、wheel `--target` 安装与 Round 0 的 10 车运动/重连/重置验收对未受影响的部分仍有效，来源为本文件 Round 0 与 `exec-evidence.md`。
- **Historical findings**: Round 0 的 CR-001…CR-004（均为 minor、open）在本轮修复并逐一复核；`review.md` 的 F-001…F-006 属设计评审（已 resolved），仅作上下文，不参与 ID 与结果计算。
- **Validation environment**: `D:\Workspace\python\VirtualRobot`；`.venv` Python 3.13.9；fastapi 0.162.0、starlette 1.10.0、pydantic 2.14.1、uvicorn 0.54.0、websockets 17.3、httpx 0.28.1、pytest 9.2.0；人工验收使用本机 Chromium（Playwright MCP）。
- **Validation evidence**:
  - Round 1：`python -m pytest tests -q`：passed，`217 passed（168 内核 + 49 Web）, 1 warning in 3.53s`；唯一 warning 仍是第三方 `StarletteDeprecationWarning`（`httpx` → `httpx2`）。
  - Round 1：`python -m pytest tests/vrobot_web -q`：passed，`49 passed`（scene 14 / driver 8 / api 27）。
  - Round 1：`sys.meta_path` 屏蔽 `fastapi`/`httpx` 的 `pytest tests`：passed，`168 passed + 1 skipped`，收集期不导入 FastAPI。
  - Round 1：`git diff --stat HEAD -- src/vrobot_sim tests`：空输出；`git diff --check`：通过。
  - Round 1：浏览器多途经点复核（`--port 8124`）：每行可增删途经点；N01→`[N08, N10]`→N09 提交 `["N08","N10"]`，响应与画布高亮均为 `N01→N08→N10→N09`（起点绿环、终点橙方框）；删除到单个途经点提交 `["N08"]`，选「无」提交 `[]`。
  - Round 1：浏览器三行环配置复核（`--port 8124`）：R1/R2/R3 三行各一个途经点，应用后 `resolved_paths` 与设计一致；启动后三车 1.50 m/s 同时行驶、Z01/Z02/Z03 各显示 `持有:`，暂停/继续按钮启用状态正确。
  - 复用（Round 0）：`python -m vrobot_web --help`、`--port 8000` 冒烟（`/` 200、`/api/map` 200、带 Upgrade 的 `/ws/state` 101）、`pip wheel` + `pip install --target` 静态资源定位、10 车 1× 运动与断线重连人工验收、重置等价性复核。
- **Scope notes**:
  - `projects/virtual-robot/backlog.md`、`projects/virtual-robot/github-sync.json`、`docs/github-projects-sync.md` 是执行基线中已存在的用户改动，不属于本 spec 交付，未纳入评审；`AGENTS.md` 同时含既有 mutex 相关改动与本项的 Web 层改动，只评审后者。
  - `AC-view-*` 以人工验收为证据；仓库没有 JS 测试设施，design.md 的 Testing 章节也只要求人工验收，因此不因缺少前端自动化测试判为未满足。
  - 仓库没有 linter / 类型检查 / 格式化配置，按 common 规则不临时引入工具；格式规范以代码审读和 `git diff --check` 为准（无空白错误）。
  - `web` extra 的 `websockets` 依赖已同步到 `design.md`、`AGENTS.md` 与 `exec-evidence.md`（CR-001 resolved）。
  - `StarletteDeprecationWarning` 提示 `TestClient` 的 httpx 依赖未来会迁移，属第三方演进风险，当前不影响结论。

## Results

- **Quality Result**: Pass
- **Spec Result**: Pass
- **Overall Result**: Pass
- **Merge readiness**: Go
- **Summary**: Round 1 复核 CR-001…CR-004 全部 resolved：设计依赖约束已与 `websockets` 对齐，页面支持有序多途经点，推进节拍与场景步长共用 `SCENE_DT_S`，慢客户端测试在运行中验证 tick 不中断。25 条 AC 全部满足，217 项测试通过，多途经点与三行环配置均经浏览器复核；无未闭合 finding。

## Spec Coverage

| Requirement | Implementation | Evidence | Status | Finding / gap |
|-------------|----------------|----------|--------|---------------|
| AC-scene-apply-builds | `scene.resolve_scene`、`app.apply_scene` | `test_scene_apply_returns_paths_and_tick_zero` 断言 `mode`、三条推导路径与 tick 0 快照与内核逐字段一致 | satisfied | None |
| AC-path-anchor-order | `scene._anchor_path` / `_shortest_path` | `test_waypoints_are_visited_in_order_with_shortest_segments`、环形三车路径用例 | satisfied | None |
| AC-path-one-way-detour | `_shortest_path` 只走 `edge_by_node_pair` 并排序邻居 | `test_one_way_edge_forces_a_detour` 断言 N03→N01→N02；不可达另测 | satisfied | None |
| AC-scene-reject-duplicate-start | `scene._check_identity` | `test_invalid_scene_returns_422_without_building[shares start]`、`test_scene.py` 合并违规用例 | satisfied | None |
| AC-scene-reject-unreachable | `_anchor_path` 逐段收集违规 | `test_unreachable_route_is_rejected_with_422`、`test_every_unreachable_segment_is_listed` | satisfied | None |
| AC-scene-reject-bounds | `_check_count` / `_check_identity` | 参数化用例覆盖 0 台、11 台与重复 `robot_id`，422 且不构建 | satisfied | None |
| AC-scene-reject-degenerate-anchors | `_check_anchors` | `test_start_equal_to_target_is_rejected`、`test_repeated_anchor_in_chain_is_rejected` | satisfied | None |
| AC-control-start | `driver._start` / `_advance` | `test_control_state_machine` 断言 start 后 `tick_index` 递增；`test_driver` 同 | satisfied | None |
| AC-control-pause-resume | `_pause` / `_resume` + `_advance` 顶部等待 | `test_pause_freezes_ticks_and_resume_continues_from_the_paused_tick`、`test_control_state_machine` | satisfied | None |
| AC-control-reset | `reset` → `_replace_simulation` | `test_reset_returns_to_tick_zero_and_keeps_the_last_scene`、API reset 用例、浏览器重置等价性复核 | satisfied | None |
| AC-control-invalid | `_reject` 无副作用返回 | `test_control_state_machine` 全程 409、`test_driver` 状态矩阵、非法 action 422 | satisfied | None |
| AC-stream-initial-frame | `subscribe()` 首条入队 `StatusFrame` | `test_websocket_initial_frame_reports_unconfigured`、`test_websocket_reconnect…`、运行中首帧 | satisfied | None |
| AC-stream-tick-frames | `_enqueue_tick` 每 tick 序列化一次 | `test_stream_sends_tick_frames_and_goes_silent_while_paused` 断言 `tick_index` 有序且不重复 | satisfied | None |
| AC-stream-paused-silent | `_advance` 的模式闸门 | `test_driver` 断言 paused 状态帧之后不再出现 tick 帧；API 侧暂停期间快照不变 | satisfied | None |
| AC-stream-reconnect | 首帧 `StatusFrame` + 前端 1 s 重连 | `test_websocket_reconnect_reports_current_mode_and_latest_snapshot`、浏览器停止/重启服务端 | satisfied | None |
| AC-snapshot-fidelity | `SnapshotPayload.from_tick` 逐字段映射 | `test_tick_frames_match_kernel_snapshots_field_by_field` 独立重建内核并逐字段比对 | satisfied | None |
| AC-view-map | `app.js` `drawZones` / `drawEdges` / `drawNodes` | 人工观察：10 节点、单行箭头、5 个区标识 | satisfied | None |
| AC-view-robots | `drawRobots`（朝向线、状态色与文字、速度） | 人工观察：颜色/文字/速度随 tick 更新 | satisfied | None |
| AC-view-resolved-paths | `drawSelectedPath` + 表格/画布选中 | 人工观察：默认选中第一台、路径节点与边加亮、绿环起点/橙方框终点、切换行后高亮改变；Round 1 多途经点 N01→[N08,N10]→N09 的响应路径与画布高亮一致 | satisfied | None |
| AC-view-zone-occupancy | `drawZoneOccupancy` | 人工观察：三角环三区同时显示 `持有:` 与 `等待:` | satisfied | None |
| AC-view-empty-state | `updateControls` + `index.html` 初始 `disabled` | 人工观察：未配置时四按钮禁用且地图可见；代码核对 | satisfied | None |
| AC-view-config-errors | `showErrors(violationsOf(...))` | 人工观察：起终点相同时一次列出两条违规且状态不变；接口测试逐类 422 | satisfied | None |
| AC-view-connection | `updateConnection` + `RECONNECT_DELAY_MS` | 人工观察：停止服务端显示「已断开，正在重连」，重启后 1 秒内对齐 | satisfied | None |
| AC-view-live-motion | 50 tick/s 推进 + `requestAnimationFrame` 重绘 | 人工观察：10 车连续 1× 运动、巡航 1.50 m/s、无明显卡顿 | satisfied | None |
| AC-kernel-untouched | 未修改 `src/vrobot_sim/` 与既有 `tests/` | `git diff --stat HEAD -- src/vrobot_sim tests` 为空；217 项全量测试通过 | satisfied | None |
| IF-HTTP-map-read | `app.read_map` + `MapPayload.from_topology` | `test_map_read_returns_the_demo_topology`（10/11/5、E02 fwd、E03 both）、`test_map_load_failure_returns_500` | satisfied | None |
| IF-HTTP-scene-apply | `app.apply_scene`（先 `resolve_scene` 后替换） | 响应形状、逐类 422、失败不改变运行状态与仿真（运行中应用非法配置仍继续推进） | satisfied | None |
| IF-HTTP-control | `app.control` | 200/409/422 全部迁移；409 返回当前 `mode` 且状态不变 | satisfied | None |
| IF-MSG-state-stream | `app.state_stream` + `driver.subscribe/_pump` | 首帧/逐 tick/暂停静默/重连；真实服务端握手 101；慢连接超时移除，Round 1 在推进中验证 tick 不中断 | satisfied | None |
| Data Model（MapPayload / SnapshotPayload / StatusFrame / TickFrame） | `schemas.py` | 帧 `kind`/`mode` 断言、字段名与内核一一对应、`unconfigured` 时 `snapshot` 为 null | satisfied | None |
| Architecture / DR-web-layer-outside-kernel | 独立包、单向依赖、静态最后挂载、入口只 `--port`、package-data；Round 1 同步依赖约束 | 代码审读；wheel `--target` 安装后定位 `static/*`；`--help` 无地址选项；`design.md` 的 `web` extra 已含 `websockets` | satisfied | None |
| DR-driver-asyncio-realtime | 单 `Simulation`、deadline 推进、单连接 1 s 发送超时、节拍默认取 `SCENE_DT_S` | 代码审读；`test_default_cadence_matches_the_scenario_step`、`test_slow_subscriber_does_not_stall_ticks_while_its_send_is_pending` | satisfied | None |

## Findings

### CR-001: `web` extra 的实际依赖超出设计约束

- **Basis**: spec
- **Severity**: minor
- **Status**: resolved
- **Origin**: full-review
- **Rule / requirement sources**: `design.md` / DR-web-layer-outside-kernel Constraints（Round 0 原文为 `web = ["fastapi", "uvicorn"]`）
- **Location**: `pyproject.toml:14`；约束位置 `specs/live-visualization/design.md:118`
- **Issue**: 交付的 `web` extra 为 `["fastapi", "uvicorn", "websockets"]`。uvicorn 基础安装不含 WebSocket 协议实现，缺少 `websockets` 时真实服务端 `/ws/state` 握手返回 404；`TestClient` 走进程内 ASGI，测试无法暴露该缺口。
- **Evidence**: 执行期间以真实 uvicorn 启动后，带 Upgrade 头的 `/ws/state` 返回 404；加入 `websockets` 后返回 101。偏差已写入 `exec-evidence.md` 的 Deviation 与 `AGENTS.md` 的约定，但 design.md 的约束文本未更新。
- **Impact**: 功能正确（IF-MSG-state-stream 与 `AC-stream-*` 在真实服务端成立），但设计约束与实际依赖清单不一致；按设计文档安装的环境会缺少 WebSocket 实现。
- **Recommendation**: 由设计负责人把 DR-web-layer-outside-kernel 的 Constraints 更新为包含 `websockets`（与 `AGENTS.md` 现有表述一致）；代码无需改动。
- **Closure test**: `pyproject.toml` 的 `web` extra 与 design.md 的 Constraints 文本一致，且真实 `python -m vrobot_web` 的 `/ws/state` 握手仍返回 101。
- **Related findings**: None

### CR-002: 页面只能配置一个途经节点，无法表达多途经点锚点链

- **Basis**: spec
- **Severity**: minor
- **Status**: resolved
- **Origin**: full-review
- **Rule / requirement sources**: `design.md` / Goals（"可选按序途经节点"）、Data Model（`waypoints` 有序列表）；Components 与 tasks.md 8.1 只描述单个「途经」下拉
- **Location**: `src/vrobot_web/static/app.js:118`（行模型 `waypoint: ""`）、`src/vrobot_web/static/app.js:209-213`（`waypoints: [row.waypoint]`）、`src/vrobot_web/static/index.html:33`
- **Issue**: 表格每行只有一个「途经」下拉，提交时最多构造单元素 `waypoints`；服务端 `SceneConfig`、BFS 分段与 `resolved_paths` 支持任意长度有序列表。
- **Evidence**: 代码审读；环形死锁配置（每车恰好一个途经点）在页面上可完成，双途经点配置只能通过 `PUT /api/scene` 构造。
- **Impact**: 工程师无法仅用页面为单车配置两段以上的途经锚点（例如连续串行经过两个节点）；核心死锁场景不受影响。设计 Components 与 tasks 的 UI 描述与实现一致，Goals 的复数表述只在 API 层成立。
- **Recommendation**: 二选一并由用户决定：为每行增加可增删/排序的途经点选择，或在 design.md 中把页面明确记为单途经点、多途经点仅属 API 能力。
- **Closure test**: 页面可为一台车配置 ≥2 个按序途经节点并提交；`PUT /api/scene` 收到有序列表，画布高亮对应完整路径。或 design.md 的 Goals/Components 明确写出页面只支持单个途经节点。
- **Related findings**: None

### CR-003: 1× 播放倍速由两个独立常量决定，无一致性约束

- **Basis**: quality
- **Severity**: minor
- **Status**: resolved
- **Origin**: full-review
- **Rule / requirement sources**: `design.md` / DR-driver-asyncio-realtime（dt=0.02 s、50 tick/s）、AC-view-live-motion（1× 实时）
- **Location**: `src/vrobot_web/driver.py:19`（`TICK_DT_S = 0.02`）、`src/vrobot_web/scene.py:22`（`SCENE_DT_S = 0.02`）
- **Issue**: 内核积分步长（`Scenario.dt_s`）与推进任务的墙钟节拍分别定义在两个模块，取值相同但互不引用，也没有测试或启动期断言保证一致。
- **Evidence**: `test_driver` 用 `dt_s=0.005` 注入更快的节拍，说明两者是可独立变化的旋钮；任一常量被改动时，页面会以 2× 或 0.5× 播放，而现有测试仍全部通过。
- **Impact**: 违反 1× 实时时没有任何失败信号，属于静默回归；当前取值一致，行为正确。
- **Recommendation**: 让推进节拍从场景步长派生单一来源（例如 `SimulationDriver` 默认取 `scene.SCENE_DT_S`，或应用场景时以 `scenario.dt_s` 设定节拍），保留构造参数供测试覆盖。
- **Closure test**: 修改单一来源即可同时改变内核步长与推进节拍；另有一个测试或启动检查断言两者的 1× 关系。
- **Related findings**: None

### CR-004: 慢客户端测试从未在推进中挂接慢连接，无法证明不拖慢 tick 循环

- **Basis**: quality
- **Severity**: minor
- **Status**: resolved
- **Origin**: full-review
- **Rule / requirement sources**: `design.md` / Key Mechanisms「实时推进与广播」、Error Handling、Testing（1 秒超时移除慢连接）；common.md 测试有效性
- **Location**: `tests/vrobot_web/test_driver.py:165-185`
- **Issue**: 慢订阅者在 `configured` 状态下挂接，测试实际超时的是首条 `StatusFrame`；慢连接被移除后仿真才 `start`，因此「慢客户端的发送阻塞不拖慢 `step()` 推进」这一核心机制没有在运行中被观察到。
- **Evidence**: 断言序列为 `subscribe(slow)` → 等待 `_subscribers` 清空 → `subscribe(fast)` → `start` → 计数 tick 帧；慢连接存在期间推进任务没有运行。若广播退化为在推进循环内同步发送，该用例仍会结束（慢连接已被移除）而无法暴露暂停推进的缺陷。
- **Impact**: 当前实现正确（发送在每连接独立任务中），但回归缺口未被测试封住；F-006 设计评审标注的「长时间慢客户端下的实测节奏」也缺少直接证据。
- **Recommendation**: 增加用例：先 `start` 并确认 tick 递增，再挂接慢订阅者，断言在慢发送等待期间 `latest_snapshot.tick_index` 持续增长、慢连接超时后被移除、快连接仍收到 tick。
- **Closure test**: 上述用例在慢发送未完成时观察 tick 持续递增；把广播改为同步发送后该用例失败或超时。
- **Related findings**: None

## Check Summary

| Check | Scope / sources | Evidence / findings |
|-------|-----------------|---------------------|
| Project and language conventions | `AGENTS.md` 约定（内核零依赖、依赖方向、构建期一次校验、不读墙钟、快照不可变）、`pyproject.toml`、Python 3.13 代码风格 | 内核目录零改动、`vrobot_web` 单向依赖、违规一次收集、仅驱动层读取墙钟；无 linter 配置，靠审读与 `git diff --check`（通过）；`node --check static/app.js` 通过；未发现风格类 finding |
| Correctness and regression | 状态机迁移、暂停/继续/重置、帧顺序与订阅生命周期、BFS 推导、错误结构与前端状态同步、Round 1 修复面 | 状态机与广播顺序经代码审读与测试确认；多途经点与三行环配置经浏览器复核；慢客户端在推进中被移除且 tick 不中断；CR-001…CR-004 全部 resolved |
| Validation | 全量测试、Web 套件、内核零改动、真实服务端冒烟、打包安装、浏览器验收 | Round 1：217 passed（1 条第三方 warning）、Web 49 passed、屏蔽导入 168+1 skipped；`git diff --stat HEAD -- src/vrobot_sim tests` 为空；真实 WS 101 与打包结果复用 Round 0 |

## Closure

| Finding | Result | Evidence |
|---------|--------|----------|
| CR-001 | resolved | 原反例「按设计文档安装会缺少 WebSocket 实现」：`design.md` 的 DR-web-layer-outside-kernel Constraints 现为 `["fastapi", "uvicorn", "websockets"]` 并注明 uvicorn 基础安装不含协议实现；`pyproject.toml` 与之一致；真实 `/ws/state` 握手仍为 101（复用 Round 0 冒烟）。代码未改。 |
| CR-002 | resolved | 原反例「页面无法表达两个途经点」：每行可增删途经点，N01→`[N08, N10]`→N09 提交 `waypoints: ["N08","N10"]`，`resolved_paths` 与画布高亮均为 `N01→N08→N10→N09`；删除到单个途经点提交 `["N08"]`，选「无」提交 `[]`；三行环配置仍正确。 |
| CR-003 | resolved | 原反例「两个 0.02 常量可独立漂移」：`driver.py` 默认 `dt_s = SCENE_DT_S`（`TICK_DT_S` 已删除），内核步长与推进节拍同源；`test_default_cadence_matches_the_scenario_step` 断言两者相等。 |
| CR-004 | resolved | 原反例「慢客户端测试从未在推进中挂接」：新增 `test_slow_subscriber_does_not_stall_ticks_while_its_send_is_pending`——慢发送未完成时快连接仍收到 ≥3 个 tick（此时慢连接仍在订阅集合中），随后慢连接超时被移除、快连接保留。 |

## Recommended Next Step

- **Suggested action**: 交付可合并（Overall Result `Pass`、Merge readiness `Go`）；无未闭合 finding，按当前快照交付或提交。
- **Findings / decisions**: CR-001…CR-004 全部 resolved，无待决事项。
- **Expected scope / validation**: 本轮改动限于 `design.md` 的依赖约束、`static/app.js`/`static/style.css` 的多途经点表格、`driver.py` 的节拍来源，以及 `tests/vrobot_web/{test_driver,test_scene}.py` 的三个新用例；验证为 217 passed、Web 49 passed、屏蔽导入 168+1 skipped、`node --check static/app.js` 通过、浏览器多途经点与三行环配置复核。
- **After remediation**: 当前快照（`sha256:5283b8fa…`）即 Closure Review round 1 的冻结版本；后续改动按新的 findings 流程处理。
