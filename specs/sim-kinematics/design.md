# Sim Kinematics Design

## Summary

本设计给调度算法工程师造一台能跑的虚拟 AMR：它在本机按差速底盘运动学沿拓扑图行驶，驶向障碍物时能在减速度约束内停
住，全程不超线速度、线加速度与转向角速度的配置上限，只有车体接触障碍那一 tick 的兜底归零除外。它是 `WI-sim-kinematics` 的交付物，同时定下另外两个 Now 项
（`WI-mutex-scheduling`、`WI-live-visualization`）必须复用的三份契约：拓扑地图数据模型、机器人状态枚举、机器人指令
接收边界。仓库里还没有代码，所以本设计一并定下包结构、运行时版本与依赖选择。

## Project Traceability

- **Project**: `projects/virtual-robot/project.md`
- **Backlog**: `projects/virtual-robot/backlog.md`
- **Work item**: `WI-sim-kinematics`

## Goals

- 单台虚拟 AMR 按差速底盘运动学沿场景配置给定的节点序列，从起点行驶到目标点并进入到达状态。
- 机器人任意 tick 的线速度、线加速度与转向角速度都不超过配置上限。唯一例外是车体与障碍接触那一 tick 的兜底归零，它的
  速度变化不受减速度上限约束。逐 tick 数值自检给出这个结论，不靠人工观察。
- 机器人驶向运行时放置的障碍物时，在最大减速度约束内停住且不与障碍物重叠；显式恢复指令能让它走完剩余路径。
- 拓扑地图数据模型一次性建模完整边属性与临界区实体，让 `WI-map-editor`、`WI-pluggable-dispatcher`、
  `WI-scale-50-robots` 不会因为本项漏字段而返工。
- 机器人状态枚举一次定义 6 个状态并冻结其语义，让路权扩展不再改动运动学层。
- 指令接收边界与机器人本体解耦：整体替换内置直通指令源时不需要改动本体代码。
- 两张内置示例地图就位，极简图供本项数值自检，demo 图供路权互斥项构造死锁。
- 10 台规模的单进程推进成本得到可复现的实测数据，用来验证 project.md 里那条尚未证实的实时性假设。

## Primary Users / Roles

- 调度算法工程师：编写场景配置、运行仿真、读取逐 tick 状态快照，判断运动学与地图契约是否符合预期。
- `WI-mutex-scheduling` 的实现者：复用本设计的地图数据模型、状态枚举与指令接收边界，替换指令源而不改本体。
- `WI-live-visualization` 的实现者：消费本设计产出的状态快照，自行决定推送与渲染节奏。

## Non-Goals

- 多车之间的路权互斥、临界区占用判定与死锁处理，`WI-mutex-scheduling` 负责。
- 机器人之间的几何重叠检测。前瞻判定只读障碍物集合，本项的机器人不会因为彼此靠近而减速，10 台规模的基准允许穿行。
- 浏览器渲染、HTTP 或 WebSocket 服务与状态推送通道，`WI-live-visualization` 负责。
- 路径规划：本项不搜索路径、不比较路线优劣，路径一律以节点序列写进场景配置。
- 地图持久化、地图文件格式与文件格式版本化，`WI-map-editor` 负责；本项地图数据是代码内置常量。
- 外部调度器接入协议，`WI-pluggable-dispatcher` 负责。
- 50 台规模的并发架构与性能优化，`WI-scale-50-robots` 负责；本项只做 10 台规模的基准测量。
- 车云通信、网络延迟与丢包，见 `PDR-comm-layer-deferred`。
- 机器人异常态与故障注入，`WI-robot-fault-states` 负责。
- 脚本化无头批量运行、事件日志导出与结果回看，见 `PDR-mvp-delivery-surface`。
- 非预期障碍物的场景编排与动态博弈触发；本项只提供障碍物的注册与注销，不提供编排语义。
- 角加速度约束：角速度按段内三角形剖面建立，不限制角速度自身的变化率。
- 车身多边形、横向偏差与路径跟踪误差。直线子阶段内 θ 恒等于该段方向，机器人质心始终落在边中心线上。
- 路宽与车型限制的通行校验，以及坡度、人机混行代价参与任何计算。本项只建模这些属性，一个都不消费。
- 传感器与感知建模；障碍物对机器人完全可见。

## Context

- 仓库当前只有 `projects/virtual-robot/project.md` 与 `projects/virtual-robot/backlog.md` 两份文件，没有代码、
  `pyproject.toml`、README 或 AGENTS.md。本设计不遵循既有模式，因为还没有模式。
- project.md 的 Confirmed Constraints 已钉死技术栈（Python 仿真内核 + Web 前端）、MVP 规模（5-10 台）、地图来源
  （代码内置示例拓扑图）和第一版不含通信层这几件事，本设计不重新讨论。
- 本机可用运行时为 Python 3.14.2（默认 `python`）与 3.13.9（`py -3`）。本设计取 3.13.9 作为开发运行时，下限 3.11，
  运行时零第三方依赖，`pytest` 是唯一开发依赖。固定方式见 Architecture 的依赖声明。
- `backlog.md` 的 Dependency Notes 规定本项先定下地图数据模型与状态集合，另外两个 Now 项随后进入澄清，避免三项重复
  决策同一份数据契约。
- project.md 风险表对本项的明确要求是边属性完整建模、MVP 只消费互斥组。本设计把路径定为配置输入，代价字段因此确实
  不进任何计算，这句约束不需要修订。

## Discovery

### Key Discoveries

- "从起点到目标点得到一串边"这件事在 backlog 里没有归属：`WI-mutex-scheduling` 把路径规划列为 Non-Goal，本项原
  Scope 也没提。本设计按用户决定把路径定为配置输入，路径规划的归属作为项目级遗留项交给 `brainstorming`。
- 单车阶段的"碰撞对象"在原 Scope 里含义不清：多车互斥被排除在外，其他机器人也不在本项。本设计确定障碍物是运行时注册
  的圆形实体，它是本项急停的唯一触发源。
- 步长与急停安全距离存在耦合：步长越大，机器人在两步之间跨过障碍边缘的可能越大。本设计因此把前瞻距离与步长挂钩，而不
  是只按刹车距离判定。
- 保证急停不把机器人带过节点的是两件事叠加：前瞻区间截断在当前段终点，以及相交兜底在接触那一 tick 立即归零。逐步接近
  时机器人停在障碍之前；障碍物在刹车距离内注册时，名义停车位置会越过障碍，兜底判定在接触时刻归零。两种收尾车体中心都不
  越过段末，因此本项不需要急停期间的段位置切换规则。
- 前瞻若只按到障碍中心的距离判定，两个方向都会出错：相邻边上的障碍物会引起本段误停，中心越过段末而近缘仍侵入本
  段的障碍又完全漏检。demo 地图是三角形环路，三边互相靠得很近，误停必然出现。因此垂直方向用中心距门槛，纵向方向
  用障碍在本段上的覆盖区间。
- 机器人质心始终贴在中心线上时，路宽与车型限制没有任何消费点：横向自由度不存在，几何约束不会生效。这是本项排除它们的
  理由，不是遗漏。
- 逐段行驶加原地转向的到达时间比真实车队偏保守，因为转角处完全停车。本设计接受这个偏差，并记进 Decision。

### Scope Decisions

- 纳入：差速底盘位姿积分、逐段速度规划与节点原地转向、圆形障碍物前瞻急停、6 状态机器人状态机、完整边属性与临界区实体的
  地图模型、两张内置示例地图、离散仿真时钟与固定步长、逐 tick 状态快照、指令接收边界、10 台规模基准测量。
- 排除：见 Non-Goals。其中路径规划与地图文件格式这两项在 Next 阶段有真实需求，分别由对应 work item 承接。边到临界区的
  反查索引同样排除在本项之外，因为本项没有读取它的行为。

## Decision Record

### DR-motion-follow-model

**Decision**: 机器人沿配置路径的边中心线逐段行驶。每条边视为一段直线，段内只做加减速，且直线子阶段内 θ 恒等于该段
方向。段末完全停车后，机器人在节点处以角速度原地转向到下一段航向，最后一步把 θ 吸附到精确的段方向再起步。接受路径时
若初始航向与第一段方向不一致，同样先做这一次原地转向。位姿由线速度 v 与角速度 ω 积分得到，直线子阶段的位移方向就是
段方向。

