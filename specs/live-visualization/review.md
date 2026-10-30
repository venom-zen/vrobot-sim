# Live Visualization Design Review

> 对 `specs/live-visualization/design.md` 的设计评审。Verdict 是评审时快照；当前流程状态见 Current Readiness。

## Verdict

- **Review round**: R2
- **Review mode**: Closure
- **Mode reason**: R1-refine-1 后 Current Readiness 为 `ready-for-closure`，`Next review mode` 为 `Closure`，
  `Refine validation` 为 `Passed`；用户明确要求 Closure Review。refine 预判值：Closure，与实际模式一致。
- **Overall at review**: Pass
- **spec-plan readiness at review**: Go
- **Findings**: 0 Blocker / 0 Major / 0 Minor
- **Summary**: F-001 到 F-006 均按冻结的 Closure test 闭合，原反例已被设计阻止；结构、标识符与成对契约
  检查通过。设计可以进入 `spec-plan`，实现阶段需落实 package-data、路径高亮、tick 0 语义与 1 秒发送
  超时等设计约束。

## Scope Reviewed

- **Reviewed file**: `specs/live-visualization/design.md`
- **Project baseline**: `08fc24b`（分支 `feat/live-visualization`）；工作区含未提交的 `AGENTS.md`、
  backlog 对账变更与 `specs/live-visualization/`。
- **Project context consulted**: `AGENTS.md`、`pyproject.toml`、`src/vrobot_sim/simulation.py`、
  `src/vrobot_sim/snapshots.py`、`src/vrobot_sim/maps/demo.py`、`tests/test_mutex_scheduling.py`、
  `projects/virtual-robot/project.md`、`projects/virtual-robot/backlog.md`；`design.md` 的 changed
  sections 及其关联章节。
- **Changed sections**: Architecture、Components、Interfaces（IF-HTTP-scene-apply、IF-HTTP-control、
  IF-MSG-state-stream）、State Machines、Key Mechanisms、Data Flow、Error Handling、Acceptance
  Criteria、Testing、Concurrency and Consistency。
- **Acceptance Criteria checked**: 25 条（场景配置与路径 7、控制状态机 4、状态推送 4、快照保真 1、
  页面可观察 8、内核兼容 1）。Goal 1-6 均有至少一条 AC；新增 `AC-view-resolved-paths` 补齐 Goal 1
  的路径展示验收。
- **Numeric re-check**: 1 / 0.02 s = 50 tick/s；0.05 ms / 20 ms = 0.25%；50 帧/s × 约 2 KB ≈
  100 KB/s；1 秒发送超时最多延迟 50 个 tick，单步 0.05 ms 时追帧约 2.5 ms，远小于超时本身，
  与 §Key Mechanisms 的 deadline 推进一致。均与正文一致。
- **Canonical contract**: `clarifying/assets/design-doc-template.md`
- **Rubric**: D1-D7

## Findings

无新增 finding。历史 finding 的闭合结果见 Closure。

## Dimension Summary

| Dimension | Status | Finding refs |
|-----------|--------|--------------|
| D1 Completeness | OK | None |
| D2 Usability | OK | None |
| D3 Conformance | OK | None |
| D4 Project Fit | OK | None |
| D5 Blind Spots | OK | None |
| D6 Over-Engineering | OK | None |
| D7 Optimization | OK | None |

## Current Readiness

- **Review round**: R2
- **Refine run**: R1-refine-1
- **Overall**: ready
- **spec-plan readiness**: Go
- **Next step**: `spec-plan`
- **Refine validation**: Not run
- **Change class**: None
- **Next review mode**: Not determined
- **Mode trigger**: None
- **Loop pressure**: None
- **Impact matrix**: None
- **Changed identifiers**: None

