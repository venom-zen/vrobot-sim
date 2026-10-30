# Mutex Scheduling Design Review

> 对 `specs/mutex-scheduling/design.md` 的设计评审。Verdict 是评审时快照；当前流程状态见 Current Readiness。

## Verdict

- **Review round**: R3
- **Review mode**: Closure
- **Mode reason**: R2-refine-1 后 Current Readiness 为 `ready-for-closure`，`Next review mode` 为
  `Closure`，`Refine validation` 为 `Passed`；用户明确要求 Closure Review。refine 预判值：Closure，
  与实际模式一致。
- **Overall at review**: Pass
- **spec-plan readiness at review**: Go
- **Findings**: 0 Blocker / 0 Major / 0 Minor
- **Summary**: F-001、F-006、F-008、F-009 均按冻结的 Closure test 闭合；F-002～F-005 保持
  closed。结构、标识符和成对契约检查通过，设计可以进入 `spec-plan`。当前实现与测试尚未包含设计
  要求的回归更新，这是实施阶段任务，不影响本轮设计结论。

## Scope Reviewed

- **Reviewed file**: `specs/mutex-scheduling/design.md`
- **Project baseline**: git HEAD `56646f8`；工作树中 `specs/mutex-scheduling/` 与 `docs/` 未跟踪，
  `AGENTS.md` 有修改；`src/vrobot_sim` 与 `tests` 按该基线核对。
- **Project context consulted**: `projects/virtual-robot/project.md`（成功指标 5-10 台）、
  `projects/virtual-robot/backlog.md`（`WI-mutex-scheduling`）、`AGENTS.md`；
  `design.md` 的 §Summary、§Goals、§Context、§Discovery、§Scope Decisions、
  `DR-scale-demo-map-extension`、§Error Handling、§Acceptance Criteria 规模、§Testing；
  `src/vrobot_sim/{snapshots,map_model,safety,simulation,robot}.py`；
  `tests/{test_simulation,test_integration_demo,test_benchmark}.py`。
- **Changed sections**: Summary、Goals、Context、Discovery、Scope Decisions、
  `DR-scale-demo-map-extension`、Error Handling、Acceptance Criteria 规模、Testing、Data Model、
  Interfaces、Components、State Machines、Key Mechanisms、Data Flow。
- **Acceptance Criteria checked**: 27 条（路权互斥 9、死锁 2、车车避让 6、状态与快照 4、
  兼容与契约 3、规模与场景 3）。Goals 1-6 均有 AC 和测试覆盖；F-001/F-008 的规模场景和
  两个创建入口均已拆开验证。
- **Numeric re-check**: 0.35 + 0.35 = 0.70 m；起始节点中心距大于 0.70 m 时两个默认车体圆在
  t=0 不相交，等于 0.70 时相切（安全判定使用严格小于比较），设计要求大于 0.70，边界成立。
  R2 已复算的 1.48、1.45、0.735、0.715 未因本轮修改变化；未发现新的数值 finding。
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

- **Review round**: R3
- **Refine run**: R2-refine-1
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
| F-001 | Major | resolved | 1 | R2 Full, R3 Closure | DR-scale-demo-map-extension | Goals, AC, Testing | 起点间距与回归 |
| F-006 | Minor | resolved | 0 | R2 Full, R3 Closure | IF-PROTO-sim-step-advance | Interfaces, Testing | 兼容性措辞与字段断言 |
| F-008 | Minor | resolved | 0 | R2 Full, R3 Closure | AC-scale-* | AC, Testing | 拆分为 scheduled/default |
| F-009 | Minor | resolved | 0 | R2 Full, R3 Closure | §State Machines | State Machines, Testing | 首段 QUEUED 转移 |

### Finding Closure Proof

**F-001**
- **Closure test**: 设计给出一个与项目规模指标一致的内置地图多车场景，场景中每台车都有独立起始位姿，
  不因初始重叠停在起点；该场景在 `Simulation.create` 与 `create_scheduled` 下都能推进到完成状态。
  若设计选择下调规模上限，必须记录该决定并同步 `project.md` 与 backlog。既有 `test_integration_demo`
  与 `test_benchmark` 要么在场景不变的前提下继续通过，要么设计明确列出必须更新的测试与替代场景。
- **Resolution evidence**: `DR-scale-demo-map-extension`；§Goals、§Context、§Discovery、§Scope Decisions；
  §Error Handling 的起点间距约束；`AC-scale-ten-robots-scheduled`、`AC-scale-ten-robots-default`、
  `AC-scale-no-initial-overlap`；§Testing 的回归清单加入 `tests/test_simulation.py`。
