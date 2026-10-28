# Implementation Plan: VirtualRobot 差速底盘运动仿真

## Overview

本实施计划由 [design.md](design.md) 中已批准的 8 条 Goals、11 条 Decision 与 43 条 Acceptance Criteria 驱动。

共 9 个 Phase 加 3 个 Checkpoint，按依赖顺序推进：工程骨架与依赖 → 地图数据模型与两张内置示例地图 → 底盘位姿积分
→ 逐段控制器 → 前瞻与急停安全判定 → 机器人状态机与指令接收边界 → 仿真内核、快照与配置校验 → 集成测试套件 →
可选的基准测量。

关键技术决策以 design.md 为准，实施时不得改写：直线子阶段内 θ 恒等于该段方向并在转向末吸附；前瞻区间在当前段终点
截断，纵向判定使用障碍在本段上的覆盖区间 `[p − r, p + r]`；急停有两种收尾（`SAFETY_DISTANCE` 与 `OVERLAP`），后者
那一步不受减速度上限约束；常规加减速用 `a_max_mps2`、急停用 `decel_max_mps2`；仿真时钟离散、由调用方驱动；交付形态
是内核库加 pytest，不提供 CLI 与网络服务。

一处计划层面的命名假定：design.md 的 Architecture 给出了模块清单（`map_model`、`kinematics`、`controller`、
`safety`、`robot`、`simulation`、`scenario`、`obstacle_field`、`snapshots`）但未固定包目录名，本计划统一按
`src/vrobot_sim/<module>.py` 落盘。改名只影响路径，不影响任何契约与 AC。

## Tasks

- [✅] 1. Phase 1: 工程骨架与依赖
  - [✅] 1.1 建立 src 布局与包骨架
    - Create `pyproject.toml`（`requires-python = ">=3.11"`、dev 依赖组仅含 `pytest`、运行时零第三方依赖）与
      `src/vrobot_sim/` 包目录，内含 1.2 至 1.7 各模块的空文件与模块级 docstring
    - Create 虚拟环境并验证解释器版本：用 `py -3 -m venv .venv` 创建，测试通过 `.venv` 内的解释器运行
    - _Design: Proposed Solution / Architecture_
  - [✅] 1.2 定义公共数据结构与枚举
    - Create `src/vrobot_sim/map_model.py`、`src/vrobot_sim/robot.py` 中的 `RobotStatus`（6 成员）、
      `EStopReason`（`NONE`/`SAFETY_DISTANCE`/`OVERLAP`）、`EdgeDirection`（`FWD`/`BOTH`）、
      `MixedTrafficClass`（`NONE`/`LOW`/`MID`/`HIGH`）、`CommandKind`（`ASSIGN_PATH`/`RESUME`）
    - _Design: Proposed Solution / Data Model_
  - [✅] 1.3 建立测试骨架与固定参数夹具
    - Create `tests/conftest.py`，导出 design.md 声明的默认底盘参数（`v_max_mps` 1.5、`a_max_mps2` 0.8、
      `decel_max_mps2` 1.5、`omega_max_radps` 1.2、`body_radius_m` 0.35、`turn_align_tolerance_rad` 0.02、
      `arrival_tolerance_m` 0.02）与默认 dt 0.02，供各阶段断言复用
    - _Design: Proposed Solution / Data Model_

