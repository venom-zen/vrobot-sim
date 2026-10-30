# Mutex Scheduling Design

## Summary

调度算法工程师需要在本机验证多车路权分配与死锁，而当前内核只让每台车独立行驶：机器人彼此不可见，地图里的
临界区数据从不生效。本项为仿真内核加入内置 FCFS 路权调度与机器人间避让。5-10 台虚拟 AMR 在同一张带互斥
组的拓扑图上并发行驶，同一临界区同时最多一台占用，其余停在入口等待；机器人互为圆形障碍，后车不会穿过后车；
demo 地图扩展到至少 10 个可起始节点，10 台车可以各自从不同节点起步，且任意两个起始节点中心距大于
0.70 m；调度器通过申请/释放、指令源与区状态读取三个契约可整体替换；demo 的三角环上可以构造出环形等待
死锁并持续观察。

## Project Traceability

- **Project**: `projects/virtual-robot/project.md`
- **Backlog**: `projects/virtual-robot/backlog.md`
- **Work item**: `WI-mutex-scheduling`

## Goals

- 调度算法工程师能让 5-10 台虚拟 AMR 在带互斥组的拓扑图上并发行驶；同一容量为 1 的区在任一时刻最多一台
  机器人占用，其余申请者停在入口节点等待。demo 提供至少 10 个可起始节点，10 台车可以各自从不同节点起步，
  且任意两个起始节点中心距大于 0.70 m。
- 机器人获得路权后才驶入区边；等待中的机器人状态为 `WAITING_RIGHT`，持权行驶的机器人状态为 `HOLDING_ZONE`。
- 机器人互为物理障碍：后车在车体圆与前车相交之前停住，前车让开后在无人干预下自动恢复行驶。
- demo 三角环上三台车路径互指时形成环形等待死锁；死锁形成后仿真继续推进，位姿与状态保持冻结，不做自动解除。
- 快照能读出每个区的占用者与排队顺序，足以判断谁在等谁。
- 调度器可整体替换：替换实现只依赖路权申请、释放、区状态读取与既有指令接收边界，机器人本体与运动学代码不变。

## Primary Users / Roles

- 调度算法工程师：配置多车路径与起始时刻，运行仿真并观察路权互斥、排队与死锁。
- `WI-live-visualization`（后续消费者）：从快照读取位姿、状态与区占用，渲染浏览器画面。
- `WI-pluggable-dispatcher`（后续消费者）：按本项定义的路权协议替换内置调度器。

## Non-Goals

- 死锁自动解除、等待超时、优先级与抢占；本项只暴露死锁。
- 外部调度器接入协议的具体形态与网络传输，归 `WI-pluggable-dispatcher`。
- 路径规划与代价最优路线选择；路径仍由场景配置提供。
- 浏览器可视化、事件日志导出与回放、脚本化批量运行。
- 50 台规模下的性能优化与并发架构。
- 车云通信、弱网与断连模拟。
- 非临界区的边级预约；机器人之间只做物理避让，不互相预留路段。
- 机器人倒车、横向绕行与超车；机器人只能沿路径前进。

## Context

现有内核按固定步长推进：每 tick 先由指令源下发指令，再让每台机器人依次做安全判定、控制量计算与位姿积分，
最后收集快照。`RobotStatus` 的六个成员已冻结，其中 `WAITING_RIGHT` 与 `HOLDING_ZONE` 已声明但从未产生。
地图数据里有 `MapCriticalZone`（标识、名称、成员边列表、容量），但内核不消费它，也没有边到区的反查索引。
`safety` 只对运行时注册的圆形障碍做前瞻判定，机器人彼此不可见。

已核实的事实：

- demo 地图含三角环 N01→N02→N03→N01，三条环边各属一个容量 1 的区（Z01/Z02/Z03），E05 同属 Z04 与 Z05。
- demo 当前有 7 个节点与 7 条边。全量车车避让下，两台车共用起始节点会在起步 tick 进入 `OVERLAP` 急停，
  因此 7 个节点最多承载 7 台可起步的机器人；本项把 demo 扩展到至少 10 个可起始节点。扩展后的 10 个起始
  节点还需两两中心距大于 0.70 m，避免不同节点上的车体圆在 t=0 相交。
- `Simulation.create` 默认使用直通指令源，只在 `start_tick` 下发路径；快照契约要求新增字段只增不改、带默认值。
- 已交付验收要求默认入口下状态只出现 `IDLE`、`MOVING`、`E_STOP`、`ARRIVED` 四种。
- 项目约定允许 `Robot` 与调度器持有运行时可变状态；调度器状态属于单个 `Simulation` 实例。

## Discovery

### Key Discoveries

- 六成员状态枚举已由前一项冻结；本项只负责产生后两个成员，不新增枚举值。
- 边到区的反查索引与 `capacity` 的语义按前一项的 Decision 留给本项建立。
- 现有急停只有显式 `RESUME` 才能恢复，默认入口的多车场景没有任何自动恢复机制。
- 机器人之间没有物理交互；多车避让必须新增，并与既有障碍判定共用同一套两步判定。
- 全量车车避让把重复起始节点变成永久 `OVERLAP`；不同节点若中心距不足，车体圆也会在 t=0 相交。当前 demo
  的 7 个节点不足以承载 10 台，规模目标要求扩展地图并保证起始节点间距。
- demo 地图三条环边容量都是 1，环形等待可以直接由场景配置构造，不需要新增地图或机制。

### Scope Decisions

