# Execution Evidence

- **Execution baseline**: 开始执行时 `D:\Workspace\python\VirtualRobot` 不是 git 仓库（`git status` 报
  `not a git repository`），因此没有 HEAD commit 可引用。开始时的目录内容只有
  `design-chain-skill-audit.md`、`projects/virtual-robot/project.md`、`projects/virtual-robot/backlog.md`、
  `specs/sim-kinematics/{design.md,review.md,tasks.md}` 五份文档，无任何代码、`pyproject.toml`、虚拟环境或测试。
  本次交付的目标范围是新建 `src/vrobot_sim/`、`tests/`、`pyproject.toml`、`.venv`、`AGENTS.md`，
  对 `tasks.md` 只写回 checkbox，其余四份既有文档未被修改、未被覆盖，也不存在需要保留的既有用户代码改动。
- **Input revisions**（内容 SHA-256，执行结束时复算）：
  - `specs/sim-kinematics/design.md` — `c5ad49a068fd8e405c0ad0e11b4ce2188f5e1034b625f625c10fdbdbbb4e9799`（43 条 AC，全部唯一且可被 `tasks.md` 解析）
  - `specs/sim-kinematics/tasks.md` — `4e59f2edd7a4c2dc5ebdd8eb5d188339c6ba03ba733f4e6d21109e556904d8fa`（相对计划只改了 30 个 checkbox：27 个必需项 `[✅]`、3 个可选项 `[✅]*`）
  - `pyproject.toml` — `4f683192e811115584101da882ce7d3b84efadac4c014e39e1aa754d8054483b`
  - `tests/conftest.py` — `cae128eaac6d92bbf0a020a312f33f6950be62d9391e72a15fe1024aaa93617b`（默认底盘参数与 dt，逐条对照 design.md 的 chassis-config）
  - 仓库指导：仓库内不存在 `AGENTS.md`/`CLAUDE.md`/README（根目录、父目录与模块目录均已检查），
    `AGENTS.md` 是本次实现新增，内容与交付后的结构一致。
- **Validation environment**: 执行目录 `D:\Workspace\python\VirtualRobot`；`.venv` 由 `py -3 -m venv .venv` 创建，
  解释器 CPython 3.13.9（design.md 选定的开发运行时，系统默认 `python` 为 3.14.2，未使用）；
  `pytest 9.2.0`（`pip 25.2` 从网络安装的唯一开发依赖）；`src` 通过 `pyproject.toml` 的
  `pythonpath = ["src"]` 导入，不安装本包；无外部服务、无数据库、无网络调用参与验证。
- **Manifest command**: `node C:\Users\wenlong.chen\.agents\skills\code-review\scripts\review-manifest.mjs --exclude specs/sim-kinematics/code-review.md --exclude specs/sim-kinematics/exec-evidence.md`
- **Diff fingerprint**: 省略。该脚本以 `git rev-parse HEAD` 为前置条件，本工作区不是 git 仓库，脚本无法运行；
  未擅自 `git init` 改变仓库形态。替代证据是交付物内容的自算哈希（口径：`src/`、`tests/`、`pyproject.toml`、
  `AGENTS.md` 下所有 `.py`/`.toml`/`.md` 按路径排序后拼接）：
  `sha256:f4039ab6af5b76b11fd212b0362e36a202c7ffa158602a06279edbec36b7f080`。
  由于没有 VCS 基线，改动归因只能靠该内容哈希与上面的目录快照，`code-review` 需要重新执行验证并自行比对。
- **Validation**:
  - `.venv/Scripts/python.exe -m pytest tests -q`：**passed，121 passed in 0.27s**（每个 Phase 门槛与 Final 门槛各跑一次，最后一次在上面这组哈希之后复跑，结果一致）
  - `.venv/Scripts/python.exe -m compileall -q src tests`：**passed**（无语法错误）。项目未声明 linter 或类型检查器，
    `dev` 依赖组按 design.md 只允许 `pytest`，因此未安装 mypy/ruff；静态检查以 `compileall` 为最强可用手段，
    架构与规范类约束改由下面的 diff 人工核对完成。
  - 导入方向与依赖政策（grep 全量核对，passed）：`src` 内非 `vrobot_sim` 的 import 只有
    `__future__/math/dataclasses/enum/types/typing`，运行时零第三方依赖成立；
    运行时模块图为 `map_model`、`kinematics`、`obstacle_field` 三个叶子，`controller` 无运行时包内依赖，
    `robot → {controller, kinematics, map_model, obstacle_field}`，`safety → robot`，`snapshots → robot`，
    `scenario → {map_model, maps, obstacle_field, robot}`，`simulation` 在最上层，无环。
  - 越界与非目标扫描（grep，passed）：`src` 内无 `zone_occup*`/`right_of_way`/`http`/`socket`/`argparse`/
    `random`/`time.time`/`sleep` 命中，即未顺手实现路权互斥、临界区占用字段、通信层、CLI、随机源与真实时钟；
    快照字段名逐一比对为声明的 8 项，不含临界区占用字段。
  - 空白符检查（`git diff --check` 不可用的替代，passed）：`src/`、`tests/`、`pyproject.toml` 无行尾空格、无 Tab、无 CR。
  - AC 覆盖比对（脚本 + `pytest --collect-only`，passed）：43 条 AC 全部被至少一个测试覆盖，
    映射到的测试名全部存在于收集结果中；逐条对应关系见下节。
  - 基准（可选 Phase 11，passed）：demo 地图 10 台 3 障碍连续 1000 tick，三次独立运行平均单步 0.0527–0.0567 ms、
    P95 0.0638–0.0770 ms，均远小于 dt = 20 ms；数据与口径记入 `benchmark-notes.md`。

