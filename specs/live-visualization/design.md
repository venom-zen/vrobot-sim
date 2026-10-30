# Live Visualization Design

## Summary

调度算法工程师要在浏览器里实时观察多车互斥与死锁，而仿真内核目前只提供进程内接口：由 pytest 之类的调用方自行驱动，
没有可配置场景的入口、没有状态通道、没有画面。本项新增一个内核之外的 Web 层 `vrobot_web`：工程师在页面上配置 1-10 台虚拟 AMR 的起点、
可选途经节点与终点，服务端校验并装配 `Simulation.create_scheduled`，按 1× 实时推进；页面通过 WebSocket 接收每个
tick 的快照，用 Canvas 绘制 demo 拓扑图上的位姿、状态、临界区持有人与等待队列，并提供启动、暂停、继续与重置控制。
内核 `vrobot_sim` 的公开契约与行为不变。

## Project Traceability

- **Project**: `projects/virtual-robot/project.md`
- **Backlog**: `projects/virtual-robot/backlog.md`
- **Work item**: `WI-live-visualization`

## Goals

- 工程师能在浏览器里配置 1-10 台机器人，每台给出起点、可选按序途经节点与终点；应用配置后立即看到推导出的节点路径与
  tick 0 画面。
- 配置非法时（重复起点、锚点重复、相邻锚点无可行路线、数量越界），页面一次列出全部违规项，且不构建仿真。
- 启动后仿真按 1× 实时推进，页面连续显示每台机器人的位置、朝向、状态与瞬时速度，以及每个临界区的持有人与等待队列。
- 暂停后画面冻结在当前状态，继续从暂停处推进，重置回到 tick 0 并保留当前配置。
- 页面断线重连后自动恢复当前运行状态与最新快照。
- 内核 `vrobot_sim` 的公开契约与行为不变，既有内核测试套件不改动通过。

## Primary Users / Roles

- 调度算法工程师：配置场景、启停观察、手动构造环形死锁；当前由作者本机使用，长期面向同团队工程师。
- `WI-scale-50-robots`（后续消费者）：本项建立的状态通道与渲染骨架是该规模性能工作的起点。

## Non-Goals

- 地图编辑（`WI-map-editor`）。本项固定使用 `demo` 地图；`minimal` 没有临界区，不承载互斥可视化语义。
- 事件日志导出、历史回放与脚本化无头运行（`WI-scripted-scenarios`）。
- 倍速控制与单步推进；本项只做 1× 实时与启动/暂停/继续/重置。
- 障碍物编辑；页面不提供障碍物配置，场景初始障碍物为空。
- 等待时长展示；`TickSnapshot` 只暴露等待队列顺序，不暴露 `arrival_tick`，用户已确认只展示核心字段。
- 多用户协作、权限与账号体系；服务只监听 127.0.0.1。
- 无障碍适配、国际化与移动端布局；文案用中文，按桌面浏览器设计，窄窗口只折叠为上下布局。
- 配置编辑的撤销栈与版本历史；未应用的编辑不影响正在运行的仿真。
- 50 台规模的渲染与推进性能优化（`WI-scale-50-robots`）。
- 死锁自动解除或任何调度策略变更；调度行为仍由 `WI-mutex-scheduling` 定义。
- 内核快照字段、状态枚举或创建入口的任何修改。

## Context

内核按调用方驱动的固定步长工作。`Simulation.create_scheduled` 装配内置 FCFS 调度器，`Simulation.step()` 返回
`TickSnapshot`；内核不读墙钟、不提供 CLI 与网络服务，节奏与暂停由调用方表达（`AGENTS.md`）。Web 层因此必须是内核
之外的调用方组件。

已核实的事实：

- `TickSnapshot` 字段：`tick_index`、`sim_time_s`、`robots`（`robot_id`、`x_m`、`y_m`、`theta_rad`、`v_mps`、
  `omega_radps`、`status`、`estop_reason`）与 `zones`（`zone_id`、`capacity`、`holder_robot_ids`、
  `waiting_robot_ids`），见 `src/vrobot_sim/snapshots.py`。
- 快照中机器人与区分别按 `robot_id`、`zone_id` 升序，同一 tick 是一个一致切面（`specs/mutex-scheduling/design.md`
  的 Data Model）。
- demo 地图含 10 个节点、11 条边与 5 个区，10 个节点两两中心距大于 0.70 m，可承载 10 台车同时起步
  （`src/vrobot_sim/maps/demo.py`）。
- 内核没有路径规划；`TopologyMap.edge_by_node_pair` 只索引可通行方向，E02 是 N02→N03 单行道，E03 是双向边
  （`src/vrobot_sim/map_model.py`、`maps/demo.py`）。