- [✅] 2. Phase 2: 拓扑地图数据模型与内置示例地图
  - [✅] 2.1 实现节点、边与临界区实体
    - Create in `src/vrobot_sim/map_model.py` the data objects `MapNode`, `MapEdge`, `MapCriticalZone`,
      `TopologyMap`，字段与 `design.md` Data Model 完全一致；临界区持有 `edge_ids` 与 `capacity`，边不存临界区字段
    - _Design: Proposed Solution / Data Model_
  - [✅] 2.2 实现构建期校验与派生索引
    - Add `build_topology_map()`：校验标识唯一、边端点存在、临界区成员边存在、同一有序节点对至多一条边、数值字段
      落在声明范围内；生成只读派生索引 `edge_by_node_pair` 与 `edge_length_m`；不生成边到临界区的反查索引
    - _Acceptance: AC-map-critical-zone-members-exist, AC-map-parallel-edge-reject, AC-map-invalid-edge-reject_
    - _Design: Proposed Solution / Data Model_
  - [✅] 2.3 内置两张示例地图
    - Create `src/vrobot_sim/maps/minimal.py`（`N01(0,0) → N02(10,0) → N03(10,5)`，两条 `BOTH` 边，坐标全整数，
      无临界区）与 `src/vrobot_sim/maps/demo.py`（三角形环路加支路与转角链，环上三条边分属 `Z01`/`Z02`/`Z03`，
      至少一条 `FWD`，至少一条边的路宽、坡度与人机混行取非默认值）
    - _Acceptance: AC-map-edge-attributes-complete, AC-map-demo-ring-dependency_
    - _Design: Proposed Solution / Data Model_
  - [✅] 2.4 为地图数据模型编写测试
    - Test 五项边属性可读且距离代价等于端点派生长度；demo 环路成立；标识重复、端点缺失、成员边缺失、平行边与数值
      越界五类构建失败各自报错并指出对象
    - _Acceptance: AC-map-edge-attributes-complete, AC-map-critical-zone-members-exist, AC-map-parallel-edge-reject, AC-map-invalid-edge-reject, AC-map-demo-ring-dependency_
    - _Design: Testing_

- [✅] 3. Phase 3: 差速底盘位姿积分
  - [✅] 3.1 实现 `kinematics`
    - Create in `src/vrobot_sim/kinematics.py` the function `advance_pose(pose, v, omega, dt, segment_heading)`：
      直线子阶段位移方向取该段方向、θ 恒等于段方向；转向子阶段位移不变；θ 归一化到 -π 到 π 的左闭右开区间
    - _Acceptance: AC-kinematics-pose-integration, AC-kinematics-no-cross-track-drift_
    - _Design: Proposed Solution / Components_
  - [✅] 3.2 为位姿积分编写单元测试
    - Test 直线段与转向子阶段两种输入；θ 归一化的边界取值；直线子阶段横向偏移恒为 0
    - _Acceptance: AC-kinematics-pose-integration, AC-kinematics-no-cross-track-drift_
    - _Design: Testing_

- [✅] 4. Phase 4: 逐段控制器
  - [✅] 4.1 实现梯形速度剖面与段末切换
    - Create in `src/vrobot_sim/controller.py` the module `Controller`：段内按 `a_max_mps2` 加速、巡航、段末按
      `a_max_mps2` 主动减速至零；剩余长度不足以按该上限停住时立即转入减速；段末归零后切换到转向子阶段
    - _Acceptance: AC-kinematics-linear-speed-bound, AC-kinematics-linear-accel-bound, AC-kinematics-normal-decel-bound, AC-kinematics-segment-end-stop_
    - _Design: Proposed Solution / Key Mechanisms / 逐段行驶与节点转向_
  - [✅] 4.2 实现原地转向与对齐完成判定
    - Add `Controller.turn_step()`：按三角形剖面产出角速度，上限 `omega_max_radps`；剩余角不大于
      `turn_align_tolerance_rad` 时判定对齐完成，并在同一步把 θ 设为精确段方向
    - _Acceptance: AC-kinematics-angular-speed-bound, AC-kinematics-turn-no-overshoot, AC-kinematics-first-turn-align_
    - _Design: Proposed Solution / Key Mechanisms / 逐段行驶与节点转向_
  - [✅] 4.3 实现到达判定
    - Add 末段直线走完的判定：剩余段长小于 `arrival_tolerance_m` 且线速度归零即为到达，到达后不再有转向
    - _Acceptance: AC-kinematics-arrival_
    - _Design: Proposed Solution / Key Mechanisms / 逐段行驶与节点转向_
  - [✅] 4.4 为控制器编写单元测试
    - Test 五种临界取值：段长恰好等于刹车距离、剩余角恰好等于 `turn_align_tolerance_rad`、障碍最近点恰好落在前瞻
      区间末端、垂直距离恰好等于两半径之和、障碍覆盖区间恰好触及当前段终点
    - _Acceptance: AC-kinematics-segment-end-stop, AC-kinematics-turn-no-overshoot, AC-kinematics-angular-speed-bound_
    - _Design: Testing_