## AC 覆盖对应关系

| AC | 证据测试 |
|----|----------|
| AC-kinematics-pose-integration | test_kinematics::直线位移/转向不位移/θ 归一化边界/连续转向落在半开区间 + test_robot::受理路径后到达 |
| AC-kinematics-no-cross-track-drift | test_kinematics::直线子阶段横向偏移恒为 0 + test_integration_minimal::θ 归一化且质心贴中心线 |
| AC-kinematics-segment-end-stop | test_robot::段末归零后原地转向 + test_controller::整段剖面停在段末 |
| AC-kinematics-turn-no-overshoot | test_controller::剩余角恰好等于容差/完整转向落在精确航向且不过冲 |
| AC-kinematics-first-turn-align | test_robot::初始航向不一致时先原地转向 |
| AC-kinematics-arrival | test_robot::到达终点点位且不再转向 + test_integration_minimal::解析端点 |
| AC-kinematics-linear-speed-bound | test_controller::巡航被上限截断 + test_integration_minimal::逐 tick 上限 |
| AC-kinematics-linear-accel-bound | test_integration_minimal::逐 tick 上升量 + test_controller::短段 |
| AC-kinematics-normal-decel-bound | test_integration_minimal::无障碍场景每步下降量 + test_controller::整段剖面 |
| AC-kinematics-estop-decel-bound | test_controller::estop_step + test_robot::每步急停上限 + test_integration_estop::内核内每步上限（仅此条 AC 断言该性质） |
| AC-kinematics-angular-speed-bound | test_controller::完整转向 + test_integration_minimal::转向 tick 数与角速度上限 |
| AC-path-task-accept / -missing-edge-reject / -single-way-violation-reject / -unknown-node-reject / -start-node-mismatch-reject | test_robot 五条同名拒绝与受理用例 + test_integration_demo::逆行单向边被拒且保持 IDLE |
| AC-estop-trigger-before-contact | test_safety::落在前瞻区间内触发 + test_integration_estop::预置障碍停住且不相交 |
| AC-estop-late-registration-overlap | test_robot::迟注册归零 + test_integration_estop::行驶中迟注册、减速途中改写原因 |
| AC-estop-lateral-obstacle-no-trigger | test_safety::侧向越门槛被跳过 + 垂直距离恰好等于两半径之和的对照组 |
| AC-estop-no-overlap | test_safety::dt 上限处预置障碍场景不出现 OVERLAP + test_integration_estop::停稳后两圆间隙 |
| AC-estop-stops-before-segment-end | test_robot::停在段终点前且段位置不变 + test_integration_estop::跨段端点用例 |
| AC-estop-straddling-obstacle-stops | test_safety::跨段端点在 dt 0.02 与 0.05 下均停稳 + test_integration_estop::本段计入前瞻 |
| AC-estop-resume-continues-path | test_robot::注销后恢复走完剩余路径 + test_integration_estop::内核版本 |
| AC-estop-resume-still-unsafe | test_robot::仍不安全时保持急停与位姿 + test_integration_estop::内核版本 |
| AC-estop-resume-invalid-state | test_robot::三种非 E_STOP 状态参数化 + test_integration_estop::行驶中 RESUME 被拒 |
| AC-estop-reassign-rejected | test_robot::E_STOP 中改道被拒且路径不变 + test_integration_estop::经指令边界投递并断言 INVALID_STATE |
| AC-estop-initial-overlap | test_robot::起始即相交第一 tick 急停 + test_integration_estop::参数化 OVERLAP 分支 |
| AC-state-unproduced-states | test_robot::两张内置地图参数化，状态只落在四个成员内 |
| AC-command-source-swap | test_robot::替身指令源逐 tick 输出一致且 `Robot.tick`/`advance_pose` 归属模块未变 |
| AC-map-edge-attributes-complete | test_map_model::五项属性可读 + 距离代价等于派生长度 |
| AC-map-critical-zone-members-exist | test_map_model::成员边均存在 + 成员边缺失被拒 + test_integration_demo::幻成员边构建失败 |
| AC-map-parallel-edge-reject | test_map_model::同一有序节点对两条边被拒并指出节点对 |
| AC-map-invalid-edge-reject | test_map_model::端点不存在被拒并指出边标识 |
| AC-map-demo-ring-dependency | test_map_model::环路三环边分属互斥临界区 + test_integration_demo::环路形状与共享边校验 |
| AC-sim-step-advances-fixed-dt | test_simulation::每步恰好前进 dt 且每台机器人积分一次 |
| AC-sim-deterministic | test_simulation::同场景两次运行快照逐字段一致 |
| AC-sim-invalid-dt-reject | test_simulation::四种非法 dt 参数化，报字段与允许范围 |
| AC-sim-invalid-map-id-reject | test_simulation::未知 map_id 列出两个合法值 |
| AC-sim-invalid-turn-tolerance-reject | test_simulation::容差除以 dt 超角速度上限，给出机器人标识与两个比较值 |
| AC-sim-snapshot-complete | test_simulation::快照字段逐项比对 + 不可变性 |
| AC-obstacle-effective-next-tick | test_simulation::注册后两台机器人次一 tick 起急停 + test_safety::刹车距离内注册照常受理 |
| AC-obstacle-invalid-radius-reject | test_safety::半径越界被拒且集合不变 |
| AC-bench-step-cost-measured | test_benchmark::10 台 demo 场景 1000 tick 平均与 P95，并标注是否小于 dt |