**Rationale**: 本项验证的是调度可用性而不是路径跟踪控制。逐段模型没有调参项、没有横向偏差，速度上限与减速度上限的断言
可以直接对每段的解析剖面核对。θ 吸附到精确值而不是停在容差窗口内，是为了保住"质心落在中心线上"这条前提：前瞻判定沿
中心线一维进行，按边判定占用的下一项也要靠它。被拒方向：边走廊内自由行驶需要路径跟踪控制器与车身几何碰撞体，MVP 成本
明显更高；参数化弧长推进不做闭环跟随，转向瞬时且没有横向自由度，不满足"位姿由 v 与 ω 积分得到"这条 Goal。

**Constraints**: 转角处完全停车使到达时间比真实车队偏保守，拿它评估调度时延会偏悲观。θ 只在转向子阶段变化，因此机器人
不会因为角度残留偏离中心线；`turn_align_tolerance_rad` 与 `arrival_tolerance_m` 因此只做浮点比较阈值，不表示允许的
偏移量。机器人质心永远落在中心线上，路宽与车型限制在本项不产生任何行为。

### DR-rotational-profile-no-angular-accel

**Decision**: 原地转向的角速度按剩余角度的三角形剖面建立，上限为 `omega_max_radps`，最后一步按剩余角度收敛并吸附到
目标航向。本项不引入角加速度上限。

**Rationale**: project.md 的 Goals 只约束最大速度、最大加速度与转向角速度三项。加一条角加速度上限会让约束集合无依据地
膨胀，也没有调用方需要它。

**Rejected concern**: 角速度在一步内从零升到上限意味着无穷角加速度，物理上不成立。

**Revisit when**: 有人用本仿真评估乘员舒适性或姿态跟踪精度，需要平滑的角速度变化时。

### DR-collision-continuous-geometry

**Decision**: 碰撞检测基于连续几何。障碍物是运行时注册的圆形实体。前瞻区间从机器人当前位置沿当前段中心线延伸，长度等
于刹车距离 `v²/(2·decel_max_mps2)`、加车体外接圆半径、再加位移余量 `v·dt`（本 tick 车速乘 dt）；区间在当前段终点截断，
不跨入下一段。判定分两步：先比垂直距离，障碍中心到该段所在直线的距离大于"障碍半径 + 车体半径"即跳过该障碍；剩下的
障碍再看它在本段上的覆盖区间 `[p − r, p + r]` 是否与前瞻区间相交，相交即请求急停。两步都成立才急停，机器人以
`decel_max_mps2` 减速到零后保持位姿；若触发时车体已经与该障碍相交，兜底判定在本 tick 直接把 v 与 ω 置零，原因记为
`OVERLAP`。

**Rationale**: 真实 AMR 的安全停止发生在接触之前，急停距离本身就该由减速度上限反推，这本来就是运动学约束符合性要覆盖
的行为。纵向判定点取障碍在本段上的最近点，一次解决两件事：半径大于 `v·dt` 的障碍不会在触发当刻已经贴上车头，中心
越过段末而近缘仍侵入本段的障碍也不会因为中心投影出界而漏检。垂直距离门槛把侧向无关的障碍物挡在判定之外，否则环路
地图上的一条边会因相邻边上的障碍误停。两个维度的参考点因此不同，纵向用覆盖区间，垂直用中心距。被拒方向：按节点或
整条边做离散封闭判定，机器人会先驶入障碍区域才停；叠加栅格障碍物层引入的分辨率本项用不上；直接比较两圆间距而不沿
中心线投影，会让相邻边上的障碍常态化误触发。

**Constraints**: 机器人被视作圆、障碍物被视作圆，判定只在当前段的中心线上沿一维进行，不检查相邻段、其他路径元素和其他
机器人。区间截断与兜底归零合起来保证一条不变量：急停期间车体中心不越过当前段终点，本项因此不需要急停中的段位置切换规则。
逐步接近的障碍必然以 `SAFETY_DISTANCE` 原因停在接触之前，`AC-estop-no-overlap` 与另两条以该原因为前提的断言才有真实
命中；已经进入刹车距离才出现的障碍仍会先接触，由兜底判定归零。兜底归零是碰撞后的制动，那一步的速度变化不受
`decel_max_mps2` 约束，也不计入运动学约束符合性的数值自检。中心落在下一段、近缘侵入本段的障碍在本段就被看见，机器人
在到达节点前停住，不会带着重叠状态停在段末。

**Rejected concern**: 把"障碍中心在下一段、近缘侵入本段"当作可接受边界，让机器人带着重叠停在节点、靠注销障碍才能脱困；
以及用创建期或注册期校验禁止在段端点邻域放置障碍，把物理上合法的摆放用规则排除掉。

**Revisit when**: 纵向判定口径需要与 `WI-mutex-scheduling` 的按边占用判定统一时，或真实地图数据证明障碍可以任意贴近段
端点摆放时。

### DR-path-supplied-by-scenario

**Decision**: 路径以节点标识序列写进场景配置，本项不含任何图搜索。序列必须首尾存在于地图，每对相邻节点之间存在方向合
规的边，且一个有序节点对唯一确定一条边。序列首标识必须等于机器人当前所在节点，起始配置下就是该机器人的 `start_node_id`。

**Rationale**: 调度验证需要把路径当可控输入，工程师要能精确指定每台车走哪几条边，才构造得出预期的互斥与死锁形状。被拒
方向：内置静态最短路会让本项实际上线路径规划，代价字段也被迫消费，跟"MVP 只消费互斥组"这条约束冲突。

**Rejected concern**: 配 5-10 台车要手写若干串节点标识，配场景变麻烦。

**Revisit when**: MVP 内出现路径规划的归属决策（见 Open Questions），或场景配置工作量成为实际瓶颈时。

### DR-robot-status-flat-enum-six

**Decision**: 机器人状态是单一扁平枚举，本项一次定义 6 个成员并冻结其语义：`IDLE`（空闲）、`MOVING`（行驶中）、
`E_STOP`（碰撞急停）、`ARRIVED`（到达）、`WAITING_RIGHT`（等待路权）、`HOLDING_ZONE`（占用临界区）。本项只产出前 4
个，后 2 个的触发归 `WI-mutex-scheduling`。

**Rationale**: 三个 Now 项共享同一份状态契约，backlog 已把依赖顺序定为本项先行。一次定死让可视化项不再跟着改枚举，也
不需要在本项实现两个用不到的状态。被拒方向：运动与调度分两层，而 MVP 只有一个消费者，分层收益无从验证；按需扩展则状态
语义要分两次定，与本项的契约职责冲突。

**Constraints**: 逐段行驶与原地转向都归入 `MOVING`，转向子阶段是机器人运行时对象上的内部字段，不是状态枚举成员。

### DR-estop-explicit-resume

**Decision**: `E_STOP` 不是终态。指令源下发 `RESUME` 且此时前瞻安全距离成立，机器人回到 `MOVING`，沿原路径的剩余部分
继续行驶。本项不实现"前方清空自动重试"，恢复只能来自显式指令。

**Rationale**: 这与真实 AMR 急停需要人工或上层复位一致，同时避免引入重试间隔、安全裕度与卡死判定这些新需求。多车场景
必然需要"停过之后再起步"，把它放在指令接收边界上，`WI-mutex-scheduling` 就不必为此新增语义。

**Rejected concern**: 障碍物持续在场时，恢复指令会立刻再次触发急停，形成人工反复下发。

**Revisit when**: 需要无人值守批量跑场景时，对应 `WI-scripted-scenarios`。

### DR-critical-zone-entity

**Decision**: 临界区是地图数据里的独立实体，持有标识、名称、成员边标识列表与容量。边不存临界区字段，成员边列表是边与
临界区关系的唯一来源。本项不生成边到临界区的反查索引。

**Rationale**: 路权申请与释放需要一个明确对象，可视化需要一个能标记的实体，后续把容量改成大于 1、或让一个临界区跨更多
边，都不必改结构。被拒方向：把分组标识写在边上，枚举全部临界区要遍历整张图，临界区级属性只能往边上重复抄写。

**Constraints**: 本项不消费该实体，只做构建期的标识存在性校验；`capacity` 的语义由 `WI-mutex-scheduling` 定义。边到
临界区的反查索引由 `WI-mutex-scheduling` 建立，本项没有任何读取它的行为，预先交付只会留下一份无人使用的结构。

### DR-discrete-sim-clock