- 两台车共用起点时，起步 tick 会因车体圆相交进入 `OVERLAP` 急停，创建期不拦截（`specs/mutex-scheduling/design.md`
  的 Error Handling）。
- 机器人对非法路径指令只返回拒绝结果，路径不生效、机器人留在 `IDLE`，没有回传通道；Web 层必须前置校验并自行报告
  违规（`src/vrobot_sim/robot.py` 的 `_intake_assign_path`）。
- 10 台车单步耗时平均值 0.0527-0.0567 ms、P95 不超过 0.077 ms，约为 dt=0.02 s 单步预算的 0.3%
  （`specs/sim-kinematics/benchmark-notes.md`）。
- 项目此前约定运行时零第三方依赖；2026-10-29 用户决定去掉该约束，Web 层可引入 FastAPI 与 uvicorn，内核保持零依赖。
- 仓库没有任何 Web 层、静态前端或 CLI 入口；10 车场景与三角环死锁场景目前只存在于测试 fixture 中。

## Discovery

### Key Discoveries

- 现有快照已经覆盖页面所需的全部展示字段，可视化不需要任何内核改动。
- 用户要的是可调场景：机器人数与每车路径配置成为本项的范围核心，固定场景方案不再采用。
- 只有起点终点不足以构造环形死锁：BFS 最短路会为 N01→N03 选直达边 E03；途经节点提供了构造死锁所需的路由控制。
- 重复起点不会在创建期报错，只会在首个 tick 变成 `OVERLAP` 急停，因此起点唯一性是 Web 层的必检项。
- 内核推进成本远低于实时预算，asyncio 单循环推进不会成为瓶颈，也无需线程。

### Scope Decisions

- **纳入 UI 场景配置**：用户选择"界面可调机器人数与起终点"，并把路径模型定为"起终点 + 可选途经节点"。backlog 的
  Open Question"是否需要在界面上调整机器人数量与目标点"确认答案为是。
- **纳入途经节点**：环形死锁的最小构造需要三台车各走两段环边，仅最短路无法表达。
- **排除倍速与单步**：用户确认只保留 backlog Scope 明示的启动/暂停/继续/重置。
- **排除等待时长**：用户确认展示核心字段，不扩展快照契约。
- **固定 demo 地图**：`minimal` 无临界区，无法展示本项的核心验证对象。
- **去除运行时零第三方依赖约束**：用户明确该约束不应阻碍用第三方实现更快更好的功能；内核仍保持零依赖，Web 依赖
  放入 optional extra，`AGENTS.md` 的约定随实现同步改写。

## Decision Record

### DR-web-stack-fastapi

**Decision**: Web 层使用 FastAPI + uvicorn；场景配置用 pydantic 模型校验；状态流用 WebSocket 推送，控制操作用 REST。

**Rationale**: pydantic 提供声明式配置校验与结构化错误，Starlette 原生支持 WebSocket 与静态文件，本地工具还能直接
使用 `/docs` 调试接口。被拒方向：标准库 `http.server` 加手写 SSE（协议与校验框架都要自建）；aiohttp（HTTP 与
WebSocket 一手包，但校验与接口文档要手写，开发体验与错误信息更差）。

**Constraints**: uvicorn 单进程单 worker，只绑定 127.0.0.1；WebSocket 只承载服务器到浏览器的状态流，浏览器到服务器
的控制走 REST。

**Rejected concern**: 为坚持运行时零第三方依赖而放弃 Web 框架、手写 HTTP 流与校验；用户明确该约束不应阻碍用第三方
实现更快更好的功能。

**Revisit when**: 部署环境禁止第三方包，或 Web 依赖的维护成本超过功能收益时。

### DR-web-layer-outside-kernel

**Decision**: 新增独立包 `src/vrobot_web/`，单向依赖 `vrobot_sim`；内核不导入 Web 层，内核包不增加任何依赖。

**Rationale**: `AGENTS.md` 约定内核不提供 CLI 与网络服务；Web 层是调用方。被拒方向：把服务端放进 `vrobot_sim`
（内核承担 Web 职责与依赖，只装内核的消费者也要安装 Web 栈）。

**Constraints**: 依赖声明为
`[project.optional-dependencies] web = ["fastapi", "uvicorn", "websockets"]`（uvicorn 的基础安装不含
WebSocket 协议实现，`/ws/state` 握手需要 `websockets`）；只装内核的场景不受影响。

### DR-scene-anchor-paths

**Decision**: 场景在 UI 上配置；每台机器人由起点、可选按序途经节点与终点组成。Web 层把相邻锚点之间用 BFS 最短路
拼接成节点路径，BFS 只走 `edge_by_node_pair` 中可通行的方向。

