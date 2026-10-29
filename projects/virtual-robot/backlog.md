# VirtualRobot Backlog

## Status Model

主状态：

```text
candidate -> ready-for-clarifying -> design-ready -> planned -> executing -> done
```

旁路状态：`blocked`、`deferred`、`cancelled`。

## Current Focus

- `WI-mutex-scheduling` — `WI-sim-kinematics` 已交付，地图数据模型与机器人状态集合已确定；
  下一步由项目发起人对它运行 `clarifying`，确定路权申请、占用与释放的流转规则。
- `WI-live-visualization` 保持 `candidate`，等 `WI-mutex-scheduling` 确定临界区占用与等待路权状态后再进入
  `clarifying`，避免重复决策状态集合。

## Work Items

| ID | Outcome | Priority | Status | Dependencies |
|----|---------|----------|--------|--------------|
| `WI-sim-kinematics` | 工程师能让单台虚拟 AMR 按运动学约束在拓扑图上行驶并正确响应碰撞 | Now | done | None |
| `WI-mutex-scheduling` | 工程师能构造并观察多车临界区互斥与死锁场景 | Now | ready-for-clarifying | `WI-sim-kinematics` |
| `WI-live-visualization` | 工程师能在浏览器里实时看到机器人位姿、状态与临界区占用 | Now | candidate | `WI-sim-kinematics`, `WI-mutex-scheduling` |
| `WI-map-editor` | 工程师能在浏览器里编辑地图而不改代码 | Next | candidate | `WI-sim-kinematics` |
| `WI-pluggable-dispatcher` | 工程师能用外部调度器替换内置调度跑同一场景 | Next | candidate | `WI-sim-kinematics`, `WI-mutex-scheduling` |
| `WI-scale-50-robots` | 50 台并发仿真能达到可接受帧率与实时倍速 | Next | candidate | `WI-mutex-scheduling`, `WI-live-visualization` |
| `WI-scripted-scenarios` | 工程师能无头批量跑场景并回看死锁形成过程 | Next | candidate | `WI-mutex-scheduling` |
| `WI-cloud-comm-sim` | 工程师能复现弱网与断网下的状态丢失与死锁 | Later | deferred | `WI-sim-kinematics` |
| `WI-corner-case-injection` | 工程师能复现非预期障碍物与动态博弈场景 | Later | deferred | `WI-sim-kinematics`, `WI-scripted-scenarios` |
| `WI-robot-fault-states` | 工程师能注入机器人异常态验证调度容错 | Later | deferred | `WI-sim-kinematics` |

### WI-sim-kinematics: 差速底盘运动仿真

- **Outcome**: 调度算法工程师能让一台虚拟 AMR 在内置示例拓扑图上，从指定起点按差速底盘运动学行驶到目标点，
  途中撞到障碍物时进入急停状态，全程不超过配置的速度、加速度与转向角速度上限。
- **Scope**: 差速底盘位姿更新（线速度 v 与角速度 ω 积分得到 x, y, θ）；电机物理约束建模；
  拓扑图上的碰撞检测与急停触发；机器人状态机流转（空闲、行驶中、碰撞急停、到达）；
  内置示例拓扑地图数据，含节点、边与完整边属性建模；仿真时钟与固定步长推进。
- **Non-Goals**: 多车之间的路权互斥与死锁处理；浏览器可视化与前端界面；Web 地图编辑器；
  车云通信与网络行为模拟；外部调度器接入协议；脚本化无头批量运行；事件日志导出与结果回看；
  异常态与故障注入；50 台规模的性能优化。
- **Success signal**: 单台机器人在内置示例地图上完成一次从起点到目标点的行驶，位姿轨迹符合差速运动学，
  速度、加速度、转向角速度均不超过配置上限；驶向障碍物时进入急停状态。证据来源为仿真状态输出与数值自检。
- **Priority**: Now
- **Status**: done
- **Dependencies**: None
- **Readiness**: 用户与 Outcome 明确；MVP 边界、Priority 和依赖已确认；不含阻塞单项设计的项目级未决决策；
  Success signal 足以指导后续澄清。地图数据模型需在本次澄清中完整覆盖全部边属性，
  以免 `WI-map-editor`、`WI-pluggable-dispatcher` 与 `WI-scale-50-robots` 返工（见 project.md 风险表）。
