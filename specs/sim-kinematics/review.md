# Sim Kinematics Design Review

> 对 `specs/sim-kinematics/design.md` 的设计评审。Verdict 是评审时快照；当前流程状态见 Current Readiness。

## Verdict

- **Review round**: R6
- **Review mode**: Full
- **Mode reason**: R5-refine-1 的 `Next review mode` 为 Full（F-019 第三次改动安全判定式并新增一条 AC），用户在
  spec-plan 门槛前选择先跑 `design-review` 而不是绕开复核。
- **Overall at review**: Pass
- **spec-plan readiness at review**: Conditional
- **Findings**: 0 Blocker / 0 Major / 1 Minor
- **Summary**: R5 的四条 finding 独立复测全部闭合。纵向新口径经全文核对已同语：八处表述统一使用"障碍在本段上的覆盖
  区间与前瞻区间相交"，唯一出现"中心投影"的位置是 Rationale 里描述旧失效模式，属正确引用。跨段端点用例按默认参数复算
  以 `SAFETY_DISTANCE` 停稳，车头距近缘余 0.0163 米（dt 0.02）与 0.1065 米（dt 0.05），车体中心停在 9.48 米与 9.39
  米，未越过段末。本轮只新增一条 Minor：两处 R5 新增的说明文字一处语句不通、一处位置表述与实际几何不符，都不改判定式、
  AC 或 Decision 语义。无 Blocker 与 Major，处置该 Minor 后即可放行。

## Scope Reviewed

- **Reviewed file**: `specs/sim-kinematics/design.md`（当前 773 行，结构校验器与行宽检查通过，AC 43 条）
- **Project baseline**: 仓库仍只有 project.md、backlog.md、design.md 与 review.md，非 git 工作区。project.md 与
  backlog.md 的 mtime 保持 10-27 18:14:34 与 18:14:43，六轮评审期间未变，不存在 `context-change`。
- **Propagation check**: 纵向口径的八处落点逐一核对：DR-collision 的 Decision（125-130 行）、Rationale（132-137 行）、
  Constraints（139-144 行）、Key Discoveries 第 4 条（79-81 行）、Components 的 `safety`（293-295 行）、Key Mechanisms
  前瞻安全距离（526-539 行）、Data Flow 第 4 步（555-559 行）、Error Handling 障碍跨段端点（589-590 行）。结论为同语。
- **Numeric re-check**: 默认参数（dt 0.02、v_max 1.5、a_max 0.8、decel_max 1.5、body_radius 0.35）下三种情形：普通
  预置（中心 5.0 米、半径 0.2 米）、跨段端点（中心 10.05 米、半径 0.2 米）、大半径贴段末（中心 9.9 米、半径 0.5 米），
  均以 `SAFETY_DISTANCE` 停稳，车头距障碍近缘分别余 0.0363、0.0163、0.0163 米；dt 取上限 0.05 时三者的余量分别为
  0.0815、0.1065、0.1065 米，车体中心均未越过段末。
- **Changed sections**: All
- **Acceptance Criteria checked**: 43 条逐条核对。R5 四条 finding 的冻结 Closure test 独立重做，不以 refine 的
  validation 结论代替。按 Testing 第 761-762 行声明的合取规则评估 THEN 的多属性写法，不再要求逐条拆分。
- **Canonical contract**: `clarifying/assets/design-doc-template.md`
- **Rubric**: D1-D7

## Findings

按 Blocker、Major、Minor 排序。

### [F-023] R5 新增的两处说明文字一处语句不通、一处位置与实际几何不符

- **Severity**: Minor
- **Introduced in**: R6
- **Origin**: refine-regression
- **Location**: `design.md §Key Mechanisms > 前瞻安全距离`（539 行）、`§Error Handling`（589-590 行）
- **Issue**: 539 行写"触发点到段末之间不越过界，兜底归零又不晚于接触时刻，因此本项不需要急停期间的段位置切换规则"，
  前半句读不出主谓关系，而它承载的是急停不变量的成立理由。589 行写跨段端点障碍"被当作最近点位于段末处的障碍参与前瞻
  判定"，实际最近点是 `p − r`，在示例参数下是 9.85 米而段末是 10.0 米，"位于段末处"读起来像等于段末。
- **Evidence**: 两处都是 R5-refine-1 改写该段时新引入的句子，规范判定式本身（125-130 行、526-530 行）正确，AC 与
  测试用例不受影响；问题限于解释性文字的准确性与可读性。
- **Closure test**: 两处句子与规范判定式一致且能独立读懂：539 行给出车体中心不越过段末的实际因果理由，589 行对最近点
  位置的描述与 `p − r` 的定义一致。
- **Recommendation**: 539 行改为"障碍在本段上的最近点不超过段末，兜底归零又不晚于接触时刻，因此车体中心必然停在段末
  之前，本项不需要急停期间的段位置切换规则"；589 行把"最近点位于段末处"改为"最近点不超过段末"。两处都属于说明文字，
  不必同步 AC 或 Decision。

## Dimension Summary

状态：`OK` 无问题，`Attention` 有 finding，`Blocked` 存在 Blocker。

| Dimension | Status | Finding refs |
|-----------|--------|--------------|
| D1 Completeness | OK | None |
| D2 Usability | Attention | F-023 |
| D3 Conformance | Attention | F-023 |
| D4 Project Fit | OK | None |
| D5 Blind Spots | OK | None |
| D6 Over-Engineering | OK | None |
| D7 Optimization | OK | None |