- **纳入完整车车避让**：用户确认机器人互为圆形障碍，排队与堵塞由物理避让显现。该能力超出 backlog 原 Scope
  文字，backlog 的 Scope 描述需要由 `brainstorming` 在下次对账时补全。
- **纳入调度器自动恢复**：内置调度器对安全条件已解除的急停车重发 `RESUME`。机器人本体仍只认显式指令，
  恢复策略属于调度器。
- **排除时间型缓解手段**：不提供等待超时、优先级、抢占与死锁解除，保证死锁状态可复现、可观察。
- **排除非临界区预约**：机器人之间只做物理避让；非区边的对向相遇可能以相交兜底停住，不在本项消除。
- **纳入 demo 地图扩展**：为承载 10 台车，demo 增加到至少 10 个可起始节点，任意两个起始节点中心距大于
  0.70 m；保留地图标识、三角环与 5 个区，受影响的节点/边计数测试、同起点回归测试与 10 车基准同步更新。

## Decision Record

### DR-rights-grant-in-dispatch

**Decision**: 路权申请在机器人推进阶段提出，最早在下一个 tick 的 dispatch 阶段获得授予。内置调度器把全部
未授予申请按 `(arrival_tick, robot_id)` 升序处理，`robot_id` 按字符串比较。

**Rationale**: 位姿与状态在 tick 内按固定顺序推进。若申请即授予，结果会依赖机器人遍历顺序；统一授予让同一
场景与遍历顺序无关，也让同 tick 竞争有确定的排序。被拒方向：申请时同步授予（顺序泄露成可观察行为）、按场景
配置顺序排队（调整配置行序就改变行为）。

**Constraints**: 每次进入临界区至少多等一个 tick，默认 dt=0.02 秒时为 20 毫秒；等待期间机器人停在入口节点。

### DR-rights-release-make-before-break

**Decision**: 机器人获得下一段路权并切换到该段时，才释放不再覆盖该段的持有区；到达终点时释放全部持有区。

**Rationale**: 若驶离区边就释放，等待下一区的机器人已不持有任何区，环形等待无法形成，成功信号要求的死锁
场景不可达。make-before-break 让等待中的车保留上一段路权，环形互等才可能成立。

**Rejected concern**: 已经驶离区边的车仍占着区，会挡住其他想进入这条边的车。

**Revisit when**: 引入节点级区归属，或真实调度实践证明等待中的车辆不应占用已离开的边时。

**Constraints**: 区占用时间比车体实际经过时间长；快照里的持有人可能是一台停在入口节点的车。

### DR-rights-atomic-multi-zone

**Decision**: 进入一条边前，把它所属且尚未持有的全部区作为一组原子申请。一个申请必须在它申请的每个区的
队列中都排第一、且每个区都有空位时，才整组授予；任一条件不满足就整组等待。

**Rationale**: demo 地图的 E05 同属 Z04 与 Z05。分步获取会让机器人驶入只持有一半路权的边，破坏互斥；整组
授予让"进入这条边需要哪些区"只有一种解释。被拒方向：按 `zone_id` 顺序逐个获取（半持有状态没有定义）。

**Constraints**: 多区申请能在某个区领先、在另一个区落后，等待期间会同时挡住两个区的后续申请，这是队首阻塞
的已知代价。

### DR-rights-no-timeout

**Decision**: 调度契约不提供超时、优先级或抢占；内置调度器只做先到先得与容量约束。

**Rationale**: backlog 的 Non-Goal 已把死锁自动解除排除在外。死锁是本项要暴露的观察对象，超时会把稳定的
死锁状态变成依赖时序的抖动，反而不利于验证。

**Rejected concern**: 死锁之后仿真永久卡住，应自动解除以便继续跑别的场景。

**Revisit when**: 进入死锁解除或调度器对比评估时，对应后续的调度能力。

### DR-dispatcher-injected-collaborator

**Decision**: 机器人通过注入的路权仲裁器协议发起申请与释放；内置调度器同时实现指令源（路径下发、自动
`RESUME`）、路权仲裁器与区状态读取；`create_scheduled` 接受可选的调度器实现（默认内置），仿真只负责
装配与驱动。

**Rationale**: 替换边界落在三个契约上：指令源、路权申请/释放、区状态读取。机器人本体与运动学代码不变；
快照的 `zones` 来自被装配的调度器，而不是写死内置实现，替换实现才能产出相同快照。被拒方向：新增请求与
授予指令（方向反转、指令集合膨胀）、调度逻辑放仿真主循环（状态来源分散，替换时要改仿真）、只比较机器人
快照并把 `zones` 限定为内置实现（无法验证整体替换，可视化也读不到替换实现的区状态）。

**Constraints**: 替换实现要同时提供路权仲裁、指令源与区状态读取三个角色，才能装配到 `create_scheduled`。

### DR-dispatcher-runtime-state

**Decision**: 运行时可变状态有两处：`Robot` 实例与调度器的路权状态（每区持有者、等待队列与申请条目）。
地图、底盘配置与快照仍不可变；调度器状态属于单个 `Simulation` 实例，不跨实例共享。

**Rationale**: 授予必须在下一个 dispatch 阶段统一结算，等待队列按 `(arrival_tick, robot_id)` 排序；这些
状态集中在调度器，机器人本体只读取申请结果，快照也只有一个区状态来源。被拒方向：把队列与持有者放回
`Robot`（调度器每 tick 反向聚合，排序与快照来源分散）。

**Constraints**: `AGENTS.md` 的运行时状态约定同步更新；替换调度器自行管理同类状态，但必须通过
`IF-PROTO-zone-state-read` 提供区状态。

