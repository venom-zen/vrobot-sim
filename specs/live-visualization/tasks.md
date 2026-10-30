# Implementation Plan: Live Visualization

## Overview

本计划把 `design.md` 的 Web 层拆成 5 个功能阶段与 4 个 Checkpoint。实现顺序是：先声明依赖并建立
可安装的包骨架，再实现纯函数式的场景校验与 BFS 推导，随后实现持有 `Simulation` 的推进器与实时
广播，接着接入 HTTP 与 WebSocket 契约，最后完成 Canvas 前端与端到端验收。内核 `vrobot_sim`
不修改，`vrobot_web` 单向依赖内核；Web 依赖只进入 `web` extra。`design.md` 是行为与 AC 的
唯一来源，本计划不新增或改写 AC。

## Tasks

- [✅] 1. Phase 1: 依赖与包骨架
  - [✅] 1.1 声明 Web 依赖与静态资源打包
    - Modify `pyproject.toml`：新增 `[project.optional-dependencies] web = ["fastapi", "uvicorn"]`，
      保持 `dependencies = []`；在 `dev` extra 中加入 `httpx` 供 `TestClient` 使用
    - 新增 `[tool.setuptools.package-data]`，声明 `vrobot_web = ["static/*"]`
    - _Design: Proposed Solution / Architecture, Decision Record / DR-web-stack-fastapi_
  - [✅] 1.2 更新 AGENTS.md 的内核依赖约定
    - Modify `AGENTS.md`：把运行时零第三方依赖的约定改为内核零依赖、Web 层通过 optional extra 引入
      FastAPI 与 uvicorn；保留"内核不读墙钟、不提供 CLI 与网络服务"
    - _Design: Discovery / Scope Decisions_
  - [✅] 1.3 创建应用工厂骨架
    - Create `src/vrobot_web/__init__.py` 与 `src/vrobot_web/app.py`，实现 `create_app()`，注册 HTTP
      与 WebSocket 路由、挂载 `static/`、管理推进任务生命周期；路由顺序为 API、WebSocket、静态目录
    - Create `src/vrobot_web/static/` 目录占位，使 package-data 有可匹配内容
    - _Design: Proposed Solution / Architecture, Proposed Solution / Components_
  - [✅] 1.4 创建模块入口
    - Create `src/vrobot_web/__main__.py`，实现 `main()`；只接受 `--port`（默认 8000），调用
      `uvicorn.run` 并把绑定地址固定为 `127.0.0.1`
    - _Design: Proposed Solution / Architecture, Decision Record / DR-web-layer-outside-kernel_
  - [✅] 1.5 建立 Web 测试的跳过机制
    - Create `tests/vrobot_web/conftest.py`，用 `pytest.importorskip("fastapi")` 与
      `pytest.importorskip("httpx")` 让 Web 测试在未安装 `web` extra 时整体跳过
    - _Design: Testing_

- [✅] 2. Checkpoint - Verify package skeleton
  - Run `pip install -e ".[dev,web]"` and `python -c "from vrobot_web.app import create_app;
    from vrobot_web.__main__ import main; create_app()"`
  - Run `python -m vrobot_web --help` and confirm only `--port` is offered, with no address option
  - Pass when imports succeed, the factory builds an app without binding a socket, and the help output
    exposes `--port`; stop on failure or missing dependency
  - _Design: Proposed Solution / Architecture_