- [✅] 5. Phase 5: 前瞻安全距离与急停判定
  - [✅] 5.1 实现障碍物场
    - Create in `src/vrobot_sim/obstacle_field.py` the class `ObstacleField` with `register(obstacle)` and
      `deregister(obstacle_id)`：校验半径大于 0 与标识唯一，非法请求拒绝且集合不变，注销不存在返回未找到；注册在
      某车刹车距离内不算错误，受理照常成功
    - _Acceptance: AC-obstacle-invalid-radius-reject, AC-obstacle-effective-next-tick_
    - _Design: Proposed Solution / Interfaces / Protocols_
  - [✅] 5.2 实现前瞻判定与两种收尾
    - Create in `src/vrobot_sim/safety.py` the class `SafetyMonitor.check(robot, obstacles, segment, dt)`：先试
      车体圆与障碍圆相交（成立即归零，原因 `OVERLAP`）；未相交时先按垂直距离跳过侧向障碍，再看障碍在本段上的覆盖
      区间与前瞻区间 `[s, s + 刹车距离 + body_radius + v·dt]` 是否相交；区间在当前段终点截断
    - _Acceptance: AC-estop-trigger-before-contact, AC-estop-lateral-obstacle-no-trigger, AC-estop-no-overlap, AC-estop-stops-before-segment-end, AC-estop-straddling-obstacle-stops, AC-estop-initial-overlap, AC-kinematics-estop-decel-bound_
    - _Design: Proposed Solution / Key Mechanisms / 前瞻安全距离_
  - [✅] 5.3 为安全判定编写单元测试与对照组
    - Test 侧向障碍不触发；跨段端点用例（中心距 `N01` 10.05 米、半径 0.2 米）在 dt 0.02 与 0.05 下均以
      `SAFETY_DISTANCE` 停稳且两圆不相交；预置障碍场景在 dt 上限处不出现 `OVERLAP`
    - _Acceptance: AC-estop-lateral-obstacle-no-trigger, AC-estop-straddling-obstacle-stops, AC-estop-no-overlap, AC-estop-stops-before-segment-end_
    - _Design: Testing_

- [✅] 6. Phase 6: 机器人状态机与指令接收边界
  - [✅] 6.1 实现机器人运行时对象与转移表
    - Create in `src/vrobot_sim/robot.py` the class `Robot`：按 `design.md` State Machines 的 16 行转移实现，含
      `MOVING` 两行互斥 guard、`E_STOP` 的"再次成立需未相交"限定、"减速途中两圆开始相交"改写原因的一行、
      `ARRIVED` 受理时先转首段航向的处理；每 tick 顺序为安全判定、控制量计算、位姿积分
    - _Acceptance: AC-estop-resume-continues-path, AC-estop-resume-still-unsafe, AC-estop-resume-invalid-state, AC-estop-reassign-rejected, AC-state-unproduced-states, AC-kinematics-pose-integration_
    - _Design: Proposed Solution / State Machines_
  - [✅] 6.2 实现指令接收边界与内置直通指令源
    - Create `CommandSource` 协议（`ASSIGN_PATH` 与 `RESUME` 两种载荷、同步受理结果、状态门禁与结构化拒绝）与
      `PassthroughCommandSource`（在机器人 `start_tick` 把 `planned_node_path` 原样放进载荷）；机器人只认载荷序列
    - _Acceptance: AC-command-source-swap, AC-path-task-accept_
    - _Design: Proposed Solution / Interfaces / Protocols_
  - [✅] 6.3 实现路径可用性判定
    - Add `Robot._validate_path(node_path)`：用 `edge_by_node_pair` 校验首节点等于当前节点、每对相邻节点之间存在
      方向合规的边；多个问题同时成立时一次返回全部违规项，错误内容至少包含缺失节点对与两侧节点标识
    - _Acceptance: AC-path-missing-edge-reject, AC-path-single-way-violation-reject, AC-path-unknown-node-reject, AC-path-start-node-mismatch-reject, AC-path-task-accept_
    - _Design: Proposed Solution / Components_
  - [✅] 6.4 为状态机与指令边界编写测试
    - Test 全部转移路径与三类路径拒绝；用替身指令源跑同一场景，断言 `robot` 与 `kinematics` 代码路径未变且逐 tick
      输出一致
    - _Acceptance: AC-command-source-swap, AC-state-unproduced-states, AC-path-missing-edge-reject, AC-path-start-node-mismatch-reject_
    - _Design: Testing_