- **Spec**: `specs/sim-kinematics/design.md`
- **Status evidence**: 交付链路完成：design review R6 为 `Go`（F-023 已修复）、`tasks.md` 30 项 checkbox 全部完成、
  `exec-evidence.md` 记录 126 项测试通过、`code-review.md` 为 `Pass / Go`（8 条 findings 全部 resolved）。
- **External ref**: [Issue #1](https://github.com/venom-zen/vrobot-sim/issues/1)。

#### Open Questions

- 边属性中的代价（距离、坡度、人机混行区）与路宽车型限制在 MVP 阶段只建模不消费，
  具体字段与取值范围需在澄清时确定。
- 碰撞检测基于拓扑图节点与边，还是叠加一层栅格障碍物，需在澄清时确定。
- 内置示例地图使用虚构布局还是真实仓库拓扑，需在澄清时向用户确认。
- 仿真步长取值与 Python 单进程实时性假设的验证方式，需在澄清时确定。

### WI-mutex-scheduling: 临界区互斥调度

- **Outcome**: 调度算法工程师能让 5-10 台虚拟 AMR 在同一张带互斥组的拓扑图上并发行驶，
  同一临界区同时只有一台机器人占用，其余在入口处等待路权；能构造出一个多车互相等待的死锁场景并观察其形成。
- **Scope**: 内置最简参考调度器，实现临界区互斥与先到先得的路权分配；机器人状态机扩展出等待路权与
  占用临界区两个状态；路权申请、授予、释放的流转；能构造并暴露死锁场景；
  调度指令接口设计成可替换，为后续接入外部调度器预留边界。
- **Non-Goals**: 外部调度器接入协议的具体定义；死锁自动解除策略；路径规划与代价最优路线选择；
  浏览器可视化；事件日志导出与死锁过程回看；50 台规模验证；通信层。
- **Success signal**: 5-10 台机器人并发运行时，同一互斥组内同时只有一台处于占用临界区状态，
  其余处于等待路权状态，没有机器人重叠穿行；示例地图上能构造出一个多车互相等待无法推进的死锁场景。
  证据来源为仿真状态输出。
- **Priority**: Now
- **Status**: ready-for-clarifying
- **Dependencies**: `WI-sim-kinematics`（消费其位姿输出、状态机与地图互斥组属性）
- **Readiness**: 依赖已满足：`WI-sim-kinematics` 已交付，地图数据模型（含 `MapCriticalZone` 与互斥组属性）
  与机器人状态枚举已确定。等待项目发起人运行 `clarifying`。
- **Spec**: Not created
- **Status evidence**: 通过 STEP 6 准入关卡：依赖项已交付（code review `Pass / Go`），Outcome、Priority、
  Success signal 与边界均已确认，无阻塞澄清的项目级未决决策。
- **External ref**: [Issue #2](https://github.com/venom-zen/vrobot-sim/issues/2)。

#### Open Questions

- 先到先得的路权申请队列在多车同时到达临界区入口时的排序规则，需在澄清时确定。
- 死锁场景由示例地图的环形依赖拓扑触发，还是需要额外的场景配置，需在澄清时确定。
- 可替换调度接口的最小契约范围（是否包含路权申请、释放、超时），需在澄清时确定。
- 机器人等待路权时是否阻塞后续路段的其他机器人，需在澄清时确定。

### WI-live-visualization: 浏览器实时可视化

- **Outcome**: 调度算法工程师能在浏览器里实时看到 5-10 台机器人的当前位置与朝向、状态机流转、
  临界区占用情况，并能手动启动、暂停和重置一次仿真。
- **Scope**: 浏览器端渲染拓扑地图（节点、边、互斥区标记）与机器人位姿；机器人状态与临界区占用的实时展示；
  仿真启动、暂停、重置的手动控制；仿真内核到前端的状态推送通道。
- **Non-Goals**: 地图编辑能力；脚本化无头运行；事件日志导出与历史回看；车云通信模拟；
  多用户共享视图与协作；50 台规模下的渲染性能优化。
- **Success signal**: 浏览器中能看到 5-10 台机器人按仿真进度移动，状态机流转与临界区占用可见，
  画面无明显卡顿，手动启动与暂停能正确控制仿真推进。证据来源为浏览器人工观察。
- **Priority**: Now
- **Status**: candidate
- **Dependencies**: `WI-sim-kinematics`（位姿与状态数据来源）、`WI-mutex-scheduling`（临界区占用与等待路权状态）
- **Readiness**: Outcome 与边界已确认。等待前两项确定状态集合与数据契约后进入澄清。
- **Spec**: Not created
- **Status evidence**: None
- **External ref**: [Issue #3](https://github.com/venom-zen/vrobot-sim/issues/3)。

#### Open Questions

- 渲染方式使用 Canvas 还是 SVG，以及状态推送频率，需在澄清时结合帧率基准结果确定。
- 需要展示哪些机器人字段（位姿、速度、状态、当前路权、等待时长），需在澄清时确定。
- 是否需要在界面上调整机器人数量与目标点，需在澄清时确定。

### WI-map-editor: 拓扑地图编辑器

- **Outcome**: 调度算法工程师能在浏览器里编辑虚拟机器人行驶的地图，增删节点与边并设置边属性，
  保存后仿真内核直接加载，不需要改代码里的内置地图数据。
- **Scope**: 节点与边的可视化增删改；边属性编辑，含方向性（单行道与双向道）、路宽与车型限制、
  代价（距离、坡度、人机混行区）、互斥组标记；地图的保存与加载；仿真内核能直接加载编辑结果。
- **Non-Goals**: 对接现有调度系统的地图导出格式；地图版本管理与多人协作编辑；
  从真实仓库布局自动生成拓扑图；三维地图。
- **Success signal**: 工程师在浏览器里新建一张含互斥组的地图并保存，仿真内核加载后机器人能在新地图上行驶，
  临界区互斥行为随互斥组标记生效。证据来源为浏览器操作与仿真运行结果。
- **Priority**: Next
- **Status**: candidate
- **Dependencies**: `WI-sim-kinematics`（地图数据模型必须先在 MVP 期完整建模，否则编辑器无处落笔）
- **Readiness**: Outcome 与边界已确认。等待 MVP 验证通过，且需要先确认现有调度系统的地图格式是否需要兼容。
- **Spec**: Not created
- **Status evidence**: None
- **External ref**: [Issue #4](https://github.com/venom-zen/vrobot-sim/issues/4)。

#### Open Questions

- 是否需要导入现有调度系统的地图导出格式，以及该格式的具体形态（见 project.md Open Questions）。
- 地图持久化方式与文件格式需在澄清时确定。
- 编辑时是否需要实时校验（孤立节点、互斥组重叠、单行道冲突），需在澄清时确定。

### WI-pluggable-dispatcher: 外部调度器接入

- **Outcome**: 调度算法工程师能把仿真器的内置调度器替换为外部调度算法，在完全相同的地图与机器人配置下
  跑同一个场景，用于对比不同调度算法的路权分配与死锁表现。
- **Scope**: 调度器接入协议的定义与实现；内置调度器与外部调度器的可互换边界；
  同场景在不同调度器下的运行一致性保证。
- **Non-Goals**: 外部调度算法本身的实现；调度算法的性能评测报告生成；多调度器同时并行对比运行。
- **Success signal**: 在不修改机器人本体模型与地图数据的前提下，把内置调度器换成一个外部调度实现，
  同一场景能正常跑通并产出可比较的状态输出。证据来源为替换前后的仿真运行结果。
- **Priority**: Next
- **Status**: candidate
- **Dependencies**: `WI-sim-kinematics`、`WI-mutex-scheduling`（需要内置调度器的接口边界先稳定）
- **Readiness**: Outcome 与边界已确认。等待 MVP 验证通过，且需要现有调度系统的指令接口样例。
- **Spec**: Not created
- **Status evidence**: None
- **External ref**: [Issue #5](https://github.com/venom-zen/vrobot-sim/issues/5)。

#### Open Questions

- 外部调度器以进程内插件形式接入，还是走独立进程与网络协议，需在澄清时确定。
- 接入协议需要暴露哪些仿真内部状态，需在澄清时确定。
- 现有调度系统的指令接口形态未知（见 project.md Open Questions）。

### WI-scale-50-robots: 50 台并发仿真

- **Outcome**: 调度算法工程师能在单机上跑起 50 台虚拟 AMR 的并发仿真，保持可接受的帧率与实时倍速，
  用于验证大规模调度算法的死锁解除与路权分配，替代物理世界的 50 台机器人测试。
- **Scope**: 并发架构与仿真推进机制；多机器人时间同步；50 台规模下的性能基准与实时倍速指标；
  大规模场景下的可视化可用性。
- **Non-Goals**: 分布式多机部署；超过 50 台规模；物理机器人群控对接。
- **Success signal**: 50 台机器人并发运行时仿真能按设定倍速推进，可视化不卡死，
  性能基准数据（单步耗时、实时倍速）可测量且达标。证据来源为基准测试输出。
- **Priority**: Next
- **Status**: candidate
- **Dependencies**: `WI-mutex-scheduling`、`WI-live-visualization`
- **Readiness**: Outcome 与边界已确认。等待 MVP 的 Python 单进程实时性假设验证结果，
  该结果决定并发架构方向。
- **Spec**: Not created
- **Status evidence**: None
- **External ref**: [Issue #6](https://github.com/venom-zen/vrobot-sim/issues/6)。

#### Open Questions

- 可接受的帧率与实时倍速的具体指标值需在澄清时由用户确定。
- 并发实现方向（多线程、多进程、异步）取决于 MVP 期的基准测试结果。
- 50 台规模下可视化是否需要降级渲染策略，需在澄清时确定。

### WI-scripted-scenarios: 场景脚本化与结果复盘

- **Outcome**: 调度算法工程师能用脚本无头运行一个多车场景，导出事件日志，
  并在事后回看谁在哪个临界区等了多久、死锁在哪一步形成，用于回归验证调度算法改动。
- **Scope**: 场景定义方式（地图、机器人数量、起点与目标点、初始配置）；无头运行入口；
  事件日志记录与导出格式；死锁形成过程的回看方式。
- **Non-Goals**: 图形化场景编排界面；场景库管理与共享；调度算法的自动评测与打分。
- **Success signal**: 工程师用一份场景配置无头跑完一次多车仿真，导出事件日志，
  并能从日志中定位死锁形成的时间点与涉及的机器人。证据来源为脚本运行输出与日志内容。
- **Priority**: Next
- **Status**: candidate
- **Dependencies**: `WI-mutex-scheduling`
- **Readiness**: Outcome 与边界已确认。用户已将本项推出 MVP（见 PDR-mvp-delivery-surface）；
  若死锁场景难以通过实时动画定位，可提前启动。
- **Spec**: Not created
- **Status evidence**: None
- **External ref**: [Issue #7](https://github.com/venom-zen/vrobot-sim/issues/7)。

#### Open Questions

- 事件日志需要记录哪些事件类型与字段，需在澄清时确定。
- 回看方式是离线解析日志还是可视化时间轴回放，需在澄清时确定。
- 场景配置的格式与存放位置需在澄清时确定。

### WI-cloud-comm-sim: 车云通信模拟

- **Outcome**: 调度算法工程师能复现仓库弱网与无网区域里的机器人行为，
  观察网络延迟、丢包与断连如何导致状态丢失、死锁与不可控的安全隐患。
- **Scope**: 机器人状态上报与调度指令下发的虚拟信道；可注入的延迟、丢包、断连与恢复；
  弱网场景下的状态一致性表现观察。
- **Non-Goals**: 真实云端调度系统实现；真实网络协议栈与无线信号建模；通信加密与鉴权。
- **Success signal**: 在注入断连的场景下，能观察到机器人状态上报中断与恢复后的行为差异，
  并复现出至少一个由弱网导致的死锁或状态丢失案例。证据来源为事件日志与可视化观察。
- **Priority**: Later
- **Status**: deferred
- **Dependencies**: `WI-sim-kinematics`（状态上报内容依赖机器人名状态机）
- **Readiness**: 用户已确认第一版不做通信层（见 PDR-comm-layer-deferred）。保留方向，暂不澄清技术细节。
- **Spec**: Not created
- **Status evidence**: None
- **External ref**: [Issue #8](https://github.com/venom-zen/vrobot-sim/issues/8)。

#### Open Questions

- 通信模型采用真实协议（MQTT、HTTP）还是抽象信道，需在进入澄清时确定。
- 弱网参数（延迟分布、丢包率、断连时长）的取值范围需在进入澄清时确定。

### WI-corner-case-injection: 长尾场景编排

- **Outcome**: 调度算法工程师能复现非预期障碍物突然出现、多车动态博弈这类长尾场景，
  验证参数固化的任务编排在 Corner Case 下的表现。
- **Scope**: 运行中注入非预期障碍物；多车动态博弈场景的编排与触发；场景复现的一致性保证。
- **Non-Goals**: 真实传感器噪声与感知算法建模；场景自动生成与模糊测试；长尾场景的覆盖率统计。
- **Success signal**: 工程师能在仿真运行中注入一个非预期障碍物，观察到机器人触发急停并影响后续调度，
  且同一场景能稳定复现。证据来源为事件日志与可视化观察。
- **Priority**: Later
- **Status**: deferred
- **Dependencies**: `WI-sim-kinematics`、`WI-scripted-scenarios`（需要场景定义与事件日志能力先就位）
- **Readiness**: 保留方向，暂不澄清技术细节。
- **Spec**: Not created
- **Status evidence**: None
- **External ref**: [Issue #9](https://github.com/venom-zen/vrobot-sim/issues/9)。

#### Open Questions

- 障碍物注入的粒度（节点级、边级、任意坐标）需在进入澄清时确定。
- 动态博弈场景需要哪些可编排要素，需在进入澄清时确定。

### WI-robot-fault-states: 机器人异常态模拟

- **Outcome**: 调度算法工程师能注入低电量、电机故障、定位丢失等机器人异常态，
  验证调度系统在机器人本体异常时的容错与重调度表现。
- **Scope**: 状态机扩展出异常态；异常态的注入方式与触发条件；异常态对路权占用与调度决策的影响。
- **Non-Goals**: 电池物理模型与充电调度；电机故障的物理成因建模；异常恢复策略的自动评测。
- **Success signal**: 工程师能在运行中把一台机器人置为异常态，观察到它释放或持有路权的行为符合预期，
  且其余机器人的调度随之调整。证据来源为仿真状态输出与事件日志。
- **Priority**: Later
- **Status**: deferred
- **Dependencies**: `WI-sim-kinematics`（状态机扩展基础）、`WI-mutex-scheduling`（异常态影响路权占用）
- **Readiness**: 用户已确认异常态与故障注入不进入 MVP。保留方向，暂不澄清技术细节。
- **Spec**: Not created
- **Status evidence**: None
- **External ref**: [Issue #10](https://github.com/venom-zen/vrobot-sim/issues/10)。

#### Open Questions

- 需要覆盖哪些异常态类型，需在进入澄清时由用户确定。
- 异常态机器人是否自动释放已占用的临界区，需在进入澄清时确定。

## Dependency Notes

- 三个 Now 项共享同一份地图数据模型与机器人状态集合。`WI-sim-kinematics` 先确定这两项契约，
  `WI-mutex-scheduling` 与 `WI-live-visualization` 再进入澄清，否则三项会重复决策同一份数据契约。
- 地图数据模型被 `WI-map-editor`、`WI-pluggable-dispatcher` 与 `WI-scale-50-robots` 共同消费。
  MVP 期只消费互斥组属性，但边属性需完整建模，否则 Next 阶段返工（见 project.md 风险表）。
- `WI-scale-50-robots` 的并发架构方向取决于 MVP 期对 Python 单进程实时性假设的基准验证结果，
  该验证在 `WI-sim-kinematics` 内进行。
- `WI-corner-case-injection` 依赖 `WI-scripted-scenarios` 的场景定义与事件日志能力；
  两者都推出 MVP，因此该项链路上不存在阻塞 MVP 的依赖。

## Deferred / Cancelled

- `WI-cloud-comm-sim` — deferred。用户在 MVP 边界确认中明确第一版不做通信层，
  决策记录见 project.md 的 PDR-comm-layer-deferred。保留稳定 ID，不删除。
- `WI-corner-case-injection` — deferred。长尾场景复现是用户背景里的第二个痛点，
  但依赖场景定义与事件日志能力，且 MVP 目标是先验证仿真能跑。保留稳定 ID。
- `WI-robot-fault-states` — deferred。用户在状态机范围确认中选择不把异常态纳入 MVP。保留稳定 ID。
