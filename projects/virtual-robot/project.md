# VirtualRobot Project Plan

## Summary

工业移动机器人（AMR）调度算法的验证目前依赖物理世界测试。测 50 台机器人的死锁解除和路权分配既耗时，
又容易造成生产事故；仓库弱网和无网区域里的状态丢失与死锁难以按需复现；参数固化的任务编排也缺少验证
非预期障碍物、动态博弈这类长尾场景的环境。

本项目提供一个纯设备端的高并发仿真工具，在本机跑起虚拟 AMR 的物理运动与状态机流转，
让调度算法工程师不占用产线就能构造并观察多车互斥与死锁场景。第一批用户是调度算法工程师本人，
工具自用，不对外交付。

## Planning Status

- **Status**: ready
- **Reason**: 目标用户、项目问题、Goals、Non-Goals、MVP 边界、成功指标和约束均已由用户逐项确认。
  三个 Now work item 完整覆盖 MVP，`WI-sim-kinematics` 已通过准入关卡。
  剩余未决问题只影响 Next 与 Later，不改变项目目标、MVP 边界或当前焦点。

## External Tracking

- **Enabled**: yes。
- **Host**: github.com。
- **Owner**: venom-zen。
- **Repo**: venom-zen/vrobot-sim。
- **Project title**: VirtualRobot。
- **Project number**: 2。
- **Project visibility**: private。
- **Mirror mode**: safe-subset。

仓库公开，只同步 safe-subset 字段；Readiness、Status evidence 和 Open Questions 留在本地 backlog。

## Target Users and Outcomes

| User / Role | Current problem | Desired outcome |
|-------------|-----------------|-----------------|
| 调度算法工程师（自用） | 只能在物理产线验证调度算法，50 台死锁解除与路权分配测试耗时且易出事故；弱网区状态丢失无法复现 | 在本机跑起 5-10 台虚拟 AMR，构造并实时观察临界区互斥与死锁，不占产线即可判断调度逻辑是否成立 |

## Goals

- 调度算法工程师能在本机跑起 5-10 台虚拟 AMR，在带互斥属性的拓扑图上完成从起点到目标点的行驶任务。
- 工程师能构造出临界区互斥、路权等待和死锁场景，并在浏览器里直接看到它们的形成过程。
- 机器人运动严格遵循差速底盘运动学约束（最大速度、最大加速度、转向角速度），位姿由线速度 v 与角速度 ω 积分得到。
- 仿真器内置一个可替换的参考调度器，后续换成外部调度器时不需要改动机器人本体模型。

## Non-Goals

- 真实硬件对接与物理机器人控制。
- 云端调度系统本身的实现；本项目只做设备端仿真。
- 多用户协作、权限体系、账号系统。
- 产品化交付能力：安装包、用户文档站、部署运维。
- 三维物理仿真；本项目只做 2D 位姿（x, y, θ），坡度仅作为边的代价属性存在。
- 第一版不模拟车云通信；不建模网络传输、延迟、丢包和断连。

## Success Metrics

| Metric | Baseline | Target | Evidence source |
|--------|----------|--------|-----------------|
| MVP 可跑通的多车规模 | 0（绿地项目） | 5-10 台虚拟 AMR 在内置示例拓扑图上完成行驶任务 | 浏览器可视化观察 + 仿真状态输出 |
| 临界区互斥正确性 | 无 | 同一互斥组内同时只有一台机器人占用，其余处于等待路权状态 | 仿真状态输出与可视化中的临界区占用标记 |
| 死锁场景可构造 | 无 | 示例地图上能构造一个多车互相等待的死锁场景并在可视化中看出 | 手动构造场景后的可视化观察 |
| 运动学约束符合性 | 无 | 机器人实际速度、加速度、转向角速度不超过配置上限 | 仿真内核数值自检 |
| 可视化流畅度 | 无 | 浏览器实时显示 5-10 台机器人位姿与状态机流转，无明显卡顿 | 浏览器人工观察 |

## MVP Boundary

### Now