**Rationale**: 用户需要可调机器人数与起终点；只取最短路时环形死锁无法构造（N01→N03 会直连 E03），途经节点以可控的
UI 成本补足表达能力。被拒方向：仅起终点加 BFS（死锁不可构造）；完整节点路径逐节点编辑（每次实验点击成本过高）。

**Constraints**: 锚点链两两相邻元素必须不同且都在地图中；相邻锚点之间必须有可行路线；单行边按方向选路，必要时绕行。

### DR-fixed-demo-map

**Decision**: 本项固定使用 `demo` 地图，不提供地图选择。

**Rationale**: 只有 demo 有临界区，互斥与死锁都发生在它上面；`minimal` 用于数值自检。被拒方向：地图下拉（增加场景
语义面与 UI 状态，MVP 无功能收益）。

**Revisit when**: `WI-map-editor` 交付或引入外部地图时。

### DR-driver-asyncio-realtime

**Decision**: 用 asyncio 后台任务按墙钟节奏推进 `Simulation.step()`，目标 50 tick/s（dt=0.02 s）；暂停阻塞推进循环，
重置用最近一次有效配置重建 `Simulation`。

**Rationale**: 内核没有时钟，节奏由调用方表达；单步约 0.05 ms，事件循环占用低于 1%，不需要线程或独立进程。被拒方向：
线程驱动（仍需与事件循环同步共享状态，收益为零）。

**Constraints**: 每个 tick 序列化一次快照并广播；服务只维护一个 `Simulation` 实例；重置丢弃当前进度，这是预期语义。

### DR-no-kernel-contract-change

**Decision**: 不修改 `vrobot_sim` 的任何公开对象：`TickSnapshot`、`ZoneSnapshot`、`RobotStatus`、`EStopReason`、
`Simulation.create_scheduled` 与 `step()` 保持交付时的字段与语义。

**Rationale**: 页面所需字段已全部在快照中；扩展契约会把可视化需求反向耦合进三个 Now 项共享的内核契约。被拒方向：
在快照中增加等待时长或渲染专用字段。

**Constraints**: 等待时长、速度向量分解等页面装饰信息只能由前端从现有字段推导；不可推导的字段不展示。

## Proposed Solution

### Architecture

新增顶层包 `src/vrobot_web/`，按职责拆分：

- `app.py`：FastAPI 应用工厂，注册 HTTP 与 WebSocket 路由，挂载静态目录，生命周期内启动与停止推进任务。
- `scene.py`：pydantic `SceneConfig`，锚点校验、BFS 路径推导、`Scenario` 与 `RobotSpec` 构建。
- `driver.py`：`SimulationDriver`，持有当前 `Simulation`、运行状态、推进任务与 WebSocket 订阅者集合。
- `schemas.py`：`MapPayload`、`SnapshotPayload`、`StatusFrame`、`TickFrame` 等序列化模型。
- `__main__.py`：`python -m vrobot_web` 入口，参数 `--port`（默认 8000）；绑定地址固定为 127.0.0.1。
- `static/`：`index.html`、`app.js`、`style.css`，无构建步骤、无 CDN 资源。

静态资源随包分发：`pyproject.toml` 声明 `[tool.setuptools.package-data]`，把 `vrobot_web` 的 `static/*` 打进安装包，
安装后的 `python -m vrobot_web` 能定位静态文件。

依赖方向：`vrobot_web` 导入 `vrobot_sim`；内核不导入 Web 层。页面与服务器同仓发布，不需要独立版本协商。路由注册
顺序为 API、WebSocket、静态目录，静态目录挂在 `/`，避免吞掉 API 路径。

### Components

- **场景服务**：接收 `SceneConfig`，完成全部前置校验（数量、标识唯一、起点唯一、锚点链、可达性），按锚点分段 BFS 得到
  每台车的节点路径，取首段航向作为 `start_theta_rad`，构造 `Scenario` 与 `Simulation.create_scheduled`。任何违规都
  收集后一次返回，不产生半成品仿真；请求体解析失败时把 pydantic 错误转成 `violations` 文本；内核抛出的
  `ScenarioValidationError` 作为最后防线转为同样的错误结构。
- **推进器**：维护 `unconfigured`、`configured`、`running`、`paused` 四种状态。应用配置成功即重建 `Simulation`，
  调用一次 `step()` 取得 `tick_index=0` 的快照并进入 `configured`；启动创建推进任务，此后快照从 `tick_index=1`
  开始递增；暂停让任务在循环顶部等待；继续唤醒；重置重建并广播新的 tick 0 快照。每个 tick 把快照序列化一次，
  向所有订阅的 WebSocket 发送，单连接发送超过 1 秒即关闭并移除该连接，推进任务继续运行。