| Finding | Severity | Status | Reopen count | Review modes | Resolution ref | Changed sections | Note |
|---------|----------|--------|--------------|--------------|----------------|------------------|------|
| F-001 | Major | resolved | 0 | R1 Full, R2 Closure | §Components、AC-view-resolved-paths | Components、Data Flow | 高亮 |
| F-002 | Minor | resolved | 0 | R1 Full, R2 Closure | §Components | Components、State Machines | tick 0 统一 step() |
| F-003 | Minor | resolved | 0 | R1 Full, R2 Closure | §Interfaces | Interfaces、Components、Error Handling | 错误结构 |
| F-004 | Minor | resolved | 0 | R1 Full, R2 Closure | §Architecture | Architecture | package-data |
| F-005 | Minor | resolved | 0 | R1 Full, R2 Closure | §Architecture | Architecture | 固定 127.0.0.1 |
| F-006 | Minor | resolved | 0 | R1 Full, R2 Closure | §Components | Components、Interfaces、Key Mechanisms | 1 秒超时 |

### Finding Closure Proof

**F-001**
- **Closure test**: 设计中 Components 与 Data Flow 描述页面如何展示每台车的推导路径，且 Acceptance
  Criteria 含一条只验证该可观察结果的 AC；按该设计实施后，应用合法配置时页面可观察到每台车的推导路径。
- **Resolution evidence**: §Components 的"前端页面"条目写明应用成功后默认选中第一台、画布高亮推导路径的
  节点与边、点击表格行或画布机器人切换选中；§Data Flow 第 2 步同步该动作；§Acceptance Criteria 的
  `AC-view-resolved-paths` 只验证该可观察结果；§Testing 的人工验收引用该 AC。
- **Counterexample check**: 原反例"应用配置后页面上看不到推导路径"：默认选中第一台即出现高亮，切换选中
  可查看其余车辆，`resolved_paths` 响应字段未变。结果：已阻止。未覆盖：真实浏览器渲染与可读性
  （人工验收项）。来源：fresh read-only context。
- **Result**: passed

**F-002**
- **Closure test**: 设计写明应用配置与重置后初始快照的生成方式（例如调用一次 `step()`），并写明
  `configured` 状态下页面显示的状态语义；按该语义实现时，应用与重置得到相同形态的初始快照。
- **Resolution evidence**: §Components 的"推进器"条目规定应用配置或重置后调用一次 `step()` 取得
  `tick_index=0` 快照；§Interfaces 的 IF-HTTP-scene-apply Response、§State Machines 的应用/重置/换配置
  三行、§Key Mechanisms 的"暂停、继续与重置"采用同一语义。`simulation.py` 的 `step()` 先累加
  `sim_time_s`，再在 `tick_index=0` 上执行首个 tick 并返回快照，与设计一致。
- **Counterexample check**: 原反例"内核创建后没有快照，configured 显示内容未定义"：应用与重置都在
  `create_scheduled` 后调用一次 `step()`，两者得到同形态的 tick 0 快照；configured 画面显示该快照。
  结果：已阻止。未覆盖：无。来源：fresh read-only context。
- **Result**: passed

**F-003**
- **Closure test**: 错误契约规定请求体解析失败（非法 JSON、类型错误、缺字段）时的响应结构，且页面展示
  该结构的行为有 AC 或错误处理描述。
- **Resolution evidence**: IF-HTTP-scene-apply 与 IF-HTTP-control 的 Errors 各有一行解析失败 422，响应体
  为 `{"violations": [解析错误文本]}`；§Components 的"场景服务"把 pydantic 错误转成 `violations` 文本；
  §Error Handling 与 `AC-view-config-errors` 覆盖页面展示。
- **Counterexample check**: 原反例"非法 JSON 时 FastAPI 默认返回 `detail`，页面按 `violations` 渲染
  为空"：两个写接口与 Error Handling 统一为 violations 结构，页面展示该结构。结果：已阻止。
  未覆盖：pydantic 错误文本的具体格式（实现细节）。来源：fresh read-only context。
- **Result**: passed