- [✅] 3. Phase 2: 场景配置与路径推导
  - [✅] 3.1 定义场景配置模型
    - Create `src/vrobot_web/scene.py` with `RobotConfig` and `SceneConfig`：`robots` 长度 1-10，
      字段 `robot_id`、`start_node_id`、`waypoints`、`target_node_id`
    - _Design: Proposed Solution / Data Model_
  - [✅] 3.2 实现锚点校验、BFS 推导与违规收集
    - 在 `scene.py` 实现 `resolve_scene(config)`：校验数量、`robot_id` 唯一、起点唯一、起点不等于
      终点、锚点相邻不同、锚点存在于 demo 地图，一次收集全部违规
    - 按锚点链分段，在 `TopologyMap.edge_by_node_pair` 上做 BFS；同层按节点标识升序保证结果确定，
      各段去掉与上一段重复的起点后拼接；取首段航向作为 `start_theta_rad`
    - 用推导结果构造 `Scenario` 与 `RobotSpec`，返回每台车的完整节点路径
    - _Acceptance: AC-scene-apply-builds, AC-path-anchor-order, AC-path-one-way-detour,
      AC-scene-reject-duplicate-start, AC-scene-reject-unreachable, AC-scene-reject-bounds,
      AC-scene-reject-degenerate-anchors_
    - _Design: Proposed Solution / Key Mechanisms, Decision Record / DR-scene-anchor-paths_
  - [✅] 3.3 定义序列化模型
    - Create `src/vrobot_web/schemas.py` with `MapPayload`、`SnapshotPayload`、`StatusFrame`、
      `TickFrame`；字段名与 `TickSnapshot` 一一对应，`status` 与 `estop_reason` 取枚举值
    - _Acceptance: AC-snapshot-fidelity_
    - _Design: Proposed Solution / Data Model_
  - [✅] 3.4 补场景单元测试
    - Add `tests/vrobot_web/test_scene.py`：直达、途经、单行绕行、不可达、重复起点、数量越界与
      退化锚点；断言 N03→N02 走 N03→N01→N02，N01→N03 无途经时直达
    - _Acceptance: AC-path-anchor-order, AC-path-one-way-detour,
      AC-scene-reject-duplicate-start, AC-scene-reject-unreachable, AC-scene-reject-bounds,
      AC-scene-reject-degenerate-anchors_
    - _Design: Testing_

- [✅] 4. Checkpoint - Verify scene derivation
  - Run `python -m pytest tests/vrobot_web/test_scene.py`
  - Verify `AC-scene-apply-builds`、`AC-path-anchor-order`、`AC-path-one-way-detour` 与四条
    `AC-scene-reject-*`
  - Pass when every scene case passes and each rejection returns all applicable violations; stop on
    failure or spec conflict
  - _Acceptance: AC-scene-apply-builds, AC-path-anchor-order, AC-path-one-way-detour,
    AC-scene-reject-duplicate-start, AC-scene-reject-unreachable, AC-scene-reject-bounds,
    AC-scene-reject-degenerate-anchors_
  - _Design: Testing_

- [✅] 5. Phase 3: 推进器与实时广播
  - [✅] 5.1 实现 SimulationDriver 状态机
    - Create `src/vrobot_web/driver.py` with `SimulationDriver`：持有 `Simulation`、`mode`、推进任务
      与订阅者集合，模式为 `unconfigured`、`configured`、`running`、`paused`
    - 应用配置或重置时重建 `Simulation`，调用一次 `step()` 取得 `tick_index=0` 快照；启动、暂停、
      继续与重置按状态机迁移，非法动作返回可转 409 的结果
    - _Acceptance: AC-control-start, AC-control-pause-resume, AC-control-reset_
    - _Design: Proposed Solution / State Machines, Decision Record / DR-driver-asyncio-realtime_
  - [✅] 5.2 实现 50 tick/s 推进与广播
    - 推进任务维护单调递增 deadline，每 0.02 s 调用 `step()`；每 tick 只序列化一次并向所有订阅者
      发送 `TickFrame`，暂停时停在循环顶部且不发帧
    - 单连接发送设 1 秒超时；超时、发送失败或连接关闭时关闭并移除该连接，推进任务与其他连接不受
      影响
    - _Acceptance: AC-stream-tick-frames, AC-stream-paused-silent_
    - _Design: Proposed Solution / Key Mechanisms_
  - [✅] 5.3 实现状态帧与重连对齐
    - 连接建立与每次模式切换时发送 `StatusFrame`；`unconfigured` 时 `snapshot` 为 `null`，其余模式
      携带最新快照；服务端不保留历史帧
    - _Acceptance: AC-stream-initial-frame, AC-stream-reconnect_
    - _Design: Proposed Solution / Data Model, Proposed Solution / Key Mechanisms_
  - [✅] 5.4 补推进器测试
    - Add `tests/vrobot_web/test_driver.py`：tick 0 快照、启动/暂停/继续/重置、暂停静默、1 秒超时
      移除慢连接、重连拿到最新快照；用短 dt 或可注入时钟控制节奏
    - _Acceptance: AC-control-start, AC-control-pause-resume, AC-control-reset,
      AC-stream-initial-frame, AC-stream-tick-frames, AC-stream-paused-silent,
      AC-stream-reconnect_
    - _Design: Testing_