- 单车运动仿真：差速底盘位姿更新、运动学约束、拓扑图碰撞检测与急停、内置示例地图。见 `WI-sim-kinematics`。
- 临界区互斥调度：路权申请、先到先得占用、等待与释放，死锁场景可暴露。见 `WI-mutex-scheduling`。
- 浏览器实时可视化：机器人位姿、状态机流转、临界区占用，手动启动与暂停。见 `WI-live-visualization`。

### Next

- 拓扑地图编辑器：节点、边、边属性（方向性、路宽与车型限制、代价、互斥组）的可视化编辑与持久化。见 `WI-map-editor`。
- 外部调度器接入：把内置调度替换为外部调度器的协议与可拔插边界。见 `WI-pluggable-dispatcher`。
- 50 台并发：并发架构、时间同步机制与性能基准。见 `WI-scale-50-robots`。
- 场景脚本化与复盘：无头批量跑场景、事件日志导出、死锁形成过程回看。见 `WI-scripted-scenarios`。

### Later

- 车云通信模拟：可注入延迟、丢包、断连的虚拟信道，复现弱网场景。见 `WI-cloud-comm-sim`。
- 长尾场景编排：非预期障碍物注入与动态博弈场景复现。见 `WI-corner-case-injection`。
- 机器人异常态：低电量、电机故障、定位丢失注入。见 `WI-robot-fault-states`。

## Capability Map

| Capability | User outcome | MVP | Work items |
|------------|--------------|-----|------------|
| 单车运动仿真 | 机器人按运动学约束在拓扑图上移动并正确响应碰撞 | Now | `WI-sim-kinematics` |
| 多车路权互斥 | 工程师能构造并观察临界区互斥与死锁场景 | Now | `WI-mutex-scheduling` |
| 实时状态可视化 | 浏览器里看到位姿、状态机流转与临界区占用 | Now | `WI-live-visualization` |
| 拓扑地图编辑 | 不改代码就能编辑节点、边和边属性 | Next | `WI-map-editor` |
| 调度器可拔插 | 用外部调度器替换内置调度跑同一场景 | Next | `WI-pluggable-dispatcher` |
| 大规模并发 | 50 台并发达到可接受帧率与实时倍速 | Next | `WI-scale-50-robots` |
| 场景批量运行与复盘 | 无头跑场景、导出事件日志、回看死锁形成过程 | Next | `WI-scripted-scenarios` |
| 车云通信模拟 | 复现弱网、丢包、断连下的状态丢失与死锁 | Later | `WI-cloud-comm-sim` |
| 长尾场景编排 | 非预期障碍物与动态博弈场景可复现 | Later | `WI-corner-case-injection` |
| 机器人异常态 | 低电量、电机故障、定位丢失可注入 | Later | `WI-robot-fault-states` |

## Constraints and Assumptions

### Confirmed Constraints

- 目标用户为调度算法工程师自用，不需要安装引导、权限体系、用户文档和对外部署能力。
- 技术栈为 Python 仿真内核 + Web 前端，可视化在浏览器中呈现。
- MVP 并发规模为 5-10 台机器人；50 台是后续性能目标，不在 MVP 内达标。
- 第一版不含通信层；机器人状态在进程内直接推送前端，不模拟网络传输、延迟与丢包。
- MVP 地图数据来自代码内置的示例拓扑图，不依赖外部系统导入。
- 调度逻辑由仿真器内置最简参考实现承担（临界区互斥 + 先到先得），指令接口设计成可替换。

### Assumptions to Validate

- Python 单进程能满足 5-10 台机器人、固定仿真步长下的实时性。尚未做基准测试；影响 `WI-sim-kinematics` 与 `WI-scale-50-robots`。验证方式：MVP 阶段用最小基准脚本测量单步耗时。
- 浏览器渲染 10 台机器人加拓扑地图能保持流畅帧率。尚未验证；影响 `WI-live-visualization`。验证方式：可视化首版跑通后人工观察帧率。
- 你们现有调度系统的地图导出格式与指令接口形态未知。影响 `WI-map-editor` 与 `WI-pluggable-dispatcher`，不影响 MVP。验证方式：进入这两项前收集现有系统的接口样例。