**Decision**: 仿真时钟离散，由调用方驱动。内核提供推进一个步长的能力，每步让每台机器人各推进一次，不读真实时间、不做
sleep 对齐。步长固定，默认 0.02 秒，可配置但不得超过 0.05 秒。

**Rationale**: 测试需要瞬间跑完数千步并逐 tick 断言，等真实时间流过就没法把数值自检写成断言。倍速与暂停的语义留给调用
方表达，也就是每秒调用多少次推进。被拒方向：内核自带 wall-clock 循环，把倍速语义塞进内核；本项就实现驱动循环，等于交
付一个真实需求尚未验证的东西。

**Constraints**: 一次推进调用必须在同一个 tick 内更新完全部机器人，快照才是一致的时间切面。

### DR-delivery-surface-library-pytest

**Decision**: 本项交付 Python 内核库与 `pytest` 测试套件，不提供 CLI，不提供网络服务。急停距离、约束上限与轨迹端点的
验收证据来自测试：跑一遍场景配置，逐 tick 断言约束并输出快照。

**Rationale**: `PDR-mvp-delivery-surface` 已决定 MVP 只交付浏览器内手动启动与观察，脚本化无头运行推到 Next。浏览器观
察归 `WI-live-visualization`，本项不需要一个下一项要重做的临时入口。

**Rejected concern**: 工程师不改代码就跑不起一台车，看不了轨迹。

**Revisit when**: `WI-live-visualization` 落地后仍缺乏直观观察手段，或 `WI-scripted-scenarios` 启动时。

### DR-edge-attributes-placeholder

**Decision**: 边一次性建模方向性、路宽、车型标签与三项代价属性（距离、坡度、人机混行）。除方向性外，其余字段本项一个
都不读。取值范围与量纲由本设计自定占位，并在字段说明里显式标注"未经真实系统校准"。距离代价不存字段，取端点坐标派生的
几何长度。

**Rationale**: project.md 风险表要求边属性在本项建模完整，否则 Next 阶段三项共用这份数据时要返工。真实的车型清单与坡
度口径无法从本仓库检索，用户已确认由本设计自定占位。被拒方向：只建模方向性与临界区，实现量最小但直接违反该约束。

**Rejected concern**: 距离代价存字段会与端点几何打架，中心线长度由坐标唯一决定。

**Revisit when**: `WI-map-editor` 进入澄清，或拿到现有调度系统的地图导出样例时，需重新校准类型、量纲与取值范围。

### DR-dispatcher-intake-boundary

**Decision**: 机器人通过指令接收边界接受外部指令，指令载荷只有 `ASSIGN_PATH`（下发节点序列）与 `RESUME`（急停后恢复）
两种，且各自只在特定状态受理：`ASSIGN_PATH` 只在 `IDLE` 与 `ARRIVED` 受理，`RESUME` 只在 `E_STOP` 受理，状态不匹配就
返回无效状态拒绝。本项内置一个直通指令源，在某台机器人的 `start_tick` 把配置里的节点序列作为 `ASSIGN_PATH` 下发。本项
不定义路权申请、授予、释放与超时指令。

**Rationale**: `PDR-scheduling-ownership` 要求指令接口可替换，而路权指令的最小契约范围已被 backlog 明确划给
`WI-mutex-scheduling` 澄清。本项只钉住"机器人接收什么、在哪个状态接收"这条边界，不预定义下一项的指令集合。急停中不受理
改道有具体原因：急停点通常落在段中间，而 `ASSIGN_PATH` 要求序列首节点等于机器人当前所在节点。受理它就得先为停在段中间
的机器人发明一套路径接入语义，那是下一项的决定，不是本项验收需要的行为。

**Rejected concern**: 让调度器在机器人急停时直接改道脱困，不必等障碍移除。

**Revisit when**: `WI-mutex-scheduling` 需要"卡住的机器人换一条预置路径脱离"这类行为时。

**Constraints**: 替换指令源必须保持同一场景的状态输出一致，这条一致性由本项的契约测试固定。

## Proposed Solution

### Architecture

Python 包采用 src 布局，运行时零第三方依赖。模块与依赖方向如下，箭头指向被依赖方：

```text
scenario ─────> map_model <───── safety
   │               ^               │
   │               │               v
   v             robot ──> controller ──> kinematics
simulation ───────┘ │                      obstacle_field
   │                v
   └──────────> snapshots
```

- `map_model`：节点、边、临界区三类数据对象，两张内置示例地图，构建期校验与派生索引生成。
- `kinematics`：差速底盘位姿积分，只有它持有 v 与 ω 到 x、y、θ 的映射。
- `controller`：逐段梯形速度规划与节点原地转向，产出本 tick 的目标 v 与 ω。
- `safety`：圆形障碍物的前瞻安全距离判定，产出急停请求与触发原因。
- `robot`：持有位姿、速度与状态枚举，接收指令，执行状态转移，每 tick 依次调用 safety、controller、kinematics。
- `simulation`：离散时钟，按 tick 推进全部机器人并收集快照；持有指令源实现。
- `scenario`：场景配置对象与创建期的配置校验。
- `obstacle_field`：持有当前生效的障碍物集合，负责注册与注销请求的半径与标识校验。
- `snapshots`：不可变的逐 tick 状态快照。
- `controller` 与 `safety` 都读 `map_model` 的边几何与派生长度，不各自再算一份。

运行时与依赖固定在 `pyproject.toml` 里：`requires-python` 取 `>=3.11`，`pytest` 写在开发依赖组。本机默认 `python`
是 3.14.2，所以开发虚拟环境用 `py -3 -m venv` 创建，测试通过虚拟环境里的解释器运行，不直接依赖系统 `python`。

下游 work item 的接入点只有两处：换掉 `simulation` 持有的指令源实现，以及消费 `snapshots` 输出。

### Components

- `scenario` + 仿真创建调用 → 读取地图标识与 dt，校验配置合法性 → 产出仿真实例与机器人集合；配置非法时报错并列出全部
  违规字段。
- 内置直通指令源 + 到达某台机器人的 `start_tick` → 把该机器人 `planned_node_path` 原样放进指令载荷 → 通过
  IF-PROTO-robot-command-intake 下发 `ASSIGN_PATH`；机器人只认载荷里的序列，不读配置字段。序列不可用时拒绝这次下发，
  机器人保持 `IDLE`。
- `robot` + 每 tick 被 `simulation` 调用一次 → 输入当前位姿、剩余段长与障碍物集合 → 依次做安全判定、控制量计算与位姿
  积分 → 产出新位姿、新状态与本 tick 实际执行的速度值。
- `safety` + 每 tick 判定（急停减速途中同样执行）→ 输入当前段中心线、车体半径与全部障碍物 → 先试两圆相交，未相交时
  再按垂直距离跳过侧向障碍、看障碍在本段上的覆盖区间是否与前瞻区间相交 → 输出是否请求急停与原因
  （`SAFETY_DISTANCE` 或 `OVERLAP`），没有请求时原因取 `NONE`。
- `controller` + 每 tick 计算 → 输入当前段剩余长度或剩余转向角与 `chassis-config` → 输出满足各上限的目标 v 与 ω。
- `kinematics` + 每 tick 积分 → 输入 v、ω 与 dt → 输出新位姿；直线子阶段的位移方向取该段方向。
- `simulation` + 每次推进结束 → 输出全体机器人的状态快照，含位姿、速度、状态与急停原因。
- 调用方 + 运行中注册或注销障碍物 → 通过 IF-PROTO-obstacle-registration 提交给 `obstacle_field` → 从下一个 tick 起
  参与安全判定。

### Data Model

#### Change Summary

| Change | Layer | Object | Purpose | Source |
|--------|-------|--------|---------|--------|
| ADD | Domain | `map-node` | 拓扑节点与平面坐标 | DR-motion-follow-model |
| ADD | Domain | `map-edge` | 边与全部边属性字段 | DR-edge-attributes-placeholder |
| ADD | Domain | `map-critical-zone` | 临界区实体与成员边 | DR-critical-zone-entity |
| ADD | Domain | `topology-map` | 地图聚合与派生索引 | DR-edge-attributes-placeholder |
| ADD | Domain | `map-minimal-example` | 供数值自检的极简示例地图 | DR-delivery-surface-library-pytest |
| ADD | Domain | `map-demo-example` | 供死锁构造的 demo 示例地图 | DR-critical-zone-entity |
| ADD | Domain | `obstacle` | 运行时圆形障碍物 | DR-collision-continuous-geometry |
| ADD | Domain | `chassis-config` | 电机物理约束上限 | DR-rotational-profile-no-angular-accel |
| ADD | Domain | `robot-spec` | 机器人静态配置 | DR-path-supplied-by-scenario |
| ADD | Domain | `robot-instance` | 机器人运行时对象 | DR-robot-status-flat-enum-six |
| ADD | Domain | `motion-command` | 指令接收边界的载荷 | DR-dispatcher-intake-boundary |
| ADD | Serialized | `tick-snapshot` | 逐 tick 状态输出 | DR-discrete-sim-clock |