- [✅] 6. Phase 4: HTTP 与 WebSocket 接口
  - [✅] 6.1 实现地图读取接口
    - 在 `src/vrobot_web/app.py` 注册 `GET /api/map`，从内置 demo 地图构造 `MapPayload`，包含节点、
      边方向与区成员边；地图加载失败返回 500 `{"violations": [...]}`
    - _Design: Proposed Solution / Interfaces_
  - [✅] 6.2 实现场景应用接口
    - 注册 `PUT /api/scene`：调用 `resolve_scene` 并应用配置，返回 `{"mode": "configured",
      "resolved_paths": {...}, "snapshot": SnapshotPayload}`；`snapshot` 取自应用后一次 `step()`
    - 校验违规、内核拒绝与请求体解析失败统一返回 422 `{"violations": [...]}`；失败不改变当前仿真
      与运行模式
    - _Acceptance: AC-scene-apply-builds, AC-scene-reject-duplicate-start,
      AC-scene-reject-unreachable, AC-scene-reject-bounds, AC-scene-reject-degenerate-anchors_
    - _Design: Proposed Solution / Interfaces, Error Handling_
  - [✅] 6.3 实现控制接口
    - 注册 `POST /api/control`，接受 `start`、`pause`、`resume`、`reset`；当前状态不允许的动作返回
      409；非法动作值或缺少 `action` 返回 422 `{"violations": [...]}`
    - _Acceptance: AC-control-start, AC-control-pause-resume, AC-control-reset, AC-control-invalid_
    - _Design: Proposed Solution / Interfaces, Proposed Solution / State Machines_
  - [✅] 6.4 实现状态流 WebSocket
    - 注册 `/ws/state`：连接建立发送当前 `StatusFrame`，模式切换广播 `StatusFrame`，`running` 时
      每个 tick 广播 `TickFrame`；每个连接独立投递，失败或超时的连接被移除
    - _Acceptance: AC-stream-initial-frame, AC-stream-tick-frames, AC-stream-paused-silent,
      AC-stream-reconnect_
    - _Design: Proposed Solution / Interfaces, Proposed Solution / Key Mechanisms_
  - [✅] 6.5 补接口集成测试
    - Add `tests/vrobot_web/test_api.py`，用 FastAPI `TestClient` 覆盖场景应用 200 与逐类 422、控制
      状态机的全部合法与非法迁移、状态流首帧/逐 tick/暂停静默/重连，以及快照与内核逐字段一致
    - _Acceptance: AC-scene-apply-builds, AC-scene-reject-duplicate-start,
      AC-scene-reject-unreachable, AC-scene-reject-bounds, AC-scene-reject-degenerate-anchors,
      AC-control-start, AC-control-pause-resume, AC-control-reset, AC-control-invalid,
      AC-stream-initial-frame, AC-stream-tick-frames, AC-stream-paused-silent, AC-stream-reconnect,
      AC-snapshot-fidelity_
    - _Design: Testing_

