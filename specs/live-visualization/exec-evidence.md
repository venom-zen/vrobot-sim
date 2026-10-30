# Execution Evidence

- **Execution baseline**: HEAD `08fc24bc837e012745b33b5476c7abe101aa081f`（branch `feat/live-visualization`）。
  开始时的既有用户改动为 `AGENTS.md`、`projects/virtual-robot/backlog.md`、
  `projects/virtual-robot/github-sync.json` 与未跟踪的 `docs/`、`specs/live-visualization/`，全部保留；
  本次交付新增 `src/vrobot_web/`、`tests/vrobot_web/`，并修改 `pyproject.toml` 与 `AGENTS.md`
  （`AGENTS.md` 的改动叠加在既有用户改动之上，内核目录 `src/vrobot_sim/` 与既有 `tests/` 文件零改动）。
- **Input revisions**:
  - `specs/live-visualization/design.md` `sha256:78784be25249bf6c03805a2dffb72b7f35323e39d710bde28d46ee166d8a4865`
  - `specs/live-visualization/tasks.md`（全部 checkbox 完成后） `sha256:f4f4f0a24986785848d0af1e7eef1c516272db9d3077d14435ff014504708def`
  - `AGENTS.md` `sha256:409dfa872e2b6184fee80c10833bb642e11a408c51b92d71ee02f151d5c00a90`
  - `pyproject.toml` `sha256:b214d5eac2da62358ff95d0b176289200b4b30453c2a6d470b36ec5b0c616704`
- **Validation environment**: `D:\Workspace\python\VirtualRobot`，`.venv` Python 3.13.9；
  fastapi 0.162.0、starlette 1.10.0、pydantic 2.14.1、uvicorn 0.54.0、websockets 17.3、
  httpx 0.28.1、pytest 9.2.0；`pip install -e ".[dev,web]"` 安装。人工验收使用本机 Chromium（Playwright MCP）。
- **Manifest command**: `node <code-review-skill>/scripts/review-manifest.mjs --exclude specs/live-visualization/code-review.md --exclude specs/live-visualization/exec-evidence.md`
- **Diff fingerprint**: `sha256:5283b8fa43abf1a12571bfccf737e8a860883b2caa3d1ead13d4b9262bef7131`
- **Validation**:
  - `python -m pytest tests -q`: passed，217 项通过（168 内核 + 49 Web），内核套件零改动通过。
  - `python -m pytest tests/vrobot_web -q`: passed，49 项通过（scene 14 / driver 8 / api 27）。
  - `python -m pytest tests -q`（以 `sys.meta_path` 屏蔽 `fastapi`、`httpx` 模拟未装 `web` extra）:
    passed，168 passed + 1 skipped，收集过程不导入 FastAPI。
  - `pip install -e ".[dev,web]"` + `python -c "from vrobot_web.app import create_app; from vrobot_web.__main__ import main; create_app()"`:
    passed，工厂构表不绑定套接字。
  - `python -m vrobot_web --help`: passed，只暴露 `--port`（默认 8000），无地址选项。
  - `python -m vrobot_web --port 8000` 冒烟：`GET /` 200、`GET /api/map` 200、
    `GET /ws/state` 带 Upgrade 头返回 101。
  - `pip wheel .` + `pip install --target` 非 editable 安装：wheel 含 `vrobot_web/static/{index.html,style.css,app.js}`，
    安装后 `STATIC_DIR` 存在且 `create_app()` 构建成功。
  - 浏览器人工验收（`--port 8123`，多途经点在 `--port 8124` 复核）：10 车配置连续 1× 运动（1.5 s 间隔两帧位置递进、巡航 1.50 m/s，无卡顿）；
    三角环配置出现 Z01/Z02/Z03 各自持有并等待下一区的环形等待，三区同时显示 `持有:` 与 `等待:` 队列；
    应用配置后默认选中 R1 并高亮路径（起点绿环、终点橙方框），点击表格行切换到 R2 后高亮随之改变；
    每行可增删途经点，配置 N01→[N08, N10]→N09 时提交 `waypoints: ["N08", "N10"]`，响应路径与画布高亮为
    `N01→N08→N10→N09`；删除到单个途经点提交 `["N08"]`，选择「无」提交 `[]`；三行环配置应用后路径正确，
    启动后三车同时行驶、三个区各自显示 `持有:`，暂停/继续按钮状态正确；
    起点等于终点时错误面板一次列出两条违规且运行状态不变；未应用配置时四个控制按钮全部禁用；
    运行中暂停后重置，页面回到 tick 0 画面，与重新应用配置后的画面逐像素一致，
    `POST /api/control` 的 reset 响应快照与 `PUT /api/scene` 响应快照逐字段相等；
    停止服务端后连接指示变为「已断开，正在重连」，重启后 1 秒内自动重连并按首条 `StatusFrame` 对齐为「未配置」。
  - `git diff --check`: passed（仅 Git 的 LF/CRLF 换行提示，无空白错误）。
- **WebSocket dependency**: `web` extra 为 `["fastapi", "uvicorn", "websockets"]`：uvicorn 的基础安装不含
  WebSocket 协议实现，缺少 `websockets` 时真实服务端 `/ws/state` 握手返回 404（`TestClient` 走进程内 ASGI，
  因此测试无法暴露该缺口）。`design.md` 的 DR-web-layer-outside-kernel 与 `AGENTS.md` 均按此记录。