## Project Risks

| Risk | Impact | Mitigation / next action | Owner |
|------|--------|--------------------------|-------|
| 内置调度器过于简化，构造不出真实死锁 | MVP 无法验证死锁解除与路权分配这一核心价值 | 示例地图须含能触发多车互相等待的环形依赖拓扑；`WI-mutex-scheduling` 澄清时把死锁可构造性列入成功信号 | 项目发起人 |
| 地图数据模型 MVP 期过窄 | Next 的编辑器、外部调度器接入与 50 台并发共用这份数据，届时返工 | `WI-sim-kinematics` 澄清时建模边属性（方向性、代价、互斥组等），MVP 只消费互斥组 | 项目发起人 |
| 缺少结果回看，调度验证价值受损 | MVP 只有实时动画，跑完无法回溯死锁形成步骤 | 事件日志导出已推至 Next；死锁难定位时启动 `WI-scripted-scenarios` | 项目发起人 |
| Python 与浏览器实时推送的帧率未验证 | 可视化卡顿会让多车场景无法观察 | MVP 早期做一次最小基准，验证假设后再确定推送频率与渲染方式 | 项目发起人 |
| 现有调度系统接口形态未知 | `WI-pluggable-dispatcher` 与 `WI-map-editor` 可能设计出不匹配的协议 | 进入 Next 前先收集现有系统的地图导出样例与指令接口定义 | 项目发起人 |

## Project Decision Record

### PDR-scheduling-ownership

**Decision**: 路权分配与死锁解除逻辑在 MVP 阶段由仿真器内置的最简调度器承担，包含临界区互斥与先到先得；指令接口设计成可替换。外部调度器接入协议推到 Next（`WI-pluggable-dispatcher`）。

**Rationale**: 用户背景里的核心痛点是多车调度算法验证成本高，第一版需要一个不依赖外部系统就能独立跑通的多车验证环境。被拒方向：只做仿真端并对接外部调度器，会把 MVP 阻塞在外部协议对齐上，且现有调度系统的接口形态尚未确认。

**Revisit when**: 内置调度器的能力边界验证清楚，或现有调度系统的指令接口样例可用时。

### PDR-mvp-delivery-surface

**Decision**: MVP 只交付浏览器内手动启动与观察。脚本化无头运行、事件日志导出与死锁过程回看推到 Next（`WI-scripted-scenarios`）。

**Rationale**: 目标用户是自用的调度算法工程师，MVP 目标是先验证仿真本身能跑。批量运行与结果复盘提高验证效率，但不构成核心验证的前提。被拒方向：MVP 即包含脚本化与日志导出，会把范围扩大到用户已明确推迟的能力上。

**Revisit when**: 需要反复回归同一批场景、需要与他人共享仿真结果，或死锁场景无法通过实时动画定位时。

### PDR-comm-layer-deferred

**Decision**: 第一版不模拟车云通信。机器人状态在进程内直接推送前端，不经过网络传输、延迟与丢包建模。弱网与断网信道模拟推到 Later（`WI-cloud-comm-sim`）。

**Rationale**: 用户已确认 MVP 验证目标是仿真本身能跑。通信层承载弱网痛点，但纳入 MVP 会把范围撑大到与"先验证仿真能跑"冲突。被拒方向：MVP 即做可注入故障的虚拟信道。

**Revisit when**: MVP 验证通过，且需要复现弱网导致的状态丢失或死锁场景时。

## Backlog

见 [backlog.md](backlog.md)。

## Open Questions

- 现有调度系统的地图导出格式与指令接口形态未知。影响 `WI-map-editor` 与 `WI-pluggable-dispatcher`，不影响 MVP 与当前焦点；在这两项进入 `clarifying` 前收集样例。
- 是否已有可复用的拓扑地图数据（真实仓库布局），还是全部使用虚构示例地图。影响示例地图的代表性，不改变 MVP 边界；在 `WI-sim-kinematics` 澄清时确认。