- [✅] 7. Phase 7: 仿真内核、快照与配置校验
  - [✅] 7.1 实现离散时钟与推进
    - Create in `src/vrobot_sim/simulation.py` the class `Simulation`：`create(scenario)` 与 `step()`，每步仿真
      时间前进一个 dt、每台机器人各推进一次、不读真实时间；全部机器人到达或急停后推进仍返回快照
    - _Acceptance: AC-sim-step-advances-fixed-dt, AC-sim-snapshot-complete_
    - _Design: Proposed Solution / Components_
  - [✅] 7.2 实现不可变快照
    - Create `src/vrobot_sim/snapshots.py` with `TickSnapshot` 与 `RobotSnapshot`：机器人按 `robot_id` 升序，字段为
      tick 序号、仿真时间、位姿三分量、线速度、角速度、状态与急停原因；不含临界区占用字段
    - _Acceptance: AC-sim-snapshot-complete_
    - _Design: Proposed Solution / Data Model_
  - [✅] 7.3 实现场景配置与创建期校验
    - Create in `src/vrobot_sim/scenario.py` the `Scenario` 配置对象与 `validate()`：`map_id` 只认 `minimal` 与
      `demo`、dt 在 0 到 0.05、起始节点存在、路径长度至少 2 且首标识等于 `start_node_id`、底盘上限为正、
      `turn_align_tolerance_rad` 除以 dt 不大于 `omega_max_radps`；失败时列出全部违规项
    - _Acceptance: AC-sim-invalid-dt-reject, AC-sim-invalid-map-id-reject, AC-sim-invalid-turn-tolerance-reject_
    - _Design: Proposed Solution / Components_
  - [✅] 7.4 为内核与配置校验编写测试
    - Test 同一场景两次运行的快照逐字段一致；三类非法配置各断言创建失败且返回全部违规项
    - _Acceptance: AC-sim-deterministic, AC-sim-invalid-dt-reject, AC-sim-invalid-map-id-reject, AC-sim-invalid-turn-tolerance-reject_
    - _Design: Testing_

- [✅] 8. Checkpoint - 单车行驶与安全停止闭环
  - Run `pytest tests -q`
  - Verify `AC-kinematics-arrival`, `AC-estop-trigger-before-contact`, `AC-estop-no-overlap`,
    `AC-estop-straddling-obstacle-stops`, `AC-estop-resume-continues-path`, `AC-command-source-swap`
  - Pass when 极简地图上的完整任务跑通、逐 tick 约束断言全部通过、急停与恢复用例通过；任一断言失败或出现设计外的
    状态取值即停止
  - _Acceptance: AC-kinematics-arrival, AC-estop-trigger-before-contact, AC-estop-no-overlap, AC-estop-straddling-obstacle-stops, AC-estop-resume-continues-path, AC-command-source-swap_
  - _Design: Testing_