#### Domain / Serialized Models

##### [ADD] map-node

- `node_id: str` — 稳定语义标识，示例地图取 `N01` 形式；在一张地图内唯一。
- `x: float`、`y: float` — 平面坐标，单位米，占位范围 0 到 200。

##### [ADD] map-edge

- `edge_id: str` — 唯一标识，示例地图取 `E01` 形式。
- `from_node_id: str`、`to_node_id: str` — 端点，必须存在于所属地图节点集合。
- `direction: EdgeDirection` — `FWD` 表示只允许 `from → to`，`BOTH` 表示双向。需要仅反向通行的边时交换两个端点表达。
- `lane_width_m: float` — 路宽，单位米，占位范围 1.0 到 6.0，默认 2.0。本项不读。
- `vehicle_classes: frozenset[str]` — 允许通行的车型标签集合，占位取值取自 `{"AMR-500","AMR-1000","FORK"}`，空集合表示
  不限车型。本项不读，也不校验机器人与边是否匹配。
- `cost_slope_percent: float` — 坡度代价，带符号百分比，占位范围 -15.0 到 15.0，默认 0.0。本项不读。
- `cost_mixed_traffic: MixedTrafficClass` — 人机混行等级枚举 `NONE`/`LOW`/`MID`/`HIGH`，默认 `NONE`。本项不读。
- 距离代价不存字段，取端点坐标派生的几何长度；这个属性的值以坐标为唯一真相。

##### [ADD] map-critical-zone

- `zone_id: str` — 唯一标识，示例地图取 `Z01` 形式。
- `name: str` — 供下游展示与日志使用。
- `edge_ids: tuple[str, ...]` — 成员边，长度至少为 1，每个标识必须存在于所属地图边集合。边与临界区的关系只有这一处来源。
- `capacity: int` — 容量，默认 1。本项校验它大于等于 1，但不读它的值。

##### [ADD] topology-map

- `map_id: str` 与 `nodes`、`edges`、`zones` 三个集合，集合内按标识唯一。
- `edge_length_m` — 每条边的几何长度，构建期由端点坐标派生，只读。
- `edge_by_node_pair` — 有序节点对到边的索引，构建期生成，路径可用性判定读它。

##### [ADD] map-minimal-example

- 用途是让约束上限的断言能解析算出，因此坐标全取整数、只有一条直线段加一个直角弯。
- 形状：`N01(0,0) → N02(10,0) → N03(10,5)`，两条 `BOTH` 边 `E01`、`E02`，长度分别为 10.0 米与 5.0 米。
- 不含临界区实体，本项不在它上面断言任何互斥语义。
- 急停用例在 `E01` 上距 `N01` 5.0 米处放一个半径 0.2 米的障碍物；跨段端点用例把同一个障碍移到距 `N01` 10.05 米处，
  即中心落在 `E02` 一侧、近缘仍在 `E01` 内。两组坐标与半径是断言的输入：默认参数下机器人都必须先减速才能停住，停稳时
  车体圆与障碍圆不相交、原因取 `SAFETY_DISTANCE`。

##### [ADD] map-demo-example

- 用途是给 `WI-mutex-scheduling` 一张能触发多车互相等待的地图，本项只验证它能通过构建期校验。
- 形状：一个三角形环路 `N01 → N02 → N03 → N01`，另接一条支路和一个由多条短边组成的转角链，用来覆盖折线弯道的表达。
- 环上三条边各属一个互不相同的临界区（`Z01`、`Z02`、`Z03`，容量均为 1），构成环形依赖的形状。
- 至少一条边取 `FWD`，用来覆盖单向边校验；至少一条边的 `lane_width_m`、`cost_slope_percent` 与
  `cost_mixed_traffic` 取非默认值，用来覆盖占位字段的读写。
- 10 台规模的基准场景就跑在这张地图上，形态见 AC-bench-step-cost-measured。

##### [ADD] obstacle

- `obstacle_id: str` — 场景内唯一。
- `center_x: float`、`center_y: float` — 平面坐标，单位米。
- `radius_m: float` — 半径，必须大于 0，占位上限 5.0。

##### [ADD] chassis-config

- `v_max_mps: float` — 线速度上限，开区间 0 到 3.0，默认 1.5。
- `a_max_mps2: float` — 常规线加减速上限，开区间 0 到 2.0，默认 0.8。直线子阶段的速度上升与段末主动减速都受它约束。
- `decel_max_mps2: float` — 急停减速度上限，开区间 0 到 3.0，默认 1.5。它限定以 `SAFETY_DISTANCE` 进行的减速过程，
  也用于反推刹车距离；车体接触障碍那一 tick 的兜底归零不受它约束。
- `omega_max_radps: float` — 转向角速度上限，开区间 0 到 3.0，默认 1.2。
- `body_radius_m: float` — 车体外接圆半径，开区间 0 到 2.0，默认 0.35。前瞻的垂直门槛与相交兜底都读它。
- `turn_align_tolerance_rad: float` — 对齐完成判定阈值，默认 0.02。`controller` 在转向子阶段用剩余角与它比较来判定
  完成，并在同一步把 θ 设为精确的段方向；它不表示允许的横向偏移。它与 dt 的比值受创建期校验约束，见
  Constraints and Indexes。
- `arrival_tolerance_m: float` — 浮点比较阈值，默认 0.02。`controller` 用剩余段长与它比较来判定段末切换，`robot` 用它
  判定最后一段走完即到达。

##### [ADD] robot-spec

- `robot_id: str` — 场景内唯一。
- `chassis: ChassisConfig` — 该车的物理约束。
- `vehicle_class: str` — 车型标签，占位取值同上。本项只用它检查配置完整性，不做通行校验。
- `start_node_id: str`、`start_theta_rad: float` — 初始位姿所在节点与初始航向。
- `planned_node_path: tuple[str, ...]` — 长度至少为 2，首标识必须等于 `start_node_id`。它只是内置直通指令源的初始下发
  内容；机器人运行时只认 `motion-command.node_path`，替换指令源下发不同序列时以载荷为准，这个字段随之失去参考意义。
- `start_tick: int` — 内置直通指令源在第几个 tick 下发这条路径，默认 0。

##### [ADD] robot-instance

- `spec: RobotSpec` 与 `pose`（`x`、`y`、`theta`）— theta 归一化到 -π 到 π 的左闭右开区间。
- `v_mps: float`、`omega_radps: float` — 上一个 tick 实际执行的速度值。
- `status: RobotStatus` — 6 成员枚举之一，见 DR-robot-status-flat-enum-six。
- `path_edge_ids: tuple[str, ...]` 与 `segment_index: int` — 由受理的 `ASSIGN_PATH` 载荷转换而来，配置字段不直接参与。
- `segment_remaining_m: float`、`turn_remaining_rad: float` — 当前段的剩余直线长度与剩余转向角。两者互斥，取值不为零的
  那个表示机器人处于直线子阶段还是转向子阶段。
- `estop_reason: EStopReason` — `NONE`/`SAFETY_DISTANCE`/`OVERLAP`，非急停状态时恒为 `NONE`。

##### [ADD] motion-command

- `kind: CommandKind` — `ASSIGN_PATH` 或 `RESUME`。
- `robot_id: str` — 目标机器人。
- `node_path: tuple[str, ...]` — `ASSIGN_PATH` 时必填，`RESUME` 时必须为空。受理状态门禁见 DR-dispatcher-intake-boundary。

##### [ADD] tick-snapshot

- `tick_index: int` 与 `sim_time_s: float` — 从 0 开始，每推进一次时间增加一个 dt。
- `robots: tuple[RobotSnapshot, ...]` — 按 `robot_id` 升序排列，让输出与内部迭代顺序无关。
- `RobotSnapshot` 含 `robot_id`、位姿三分量、`v_mps`、`omega_radps`、`status`、`estop_reason`。
- 快照不可变，不含临界区占用字段。临界区可视化要用的扩展，等 `WI-mutex-scheduling` 与
  `WI-live-visualization` 一起决定。