**F-004**
- **Closure test**: 设计说明静态资源的打包或运行方式，使安装后的入口能定位 `static/` 文件（声明
  package-data 或规定 editable 安装运行）。
- **Resolution evidence**: §Architecture 声明 `[tool.setuptools.package-data]` 把 `vrobot_web` 的
  `static/*` 打进安装包；`pyproject.toml` 当前没有该项，实施时新增，恰为本项要求。
- **Counterexample check**: 原反例"非 editable 安装后 `python -m vrobot_web` 找不到 `index.html`"：
  package-data 把静态文件打进安装包。结果：已阻止。未覆盖：实际 wheel 构建与安装验证（实施阶段测试）。
  来源：fresh read-only context。
- **Result**: passed

**F-005**
- **Closure test**: 设计对监听地址给出单一约定：固定 127.0.0.1（删除或限制 `--host`），或说明
  `--host` 可覆盖并写明无认证前提下的暴露风险。
- **Resolution evidence**: §Architecture 只保留 `--port`，绑定地址固定为 127.0.0.1；§Non-Goals 与
  DR-web-stack-fastapi Constraints 同为 127.0.0.1；`find-identifiers.mjs` 显示 `--host` 零残留。
- **Counterexample check**: 原反例"`--host` 可覆盖为 0.0.0.0，无认证下暴露服务"：入口不再接受地址
  参数，三处约定一致。结果：已阻止。未覆盖：无。来源：fresh read-only context。
- **Result**: passed

**F-006**
- **Closure test**: 设计为广播定义发送超时或非阻塞丢弃策略，并说明慢客户端对推进节奏的约束；按该策略
  实现后，慢客户端不会拖慢 `step()` 的推进节奏。
- **Resolution evidence**: §Components 的"推进器"、IF-MSG-state-stream 的 Delivery、§Key Mechanisms 的
  "实时推进与广播"、§Error Handling 与 §Concurrency and Consistency 统一为单连接发送 1 秒超时后关闭并
  移除；边界算例写明移除后推进继续按 50 tick/s 前进。
- **Counterexample check**: 原反例"客户端在线但停止读取，发送等待 drain，推进停在该步"：发送超时封顶
  1 秒，超时即移除该连接；deadline 单调递增，最多 50 个 tick 的追帧耗时约 2.5 ms。结果：已阻止。
  未覆盖：长时间慢客户端下的实测节奏（实施阶段测试）。来源：fresh read-only context。
- **Result**: passed

## Closure

| Finding | Title | Result | Resolution ref | Summary |
|---------|-------|--------|----------------|---------|
| F-001 | Goal 1 的推导路径展示没有落到组件与 AC | closed | §Components、AC-view-resolved-paths | 画布路径高亮已覆盖。 |
| F-002 | 初始 tick 0 快照的生成语义未定义 | closed | §Components、§State Machines | 应用与重置统一取 tick 0。 |
| F-003 | 请求体格式错误的响应形状未纳入错误契约 | closed | §Interfaces、§Error Handling | 统一 violations 结构。 |
| F-004 | 静态资源未定义打包与运行方式 | closed | §Architecture | package-data 打包 static/*。 |
| F-005 | 监听地址的约定与 `--host` 参数不一致 | closed | §Architecture | 固定 127.0.0.1。 |
| F-006 | 广播等待慢客户端可能停顿推进 | closed | §Components、§Key Mechanisms | 1 秒超时后移除连接。 |

## Recommended Next Step

进入 `spec-plan`。实现阶段需落实：`vrobot_web` 的 optional extra 与 package-data；应用与重置后调用
一次 `step()` 的 tick 0 语义；两个写接口的 violations 错误结构；前端默认选中与画布路径高亮；WebSocket
单连接 1 秒发送超时；入口固定绑定 127.0.0.1。所有 finding 已终态，`spec-plan readiness` 为 `Go`；
本轮不自动调用下游 skill。