**Revisit when**: 多个仿真共享调度器、引入并发调度，或把调度状态持久化时。

### DR-scale-demo-map-extension

**Decision**: 扩展 `demo` 地图到至少 10 个可起始节点；10 台车各自使用不同起始节点，且任意两个起始节点的
中心距大于 0.70 m；现有 N01–N03 三角环与 Z01–Z05 保持不变，地图标识仍为 `demo`。

**Rationale**: 全量车车避让下，两台车共用起始节点会永久 `OVERLAP` 急停；即使节点不同，中心距不足时
车体圆也会在 t=0 相交。当前 demo 只有 7 个节点，无法承载 5-10 台目标中的 10 台。用户选择扩展 demo，
而不是下调规模或引入边内起始位姿。被拒方向：下调 MVP 规模（削弱项目指标）、边内起始位姿（改动场景
契约与首段语义）。

**Constraints**: 10 个起始节点两两中心距大于 0.70 m；新增节点与边必须通过既有地图构建校验；新增边按
需要加入临界区；依赖 demo 节点/边数量的测试、`test_simulation.py` 的同起点回归与 10 车基准同步更新；
默认入口与 `create_scheduled` 的创建语义不变。

**Revisit when**: 引入外部地图、允许边内起始位姿，或项目规模指标不再要求 10 台时。

### DR-creation-entry-backward-compatible

**Decision**: `Simulation.create` 保持现有默认：直通指令源、无路权门禁，车车避让生效。新增
`Simulation.create_scheduled` 默认使用内置调度器，也可注入替换实现，并向每台机器人注入同一个仲裁器。

**Rationale**: 已交付验收依赖默认入口：快照状态只出现四个值、`RESUME` 仅由显式指令触发。默认套上调度器会
同时改变这两条契约。显式入口让调度成为可识别的选择，也避免单车上区时产生无人消费的调度状态。被拒方向：
默认入口直接启用调度器（改变已交付行为与既有测试）。

**Constraints**: 多车场景若使用默认入口，临界区不生效；使用者必须选择 `create_scheduled` 才得到本项行为。

### DR-peers-tick-start-circles

**Decision**: 每个 tick 开始时采集全部机器人的位姿与车体半径，作为本 tick 所有车车判定的输入。机器人在
tick 内只读取这份集合，不读取同 tick 其他机器人的最新位姿。

**Rationale**: 让判定与机器人遍历顺序无关，同一场景重跑结果一致，并与快照"同一时间切面"的语义对齐。

**Constraints**: 对向行驶的相对接近速度可达单车两倍，单侧刹车距离不足以保证不重叠；相交兜底会在重叠当 tick
把速度归零，保证停住而不保证不重叠。临界区互斥使 demo 地图上不会出现同区对向行驶。

### DR-auto-resume-dispatcher-policy

**Decision**: 内置调度器在每 tick 的 dispatch 阶段对所有 `E_STOP` 机器人下发 `RESUME`；机器人仍按既有受理
语义决定是否恢复行驶。

**Rationale**: 全避让后跟驰会频繁急停，人工恢复不可行。机器人本体"只认显式指令"的契约不变，恢复策略放在
调度器，替换调度器可以改变策略。被拒方向：机器人内部自动重试（推翻已交付的显式恢复语义）。

**Constraints**: 启用调度器后，静态障碍移除的机器人也会自动恢复；默认入口不启用该策略，保持显式恢复。

### DR-status-flat-enum-priority

**Decision**: 六个状态成员不变。`WAITING_RIGHT` 表示停在入口等待路权；`HOLDING_ZONE` 表示持有至少一个区
（包括转向与切换瞬间）。同一 tick 多个条件同时成立时，展示优先级为 `E_STOP` > `WAITING_RIGHT` >
`HOLDING_ZONE` > `MOVING`；`IDLE` 与 `ARRIVED` 不受影响。

**Rationale**: 枚举是三个 Now 项共用的契约，不应新增成员；优先级让一台车在快照里只有一个取值，且表达最
关键的阻塞原因。

**Constraints**: 持有区的急停车在快照中显示 `E_STOP`，它的区占用需要从 `zones` 字段读取。

## Proposed Solution

### Architecture

新增两个模块，其余模块做定点扩展：

- `rights`（新增叶子模块）：定义路权申请、释放与 `GrantOutcome` 结果枚举，不导入包内其他模块。
- `robot`（扩展）：注入仲裁器，新增持有区集合与待授予申请；依赖 `rights`（新增）、`controller`、
  `kinematics`、`map_model` 与 `obstacle_field`（既有）。
- `safety`（扩展）：判定输入增加其他机器人圆集合，继续只依赖 `robot`。
- `dispatcher`（新增顶层模块）：`FcfsDispatcher` 实现指令源、路权仲裁器与区状态读取，持有每区持有者与等待
  队列；依赖 `robot`、`map_model`、`rights` 与 `snapshots`。
- `simulation`（扩展）：装配内置或注入的调度器与机器人，每 tick 采集起始位姿并在推进后采集快照；依赖
  `dispatcher`、`scenario`、`snapshots`、`robot` 与 `safety`。
- `snapshots`（扩展）：新增 `ZoneSnapshot`，`TickSnapshot` 增加 `zones` 字段。
- `map_model`（扩展）：构建期派生边到区的反查索引 `edge_zones`，仍是叶子模块。
- `maps/demo`（扩展）：增加到至少 10 个可起始节点；地图标识、三角环与既有区保持不变。

### Components

