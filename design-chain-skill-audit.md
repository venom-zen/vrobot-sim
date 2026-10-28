# design-review / design-refine 审计报告

审计依据：`skill-father` Mode B 的四维度清单与
[失效模式库](file:///C:/Users/wenlong.chen/.agents/skills/skill-father/references/optimization-lessons.md)。

触发本次审计的事实：`specs/sim-kinematics` 的设计评审进行了 5 轮 review + 5 轮 refine（R1 Full、
R1-refine、R2 Full、R2-refine、R3 Closure、R3-refine、R4 Full、R4-refine、R5 Full、R5-refine），
第 6 轮的 `Next review mode` 仍是 `Full`，用户质疑循环不收敛。

## 审计范围与证据限制

审计对象（全部完整读取）：

- [design-review/SKILL.md](file:///C:/Users/wenlong.chen/.agents/skills/design-review/SKILL.md)（247 行）
- [review-lifecycle.md](file:///C:/Users/wenlong.chen/.agents/skills/design-review/references/review-lifecycle.md)（235 行）
- [closure-review.md](file:///C:/Users/wenlong.chen/.agents/skills/design-review/references/closure-review.md)
- [review-rubric.md](file:///C:/Users/wenlong.chen/.agents/skills/design-review/references/review-rubric.md)
- [review-template.md](file:///C:/Users/wenlong.chen/.agents/skills/design-review/assets/review-template.md)
- [design-refine/SKILL.md](file:///C:/Users/wenlong.chen/.agents/skills/design-refine/SKILL.md)（318 行）

Mode B STEP 1 要求"读 git 历史判断每次修改是失败驱动的补丁还是凭空的添加"。`C:\Users\wenlong.chen\.agents\skills`
不是 git 仓库（`git log` 与 `git status` 都返回 not a git repository），演进脉络改由两类产物重建：
失效模式库已登记的 P17（评审-修复循环不收敛），以及本次 `specs/sim-kinematics/review.md` 的逐轮记录。

## 结论

四个维度里，语体（一致性、翻译腔、中英混排）没有发现缺陷；跨文件术语、ID 前缀、字段标签均对齐。
问题集中在**行为规则**：协议已经写进了正确的收敛策略（P17 的"refine 后默认 Closure"），但分类粒度和
finding 归属规则把它推翻了，导致循环没有可达的终止条件。9 条发现分三级，A 组 4 条互相依赖。

---

## Tier 1 行为缺陷（循环不收敛的直接原因）

### A1 组件内的承重判定式被归为 high-risk-design，机械续期 Full

- **位置**：`review-lifecycle.md:71-72`（`high-risk-design` 定义）、`review-lifecycle.md:80`（映射到 Full）
- **维度**：行为规则 / 一致性
- **缺陷**：`high-risk-design` 的枚举项含"安全"。本协议中该词指认证、授权、数据访问边界；避障设计的
  前瞻判定式在中文里也叫"安全判定"。一个只在单组件内部生效的几何公式改动因此被判成 high-risk，
  按 `:80` 强制 `Next review mode: Full`。
- **本 session 证据**：R5-refine-1 的 `Change class: high-risk-design`，`Mode trigger` 写的是"改动跨
  Decision、Key Mechanisms、Data Flow、Interfaces、Error Handling、AC 与 Testing 七个位置"。跨七个章节
  是**传播面**，不是**风险边界**——这两者在 `:74-81` 的出口选择里被混用了。
- **关联模式**：P17 的修法第一句"refine 后默认执行 Closure Review"在本条上失效。
- **修法**：改定义处，不新增禁止条款。
  1. `:71-72` 把"安全、权限"写成"安全与权限边界（认证、授权、数据访问）"。
  2. 在 `:70-72` 之后补一条正向分类：单个组件内部的算法、几何或数值判定式改动归
     `behavior-propagation`，除非它改变跨组件可观察行为或契约形状。
  3. `:80` 判 Full 的条件里，把"改动跨多章节"与"改变风险边界"分开表述，前者对应 `Closure`。

### A2 finding 按身份切分，按位置收敛，熔断器不可达

- **位置**：`review-lifecycle.md:131-132`（Finding Identity）、`:179-189`（Reopen circuit breaker）、
  `:188-189`"本规则只作用于同一 finding；不同根因的新 finding 照常创建"
- **维度**：行为规则（缺关卡，导致竞态）
- **缺陷**：熔断器按单个 finding ID 计数（第 3 次不通过 Closure test 才 `escalated`）。同一处承重判定
  每轮产生**不同反例**时，每轮都是 Reopen count 0 的新 ID，计数永远从零开始，熔断器永不触发。
- **本 session 证据**：F-012（迟注册时 OVERLAP 归因错误）、F-016（前瞻公式漏算障碍半径，Blocker）、
  F-019（转角邻域）、F-020（`E_STOP` guard 与前瞻谓词重叠）四条都落在同一条前瞻/急停判定式上，
  反例各不相同，因此各自 Reopen count 为 0 或 1。`review.md` 的 finding 表格里这条链完全看不出来。
- **修法**：在 Finding Identity 一节（`:129-143`）补一条归属规则，让既有熔断器变得可达：
  > finding 的归属对象是承重判定——一条规则、一个判定式、一个状态表行、一个字段。同一承重判定上
  > 的后续缺陷沿用该判定首次出现的 `F-###` 并设为 `reopened`，即使反例不同；本轮的新反例写进 Note，
  > 原反例的复测结果保留。
  `:188-189` 的"不同根因的新 finding 照常创建"补一句限定：根因按承重判定归属，不按单个反例归属。

### A3 Full 模式没有新 finding 准入闸门，而规则反复把轮次送回 Full

- **位置**：`closure-review.md` 的 New findings 一节（四条准入问题，仅 Closure 生效）；
  `review-lifecycle.md:151`（`baseline-miss` 标注"仅 Full"）
- **维度**：行为规则 / 结构分层
- **缺陷**：Full 是协议里**专为"上一轮漏检"设计的模式**（`baseline-miss` 只允许在 Full 出现），
  同时它按 D1-D7 全量发散、不设准入问题。A1 又不断把轮次判回 Full。于是每一轮都拿到一次
  "重新自由发散 43 条 AC"的配额，产出新 finding 是概率上的必然。
- **本 session 证据**：R5 的 F-019 Origin 记为 `baseline-miss`；R4 的 F-016 同样是 `baseline-miss`
  且它从 R1 就存在。两条都由 Full 模式的无闸门发散产生。
- **修法**：把 `closure-review.md` New findings 的四条准入问题上移到
  `review-rubric.md` 末尾的 Semantic Review admission gate，两种模式共用；Full 与 Closure 的差别
  退回 Origin 表本身（Full 允许 `baseline-miss` 与 `context-change`，Closure 不允许）。
  `closure-review.md` 改为引用该 gate，不留两份（P13）。

### A4 循环层没有三选一的处置出口

- **位置**：`review-lifecycle.md:182-186`（单条 finding 的 escalated 三选一）、
  `review-template.md` Current Readiness 的注释（只对 `escalated` 要求三选一）
- **维度**：行为规则（升级边界缺 owner）
- **缺陷**：协议只为"同一条 finding 反复重开"设计了用户裁决出口，没有为"整个循环在同一区域反复
  产生新 finding"设计出口。所以第 6 轮只能由 reviewer 临场发明一个非模板字段来提请用户裁定。
- **本 session 证据**：我在 `review.md` 的 Current Readiness 里塞了一条
  `**Loop cost note**`，模板没有这个字段，`review-lifecycle.md:87-95` 的固定字段清单也没有。
- **修法**：在 lifecycle 新增一条循环规则，复用已有的 Origin 枚举，不引入新度量（避免 P7 的伪精确
  阈值）：
  > 本轮新 finding 中 `baseline-miss` 占多数，且上一轮同样如此时，`Next review mode` 不再自动设为
  > `Full`。Current Readiness 记一行 `Loop pressure`，Recommended Next Step 改为请用户在
  > Full / Closure / 直接进入 `spec-plan` 三选一，并写明每种选择放弃哪部分保证。
  同步在 `review-template.md` 的 Current Readiness 增加 `Loop pressure` 字段（无循环时写 `None`），
  在 `design-review/SKILL.md:196-203` 的 STEP 8 增加这条分支。

---

## Tier 2 产物质量与验证缺陷

### B1 六轮全部在同一上下文自审，作者偏差没有隔离

- **位置**：`design-review/SKILL.md:92-143`（STEP 3 与 STEP 5，全文没有子代理条款）
- **维度**：行为规则
- **缺陷**：写公式、测公式、审公式的是同一个不断被压缩重述的上下文。反例清单继承作者的假设，
  同一处错误可以连续多轮不被发现。
- **本 session 证据**：F-016（前瞻公式漏算障碍半径）从 R1 就在文档里。R2 我确实做了数值复测，
  但只模拟了"迟注册"一条路径，从没模拟"逐步接近"。该 Blocker 到 R4 才被发现，我自己在 R4 报告里
  把它登记为一次评审失败。
- **关联模式**：P20 已经给出这条修法（"消除作者偏差：修复后的 Closure Review 由全新只读子代理执行
  冻结的 Closure test"），但没有接进 design-review。
- **修法**：在 STEP 5 加默认路由：refine 之后的反例复测交给只读子代理执行，输入限定为 `design.md`
  的相关章节加冻结的 Closure test，**不传历史 review 的推理文本**（否则会继承同一假设）；要求返回
  结论加 `path:line` 证据与复算所用场景，并规定返回体量上限。按 P20 的前提，这一条只在边界压缩
  成立时才有收益——只复测反例，不按维度重做全量评审。

### B2 `Refine validation: Passed` 无法区分机器校验与自评

- **位置**：`review-lifecycle.md:107-122`（七道关）、`:99-105`（Finding Closure Proof 字段表）、
  `design-refine/SKILL.md:234-272`（STEP 10）
- **维度**：行为规则（验证定义不区分来源）
- **缺陷**：七道关中只有第 5 关（`find-identifiers.mjs`、`check-design-doc.mjs`）可执行；第 1-3 关
  （Closure test 是否覆盖原根因、原反例是否已被阻止）由 refine 自己判定。`Passed` 把两者合并成一格，
  下一轮 reviewer 读不出哪些结论有机器证据、哪些是自评。反例清单本身也不留痕。
- **本 session 证据**：机器关卡抓到过一次真实残留（`纵向投影` 在 Error Handling 的残余，脚本 exit 1）；
  而"F-018 七项修复只落地五项"没有任何关卡能抓，靠我事后自查才发现。
- **修法**：改现有字段，不新增字段。`review-lifecycle.md:104` 的 `Counterexample check` 含义改为：
  本轮实际复算的反例场景清单（逐条命名），仍成立时写场景名与结果。这样若某轮只测了"迟注册"，
  下一轮看得见清单缺项，而不是只看见 `passed`。第 1-3 关在字段表里标注为 reviewer 判定、
  第 5 关标注为脚本判定。

### B3 设计中的定量声明没有"自带边界算例"的要求

- **位置**：`review-rubric.md` 的 D5 三组清单（User-facing / Data / Integration，均无定量复算项）、
  `review-template.md` 的 Scope Reviewed（无对应字段）
- **维度**：行为规则 / 一致性（P13 的反向漂移：实践已在用，模板未登记）
- **缺陷**：判定式、阈值、区间的正确性只能靠评审现场发现，评审因此变成设计的第一次验证，后续所有
  轮次都在做回归。
- **本 session 证据**：R2 的 `**Numeric re-check**` 是我临场加进 Scope Reviewed 的字段，模板与
  lifecycle 都没有它。本项 5 轮里 3 轮的主要 finding 都是定量问题（F-012、F-016、F-019）。
- **修法**：两处各加一项。
  1. `review-rubric.md` 的 D2 加一条：设计中的定量声明（判定式、阈值、区间、边界值）必须在正文自带
     一个边界算例，写明代入值与结果；缺失即是一条 finding。
  2. `review-template.md` 的 Scope Reviewed 增加 `**Numeric re-check**`，注明仅在设计含定量声明时填写，
     写清算例的代入值与结论。

---

## Tier 3 一致性与归属

### C1 模式改写权在两个文件里说法冲突，升级路径没有 owner

- **位置**：`design-review/SKILL.md:89-90`（reviewer 可按实际条件改模式并记 Mode reason）
  vs `review-lifecycle.md:46`（Closure 的准入写成"下一轮模式为 Closure 时执行"）
- **维度**：一致性
- **缺陷**：按 `:46`，模式由 refine 写定，reviewer 不能降档；按 SKILL.md `:89-90`，reviewer 可以改。
  两处冲突的实际后果：用户问"第 6 轮凭什么还是 Full"时，给不出"谁有权改"的答案，只能把裁定权推回
  用户口头授权。
- **修法**：lifecycle 明确 `Next review mode` 是 refine 的预判，改写权只属于用户（或 A4 的
  `Loop pressure` 规则触发后由用户选择）；`:46` 的准入条件改为读改写后的实际模式。
  SKILL.md `:89-90` 与 `:221` 的 Verification 项同步引用这一条。

### C2 readiness 初始化规则在两个文件各写一份

- **位置**：`design-review/SKILL.md:153-158` 重述了 `review-lifecycle.md:195-210` 的 Overall 与
  `spec-plan readiness` 映射
- **维度**：一致性（P13）
- **缺陷**：同一规则两份表述，改动落单处即漂移。lifecycle 的 `:3` 已经声明"以 design-review 的定义为准，
  design-refine 不得复制状态定义"，但 SKILL.md 自己复制了一份。
- **修法**：SKILL.md STEP 6 只保留"按 lifecycle 的 Current Readiness 初始化"并给出 finding 数到状态的
  一句话摘要，不重述枚举。

### C3 P17 已被实现但被 A1 推翻

- **位置**：`optimization-lessons.md:116-134`（P17）vs `review-lifecycle.md:80`
- **维度**：行为规则（经验库与协议不一致）
- **缺陷**：P17 的修法写明"refine 后默认执行 Closure Review"，Full 只留给 Goals、Non-Goals、
  Architecture、数据所有权与公共契约变化。`review-lifecycle.md:80` 的分类粒度让任何触及承重规则的修复
  都判 Full，默认值实际不存在。
- **修法**：修 A1 即闭合本条。在 P17 的修法段落末尾补一句指向 lifecycle 的分类条款，避免经验库与协议
  两处各说一遍。

---

## 建议实施顺序

1. **A2 → A4**：先让熔断器可达，再给它一个出口。这两条构成最小闭环，单独做 A1 或 A3 都仍会退回
   今天的状态（只是把 Full 的触发频率降低，终止条件依旧不存在）。
2. **A1 → A3**：把 Full 的触发面收窄，并给两种模式装上同一个准入闸门。
3. **B1 → B2**：这两条防的是"同一个错误被同一个人漏检三轮"，与循环长度无关，价值独立于 A 组。
4. **C1 → B3 → C2 → C3**：一致性与模板字段补齐。

## 改动后的自查关卡

1. `review-lifecycle.md` 的承重判定归属规则是否只定义一次，`closure-review.md` 与 `review-rubric.md`
   改为引用而非复述？IF 否，THEN 合并到 lifecycle（P13）。
2. 准入闸门是否已在两种模式下都能执行？IF 否，THEN 回到 A3。
3. `Loop pressure` 规则能否自检？判据只用已有的 Origin 枚举，不引入"保持稳定 N 轮"这类无操作定义的
   阈值（P7）。IF 写成了百分比或计数，THEN 改为可判定的枚举比较。
4. 新增条款是否都写成正向契约（canonical output、source of truth、状态出口、升级条件、validation），
   而不是追加"不要/禁止"（P19）？逐条对照 `skill-father` 的正向边界顺序。
5. 改完后通读四个文件，确认"安全""风险边界""传播面"三个词在 lifecycle 与两个 SKILL.md 里各只有一个
   含义；运行 `check-markdown-lines.mjs` 确认无超长行。