- [✅] 7. Checkpoint - Verify HTTP and WebSocket contracts
  - Run `pip install -e ".[dev,web]"` then `python -m pytest tests/vrobot_web`
  - Verify scene, control, stream and snapshot ACs; confirm Web tests skip when the `web` extra is
    absent and the kernel suite is unaffected
  - Pass when all web tests pass and a kernel-only run collects without importing FastAPI; stop on
    failure or contract mismatch
  - _Acceptance: AC-scene-apply-builds, AC-control-start, AC-control-pause-resume, AC-control-reset,
    AC-control-invalid, AC-stream-initial-frame, AC-stream-tick-frames, AC-stream-paused-silent,
    AC-stream-reconnect, AC-snapshot-fidelity_
  - _Design: Testing_

- [✅] 8. Phase 5: 前端页面
  - [✅] 8.1 搭建页面结构与样式
    - Create `src/vrobot_web/static/index.html` 与 `style.css`：左侧场景编辑表格（增删机器人、
      起点/途经/终点下拉、应用按钮）、控制按钮、错误面板与连接指示；右侧 Canvas；无构建步骤、无 CDN
    - 未应用配置时禁用启动、暂停、继续与重置按钮
    - _Acceptance: AC-view-empty-state_
    - _Design: Proposed Solution / Components_
  - [✅] 8.2 实现地图、机器人与区渲染
    - Create `src/vrobot_web/static/app.js`：加载 `MapPayload` 绘制节点、单行边箭头、区标识与
      区成员边高亮带；按世界坐标等比缩放，窗口变化时重算
    - 用 `requestAnimationFrame` 绘制最新快照；机器人画朝向线、状态颜色与文字、瞬时速度；区上标注
      持有人与等待队列
    - _Acceptance: AC-view-map, AC-view-robots, AC-view-zone-occupancy_
    - _Design: Proposed Solution / Components, Proposed Solution / Data Flow_
  - [✅] 8.3 实现选中与路径高亮
    - 应用配置成功后默认选中第一台机器人；点击表格行或画布机器人切换选中；在画布高亮选中机器人的
      完整节点路径，路径节点与边加亮，起点与终点用不同标记
    - _Acceptance: AC-view-resolved-paths_
    - _Design: Proposed Solution / Components, Proposed Solution / Data Flow_
  - [✅] 8.4 实现控制、错误与连接状态
    - 连接 `/ws/state`，用首条 `StatusFrame` 对齐模式与快照；控制按钮按模式启用并调用
      `POST /api/control`；断开时显示断开状态并按 1 秒间隔重连
    - 配置失败时把响应中的全部 `violations` 显示在错误面板
    - _Acceptance: AC-view-config-errors, AC-view-connection, AC-view-empty-state_
    - _Design: Error Handling, Proposed Solution / Key Mechanisms_
  - [✅] 8.5 校验静态资源随包分发
    - 确认非 editable 安装后 `create_app()` 能定位 `static/*`；修正静态目录定位方式或 package-data
      配置
    - _Design: Proposed Solution / Architecture_

- [✅] 9. Checkpoint - Verify full delivery
  - Run `python -m pytest tests`（内核套件零改动通过；未装 `web` extra 时 Web 测试跳过）
  - Run `python -m pytest tests/vrobot_web` after `pip install -e ".[dev,web]"`
  - Run `python -m vrobot_web --port 8000`，分别用 10 车配置与三角环死锁配置人工观察 1× 实时运动、
    路径高亮、区占用、错误提示与断线重连
  - Verify `AC-kernel-untouched`、`AC-view-live-motion`、`AC-view-resolved-paths` 与其余
    `AC-view-*` 行为
  - Pass when the kernel suite passes unchanged, web tests pass, and the page shows continuous 1×
    motion with paths and zone occupancy visible; stop on failure or spec conflict
  - _Acceptance: AC-kernel-untouched, AC-view-live-motion, AC-view-resolved-paths_
  - _Design: Testing_

## Notes

- Tasks marked with `*` may be skipped in MVP mode.
- Keep task numbering stable after execution begins.
- `design.md` is the source of truth; do not copy full AC text into this file.