- **内置调度器**：构造时输入场景的机器人清单与拓扑地图。dispatch 阶段依次做三件事：按排序处理未授予申请；
  在 `start_tick` 下发 `ASSIGN_PATH`；向所有 `E_STOP` 机器人下发 `RESUME`。它同时接受申请与释放，并通过
  区状态读取契约给出每区持有者与等待队列。
- **路权与区状态契约**：`rights` 定义申请、释放与结果枚举；区状态读取由调度器实现，返回
  `ZoneSnapshot` 数据。机器人只依赖路权协议，不依赖内置调度器的具体类型。
- **机器人**：受理路径后记录路径；在首段或切换段前计算即将进入的段尚未持有的区，发起申请；未授予则停在
  入口等待，授予则释放不再覆盖新段的区并切换段。等待期间每个 tick 重复申请读取结果。状态按持有集合与
  阻塞原因取值。
- **安全判定**：对注册障碍物与其他机器人圆一起执行"相交兜底 + 垂直跳过 + 覆盖区间与前瞻区间相交"的既有
  两步判定，每台车判定时排除自己。
- **仿真**：装配内置或注入的调度器与机器人；每 tick 在推进前固定车车判定输入，推进时把 tick 序号与机器人
  圆集合交给每台车，推进后采集快照，并通过区状态读取契约采集区状态。
- **地图数据**：在构建期从临界区的成员边列表派生 `edge_zones`，保证边与区关系只有一个来源；demo 扩展到至少
  10 个可起始节点，新增边按需要加入临界区。

### Data Model

#### Change Summary

| Change | Layer | Object | Purpose | Source |
|--------|-------|--------|---------|--------|
| ADD | Domain | `ZoneSnapshot` | 快照中的区占用与排队 | `snapshots` |
| MODIFY | Domain | `TickSnapshot` | 新增 `zones` 字段 | `snapshots` |
| MODIFY | Domain | `TopologyMap` | 新增边到区反查索引 | `map_model` |
| ADD | Domain | `GrantOutcome` | 路权申请结果枚举 | `rights` |

#### Domain / Serialized Models

##### [ADD] ZoneSnapshot

- 字段：`zone_id`、`capacity`、`holder_robot_ids`、`waiting_robot_ids`。
- `holder_robot_ids` 按 `robot_id` 升序；`waiting_robot_ids` 按 `(arrival_tick, robot_id)` 升序。
- 一个多区申请会在它申请的每个区的等待列表里各出现一次。
- 只在启用调度器时产生；未启用时 `TickSnapshot.zones` 为空元组，所有区都不出现。启用的调度器（内置或
  替换实现）通过 `IF-PROTO-zone-state-read` 提供这些数据。

##### [MODIFY] TickSnapshot

- 新增字段 `zones: tuple[ZoneSnapshot, ...] = ()`，按 `zone_id` 升序。
- 既有字段与语义不变；新增字段带默认值，既有消费方不受影响。

##### [MODIFY] TopologyMap

- 新增只读派生索引 `edge_zones: Mapping[str, tuple[str, ...]]`：键为边标识，值为包含该边的区标识，按
  `zone_id` 升序。
- 索引由 `build_topology_map` 从 `zones` 的成员边列表一次派生，不引入第二个数据来源；既有字段与构建错误
  语义不变。

##### [ADD] GrantOutcome

- 枚举两个取值：`GRANTED` 表示申请已获授予；`QUEUED` 表示申请在排队，尚未授予。
- 只作为申请调用的同步结果，不承载队列位置或其他状态。

#### Constraints and Indexes

- `edge_zones` 必须与 `zones` 的成员边列表一致；两者在同一构建调用内生成。
- 任一区的持有人数不超过它的容量；等待队列按 `(arrival_tick, robot_id)` 排序。
- 同一 `(robot_id, segment_index)` 至多存在一个申请条目；重复申请返回当前结果，不重复入队。
- 机器人任一时刻的持有集合都能在 `edge_zones` 里找到来源：行驶中来自当前段，入口等待时来自上一段。
- `ZoneSnapshot` 的持有人与等待者顺序来自 `IF-PROTO-zone-state-read`，与调度器内部状态一致。

#### Concurrency and Consistency

- 单线程离散仿真，没有锁与并发访问：授予只发生在 dispatch 阶段，申请与释放在机器人推进阶段。
- 调度器状态属于单个 `Simulation` 实例，不跨实例共享；区持有者与等待队列只在当前仿真内有效。
- 车车判定固定读取 tick 起始位姿；快照固定读取 tick 结束状态，两者不混用。

### Interfaces

#### Change Summary

| Change | Kind | Contract ID | Producer | Consumer | Compatibility |
|--------|------|-------------|----------|----------|---------------|
| ADD | Protocol | IF-PROTO-right-of-way-arbitration | 机器人 | 调度器 | 新契约，替换实现需配套指令源与区状态读取 |
| ADD | Protocol | IF-PROTO-zone-state-read | 仿真 | 调度器 | 新契约，内置与替换实现都必须提供 |
| MODIFY | Protocol | IF-PROTO-sim-step-advance | 调用方 | 仿真内核 | 只增字段、可选创建输入与创建入口，向后兼容 |

- IF-PROTO-robot-command-intake: No changes — 指令类型与受理状态门禁不变；调度器自动重发 `RESUME` 走既有
  受理语义。
- IF-PROTO-obstacle-registration: No changes。
- **Messages**: No changes — 不引入消息通道。
- **HTTP APIs**: No changes — 本项不提供 HTTP 接口。

#### Protocols

##### [ADD] IF-PROTO-right-of-way-arbitration