- **HTTP 与 WebSocket 接口**：地图读取、场景应用、控制操作与状态流四个接口，定义见 Interfaces。
- **前端页面**：左侧为场景编辑表格（添加/删除机器人、下拉选择起点/途经/终点、应用配置）、状态行（连接、模式、地图
  标识与实时读数）、控制按钮与动效开关、图例与错误面板；右侧为 Canvas 画布。画布按世界坐标等比缩放，绘制 1 m 细
  网格与 5 m 主网格；每条边按 `lane_width_m` 铺出车道带，单行边沿车道画方向箭头；区的成员边铺半透明色带并加虚线
  边界，区与车道交接处画闸栏；节点画成停靠位方块。机器人画成俯视 AMR（车体、轮组、状态色顶灯与状态环），旁边
  标注状态与瞬时速度；运行时按状态色绘制渐隐轨迹，等待路权与急停状态叠加脉冲。选中机器人的推导路径用亮色虚线
  高亮，起点与终点用不同标记区分；节点、区与机器人标签互相避让，左下角绘制比例尺。动效开关控制轨迹与脉冲，
  偏好存入 `localStorage`，首次访问默认跟随 `prefers-reduced-motion`。页面用 `requestAnimationFrame` 绘制最新
  快照，窗口尺寸变化时重算缩放，窄窗口下侧栏与画布改为上下布局。

### Data Model

#### Change Summary

| Change | Layer | Object | Purpose | Source |
|--------|-------|--------|---------|--------|
| ADD | Domain | SceneConfig | 浏览器提交的场景配置 | `vrobot_web.scene` |
| ADD | Serialized | MapPayload | 地图渲染数据 | `vrobot_web.schemas` |
| ADD | Serialized | SnapshotPayload | 单 tick 快照 JSON | `vrobot_web.schemas` |
| ADD | Serialized | StatusFrame | 运行状态消息 | `vrobot_web.schemas` |
| ADD | Serialized | TickFrame | 每 tick 状态消息 | `vrobot_web.schemas` |

内核数据对象不修改，本表只列新增的 Web 层模型。

#### Domain / Serialized Models

##### [ADD] SceneConfig

- `robots: list[RobotConfig]`，长度 1-10。
- `RobotConfig` 字段：`robot_id`（字符串，配置内唯一）、`start_node_id`、`waypoints`（有序字符串列表，可为空）、
  `target_node_id`。
- 地图固定为 `demo`，不出现在配置中；配置以机器人锚点为准，推导出的节点路径只出现在应用配置的响应里。

##### [ADD] MapPayload

- `map_id`、`nodes`（`node_id`、`x_m`、`y_m`）、`edges`（`edge_id`、`from_node_id`、`to_node_id`、`direction`、`lane_width_m`）、
  `zones`（`zone_id`、`name`、`capacity`、`edge_ids`）。
- 全部字段来自 `TopologyMap`，不引入第二个数据来源；`direction` 取值 `fwd` 或 `both`。

##### [ADD] SnapshotPayload

- `tick_index`、`sim_time_s`、`robots`、`zones`。
- `robots` 元素：`robot_id`、`x_m`、`y_m`、`theta_rad`、`v_mps`、`omega_radps`、`status`、`estop_reason`；
  `status` 与 `estop_reason` 分别取 `RobotStatus` 与 `EStopReason` 的枚举值。
- `zones` 元素：`zone_id`、`capacity`、`holder_robot_ids`、`waiting_robot_ids`。
- 字段名与 `TickSnapshot` 一一对应，值直接来自快照对象；顺序沿用内核排序（机器人按 `robot_id`，区按 `zone_id`）。

##### [ADD] StatusFrame

- 字段 `kind` 固定为 `"status"`，`mode` 取 `unconfigured`、`configured`、`running`、`paused`，`snapshot` 为
  `SnapshotPayload` 或 `null`（仅 `unconfigured`）。
- 在 WebSocket 连接建立与每次运行状态切换时发送，用于对齐页面状态。

##### [ADD] TickFrame

- 字段 `kind` 固定为 `"tick"`，`mode` 固定为 `"running"`，`snapshot` 为 `SnapshotPayload`。
- 仅在 `running` 时每个 tick 发送一次，顺序与 `tick_index` 递增一致。

#### Constraints and Indexes

- `robot_id` 在配置内唯一；机器人数量在 1-10 之间。
- 各机器人起点两两不同；demo 有 10 个可起始节点，起点唯一性同时约束了上限 10。
- 锚点链（起点、途经节点、终点）相邻元素不同且全部是 demo 节点；相邻锚点之间必须存在可行路线。
- 推导路径满足内核 `_validate_path` 的相邻性约束：每个相邻节点对位于 `edge_by_node_pair` 中。

#### Concurrency and Consistency