#### Constraints and Indexes

- `node_id`、`edge_id`、`zone_id`、`robot_id`、`obstacle_id` 在各自集合内唯一，重复即构建失败。
- 一个有序节点对至多一条边。本项不支持平行边，构建期校验并报错。
- 边的端点、临界区的成员边必须存在于同一张地图，缺失即构建失败。
- 两张内置示例地图的标识固定为 `minimal` 与 `demo`，加载入口只认这两个值。
- demo 地图必须至少含一个临界区实体；极简地图必须不含临界区实体。
- `capacity`、`lane_width_m`、`radius_m` 与底盘各上限必须落在各自声明的范围内。
- `turn_align_tolerance_rad` 除以 dt 不大于该车的 `omega_max_radps`。吸附那一步的角度变化不超过阈值，若阈值除以 dt
  超过角速度上限，完成对齐的这一步本身就会违反角速度约束。校验发生在仿真实例创建时，因为 dt 属于场景而非底盘配置。
- `edge_by_node_pair` 是构建期生成的只读派生索引，不作为可写字段存在；本项不生成边到临界区的反查索引。

#### Concurrency and Consistency

- 本项单线程离散推进，一个 tick 内所有机器人顺序更新，无并发与竞态。
- 数据对象构建后不可变；运行时可变状态只存在于 `robot-instance`，且归所属仿真实例独占。
- 同一份场景配置两次运行必须得到逐 tick 完全一致的输出，因为推进路径既没有随机源也不读真实时间。

### Interfaces

#### Change Summary

| Change | Kind | Contract ID | Producer | Consumer | Compatibility |
|--------|------|-------------|----------|----------|---------------|
| ADD | Protocol | `IF-PROTO-robot-command-intake` | 指令源 | 机器人 | 新契约，`WI-mutex-scheduling` 之后追加指令类型 |
| ADD | Protocol | `IF-PROTO-sim-step-advance` | 调用方（测试、后续前端服务） | 仿真内核 | 新契约，快照只增字段 |
| ADD | Protocol | `IF-PROTO-obstacle-registration` | 场景调用方 | `obstacle_field` | 新契约 |

- **HTTP APIs**: No changes — 本项不提供任何 HTTP 接口，见 DR-delivery-surface-library-pytest。
- **Messages**: No changes — 本项不引入消息通道，状态推送归 `WI-live-visualization` 定义。
- **内部模块调用**: `robot` 与 `safety`、`controller`、`kinematics` 之间的调用是同一内核内部的拆分，没有外部调用方会独立
  消费，因此不列为契约；它们的输入输出在 Components 与 Key Mechanisms 中定义。

#### Protocols

##### [ADD] IF-PROTO-robot-command-intake

- **Direction**: 指令源 -> 机器人。
- **Command / Opcode**: `ASSIGN_PATH`、`RESUME`。
- **Framing / Payload**: 进程内同步调用的 `motion-command` 对象，字段见该对象。
- **ACK / Timeout / Retry**: 同步返回受理结果。两种指令都有受理状态门禁：`ASSIGN_PATH` 只在 `IDLE` 与 `ARRIVED` 受理，
  `RESUME` 只在 `E_STOP` 受理，状态不匹配返回无效状态拒绝。路径不可用时返回结构化错误，含被拒原因与涉及的节点标识。
  这条调用没有超时概念，也没有重试：指令源在下一个 tick 自行改发或重发。
- **Versioning**: `WI-mutex-scheduling` 之后追加指令类型，追加不改变现有两种类型的语义与受理状态门禁。

##### [ADD] IF-PROTO-sim-step-advance

- **Direction**: 调用方 -> 仿真内核。
- **Command / Opcode**: 创建仿真实例、推进一个步长。
- **Framing / Payload**: 创建时输入 `scenario` 配置对象；推进时无入参，返回本 tick 的 `tick-snapshot`。
- **ACK / Timeout / Retry**: 两处都同步返回。创建时 dt 非法、`map_id` 不在内置两张地图之内或配置校验失败即返回错误，
  不产出半成品的仿真实例。全部机器人都已到达或急停之后，推进调用仍返回快照，调用方据此自己结束循环。
- **Versioning**: 快照字段只增不改，新增字段必须带默认值，让既有消费方读法不受影响。

##### [ADD] IF-PROTO-obstacle-registration

- **Direction**: 场景调用方 -> `obstacle_field`。
- **Command / Opcode**: 注册障碍物、注销障碍物。
- **Framing / Payload**: 注册输入 `obstacle` 对象，注销输入 `obstacle_id`。
- **ACK / Timeout / Retry**: 同步返回受理结果。半径非法或标识重复时拒绝并返回原因，障碍物集合不变；注销一个不存在的
  标识时返回未找到，集合同样不变。注册成功自下一个 tick 起对所有机器人可见。把障碍物注册在某台机器人前方的刹车距离内
  不算错误，受理照常成功，后果是该机器人由相交兜底在接触时刻归零，原因记为 `OVERLAP`。
- **Versioning**: 本项不定义非圆形障碍物，`WI-corner-case-injection` 之后决定要不要扩展形状。

### State Machines

| Current state | Trigger / Guard | Target state | Side effects |
|---------------|-----------------|--------------|--------------|
| `IDLE` | `ASSIGN_PATH`，序列可用、首节点等于当前节点且航向已与第一段方向对齐 | `MOVING` | 记录路径边序列，置第一段剩余长度，`estop_reason` 为 `NONE` |
| `IDLE` | `ASSIGN_PATH`，序列缺边、逆行或含未知节点 | `IDLE` | 返回结构化拒绝并列出全部违规项，位姿与速度不变 |
| `IDLE` | `ASSIGN_PATH`，首节点不等于机器人当前节点 | `IDLE` | 返回结构化拒绝，错误中至少给出两侧节点标识 |
| `IDLE` | `ASSIGN_PATH` 可用但初始航向偏离第一段方向 | `MOVING` | 进入起始节点的转向子阶段，剩余段长在转向完成后设置 |
| `ARRIVED` | `ASSIGN_PATH`，序列可用且首节点等于当前节点 | `MOVING` | 覆盖原路径与段位置；航向与第一段不一致时先转入转向子阶段，再起步 |
| `ARRIVED` | `RESUME` | `ARRIVED` | 返回无效状态拒绝，位姿与速度不变 |
| `MOVING` | 走完最后一段直线部分且线速度归零 | `ARRIVED` | v 与 ω 置零，`segment_index` 停在末段 |
| `MOVING` | 前瞻判定安全距离不足，且车体尚未与障碍相交 | `E_STOP` | `estop_reason` 记为 `SAFETY_DISTANCE`，本 tick 起按 `decel_max_mps2` 减速 |
| `MOVING` | 车体圆与障碍圆相交 | `E_STOP` | `estop_reason` 记为 `OVERLAP`，v 与 ω 立即置零 |
| `MOVING` | `RESUME` | `MOVING` | 返回无效状态拒绝，本 tick 行为不变 |
| `E_STOP` | `RESUME`（载荷 `node_path` 为空）且按该车 `v_max_mps` 的名义前瞻安全距离成立 | `MOVING` | 从静止重新按剖面加速，路径与段位置保持不变 |
| `E_STOP` | `RESUME` 但名义前瞻安全距离不成立 | `E_STOP` | `estop_reason` 更新为该次判定的原因（仍与障碍相交时为 `OVERLAP`，否则 `SAFETY_DISTANCE`），位姿不变 |
| `E_STOP` | `RESUME` 携带非空 `node_path` | `E_STOP` | 返回载荷形状结构化拒绝，路径、位姿与速度都不变 |
| `E_STOP` | `ASSIGN_PATH` | `E_STOP` | 返回无效状态拒绝，路径、位姿与速度都不变 |
| `E_STOP` | 速度尚未归零时前瞻判定再次成立，且车体尚未与障碍相交 | `E_STOP` | 保持急停，不重复累计触发次数 |
| `E_STOP` | 减速途中两圆开始相交 | `E_STOP` | `estop_reason` 由 `SAFETY_DISTANCE` 改为 `OVERLAP`，v 与 ω 立即置零 |
| `E_STOP` | 急停减速使 `segment_remaining_m` 归零 | `E_STOP` | 不做段位置切换。段内截断口径下该情形不成立，出现即为实现错误 |

`WAITING_RIGHT` 与 `HOLDING_ZONE` 的进入与退出转移不在本项，`WI-mutex-scheduling` 负责定义。