- [✅] 9. Phase 9: 集成测试套件
  - [✅] 9.1 编写极简地图完整任务测试
    - Test 单台机器人在 `minimal` 地图从 `N01` 到 `N03`：逐 tick 断言五条约束上限类 AC、到达位姿落在末段中心线上、
      期望值按整数坐标解析算出
    - _Acceptance: AC-kinematics-linear-speed-bound, AC-kinematics-linear-accel-bound, AC-kinematics-normal-decel-bound, AC-kinematics-angular-speed-bound, AC-kinematics-arrival, AC-kinematics-no-cross-track-drift_
    - _Design: Testing_
  - [✅] 9.2 编写急停三用例与恢复测试
    - Test 预置障碍逐步接近、跨段端点、行驶中或急停减速中迟注册三个用例，分别断言原因取值唯一且符合各自 AC；另测
      注销障碍后恢复行驶能走完原路径剩余部分
    - _Acceptance: AC-estop-trigger-before-contact, AC-estop-straddling-obstacle-stops, AC-estop-late-registration-overlap, AC-estop-resume-continues-path, AC-estop-initial-overlap, AC-estop-resume-still-unsafe_
    - _Design: Testing_
  - [✅] 9.3 编写 demo 地图构建期测试
    - Test demo 地图通过构建期校验且环路、多临界区共享边、单向边与占位属性齐备；本阶段不断言多车行为
    - _Acceptance: AC-map-demo-ring-dependency, AC-map-edge-attributes-complete, AC-map-critical-zone-members-exist_
    - _Design: Testing_

- [✅] 10. Checkpoint - AC 覆盖与规范一致
  - Run `pytest tests -q` 与 design.md 的 43 条 AC 覆盖比对
  - Verify 每条 AC 至少被一个任务或 Checkpoint 覆盖；急停减速过程的每步上限只由
    `AC-kinematics-estop-decel-bound` 断言，不并入其他 THEN
  - Pass when 全部用例通过且覆盖比对无缺项；出现未覆盖 AC 即停止并回到计划
  - _Acceptance: AC-kinematics-estop-decel-bound, AC-obstacle-effective-next-tick, AC-obstacle-invalid-radius-reject, AC-state-unproduced-states_
  - _Design: Testing_

- [✅]* 11. Optional Phase: 基准测量与结论记录
  - [✅]* 11.1 编写 10 台规模基准测试
    - Test 场景固定为 demo 地图、10 台机器人各一条合法路径与 3 个固定位置障碍物，连续推进 1000 tick，产出平均与
      P95 单步耗时并标注平均值是否小于 dt；10 台允许互相穿行，因为本项不检测机器人之间的几何重叠
    - _Acceptance: AC-bench-step-cost-measured_
    - _Design: Testing_
  - [✅]* 11.2 把基准结论记入 spec 目录
    - Create `specs/sim-kinematics/benchmark-notes.md`，记录实测单步耗时与 dt 的关系，作为
      `WI-scale-50-robots` 的输入；该测试不参与常规构建失败判定
    - _Design: Open Questions_

## Notes

- Tasks marked with `*` may be skipped in MVP mode.
- Keep task numbering stable after execution begins.
- `design.md` is the source of truth; do not copy full AC text into this file.
- 本设计无数据库与外部集成，故无迁移与 SQL 任务；地图数据是代码内置常量，持久化归 `WI-map-editor`。
- 以下能力属已批准的 Non-Goals，实施时不要顺手加：路权互斥与死锁处理、浏览器可视化、路径规划、地图文件格式、外部
  调度器协议、50 台规模优化、通信层、异常态注入、脚本化无头运行与事件日志导出、角加速度约束、机器人之间的重叠检测。
- `pyproject.toml` 的包名与目录 `src/vrobot_sim/` 是本计划的命名假定；改名只调整路径，不改变任何 AC 与契约。