- **Counterexample check**: 同起点测试：`tests/test_simulation.py:50-74` 与 `:183-190` 仍是同起点并
  断言 `MOVING`，§Testing 明确要求改为不同起点或断言 `OVERLAP` 的 `E_STOP`；这属于设计允许的测试
  更新。`tests/test_integration_demo.py:22-44,77-86` 的 R1/R2 同起点同样列入更新；0.5 m 节点间距
  场景被 `>0.70 m` 约束排除；10 车双入口由两条规模 AC 覆盖。未覆盖：扩展 demo 的实际坐标与 10 车
  运行时完成情况（设计阶段无实现）。来源：fresh read-only context。
- **Result**: passed

**F-006**
- **Closure test**: `IF-PROTO-sim-step-advance` 的 Compatibility 明确区分既有字段与语义不变、新增
  `zones` 默认空元组，且 §Data Model 与契约措辞一致；一个按旧字段读取并检查 `zones` 默认值的契约测试
  可验证该承诺。
- **Resolution evidence**: §Interfaces 的 Compatibility 改为“既有字段与语义不变；`zones` 默认空元组”；
  §Data Model 的字段声明；§Testing 的契约测试与 `tests/test_simulation.py` 字段断言更新。
- **Counterexample check**: `tests/test_simulation.py:61` 的三字段精确断言仍存在，§Testing 要求在更新中
  加入 `zones` 并验证默认空元组；契约的兼容性不再承诺“返回结构不变”。未覆盖：运行时字段断言执行。
  来源：fresh read-only context。
- **Result**: passed

**F-008**
- **Closure test**: `create_scheduled` 与 `Simulation.create` 各有一条独立 AC（或默认入口的结果移入
  `AC-compat-default-create` 的规模场景），每条只含一个入口和一个完成结果；§Testing 能分别引用两条 AC。
- **Resolution evidence**: `AC-scale-ten-robots-scheduled` 与 `AC-scale-ten-robots-default`；§Testing
  分别引用两条 AC。
- **Counterexample check**: 旧 `AC-scale-ten-robots` 在设计正文 0 残留；两条新 AC 各含一个入口和一个
  完成结果；`find-identifiers.mjs` 显示两条新 ID 各出现 2 次。未覆盖：运行时 10 车测试执行。
  来源：fresh read-only context。
- **Result**: passed

**F-009**
- **Closure test**: 状态表有一条首段申请排队时 `IDLE/ARRIVED -> WAITING_RIGHT` 的转移，或在
  `IDLE/ARRIVED` 行写明 `QUEUED` 时的目标状态；§Testing 有一个首段即排队的场景，按表可以实现。
- **Resolution evidence**: §State Machines 的两条 `IDLE/ARRIVED` 转移；§Key Mechanisms 的首段申请说明；
  §Data Flow 第 5 步；§Testing 的单元与集成首段排队场景。
- **Counterexample check**: 首段申请返回 `QUEUED` 已映射为 `WAITING_RIGHT`，并写明 v 与 ω 置零、停在
  起点；`GRANTED` 或无未持有区时进入 `MOVING`。§Testing 同时列出首段排队的单元与集成场景。未覆盖：
  运行时首段排队。来源：fresh read-only context。
- **Result**: passed

## Closure

| Finding | Title | Result | Resolution ref | Summary |
|---------|-------|--------|----------------|---------|
| F-001 | 节点起点冲突 | closed | `DR-scale-demo-map-extension` | 10 个起始节点 >0.70 m；回归与双入口 AC 已同步。 |
| F-002 | 仲裁器无装配入口 | closed | `DR-dispatcher-injected-collaborator` | 可注入调度器，区状态由所用实现提供。 |
| F-003 | 运行时状态约定冲突 | closed | `DR-dispatcher-runtime-state`、`AGENTS.md` | 允许 Robot 与调度器持有状态，每 Simulation 一份。 |
| F-004 | `WAITING_RIGHT` 授予结果路径未定义 | closed | §State Machines、§Testing | 等待车每 tick 重复读取结果。 |
| F-005 | 车车避让边界算例高估余量 | closed | §Key Mechanisms 车车避让 | 最坏触发 1.45 m、停后中心距 0.715 m；0.73 为名义值。 |
| F-006 | `zones` 兼容性 | closed | `IF-PROTO-sim-step-advance` | 既有字段不变、`zones` 默认空元组；契约测试覆盖。 |
| F-008 | 规模 AC 合并 | closed | `AC-scale-*` | 拆分 scheduled/default；Testing 分别引用。 |
| F-009 | 首段排队状态 | closed | §State Machines、§Testing | 首段 `QUEUED` 转移已补。 |

## Recommended Next Step

进入 `spec-plan`。设计和测试计划需要落实：demo 扩展到至少 10 个可起始节点并保证任意两个起始节点
中心距大于 0.70 m；`tests/test_simulation.py`、`tests/test_integration_demo.py` 与
`tests/test_benchmark.py` 的回归更新；`TickSnapshot.zones` 的契约测试与字段断言；两条规模 AC；
首段排队状态。所有 finding 已终态，`spec-plan readiness` 为 `Go`；本轮不自动调用下游 skill。