### Key Mechanisms

#### 逐段行驶与节点转向

机器人在一段内先按梯形剖面加速、巡航、再减速，段末主动减速受 `a_max_mps2` 约束：剩余长度不足以按该上限停住时立即转入
减速。段末速度归零后进入转向子阶段，按三角形剖面原地旋转到下一段航向。剩余角不大于 `turn_align_tolerance_rad` 即判定
对齐完成，`controller` 在同一步把 θ 设为精确的段方向，这是全文唯一的对齐完成判定条件。吸附那一步的角度变化不超过该阈值，
所以创建期校验要求 `turn_align_tolerance_rad` 除以 dt 不大于 `omega_max_radps`。转向完成后切换到下一段，直线子阶段内 θ
不再变化，位移方向就是段方向。接受路径时若当前航向与第一段方向不一致，也先走一遍这个转向子阶段，再开始直线行驶。最后
一段的直线部分走完即判定到达，判定依据是剩余段长小于 `arrival_tolerance_m`；到达后不再有转向。

#### 前瞻安全距离

每个 tick 先算刹车距离 `v²/(2·decel_max_mps2)`，加上车体半径和位移余量 `v·dt`，得到前瞻长度。前瞻区间从机器人当前位置
沿当前段中心线延伸，到该段终点为止，不跨入下一段。判定分两步：障碍中心到该段所在直线的垂直距离大于"障碍半径 + 车体
半径"时先跳过；剩下的障碍看它在本段上的覆盖区间 `[p − r, p + r]` 与前瞻区间是否相交，相交即请求急停。垂直门槛用中心距，
纵向门槛用覆盖区间，两个维度的参考点不同：垂直门槛保证相邻边上的障碍不引起本段误停，纵向用覆盖区间则让半径较大的障碍
不会在触发当刻已经贴上车头，也让中心越过段末而近缘仍在本段内的障碍不漏检。

车体圆与障碍圆相交是兜底判定，每个 tick 都先试一次，包括机器人已经处于 `E_STOP` 的减速途中。相交成立时本 tick 把 v 与
ω 置零，原因取 `OVERLAP`，不再进入安全距离分支；未相交时才看前瞻区间。兜底归零是碰撞后的制动，那一步的速度变化不受
`decel_max_mps2` 约束，也不参与急停减速度的数值自检，两条分支因此在一个 tick 内互斥。

急停有两种收尾。障碍在刹车距离之外、机器人逐步接近时，前瞻先触发，机器人按 `decel_max_mps2` 减速并停在障碍之前。障碍
在机器人已经进入自身刹车距离时才注册时，相交判定先成立，机器人在接触那一 tick 归零，原因取 `OVERLAP`。中心落在下一段
而近缘侵入本段的障碍属于前一种收尾：它的本段最近点就是近缘，机器人在到达节点之前就停住。两种收尾都满足同一条不变量：
车体中心不越过当前段终点。障碍在本段上的最近点不超过段末，兜底归零又不晚于接触时刻，因此车体中心必然停在段末之前，
本项不需要急停期间的段位置切换规则。

恢复指令的前瞻判定不按当前的 0 速度，而按该车的 `v_max_mps` 取名义速度：静止机器人的刹车距离为 0，前瞻区间只剩车体
半径，任何以 `SAFETY_DISTANCE` 停稳的位置都会被判定为可恢复，机器人会起步再立刻重新触发急停，正落在
DR-estop-explicit-resume 要回避的"人工反复下发"上。每 tick 的常规判定仍使用当前速度，两个口径互不替代。

#### 快照一致性

一个 tick 内先让每台机器人依次完成安全判定、控制量计算与位姿积分，再统一收集快照。快照按 `robot_id` 升序排列，内容全
是本 tick 结束后的值，所以同一 tick 的快照不受机器人迭代顺序影响。

### Data Flow

1. 调用方通过 IF-PROTO-sim-step-advance 创建仿真实例，输入场景配置。`scenario` 先校验 `map_id`、dt、机器人配置与路径
   形状，`simulation` 再按 `map_id` 取对应的内置地图，`map_model` 校验节点、边与临界区的完整性，返回仿真实例，或在任一
   校验失败时返回具体错误项。
2. 调用方每次通过 IF-PROTO-sim-step-advance 推进一个 tick；`simulation` 先把仿真时间前进一步，再逐台机器人处理。
3. 到达某台机器人的 `start_tick` 时，内置直通指令源通过 IF-PROTO-robot-command-intake 下发 `ASSIGN_PATH`。机器人此刻
   处于 `IDLE`，`robot` 用 `edge_by_node_pair` 校验首节点等于当前节点、每对相邻节点的边存在且方向合规：通过则进入
   `MOVING`，失败则返回结构化错误并保持 `IDLE`。
4. 每个 tick `robot` 先调用 `safety`，输入当前段中心线、车体半径与障碍物场。`safety` 先做兜底相交判定：车体圆已与某个
   障碍圆相交时，本 tick 把 v 与 ω 置零，原因取 `OVERLAP`，`robot` 转入 `E_STOP` 并跳过控制量计算。未相交时再按垂直距离
   跳过侧向障碍，判断障碍在本段上的覆盖区间 `[p − r, p + r]` 是否与前瞻区间相交；相交即请求急停，`robot` 转入
   `E_STOP`，只按 `decel_max_mps2` 递减速度。
   区间截断与兜底归零共同保证减速期间车体中心不越过当前段终点。
5. 没有急停请求时 `robot` 调用 `controller`，输入剩余段长或剩余转角与 `chassis-config`，产出满足各上限的目标 v 与 ω。
   段末主动减速受 `a_max_mps2` 约束。
6. `robot` 调用 `kinematics`，输入目标 v、ω 与 dt，积分出新的 x、y 与归一化 θ。直线子阶段的位移方向取该段方向，转向子
   阶段位移不变。
7. `robot` 检查转移条件：段末归零即转入转向子阶段，末段直线走完即转 `ARRIVED`。随后 `simulation` 收集全部机器人的
   `RobotSnapshot`，按 IF-PROTO-sim-step-advance 的返回结构交给调用方。
8. 调用方在运行中通过 IF-PROTO-obstacle-registration 注册或注销圆形障碍物；`obstacle_field` 校验半径与标识唯一性后
   生效，下一个 tick 的第 4 步即读到变化。非法请求返回结构化错误，集合不变。

## Error Handling

- 地图构建期错误：标识重复、边端点缺失、临界区成员边缺失、同一有序节点对出现两条边、`capacity` 或其他数值字段越界。
  检测发生在 `topology-map` 构建时，整个仿真实例创建失败，错误信息指出具体对象与字段，不产出半成品地图。
- 场景配置错误：`map_id` 不是 `minimal` 或 `demo`、机器人起始节点不存在、路径长度小于 2、路径首标识与 `start_node_id`
  不一致、dt 小于等于 0 或超过 0.05、底盘各上限小于等于 0、`turn_align_tolerance_rad` 除以 dt 超过该车
  `omega_max_radps`。检测发生在 `scenario` 的创建期校验，创建失败并列出全部违规项，不只报第一个。
- 路径不可用：节点序列含地图中不存在的节点、相邻节点对没有边、有边但逆行单向边、首节点与机器人当前所在节点不一致。多个
  问题在同一 tick 成立时一次返回全部违规项。检测发生在 `ASSIGN_PATH` 受理时，机器人保持原状态，指令返回结构化拒绝，
  指令源可以修正后重发。
- 无效恢复：非 `E_STOP` 状态收到 `RESUME`，返回无效状态拒绝，机器人本 tick 行为不变。
- 急停中改道：`E_STOP` 状态收到 `ASSIGN_PATH`，返回无效状态拒绝，路径、位姿与速度都不变。要先恢复，机器人才可能接受
  新路径；恢复不安全时按下一条立即回到 `E_STOP`。
- 不安全恢复：`E_STOP` 状态下恢复时安全距离仍不成立，机器人立即回到 `E_STOP`。这是合法转移而不是错误，位姿不变。
- 急停时已接触：两类成因。一是障碍物在某台机器人已经进入自身刹车距离后才注册，下一个 tick 就满足相交或前瞻条件；二是
  离散步长让机器人在一步内跨过障碍边缘。检测都在 `safety` 的相交兜底，每个 tick 都执行，包括机器人已经在 `E_STOP`
  减速途中；行为是立即把 v 与 ω 置零、
  `estop_reason` 记为 `OVERLAP`，车体与障碍处于接触状态，该步的速度变化不受 `decel_max_mps2` 约束。第一类与 dt 取值无关，
  减半 dt 也不能避免。场景级测试只在预置障碍的场景里断言这个原因不出现；迟注册场景不在该断言范围内，本项不为此修改
  注册接口的受理条件。