- 推进、状态切换与快照序列化都在同一个事件循环内顺序执行，没有锁；广播发生在 `step()` 之后，一个 tick 只序列化一次。
- WebSocket 发送失败或超时只移除对应订阅者；推进任务与 `Simulation` 状态不受影响。
- 应用新配置先校验后替换：校验失败时当前仿真与运行状态保持不变。

### Interfaces

#### Change Summary

| Change | Kind | Contract ID | Producer | Consumer | Compatibility |
|--------|------|-------------|----------|----------|---------------|
| ADD | HTTP | IF-HTTP-map-read | 浏览器 | `vrobot_web` | 新接口 |
| ADD | HTTP | IF-HTTP-scene-apply | 浏览器 | `vrobot_web` | 新接口 |
| ADD | HTTP | IF-HTTP-control | 浏览器 | `vrobot_web` | 新接口 |
| ADD | Message | IF-MSG-state-stream | `vrobot_web` | 浏览器 | 新契约，页面与服务器同仓发布 |

- **Messages**: 新增 IF-MSG-state-stream；无其他消息通道。
- **Protocols**: No changes — 内核 `IF-PROTO-sim-step-advance` 等进程内契约不修改，推进任务按既有语义调用 `step()`。

#### HTTP APIs

##### [ADD] IF-HTTP-map-read

- **Method / Path**: `GET /api/map`
- **Auth**: 无；服务只监听 127.0.0.1。
- **Content-Type**: `application/json`
- **Idempotency**: 只读，重复调用返回相同结果。

###### Request

无请求参数。

###### Response

- 200，响应体为 `MapPayload`，描述当前固定的 demo 地图。

###### Errors

| Condition | Result |
|-----------|--------|
| 地图加载失败（内置地图数据损坏） | 500，响应体为 `{"violations": [<原因>]}` |

##### [ADD] IF-HTTP-scene-apply

- **Method / Path**: `PUT /api/scene`
- **Auth**: 无。
- **Content-Type**: `application/json`
- **Idempotency**: 同一配置重复应用得到相同的 tick 0 快照与相同的推导路径；应用成功会替换当前仿真并回到
  `configured`，正在运行的仿真随之停止。

###### Request

| Field | Location | Type | Required | Meaning |
|-------|----------|------|----------|---------|
| `robots` | body | array | Yes | 1-10 个机器人配置 |
| `robots[].robot_id` | body | string | Yes | 机器人标识，配置内唯一 |
| `robots[].start_node_id` | body | string | Yes | 起点节点 |
| `robots[].waypoints` | body | string[] | No | 按序途经节点，可为空 |
| `robots[].target_node_id` | body | string | Yes | 终点节点 |

###### Response

- 200，响应体：`{"mode": "configured", "resolved_paths": {<robot_id>: [<节点>...]}, "snapshot": SnapshotPayload}`。
  `resolved_paths` 是每台车推导出的完整节点路径；`snapshot` 是应用后调用一次 `step()` 取得的 `tick_index=0` 快照。

###### Errors

| Condition | Result |
|-----------|--------|
| 机器人数量不在 1-10 | 422，`{"violations": [全部违规项]}` |
| `robot_id` 重复、起点重复、起点等于终点、锚点重复、锚点不在地图中 | 422，`{"violations": [全部违规项]}` |
| 相邻锚点之间没有可行路线 | 422，`{"violations": [全部违规项]}` |
| 请求体不是合法 JSON、字段类型错误或缺少必填字段 | 422，`{"violations": [解析错误文本]}` |
| 内核仍拒绝场景 | 422，`{"violations": [内核违规项]}` |

所有错误都不改变当前仿真与运行状态。

##### [ADD] IF-HTTP-control

- **Method / Path**: `POST /api/control`
- **Auth**: 无。
- **Content-Type**: `application/json`
- **Idempotency**: 只接受当前状态允许的动作；重复发送同一动作按状态机判定，不产生额外副作用。

###### Request

| Field | Location | Type | Required | Meaning |
|-------|----------|------|----------|---------|
| `action` | body | string | Yes | `start`、`pause`、`resume`、`reset` 之一 |

###### Response

- 200，响应体：`{"mode": <新状态>, "snapshot": SnapshotPayload}`。

###### Errors

| Condition | Result |
|-----------|--------|
| 尚未应用场景（`unconfigured`） | 409，`{"mode": "unconfigured", "violations": [...]}` |
| `start` 但状态不是 `configured`，或 `pause` 但状态不是 `running` | 409，状态不变 |
| `resume` 但状态不是 `paused`，或 `reset` 但状态是 `unconfigured` | 409，状态不变 |
| `action` 不是四个值之一，或请求体不是合法 JSON、缺少 `action` | 422，`{"violations": [...]}` |

#### Messages