D1：43 条 AC 覆盖 8 条 Goal 的正常流、错误流与边界；`AC-estop-straddling-obstacle-stops` 补齐了跨段端点这一条边界。

D4：设计对 project.md 与 backlog.md 的引用逐条为真，两份规划文件六轮未变；`v·dt`、`requires-python`、venv 与运行时
版本的表述与本机实测一致。

D5：急停的三类触发路径（逐步接近、迟注册、穿隧）都有确定收尾与对应断言；跨段端点障碍已归入第一类。权限、迁移、外部
集成、并发与运营风险在本项仍不适用。

D6：无零消费者字段；`decel_max_mps2` 的一字段两用已在字段说明与 AC 中分别限定。

D7：没有发现能同时满足全部 Goals 且新增面更小的方案；纵向判定从中心投影改为覆盖区间是最小的正确修法。

## Current Readiness

- **Review round**: R6
- **Refine run**: R6-refine-1
- **Overall**: ready
- **spec-plan readiness**: Go
- **Next step**: 运行 `spec-plan` 生成 `specs/sim-kinematics/tasks.md`。
- **Refine validation**: Passed
- **Change class**: direct-repair
- **Next review mode**: None
- **Mode trigger**: None
- **Impact matrix**: F-023 的两处说明文字 -> Key Mechanisms 前瞻安全距离第三段、Error Handling 障碍跨段端点条目；
  判定式、43 条 AC、Decision、Goals、Non-Goals、Data Model 与 Testing 均未改动
- **Changed identifiers**: None

| Finding | Severity | Status | Reopen count | Resolution ref | Changed sections | Note |
|---------|----------|--------|--------------|----------------|------------------|------|
| F-023 | Minor | resolved | 0 | §Key Mechanisms 前瞻安全距离 | KM, EH | 两处说明文字改写，语义与判定式不变 |

F-001 至 F-022 维持终态，逐条结果见 Closure 表。F-023 属不改行为契约的说明文字修复，按 lifecycle 的 direct-repair
出口将 `Next review mode` 定为 None，readiness 进入 `ready / Go`。

## Closure

| Finding | Title | Result | Resolution ref | Summary |
|---------|-------|--------|----------------|---------|
| F-001 | 前瞻缺横向过滤与段末裁剪 | closed | DR-collision-continuous-geometry | 垂直门槛与段内截断在位 |
| F-002 | 转向完成写在两套条件 | closed | DR-motion-follow-model | 完成条件唯一，比值校验在位 |
| F-003 | 段末减速无约束归属 | closed | §chassis-config | 常规与急停各有上限归属与 AC |
| F-004 | 急停期间两条行为 | closed | DR-dispatcher-intake-boundary | 改道拒绝已定，越段末不成立 |
| F-005 | map_id 无错误语义 | closed | §Error Handling | 创建期校验与 AC 齐备 |
| F-006 | 路径双来源无取舍 | closed | DR-path-supplied-by-scenario | 运行时以指令载荷为准 |
| F-007 | obstacle_field 无定义 | closed | §Architecture | 模块清单与注册责任一致 |
| F-008 | 基准场景形态未定 | closed | §AC-bench-step-cost-measured | 地图、路径与障碍数三项已指明 |
| F-009 | zones_by_edge 无调用方 | closed | DR-critical-zone-entity | 索引移出本项，零残留 |
| F-010 | 车体间重叠未声明 | closed | DR-collision-continuous-geometry | Non-Goals 与基准口径一致 |
| F-011 | 开发运行时无固定方式 | closed | §Architecture | requires-python 与 venv 已写明 |
| F-012 | OVERLAP 成因与不变量理由 | closed | DR-collision-continuous-geometry | 成因分类与豁免口径在位 |
| F-013 | IDLE 两行 guard 重叠 | closed | §State Machines | 航向限定使两行互斥 |
| F-014 | MOVING 两行急停转移同时命中 | closed | §State Machines | guard 互斥，AC 各述单一结果 |
| F-015 | Summary 缺兜底例外 | closed | DR-collision-continuous-geometry | 例外句已同步，七处一致 |
| F-016 | 前瞻区间漏算障碍半径 | closed | DR-collision-continuous-geometry | 边界扫描确认提前停住 |
| F-017 | 急停减速途中转 OVERLAP | closed | §State Machines | 转移行、AC 扩写与用例齐备 |
| F-018 | 多问题并存时返回内容两解 | closed | §Error Handling | 一次返回全部违规项 |
| F-019 | 跨段端点障碍漏检致节点卡死 | closed | DR-collision-continuous-geometry | 纵向改覆盖区间判定，复算不接触 |
| F-020 | E_STOP 相交行与再次成立行同命中 | closed | §State Machines | 未相交限定使两行互斥 |
| F-021 | ARRIVED 行缺首段航向处理 | closed | §State Machines | 与 first-turn-align 同口径 |
| F-022 | AC 的 THEN 多结果表述 | closed | §Testing | 合取规则已声明并收窄 trigger 条 |

## Recommended Next Step

运行 `spec-plan` 生成 `specs/sim-kinematics/tasks.md`。R6 复核通过，F-023 已修复，`Refine validation` 为 Passed 且
`Next review mode` 为 None，Current Readiness 为 `ready / Go`，满足 spec-plan 的门槛。规划时按 design.md 的章节建立
43 条 AC 的覆盖表，实施顺序建议为工程骨架与依赖、地图数据模型与两张内置示例地图、kinematics 与 controller、safety
与 robot 状态机、simulation 与快照、指令接收边界与障碍物注册、测试套件与基准测量。