- 障碍跨段端点：障碍中心落在下一段、覆盖区间仍与本段相交。这不是错误，本段把它当作最近点不超过段末的障碍参与前瞻
  判定，机器人在到达节点之前以 `SAFETY_DISTANCE` 停住。注册时机已经晚于接触时，按上一条由相交兜底归零。
- 初始重叠：机器人初始位姿与场景初始障碍物集合相交。实例创建照常成功，但机器人第一个 tick 即处于 `E_STOP`，原因记为
  `OVERLAP`。
- 障碍物注册错误：半径小于等于 0 或标识重复，返回结构化拒绝，集合不变。注销不存在的标识返回未找到，集合同样不变。
- 以上错误都不产生部分写入：地图构建、仿真创建与障碍物注册三处都是先完整校验、再一次生效。

## Acceptance Criteria

### 运动学与行驶

- **AC-kinematics-pose-integration**:
  WHEN 机器人在一个 tick 内以目标线速度 v 与角速度 ω 行驶, THEN 系统 SHALL 按差速底盘模型更新 x 与 y，并把 θ 归一化到
  -π 到 π 的左闭右开区间。
- **AC-kinematics-no-cross-track-drift**:
  WHEN 机器人处于直线子阶段, THEN 系统 SHALL 使 θ 恒等于该段方向，位姿沿该段中心线推进，不产生横向偏移。
- **AC-kinematics-segment-end-stop**:
  WHEN 机器人走完当前段的直线部分, THEN 系统 SHALL 把线速度归零并切换到该节点的原地转向子阶段，状态仍为 `MOVING`。
- **AC-kinematics-turn-no-overshoot**:
  IF 剩余转向角不大于 `turn_align_tolerance_rad`, THEN 系统 SHALL 判定对齐完成，在同一步把 θ 设为精确的段方向，且该步
  隐含的角速度不超过 `omega_max_radps` 加上判定容差。
- **AC-kinematics-first-turn-align**:
  WHEN 机器人接受路径后当前航向与第一段方向不一致, THEN 系统 SHALL 先在所在节点原地转向到第一段方向，再开始直线行驶。
- **AC-kinematics-arrival**:
  WHEN 机器人走完路径最后一段的直线部分且线速度归零, THEN 系统 SHALL 把状态置为 `ARRIVED` 并把 v 与 ω 置零。

### 约束符合性

- **AC-kinematics-linear-speed-bound**:
  WHEN 调用方在任意 tick 读取任意机器人的线速度, THEN 系统 SHALL 使它不超过该车的 `v_max_mps` 加上判定容差。
- **AC-kinematics-linear-accel-bound**:
  WHEN 相邻两个 tick 之间线速度上升, THEN 系统 SHALL 使上升量不超过 `a_max_mps2` 乘 dt 加上判定容差。
- **AC-kinematics-normal-decel-bound**:
  WHEN 机器人处于段末主动减速过程, THEN 系统 SHALL 使每步下降量不超过 `a_max_mps2` 乘 dt 加上判定容差。
- **AC-kinematics-estop-decel-bound**:
  WHEN 机器人以 `SAFETY_DISTANCE` 原因处于急停减速过程, THEN 系统 SHALL 使每步下降量不超过 `decel_max_mps2` 乘 dt
  加上判定容差。
- **AC-kinematics-angular-speed-bound**:
  WHEN 机器人处于原地转向子阶段, THEN 系统 SHALL 使角速度的绝对值不超过 `omega_max_radps` 加上判定容差。

### 任务与路径

- **AC-path-task-accept**:
  WHEN 指令源下发的节点序列首标识等于机器人当前所在节点，且每对相邻节点之间存在方向合规的边, THEN 系统 SHALL 接受该
  指令并使机器人进入 `MOVING`。
- **AC-path-missing-edge-reject**:
  IF 节点序列中某对相邻节点之间没有方向合规的边, THEN 系统 SHALL 拒绝这次下发、返回指明缺失节点对的错误，并让机器人
  保持原状态与原速度。
- **AC-path-single-way-violation-reject**:
  IF 节点序列要求沿一条 `FWD` 边从 `to_node_id` 走到 `from_node_id`, THEN 系统 SHALL 以同一种结构化拒绝处理这次下发。
- **AC-path-unknown-node-reject**:
  IF 节点序列含地图中不存在的节点标识, THEN 系统 SHALL 拒绝这次下发，并在错误中至少给出该标识。
- **AC-path-start-node-mismatch-reject**:
  IF 节点序列首标识不等于机器人当前所在节点, THEN 系统 SHALL 拒绝这次下发，在错误中至少给出两侧节点标识，机器人状态
  与位姿不变。

### 急停与恢复

- **AC-estop-trigger-before-contact**:
  WHEN 障碍在本段上的最近点落在刹车距离加车体半径加位移余量 `v·dt` 的范围内，该障碍中心到该段所在直线的垂直距离不大于
  其半径与该车 `body_radius_m` 之和，且该车车体尚未与任何障碍相交, THEN 系统 SHALL 请求急停、把状态置为 `E_STOP`，
  `estop_reason` 取 `SAFETY_DISTANCE`。
- **AC-estop-late-registration-overlap**:
  WHEN 调用方注册一个障碍物，使某台处于行驶或急停减速状态的机器人在下一个 tick 的车体圆与该障碍相交, THEN 系统 SHALL
  在该 tick 把 v 与 ω 置零，把 `estop_reason` 记为 `OVERLAP`，并跳过安全距离减速分支。
- **AC-estop-lateral-obstacle-no-trigger**:
  IF 障碍中心到当前段所在直线的垂直距离大于该障碍半径与该车 `body_radius_m` 之和, THEN 系统 SHALL 跳过这个障碍物，
  不因它请求急停。
- **AC-estop-no-overlap**:
  WHEN 机器人以 `SAFETY_DISTANCE` 原因停稳, THEN 系统 SHALL 使车体圆与障碍圆不相交，且 `estop_reason` 保持
  `SAFETY_DISTANCE`。
- **AC-estop-stops-before-segment-end**:
  WHEN 机器人以 `SAFETY_DISTANCE` 原因停稳, THEN 系统 SHALL 使停止位置落在当前段终点之前，且 `segment_index` 与段
  子阶段都保持不变。
- **AC-estop-straddling-obstacle-stops**:
  WHEN 障碍中心落在下一段、其覆盖区间与本段终点相交，且机器人在本段上以默认参数巡航接近, THEN 系统 SHALL 在当前段把
  它计入前瞻判定，并在到达段终点之前以 `SAFETY_DISTANCE` 原因停稳，车体圆与该障碍不相交。
- **AC-estop-resume-continues-path**:
  WHEN 机器人在 `E_STOP` 收到 `RESUME` 且此时前瞻安全距离成立, THEN 系统 SHALL 回到 `MOVING`，沿原路径剩余部分继续
  行驶而不重头开始。
- **AC-estop-resume-still-unsafe**:
  IF 机器人在 `E_STOP` 收到 `RESUME` 时安全距离仍不成立, THEN 系统 SHALL 立即回到 `E_STOP` 并保持位姿不变。
- **AC-estop-resume-invalid-state**:
  IF 机器人处于 `MOVING`、`IDLE` 或 `ARRIVED` 时收到 `RESUME`, THEN 系统 SHALL 返回无效状态拒绝且不改变其状态。
- **AC-estop-reassign-rejected**:
  IF 机器人处于 `E_STOP` 时收到 `ASSIGN_PATH`, THEN 系统 SHALL 返回无效状态拒绝，并保持路径、位姿与速度不变。
- **AC-estop-initial-overlap**:
  IF 机器人初始位姿与场景初始障碍物集合中的某个障碍物相交, THEN 系统 SHALL 在第一个 tick 就把状态置为 `E_STOP` 且把
  `estop_reason` 记为 `OVERLAP`。

### 状态机契约

- **AC-state-unproduced-states**:
  WHEN 以任一内置示例地图与合法场景配置运行本项仿真, THEN 系统 SHALL 使状态取值只出现在 `IDLE`、`MOVING`、`E_STOP`
  与 `ARRIVED` 四者之中。