##### [ADD] IF-MSG-state-stream

- **Channel / Topic**: WebSocket `/ws/state`
- **Producer / Consumer**: `vrobot_web` 推送，浏览器消费。
- **Trigger**: 连接建立时发送一条 `StatusFrame`；运行状态切换时发送 `StatusFrame`；`running` 时每个 tick 发送一条
  `TickFrame`。
- **Envelope / Payload**: 文本帧，JSON 编码；`StatusFrame` 与 `TickFrame` 定义见 Data Model。
- **Delivery**: 单连接内按发送顺序投递，不重传、不去重。单次发送超过 1 秒未完成即关闭并移除该连接。断开后由客户端
  重连，依靠连接建立时的 `StatusFrame` 重新对齐；服务端不为断开的连接保留历史帧。
- **Versioning**: 页面与服务器同仓发布，不提供跨版本兼容；字段变化随两者一起交付。

### State Machines

推进器运行状态：

| Current state | Trigger / Guard | Target state | Side effects |
|---------------|-----------------|--------------|--------------|
| `unconfigured` | 应用配置成功 | `configured` | 构建 `Simulation`，调用一次 `step()` 取得 tick 0 快照；广播 `StatusFrame` |
| `unconfigured` / `configured` / `running` / `paused` | 应用配置失败 | 不变 | 返回 422；当前仿真与任务不受影响 |
| `configured` | `start` | `running` | 启动推进任务；广播 `StatusFrame` |
| `running` | `pause` | `paused` | 推进循环停在下一个 tick 前；广播 `StatusFrame` |
| `paused` | `resume` | `running` | 唤醒推进循环，从暂停时 tick 继续；广播 `StatusFrame` |
| `configured` / `running` / `paused` | `reset` | `configured` | 按最近一次有效配置重建并取得 tick 0 快照；广播 `StatusFrame` |
| `configured` / `running` / `paused` | 应用配置成功 | `configured` | 停止推进任务，换新 `Simulation`，取得 tick 0 快照；广播 `StatusFrame` |
| 任一状态 | 状态不允许的动作 | 不变 | 返回 409；不广播 |

机器人状态（`IDLE`、`MOVING`、`E_STOP`、`ARRIVED`、`WAITING_RIGHT`、`HOLDING_ZONE`）完全由内核决定，Web 层只做展示，
不引入新的机器人状态。

### Key Mechanisms

#### BFS 路径推导

每台车按锚点链切段：起点→途经 1→…→途经 n→终点。每段在 `edge_by_node_pair` 的有向相邻关系上做 BFS，同层按节点标识
升序出队以保证结果确定；各段路径去掉与上一段重复的起点后拼接。若任一相邻锚点对没有路线，收集为违规项。

边界算例：

- 起点 N01、途经 N02、终点 N03：第一段 N01→N02，第二段 N02→N03（E02 允许该方向），路径 `[N01, N02, N03]`。
- 起点 N01、终点 N03、无途经：直达边 E03 双向可用，路径 `[N01, N03]`。
- 起点 N03、终点 N02：E02 是 N02→N03 单行，反向不可用，BFS 走 N03→N01→N02，路径 `[N03, N01, N02]`。
- 环形死锁的最小配置：R1 起点 N01、途经 N02、终点 N03；R2 起点 N02、途经 N03、终点 N01；R3 起点 N03、途经 N01、
  终点 N02。推导路径与 `tests/test_mutex_scheduling.py` 的环形场景一致。

#### 实时推进与广播

推进任务维护单调递增的 deadline，每次 `await asyncio.sleep(max(0, deadline - loop.time()))` 后调用 `step()`，把
`TickSnapshot` 序列化为一条 `TickFrame` 文本，逐个发送给订阅者。`status` 与 `estop_reason` 取枚举值发送。每次
向单个连接发送设 1 秒超时：超时即关闭并移除该连接，其余连接与推进节奏不受影响。

边界算例：dt = 0.02 s 时目标 50 tick/s；单步实测约 0.05 ms，占单步预算 0.05/20 = 0.25%，事件循环其余时间空闲。
每 tick 序列化一次、单客户端发送约 2 KB 量级 JSON（10 机器人 8 字段加 5 个区，估算值），约 100 KB/s，本地回环无压力。
客户端停止读取导致发送在 1 秒内未完成时，该连接被移除，推进任务继续按 50 tick/s 前进。

#### 暂停、继续与重置

`pause` 让推进循环在 tick 边界等待，不推进 `Simulation`，因此暂停期间不会有新的 `TickFrame`；画面保留最后一条快照。
`resume` 唤醒后继续用同一 `Simulation` 推进，`tick_index` 从暂停处递增。`reset` 取消推进任务，按最近一次有效配置重新
`create_scheduled` 并调用一次 `step()` 取得 tick 0 快照，运行模式回到 `configured`。暂停与重置都先切换状态再广播
`StatusFrame`，保证客户端看到的模式与快照属于同一个时刻。