- **Direction**: 机器人 -> 路权仲裁器。
- **Command / Opcode**: `request-right`、`release-right`。
- **Framing / Payload**: 进程内同步调用。`request-right` 载荷为 `robot_id`、`segment_index`、`zone_ids`
  （升序元组）与 `tick_index`；`release-right` 载荷为 `robot_id` 与 `zone_ids`。
- **ACK / Timeout / Retry**: `request-right` 同步返回 `GRANTED` 或 `QUEUED`。同一 `(robot_id,
  segment_index)` 的重复申请不重复入队，只返回当前结果；等待中的机器人在后续 tick 重复调用读取最新结果，
  原始 `arrival_tick` 与排队位置不变。释放后以不同的 `segment_index` 再次申请视为新的申请。没有超时与
  重试：排队由调度器在后续 tick 自行授予。`release-right` 无返回值；释放未持有的区是幂等无操作。
- **Errors**: 调用方只提交地图里存在的区标识，且 `zone_ids` 非空（下一段无区或已全部持有时不发起调用）；
  因此协议没有运行时错误分支。
- **Versioning**: 新契约。替换实现必须同时提供 IF-PROTO-robot-command-intake 的路径下发、自动恢复与
  IF-PROTO-zone-state-read，才能装配到 `create_scheduled`。

##### [ADD] IF-PROTO-zone-state-read

- **Direction**: 仿真 -> 调度器（区状态提供者）。
- **Command / Opcode**: `read-zone-state`。
- **Framing / Payload**: 进程内同步调用，无入参；返回地图中每个区的 `zone_id`、`capacity`、
  `holder_robot_ids` 与 `waiting_robot_ids`。持有人按 `robot_id` 升序，等待者按 `(arrival_tick, robot_id)`
  升序，区按 `zone_id` 升序。
- **ACK / Timeout / Retry**: 同步返回；只读且幂等，没有超时与重试。未启用调度器时不调用，`zones` 为空元组。
- **Errors**: 没有运行时错误分支；实现必须覆盖地图中的全部区。
- **Versioning**: 新契约。内置调度器与替换实现都必须提供；`create_scheduled` 装配的对象负责实现。

##### [MODIFY] IF-PROTO-sim-step-advance

- **Direction**: 调用方 -> 仿真内核。
- **Command / Opcode**: 创建仿真实例（`create`、新增 `create_scheduled`）、推进一个步长。
- **Framing / Payload**: 创建输入场景配置；`create_scheduled` 接受可选的调度器实现（默认内置），该实现
  同时提供指令源、路权仲裁与区状态读取。推进无入参，返回 `tick-snapshot`；快照新增 `zones` 字段。
- **ACK / Timeout / Retry**: 与原契约一致：创建失败不产出半成品实例；推进始终返回快照。
- **Compatibility**: 原 `create` 的既有字段与语义不变；`TickSnapshot` 新增 `zones` 带默认空元组，旧
  消费方按既有字段读取不受影响；`create_scheduled` 的调度器输入可省略。

### State Machines

`IDLE`、`MOVING`、`E_STOP`、`ARRIVED` 之间既有的转移保持原语义，未列出的旧行继续有效。新增与变化的转移：

| Current state | Trigger / Guard | Target state | Side effects |
|---------------|-----------------|--------------|--------------|
| `IDLE` / `ARRIVED` | `ASSIGN_PATH` 受理；首段无未持有区或申请获授 | `MOVING` | 记录路径；首段有未持有区时切换段 |
| `IDLE` / `ARRIVED` | `ASSIGN_PATH` 受理；首个 tick 首段申请返回 `QUEUED` | `WAITING_RIGHT` | 记录路径；v 与 ω 置零，停在起点；保留申请条目 |
| `MOVING` / `HOLDING_ZONE` | 走完一段，下一段无未持有区 | `HOLDING_ZONE` / `MOVING` | 释放不再覆盖下一段的区，进入转向或直行 |
| `MOVING` / `HOLDING_ZONE` | 走完一段，下一段有未持有区且申请获授 | `HOLDING_ZONE` / `MOVING` | 释放不再覆盖新段的区，切换段并转向或直行 |
| `MOVING` / `HOLDING_ZONE` | 走完一段，下一段有未持有区且申请排队 | `WAITING_RIGHT` | v 与 ω 置零，停在入口节点，保留已获得的区 |
| `WAITING_RIGHT` | 重复申请返回 `GRANTED` | `HOLDING_ZONE` / `MOVING` | 释放不再覆盖新段的区，切换段；`arrival_tick` 不变 |
| `WAITING_RIGHT` | 重复申请返回 `QUEUED` | `WAITING_RIGHT` | 位姿与速度不变；保留原 `arrival_tick` |
| `MOVING` / `HOLDING_ZONE` | 走完最后一段 | `ARRIVED` | 释放全部持有区，v 与 ω 置零 |
| `MOVING` / `HOLDING_ZONE` | 障碍物或机器人触发急停 | `E_STOP` | 既有急停行为不变，持有区不释放 |
| `E_STOP` | `RESUME`（显式或调度器自动）且安全成立 | `HOLDING_ZONE` / `MOVING` | 按持有集合恢复状态，沿原路径继续 |
| `E_STOP` | `RESUME` 但安全不成立 | `E_STOP` | 位姿不变，`estop_reason` 更新 |

等待中的机器人每个 tick 以相同的 `(robot_id, segment_index)` 重复申请；没有推送通道，
重复 `request-right` 是读取授予结果的唯一路径。

### Key Mechanisms

#### 每 tick 授予与先到先得