- **AC-command-source-swap**:
  IF 用另一个指令源实现换掉内置直通指令源，且它下发同样的节点序列, THEN 系统 SHALL 在不修改 `robot` 与 `kinematics`
  代码的前提下产出逐 tick 一致的状态输出。

### 地图数据模型

- **AC-map-edge-attributes-complete**:
  WHEN 调用方加载任一内置示例地图并读取任意一条边, THEN 系统 SHALL 提供方向性、路宽、车型标签、坡度代价与人机混行代价
  五项属性，且边的距离代价等于端点坐标派生的几何长度。
- **AC-map-critical-zone-members-exist**:
  WHEN 系统构建任一拓扑地图并读取其中每个临界区实体, THEN 系统 SHALL 使该实体的成员边标识全部存在于同一张地图的边集合
  中。
- **AC-map-parallel-edge-reject**:
  IF 构造的地图数据在同一个有序节点对上放入两条边, THEN 系统 SHALL 让地图构建失败并指出该节点对。
- **AC-map-invalid-edge-reject**:
  IF 构造的地图数据中某条边的端点标识不在节点集合里, THEN 系统 SHALL 让地图构建失败并指出该边标识。
- **AC-map-demo-ring-dependency**:
  WHEN 系统构建 demo 示例地图, THEN 系统 SHALL 在其中得到一个由至少三条边组成的环路，且环上每条边属于互不相同的临界区。

### 仿真推进

- **AC-sim-step-advances-fixed-dt**:
  WHEN 调用方推进一个 tick, THEN 系统 SHALL 使仿真时间恰好增加 dt，且每台机器人的运动学各推进一次。
- **AC-sim-deterministic**:
  WHEN 同一份场景配置连续运行两次, THEN 系统 SHALL 产出逐 tick 完全相同的快照序列。
- **AC-sim-invalid-dt-reject**:
  IF 场景配置的 dt 小于等于 0 或大于 0.05, THEN 系统 SHALL 使仿真实例创建失败，并给出该字段与允许范围。
- **AC-sim-invalid-map-id-reject**:
  IF 场景配置的 `map_id` 既不是 `minimal` 也不是 `demo`, THEN 系统 SHALL 使仿真实例创建失败，并给出该字段与两个合法值。
- **AC-sim-invalid-turn-tolerance-reject**:
  IF 某台机器人的 `turn_align_tolerance_rad` 除以 dt 大于它的 `omega_max_radps`, THEN 系统 SHALL 使仿真实例创建失败，
  并给出该机器人标识与参与比较的两个值。
- **AC-sim-snapshot-complete**:
  WHEN 调用方读取任一 tick 的快照, THEN 系统 SHALL 在其中看到 tick 序号、仿真时间，以及每台机器人的标识、位姿三分量、
  线速度、角速度、状态与急停原因。

### 障碍物注册

- **AC-obstacle-effective-next-tick**:
  WHEN 调用方在运行中注册一个合法圆形障碍物, THEN 系统 SHALL 从下一个 tick 起让所有机器人对它做前瞻判定。
- **AC-obstacle-invalid-radius-reject**:
  IF 注册请求的半径小于等于 0, THEN 系统 SHALL 拒绝该请求并保持障碍物集合不变。

### 实时性假设

- **AC-bench-step-cost-measured**:
  WHEN 以 demo 地图、10 台机器人各一条合法路径与 3 个固定位置的圆形障碍物，按默认 dt 连续推进 1000 个 tick, THEN
  系统 SHALL 产出平均单步耗时与 P95 单步耗时两个数值，并标注平均耗时是否小于 dt。

## Testing

- 单元测试覆盖 `kinematics` 的位姿积分与 θ 归一化、`controller` 的梯形剖面与剩余角收敛、`safety` 的垂直门槛、纵向覆盖
  区间判定与相交兜底，以及 `map_model` 的全部构建期校验分支。边界取值覆盖五种临界情形：段长恰好等于刹车距离、剩余角
  恰好等于 `turn_align_tolerance_rad`、障碍最近点恰好落在前瞻区间末端、障碍中心到段所在直线的垂直距离恰好等于两个半径
  之和、障碍覆盖区间恰好触及当前段终点。
- 场景级测试在极简地图上跑完整任务，逐 tick 断言五条约束上限类 AC，并核对到达位姿落在末段中心线上。急停组用例只对以
  `SAFETY_DISTANCE` 停稳的过程断言减速度上限，`OVERLAP` 那一 tick 跳过该断言。极简地图坐标全为整数，期望速度剖面和轨迹
  端点都能解析算出。
- 急停与恢复测试覆盖 AC-estop-trigger-before-contact 至 AC-estop-initial-overlap 全部急停类 AC。其中
  AC-estop-no-overlap 与 AC-estop-stops-before-segment-end 是两条几何断言，AC-estop-lateral-obstacle-no-trigger 用相邻
  边上的障碍物做对照组断言它不触发急停，AC-estop-reassign-rejected 断言急停中改道被拒，另外还覆盖注销障碍物后恢复行驶
  仍能走完原路径剩余部分的行为。三个用例分别对应三条 AC：预置障碍的逐步接近用例对应 AC-estop-trigger-before-contact，
  用 5.0 米位置与 0.2 米半径，断言停稳时两圆不相交且原因取 `SAFETY_DISTANCE`；跨段端点用例把障碍放在距 `N01` 10.05 米
  处，对应 AC-estop-straddling-obstacle-stops，断言机器人在到达节点前停住；行驶中或急停减速中把障碍注册进刹车距离的用例
  对应 AC-estop-late-registration-overlap，断言相交那一 tick 归零且原因改为 `OVERLAP`。三个用例都断言 `estop_reason`
  在同一 tick 只有一个取值。"在 dt 上限处不出现 OVERLAP"这一断言只在预置障碍的场景里检查。
- 路径校验测试覆盖任务与路径一组 AC，含首节点不一致、逆行单向边与未知节点标识三类拒绝。配置校验测试覆盖
  AC-sim-invalid-dt-reject、AC-sim-invalid-map-id-reject 与 AC-sim-invalid-turn-tolerance-reject，断言创建失败时列出的
  是全部违规项而不是第一个。
- 契约测试覆盖 AC-command-source-swap：注入一个替身指令源，断言本体代码路径未变，且输出快照与内置直通指令源逐 tick 相同。
- 确定性测试覆盖 AC-sim-deterministic，逐字段比较同一场景两次运行的快照。
- 基准测试覆盖 AC-bench-step-cost-measured，场景形态固定为 demo 地图、10 台机器人各一条合法路径与 3 个固定位置障碍物。
  这 10 台机器人允许互相穿行，因为本项不检测机器人之间的几何重叠，产出的数据只用于评估推进成本，不代表本体间碰撞已排除。
  实测数据用来处置 project.md 的实时性假设，结果记录进 spec 目录供 `WI-scale-50-robots` 引用；该测试不参与常规构建失败
  判定，避免机器抖动引起误报。
- demo 地图只做构建期验证，覆盖 AC-map-demo-ring-dependency 与多临界区共享边的校验。本项不在 demo 地图上断言多车行为，
  因为路权互斥不在本项范围。
- AC 的 THEN 允许在同一 tick 内列出多个可观察属性，每个属性对应一个测试断言。跨 tick 或跨状态的过程结果一律拆成独立
  条目：急停减速过程的每步上限单独由 AC-kinematics-estop-decel-bound 断言，不并入其他 THEN。

## Open Questions

- 车型标签的真实取值集合、路宽典型值，以及坡度与人机混行的量纲口径需要向真实设备库与现有地图数据校准。本项不消费这些
  字段，因此不影响本项行为与验收；校准在 `WI-map-editor` 进入澄清前完成。
- 10 台规模单步耗时的达标阈值取决于 50 台规模的性能指标定义。本项只产出实测数据、不判定达标，阈值等
  `WI-scale-50-robots` 澄清时确定。
- `WI-mutex-scheduling` 是否需要抢占语义，会影响 `WAITING_RIGHT` 与 `HOLDING_ZONE` 两个状态的转移定义。本项已冻结状态
  名称与语义，那个 work item 澄清时只需补转移表，不改枚举。
- 路径规划在 MVP 内没有 work item 承接：`WI-mutex-scheduling` 已把它列为 Non-Goal，本项按用户决定不做图搜索。归属需要
  `brainstorming` 决定是补一个 work item 还是并入现有项，这不影响本项验收。