#### 重连对齐

每个 WebSocket 连接建立后的第一条消息都是 `StatusFrame`，包含当前 `mode` 与最新快照（`unconfigured` 时为 `null`）。
页面断线后以 1 秒固定间隔重试；重连成功即以首条 `StatusFrame` 覆盖本地状态，随后恢复接收 `TickFrame`。服务端只维护
一个仿真实例，仿真在浏览器断开期间继续按原状态推进，重连后的快照总是当前状态。

### Data Flow

1. 页面加载：浏览器请求静态资源与 IF-HTTP-map-read 获取 `MapPayload`，绘制地图骨架；随后建立 IF-MSG-state-stream
   连接，收到 `StatusFrame(unconfigured)`，控制按钮按状态初始化。
2. 配置场景：用户编辑表格并提交，浏览器通过 IF-HTTP-scene-apply 提交 `SceneConfig`；场景服务校验并推导路径，装配
   `Simulation.create_scheduled`，返回 `resolved_paths` 与 tick 0 快照；页面切到 `configured` 画面，默认选中第一台
   机器人并在画布上高亮其推导路径，点击机器人或表格行切换选中。校验失败时返回 422，页面列出全部违规项，当前状态不变。
3. 启动：浏览器通过 IF-HTTP-control 发送 `start`，推进任务开始逐 tick 调用内核推进并广播 `TickFrame`；页面用最新
   快照重绘。
4. 暂停/继续：`pause` 使推进循环停在 tick 边界并广播 `StatusFrame`，页面冻结画面；`resume` 唤醒循环，广播新的
   `StatusFrame` 后继续发送 `TickFrame`。
5. 重置：`reset` 重建 `Simulation` 并广播 tick 0 的 `StatusFrame`，页面回到 `configured`。
6. 失败路径：非法配置返回 422 且不触发状态切换；非法控制返回 409；WebSocket 断开时服务端移除订阅者但继续推进，
   页面显示断开状态并在重连后通过 `StatusFrame` 对齐。

## Error Handling

- 场景违规一次列出全部项：数量越界、`robot_id` 重复、起点重复、起点等于终点、锚点重复、锚点不在 demo 地图、相邻锚点
  无可行路线。返回 422，不构建仿真，当前运行状态不变。
- 请求体解析失败（非法 JSON、字段类型错误、缺少必填字段）：返回 422，响应体统一为 `{"violations": [解析错误文本]}`。
- 内核 `ScenarioValidationError`（防御性兜底）：转为同样的 422 错误结构，附内核违规文本。
- 非法控制动作：返回 409，状态与仿真不变。
- WebSocket 发送失败、单次发送超过 1 秒或连接关闭：关闭并移除该订阅者；推进任务与其他连接不受影响。
- 页面在 `unconfigured` 状态下没有可用控制；前端禁用按钮，服务端对任何控制动作返回 409。
- 前端请求失败（服务未启动、网络错误）：错误面板显示原因并允许重试；WebSocket 断开时连接指示变为断开并自动重连。
- 浏览器刷新：仿真不重置；页面通过首条 `StatusFrame` 恢复当前模式与最新快照。
- 同一配置包含不可达路线与重复起点：两类违规同时出现在一次响应中，修复顺序不影响错误收集。

## Acceptance Criteria

### 场景配置与路径

- **AC-scene-apply-builds**:
  WHEN 提交合法的 1-10 车配置, THEN 系统 SHALL 返回 `configured` 模式、每台车的推导路径与 tick 0 快照。
- **AC-path-anchor-order**:
  WHEN 配置包含起点、途经节点与终点, THEN 推导路径 SHALL 按顺序经过全部锚点，且相邻锚点之间是最短可行路线。
- **AC-path-one-way-detour**:
  WHEN 相邻锚点之间只有反方向的单行边, THEN 系统 SHALL 选择符合方向的绕行路线，没有绕行时判为违规。
- **AC-scene-reject-duplicate-start**:
  IF 两台机器人使用同一起点, THEN 系统 SHALL 返回 422 并列出重复起点违规，不构建仿真。
- **AC-scene-reject-unreachable**:
  IF 相邻锚点之间不存在可行路线, THEN 系统 SHALL 返回 422 并列出该违规，不构建仿真。
- **AC-scene-reject-bounds**:
  IF 机器人数量不在 1-10 之间或 `robot_id` 重复, THEN 系统 SHALL 返回 422 并列出全部违规项。
- **AC-scene-reject-degenerate-anchors**:
  IF 起点等于终点或锚点链中相邻元素相同, THEN 系统 SHALL 返回 422 并列出该违规。

