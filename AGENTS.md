# VirtualRobot

虚拟 AMR 调度验证项目。当前已交付 `WI-sim-kinematics`（差速底盘运动学仿真内核），
其余能力按 `projects/virtual-robot/backlog.md` 推进。

## 结构

- `src/vrobot_sim/` — 仿真内核库。`map_model`（拓扑地图与构建期校验）、`kinematics`（位姿积分）、
  `controller`（逐段速度剖面）、`safety`（前瞻安全距离与相交兜底）、`robot`（状态机与指令接收边界）、
  `rights`（路权协议与结果枚举）、`dispatcher`（内置 FCFS 调度器）、`simulation`（离散时钟）、
  `scenario`（场景配置与创建期校验）、`obstacle_field`（障碍物注册）、`snapshots`（不可变快照）、
  `maps/`（两张内置示例地图）。
- `src/vrobot_web/` — 实时可视化 Web 层（FastAPI + uvicorn + Canvas 前端），单向依赖 `vrobot_sim`，
  通过 `web` extra 安装。
- `tests/` — pytest 套件，含单元、场景、契约与基准测试。
- `projects/virtual-robot/` — 项目方向与滚动 backlog。
- `specs/<topic>/` — 单项需求的 design.md（行为与验收）、tasks.md（执行计划）、exec-evidence.md（验证证据）。

## 命令

```bash
py -3 -m venv .venv                 # 开发运行时固定 3.13.9，包下限 3.11
.venv/Scripts/python.exe -m pip install -e ".[dev,web]"
.venv/Scripts/python.exe -m pytest tests -q
.venv/Scripts/python.exe -m vrobot_web --port 8000   # 浏览器打开 http://127.0.0.1:8000
```

测试通过 `pyproject.toml` 的 `pythonpath = ["src"]` 直接导入包，不需要安装本包。

## 约定

- 内核运行时零第三方依赖；Web 层依赖 FastAPI、uvicorn 与 websockets（uvicorn 的 WebSocket 协议实现），
  只放在 `web` extra 里，内核不导入 Web 层。
  `dev` 依赖组只有 `pytest` 与 `httpx`（`TestClient` 使用）。不要为省事在内核引入 numpy、pydantic 或网络库。
- 依赖方向：`map_model`、`kinematics`、`obstacle_field`、`rights` 是叶子模块，不导入包内任何其他模块；
  `controller`、`robot`、`safety`、`snapshots` 只能向上依赖它们；`dispatcher`、`simulation`、`scenario`
  在最上层。
- `RobotStatus`、`EStopReason`、`CommandKind` 这几个共享枚举定义在 `robot.py`，因此 `safety` 与
  `snapshots` 运行时导入 `robot` 是允许的、也是单一归属的要求；反过来 `robot.py` 不得运行时导入
  `safety`，否则构成导入环。`Robot` 需要的 `SafetyMonitor` 由 `simulation` 构造时注入，
  `robot.py` 只在 `TYPE_CHECKING` 下引用它。每 tick 调用序仍是"安全判定 → 控制量 → 位姿积分"。
  路权结果枚举 `GrantOutcome` 定义在 `rights.py`，`robot` 与 `dispatcher` 只依赖该模块。
- 地图数据、底盘配置、快照都是构建后不可变的（frozen dataclass + 只读派生索引）；
  运行时可变状态只允许存在于 `Robot` 实例与调度器的路权状态（每区持有者、等待队列与申请条目）上。
  调度器状态属于单个 `Simulation` 实例，不跨实例共享。
- 地图构建、仿真创建与障碍物注册三处都是先完整校验再一次生效，错误要列出全部违规项，
  不产出半成品对象。
- 内置示例地图标识固定为 `minimal` 与 `demo`，加载入口只认这两个值。
- 内核不读真实时间、不提供 CLI 与网络服务；倍速与暂停由调用方表达。

改动运动学、地图契约或状态枚举前，先读 `specs/sim-kinematics/design.md` 的 Decision Record 与
Acceptance Criteria；这三份契约由 `WI-mutex-scheduling` 与 `WI-live-visualization` 共用。