dispatch 阶段的授予按 `(arrival_tick, robot_id)` 升序处理每个未授予申请：只有当它在申请的每个区的等待队列
里都排第一，并且每个区的当前持有人数小于容量时，才整组授予并登记持有人。申请在机器人推进阶段提出，最早在
下一个 tick 生效，因此每次进入临界区至少多等一个 tick。等待中的机器人重复申请只读取当前结果，不改变
原始 `arrival_tick` 或排队位置；同一申请条目在释放前不会重复入队。

边界算例：

- 同 tick：R2 与 R10 在 tick 40 同时申请空闲的 Z01。`robot_id` 按字符串比较，"R10" 小于 "R2"，因此
  授予 R10，R2 留在队首等待下一次释放。
- 跨 tick：R9 在 tick 100 申请，R1 在 tick 101 申请同一区，则先授予 R9，即使 "R1" 字符串更小。
- 容量：容量为 2 的区已有 R1 与 R2 持有，R3 排队；R1 释放后的下一次 dispatch 授予 R3。

#### 路权门禁与 make-before-break 释放

机器人在两个时刻评估路权：受理新路径后的首个 tick，以及走完一段且仍有后续段的时刻。需要的区等于即将进入的
段（首段或下一段）所属区减去当前持有区；为空则直接进入该段，非空则向仲裁器申请。未授予时机器人状态为
`WAITING_RIGHT`，v 与 ω 置零，位姿停在入口节点，并继续持有已获得的区。授予后机器人释放不再覆盖新段的区，
再进入转向或直行子阶段；状态按持有集合在 `HOLDING_ZONE` 与 `MOVING` 之间取值。到达终点释放全部持有区。

等待中的机器人每个 tick 以相同 `(robot_id, segment_index)` 重复调用 `request-right`：返回 `GRANTED` 时
切换段，返回 `QUEUED` 时保持等待，原始 `arrival_tick` 不变。

边界算例：R1 走完 E01 到达 N02，申请 Z02 未获授予，此时仍持有 Z01；直到 R1 获得 Z02 并切换到 E02 的那
个 tick，才释放 Z01。

#### 多区边的原子申请

进入 E05 需要的区集合是 {Z04, Z05} 减去已持有区。从 E06 过来的车已持有 Z05，只申请 {Z04}；从 E04 过来
的车已持有 Z04，只申请 {Z05}。授予按组判定，一个区不满足就整组等待，等待期间已持有的区不释放。

边界算例：R1 在 N05 持有 Z05、申请 Z04，而 Z04 被 R5 持有。R2 在 Z04 排队并想进入 E04。R1 与 R2 都
等待，Z04 在 R5 释放前不会授予任何人；R1 仍占着 Z05，挡住想从 E06 进入 E05 的后续车。这是原子申请接受的
队首阻塞。

#### 车车避让

仿真在每个 tick 的机器人推进前采集全部机器人的位姿与 `body_radius_m`，形成本 tick 的机器人圆集合。每台车
判定时排除自己，其余圆与注册障碍物一起走既有两步判定：先做相交兜底，再按垂直距离跳过侧向对象，最后按覆盖
区间与前瞻区间判安全距离。

后车与静止前车同向时的边界算例：默认 v=1.5、`decel_max_mps2`=1.5 时连续刹车距离为 1.5²/(2·1.5)=0.75，
前瞻长度为 0.75 + 0.35 + 1.5·0.02 = 1.13。判定在 tick 起始执行，前车中心距后车 1.48 米时触发；如果
上一 tick 尚未触发，后车可能已用 0.03 米的一步进入阈值，因此最坏触发距离约 1.45 米。后车按 0.03 m/s
每 tick 离散减速，实走 0.735 米停住，最坏中心距不小于 1.45 - 0.735 = 0.715 米，大于两个 0.35 米半径
之和 0.70 米，因此不重叠。1.48、0.75 与 0.73 是名义值，不是最坏下界。

对向相遇时相对接近速度可达单车两倍，单侧刹车距离不足以保证不重叠；相交兜底会在重叠当 tick 把速度归零，
保证停住而不保证不重叠。临界区互斥使 demo 地图上不会出现同区对向行驶。

#### 自动恢复与死锁暴露

调度器在每个 dispatch 阶段向所有 `E_STOP` 机器人下发 `RESUME`。机器人按既有受理语义处理：安全成立则恢复
行驶，不成立则保持急停并更新原因。恢复策略不写进机器人本体。

环形等待的判定不依赖新状态：每区容量 1，持有者正在等待另一个区，授予条件永远不成立，且没有超时，因此状态
保持。快照的 `zones` 字段呈现持有与等待关系；仿真继续推进，等待车的位姿与状态不变。

边界算例：后车停在距前车中心约 0.715 米处；前车驶离后，中心距超过恢复判定所需的 1.48 米后的第一个
dispatch，后车收到 `RESUME` 并恢复行驶。

#### 快照一致性

同一 tick 先完成授予与全部机器人推进，再采集快照。`zones` 通过 IF-PROTO-zone-state-read 读取调度器在
tick 结束时的持有与队列状态，机器人快照仍按 `robot_id` 排序，区快照按 `zone_id` 排序。车车判定使用
tick 起始位姿，快照使用 tick 结束位姿。

### Data Flow

1. 调用方通过 IF-PROTO-sim-step-advance 的 `create_scheduled` 创建实例：内核校验场景、加载地图、派生
   `edge_zones`，构造内置 `FcfsDispatcher` 或使用调用方注入的替换实现，把它作为指令源、仲裁器与区状态
   提供者注入仿真和每台机器人。