## 落地时的解释性决定（未改动任何 AC，供评审确认）

1. **`sim_time_s` 与 `tick_index` 的配对**：Data Flow 第 2 步是"先把仿真时间前进一步，再逐台机器人处理"，
   第 7 步是"快照内容全是本 tick 结束后的值"，因此第一次 `step()` 返回 `tick_index=0`、`sim_time_s=dt`；
   相邻快照的时间差恒为 dt，满足 AC-sim-step-advances-fixed-dt。
2. **段末落点吸附到节点**：离散剖面会让机器人以不超过 `arrival_tolerance_m` 的误差停在节点附近
   （实测最大 0.015 米，量级即 `v_max·dt/2`）。若不吸附，下一段中心线会带上同量级横向偏移，
   与 AC-kinematics-no-cross-track-drift 的"不产生横向偏移"和 `minimal` 地图整数坐标的解析期望冲突，
   因此在段末归零的那一步把质心设为节点精确坐标，与 design 已批准的 θ 吸附是同一条理由。
3. **速度剖面用解析弧线 + 单步下降下限**：`target = max(v - a_max·dt, min(v_max, v + a_max·dt, sqrt(2·a_max·剩余长)))`。
   先试过纯触发式 bang-bang，会在刹车线附近来回加减速（实测出现两段减速区间）；改用弧线后
   每步上升与下降都精确等于 `a_max·dt`，剖面单调且实测不越过段末超过 `arrival_tolerance_m`。
4. **RESUME 的前瞻判定参考速度**：按每 tick 公式取当前速度时，静止机器人的刹车距离为 0，
   前瞻窗口只剩车体半径，"障碍物仍在正前方"恢复起来恒判为安全，AC-estop-resume-still-unsafe 无法成立
   （恢复后会立即再次触发急停，形成反复）。因此恢复判定改用该车 `v_max` 作为参考速度，
   正常每 tick 判定仍用当前速度。这是设计文字未钉死的取值，需要评审确认。
5. **Phase 边界的两处归属**：任务 4.1/4.3 引用的 `AC-kinematics-segment-end-stop` 与 `AC-kinematics-arrival`
   是可观察状态转移，实现在 `robot.py`（Phase 6），判定谓词在 `controller.py`（Phase 4）；
   因此 4.1/4.3 先标记完成，两条 AC 的直接证据来自 test_robot、test_integration_minimal 与 Checkpoint 8。
6. **`EStopReason` 的位置导致一处注入**：任务 1.2 把 `EStopReason` 钉在 `robot.py`，而 `safety` 需要产出它，
   为避免运行时导入环，`Robot` 由 `simulation` 注入 `SafetyMonitor`，`robot.py` 只在 `TYPE_CHECKING` 下引用它。
   每 tick 仍然是"安全判定 → 控制量 → 位姿积分"的调用序，契约未变。
7. **`beyond` 场景未测项**：本项不含机器人之间几何重叠检测（Non-Goal），基准场景 10 台允许互相穿行，
   `benchmark-notes.md` 已注明该数据不代表本体间碰撞已排除。