### 控制状态机

- **AC-control-start**:
  WHEN `configured` 状态收到 `start`, THEN 系统 SHALL 开始推进并使 `tick_index` 随时间递增。
- **AC-control-pause-resume**:
  WHEN `running` 状态收到 `pause`, THEN 快照 SHALL 停止变化；收到 `resume` 后 SHALL 从暂停时的 tick 继续递增。
- **AC-control-reset**:
  WHEN 已应用配置的状态收到 `reset`, THEN 系统 SHALL 回到 tick 0 且保留最近一次有效配置。
- **AC-control-invalid**:
  IF 当前状态不接受该动作, THEN 系统 SHALL 返回 409 且运行状态与仿真不变。

### 状态推送

- **AC-stream-initial-frame**:
  WHEN 浏览器连接状态流, THEN 第一条消息 SHALL 是包含当前模式与最新快照的 `StatusFrame`。
- **AC-stream-tick-frames**:
  WHEN 仿真处于 `running`, THEN 系统 SHALL 每个 tick 推送一条 `TickFrame`，顺序与 `tick_index` 递增一致。
- **AC-stream-paused-silent**:
  WHEN 仿真处于 `paused`, THEN 系统 SHALL 不推送新的 `TickFrame`，仅在状态切换时推送 `StatusFrame`。
- **AC-stream-reconnect**:
  WHEN 连接断开后重新连接, THEN 系统 SHALL 通过首条 `StatusFrame` 让页面恢复当前模式与最新快照。

### 快照保真

- **AC-snapshot-fidelity**:
  WHEN 任一 `TickFrame` 到达页面, THEN 其机器人与区字段值 SHALL 与同一 tick 的内核 `TickSnapshot` 逐字段一致。

### 页面可观察行为

- **AC-view-map**:
  WHEN 页面加载完成, THEN 页面 SHALL 显示 demo 地图的节点、边与区标识。
- **AC-view-robots**:
  WHEN 仿真显示任意快照, THEN 每台机器人 SHALL 显示位置、朝向、状态（颜色与文字）与瞬时速度。
- **AC-view-resolved-paths**:
  WHEN 应用合法配置后选中一台机器人, THEN 页面 SHALL 在画布上高亮该机器人推导出的完整节点路径（节点与边）。
- **AC-view-zone-occupancy**:
  WHEN 某个区有持有人或等待者, THEN 页面 SHALL 在该区标出持有人与等待队列。
- **AC-view-empty-state**:
  WHEN 尚未应用配置, THEN 页面 SHALL 显示地图并禁用启动、暂停、继续与重置按钮。
- **AC-view-config-errors**:
  WHEN 配置未通过校验, THEN 页面 SHALL 列出响应中的全部违规项。
- **AC-view-connection**:
  WHEN 状态流断开, THEN 页面 SHALL 显示断开状态，并在自动重连后恢复显示当前状态。
- **AC-view-live-motion**:
  WHEN 10 台机器人在 demo 地图上运行, THEN 页面 SHALL 按 1× 实时节奏连续显示运动，人工观察无明显卡顿。
- **AC-view-motion-toggle**:
  WHEN 用户关闭动效开关, THEN 页面 SHALL 停止绘制轨迹与状态脉冲，并在重新加载后保持该偏好；没有已存偏好时
  SHALL 跟随系统的 `prefers-reduced-motion` 设置。

### 内核兼容

- **AC-kernel-untouched**:
  WHEN 本项交付, THEN `vrobot_sim` 的公开契约与行为 SHALL 与交付前一致，既有内核测试不改动通过。

## Testing

- 单元测试（`vrobot_web`）：`SceneConfig` 解析与违规收集；BFS 推导的直达、途经、单行绕行与不可达分支；锚点去重与起终点
  检查；`SnapshotPayload` 序列化字段名与枚举值。
- 集成测试（FastAPI `TestClient`，含 WebSocket 连接）：场景应用 200 与 422（逐类违规）；控制状态机的全部合法与非法
  迁移；状态流首帧、运行中逐 tick 帧、暂停静默、重连对齐；tick 0 与运行若干 tick 后的快照保真（与内核快照逐字段对比）；
  重置回到 tick 0。
- 回归测试：既有 `vrobot_sim` 测试套件零改动全部通过；Web 测试放在独立目录，安装 `web` extra 后才运行，内核测试仍只
  依赖 pytest。
- 人工验收：按项目既有假设验证浏览器帧率——用 10 车配置与三角环死锁配置各运行一次，观察 `AC-view-live-motion`、
  `AC-view-resolved-paths` 与其余 `AC-view-*` 行为。

## Open Questions

无遗留问题。