2. 每个 tick，仿真在推进前采集全部机器人的起始位姿与车体半径，作为本 tick 车车判定的固定输入。
3. 调度器在同一 tick 的 dispatch 阶段做授予：按 `(arrival_tick, robot_id)` 检查未授予申请，满足条件即登记
   区持有人。
4. 调度器通过 IF-PROTO-robot-command-intake 在 `start_tick` 下发 `ASSIGN_PATH`，并对每台 `E_STOP` 机器人
   下发 `RESUME`。
5. 机器人推进时，在首段或切换段前通过 IF-PROTO-right-of-way-arbitration 提出申请；首段申请在受理路径后的
   首个 tick 发出。未授予则停在入口进入 `WAITING_RIGHT`；已授予则释放不再覆盖新段的区并切换段。等待中的
   机器人每个 tick 以相同申请重复读取结果，授予后切换段。
6. 机器人调用 `safety`，输入注册障碍物与本 tick 起始位姿的其他机器人圆，得到急停请求或继续行驶；随后按
   既有控制与积分逻辑推进。
7. 仿真通过 IF-PROTO-zone-state-read 采集区状态，收集快照并通过 IF-PROTO-sim-step-advance 返回。
8. 失败路径：申请排队时车停在入口；自动 `RESUME` 遇阻挡时车保持 `E_STOP`；环形等待形成后快照持续显示
   同一占用关系，仿真继续推进但不产生位姿变化。

## Error Handling

- 申请未知区标识：内置实现只接受来自 `edge_zones` 的标识，机器人也只产生这些标识，因此不设运行时校验分支。
- 释放未持有的区：幂等无操作，不改变持有集合。
- 重复申请同一 `(robot_id, segment_index)`：返回当前授予状态，不重复入队。
- 没有路权仲裁器：默认入口不启门禁，快照状态不产生 `WAITING_RIGHT` 与 `HOLDING_ZONE`。
- 地图没有临界区（`minimal` 地图）：没有任何申请发生，`create_scheduled` 只做路径下发与自动恢复，快照
  `zones` 为空元组。
- 环形等待：不是错误；快照可见，仿真继续推进，不触发补偿或解除。
- 初始车体重叠：尝试起步的机器人在该 tick 进入 `E_STOP`，原因 `OVERLAP`；重叠解除前自动恢复无效。
- 前车阻挡：自动 `RESUME` 是合法指令，但安全判定不成立时机器人保持 `E_STOP`，位姿不变。
- 对向相遇：可能触发相交兜底；本项只保证停住，不保证对向不重叠。
- 场景把两台车的起始位姿放在同一个位置或中心距不足 0.70 m：尝试起步的车进入 `E_STOP`；这是场景配置
  责任，创建期不拦截。内置的 10 车 demo 场景为每台车分配不同起点，且任意两个起始节点的中心距大于
  0.70 m；同一节点或过近节点对不能作为独立起始位姿。

## Acceptance Criteria

### 路权互斥

- **AC-rights-single-holder**:
  WHEN 两台机器人申请同一容量为 1 的区并都尝试驶入, THEN 系统 SHALL 保证任一快照中该区的持有人至多一台，
  另一台停在入口节点且状态为 `WAITING_RIGHT`。
- **AC-rights-fcfs-same-tick**:
  WHEN 同一 tick 内两台机器人对同一空闲区提出申请, THEN 系统 SHALL 在下一次授予中按 `robot_id` 字符串升序
  先授予排在前面的机器人。
- **AC-rights-fcfs-arrival**:
  WHEN 两台机器人在不同 tick 申请同一区, THEN 系统 SHALL 先授予更早提出申请的机器人，与 `robot_id` 大小
  无关。
- **AC-rights-atomic-multi-zone**:
  IF 机器人即将进入的边属于多个区且其中任一区没有空位或尚未排到队首, THEN 系统 SHALL 不授予该组中的任何
  一个区，并让机器人停在入口节点。
- **AC-rights-capacity**:
  WHEN 某区容量为 2 且已有两台机器人持有, THEN 系统 SHALL 让第三台机器人排队，直到其中一台释放后才授予。
- **AC-rights-release-make-before-break**:
  WHEN 机器人获得下一段路权并切换到该段, THEN 系统 SHALL 释放所有不再覆盖该段的持有区。
- **AC-rights-hold-while-waiting**:
  WHEN 机器人在入口节点等待下一段路权, THEN 系统 SHALL 继续持有它已经获得的上一段区，快照中该机器人既是
  等待者又是该区的持有人。
- **AC-rights-holding-status**:
  WHEN 机器人持有至少一个区且正在转向或行驶, THEN 快照状态 SHALL 为 `HOLDING_ZONE`。
- **AC-rights-waiting-status**:
  WHEN 机器人申请未获授予, THEN 快照状态 SHALL 为 `WAITING_RIGHT` 且线速度为零。

### 死锁暴露

- **AC-deadlock-ring-forms**:
  WHEN demo 地图上三台机器人的路径在三角环上互指并依次获得首条环边路权, THEN 系统 SHALL 在每台车到达下一
  区入口后形成环形等待：三者状态为 `WAITING_RIGHT`，三区的持有人与等待者在快照中首尾相接成环。
- **AC-deadlock-persists**:
  WHEN 环形等待形成后继续推进仿真, THEN 系统 SHALL 保持三台机器人的位姿与状态不变，且不自动解除死锁。

### 车车避让

- **AC-peers-rear-end**:
  WHEN 后车沿同一段接近一辆静止前车, THEN 系统 SHALL 在前车车体圆与自身车体圆相交之前进入 `E_STOP`，
  `estop_reason` 为 `SAFETY_DISTANCE`。
- **AC-peers-auto-resume**:
  WHEN 前车驶离后安全距离重新成立, THEN 系统 SHALL 由内置调度器在下一个 tick 自动下发 `RESUME`，后车无需
  外部指令即可恢复行驶。
- **AC-peers-resume-blocked**:
  IF 自动 `RESUME` 下发时前车仍在安全距离内, THEN 系统 SHALL 让后车保持 `E_STOP` 与位姿不变。
- **AC-peers-tick-start-poses**:
  WHEN 任一机器人在 tick 内做安全判定, THEN 系统 SHALL 使用其他所有机器人在该 tick 起始时刻的位姿与车体
  半径，包含 `IDLE`、`WAITING_RIGHT`、`ARRIVED` 与 `E_STOP` 的车。
- **AC-peers-order-independent**:
  WHEN 同一场景只交换 `scenario.robots` 的书写顺序, THEN 系统 SHALL 产出逐 tick 完全相同的快照序列。
- **AC-peers-initial-overlap**:
  IF 两台机器人的初始车体圆相交且其中一台尝试起步, THEN 系统 SHALL 在该 tick 让尝试起步的机器人进入
  `E_STOP`，`estop_reason` 为 `OVERLAP`。

### 状态与快照

- **AC-status-estop-over-holding**:
  WHEN 持有区的机器人因障碍或机器人接近进入 `E_STOP`, THEN 快照状态 SHALL 为 `E_STOP`。
- **AC-status-holding-after-resume**:
  WHEN 持有区的急停车获得安全恢复, THEN 快照状态 SHALL 回到 `HOLDING_ZONE`。
- **AC-snapshot-zone-detail**:
  WHEN 启用调度器后读取任一 tick 快照, THEN 系统 SHALL 给出每个区的标识、容量、持有人与等待者，且等待者按
  `(arrival_tick, robot_id)` 升序排列。
- **AC-snapshot-zones-default**:
  WHEN 未启用调度器的场景读取快照, THEN `zones` 字段 SHALL 为空元组，既有字段含义不变。

### 兼容与契约

- **AC-compat-default-create**:
  WHEN 调用方使用 `Simulation.create` 创建场景, THEN 系统 SHALL 沿用直通指令源与无路权门禁，快照状态不出现
  `WAITING_RIGHT` 或 `HOLDING_ZONE`。
- **AC-compat-scheduled-create**:
  WHEN 调用方使用 `Simulation.create_scheduled` 创建场景, THEN 系统 SHALL 启用调度器（默认内置；注入时使用
  替换实现），同时完成路径下发、路权门禁与自动恢复。
- **AC-contract-arbiter-swap**:
  IF 用另一个调度器实现替换内置调度器，且该实现提供相同的指令源、申请/释放与区状态读取语义, THEN 系统
  SHALL 在不修改机器人本体与运动学代码的前提下产出逐 tick 相同的快照。

### 规模与场景

- **AC-scale-ten-robots-scheduled**:
  WHEN 使用扩展后的 demo 地图创建 10 台机器人，每台从不同节点起步、任意两个起始节点的中心距大于 0.70 m，
  并配置可完成路径, THEN 系统 SHALL 在 `create_scheduled` 下推进到 10 台全部 `ARRIVED`。
- **AC-scale-ten-robots-default**:
  WHEN 使用同一 10 车场景, THEN 系统 SHALL 在 `Simulation.create` 下（无路权门禁）推进到 10 台全部
  `ARRIVED`。
- **AC-scale-no-initial-overlap**:
  WHEN 10 台机器人使用 demo 的 10 个不同起始节点，且任意两个节点的中心距大于 0.70 m, THEN 首个 tick 的
  快照 SHALL 不出现原因为 `OVERLAP` 的 `E_STOP`。

## Testing

- 单元测试：调度器的排队、授予、释放、原子组、容量与排序规则；等待期间的重复申请读取；首段申请即排队的
  状态切换；`edge_zones` 派生结果与成员边列表一致。
- 集成测试：两车争一区、多区边、环形死锁、跟驰与自动恢复、初始重叠、首段申请即排队、10 车规模场景；
  10 车场景在 `create_scheduled` 与 `Simulation.create` 下分别推进到全部 `ARRIVED`；覆盖
  AC-rights-single-holder、AC-deadlock-ring-forms、AC-peers-rear-end、AC-peers-auto-resume、
  AC-scale-ten-robots-scheduled、AC-scale-ten-robots-default 与 AC-scale-no-initial-overlap。
- 契约测试：替换调度器（仲裁、指令源与区状态读取）的一致性、顺序无关性、快照兼容（既有字段与 `zones`
  默认值）；覆盖 AC-contract-arbiter-swap、AC-peers-order-independent 与 AC-snapshot-zones-default。
- 回归测试：受 demo 地图扩展影响的 `tests/test_integration_demo.py`（节点/边计数、R1/R2 改为不同起点）、
  `tests/test_benchmark.py`（10 车基准）与 `tests/test_simulation.py`（`TickSnapshot` 字段断言加入
  `zones`；同起点场景改为不同起点或断言 `OVERLAP` 的 `E_STOP`）同步更新；其余既有 pytest 套件在默认
  入口下全部通过；覆盖 AC-compat-default-create。
- 基准测试：使用扩展后的 demo 地图跑 10 车基准，10 台车使用 10 个不同起始节点，且任意两个起始节点的
  中心距大于 0.70 m，测量包含车车判定的单步耗时。

## Open Questions

无遗留问题。
