# GitHub Projects 同步经验

> 2026-10-28，在 `venom-zen/vrobot-sim` 上把 `projects/virtual-robot/backlog.md` 的 10 个 work item
> 镜像成 GitHub Project #2 与 Issue #1–#10 的完整记录。本文用于把这次实践沉淀为可复用的流程，
> 后续并入 `brainstorming` 技能，指导项目规划阶段的外部跟踪。

## 1. 结论先行

- **可行且成本低**：10 个 work item 从创建 Project、建字段、建 Issue、入板到设置 Priority / Status，
  全程约 50 次 `gh` 调用，几分钟内完成。本次产物：Project #2（`venom-zen` 名下私有看板）、Issue #1–#10、
  backlog 对账提交 `11d7869`。
- **必须保持单向同步**：`backlog.md` 是唯一事实源，GitHub 侧只做镜像。不要让看板状态反向覆盖本地文档，
  否则两个事实源迟早冲突，而 agent 读取的是本地文档。
- **同步前先对账**：先把 backlog 的状态按交付证据修正，再同步。否则推出去的是错误进度。
- **公开性要显式确认**：公开仓库上的 Issue 会公开；私有的 Project 只影响看板本身。
- **看板视图仍需手工建**：`gh` 2.103.3 没有创建视图的命令，Board / Table 分组视图要去网页里加。

## 2. 对象模型与映射

| 本地（backlog.md） | GitHub 侧 | 说明 |
|--------------------|-----------|------|
| `WI-<name>` | 一个 Issue | 标题用 `WI-<name>: <中文名>`，正文镜像该 WI 的整段内容 |
| `Outcome` / `Scope` / `Non-Goals` / `Success signal` | Issue 正文 | 原样搬运，不加改写 |
| `Priority`（Now / Next / Later） | 单选项字段 **Priority** + 标签 `priority:now/next/later` | 字段用于看板分组，标签用于 Issue 列表筛选 |
| `Status`（流程状态） | 内置 **Status**：`Todo` / `In Progress` / `Done` | 粗粒度映射，细状态留在 Issue 正文里 |
| `Spec` | Issue 正文中的路径 | 不要为不存在的设计创建空链接 |
| `Dependencies` | Issue 正文 | 依赖关系暂不建模成 GitHub 原生依赖，避免两处维护 |
| `External ref` | 可写入 Issue URL | 让 backlog 能反查对应 Issue，建议同步时回填 |
| 整个项目 | 用户级私有 Project，关联仓库 | 用户级 Project 默认私有；仓库公开时 Issue 仍公开 |

### Status 映射

| backlog Status | Project Status | 备注 |
|----------------|----------------|------|
| `done` | Done | 仅在有交付证据时使用 |
| `executing` / `planned` | In Progress | |
| `candidate` / `ready-for-clarifying` / `design-ready` | Todo | 细状态保留在 Issue 正文 |
| `blocked` | Todo + `blocked` 标签 | 建议增加标签，别只靠正文 |
| `deferred` | Todo + Priority `Later` + `deferred` 标签 | 或直接关闭 Issue，按团队习惯二选一 |
| `cancelled` | 关闭 Issue | |

## 3. 前置条件与授权

### 3.1 安装与登录

```powershell
scoop install gh                      # 本次用 scoop；winget 亦可
gh auth login --hostname github.com --git-protocol https --web --scopes project
```

- 必须带 `--scopes project`。默认登录只有 `repo`、`read:org`、`gist`，Projects v2 的 GraphQL 调用会失败。
- 先看 `gh auth status` 确认登录账号与权限：

```text
Token scopes: 'gist', 'project', 'read:org', 'repo'
```

- 交互式登录无法由 agent 的非交互 shell 完成，需要用户自己执行；Claude Code 里可用 `!` 前缀。

### 3.2 确认目标账号与仓库

```powershell
gh auth status
gh repo view venom-zen/vrobot-sim --json visibility,url
```

### 3.3 账号迁移与凭据

- GitHub 账号改名（`venom248` → `venom-zen`）不会让 Personal Access Token 失效，令牌仍归属同一账号。
- Windows 凭据管理器（GCM）可能同时存着多个 GitHub 账号的令牌。本次第一次 push 就因取到另一个账号
  `venomwise` 的令牌而被 403 拒绝。
- 处理办法：把远端 URL 固定为令牌所属的旧用户名，凭据仍由 GCM 提供，URL 里不出现令牌：

```powershell
git remote set-url origin https://venom248@github.com/venom-zen/vrobot-sim.git
```

- `gh` 的登录态独立于 GCM，两者互不影响。排查 403 时先分清是 git push 的凭据问题还是 gh 的 scope 问题。

## 4. 执行步骤

以下命令以 owner=`venom-zen`、repo=`venom-zen/vrobot-sim`、project 标题 `VirtualRobot` 为例。

### 4.1 创建 Project 并关联仓库

```powershell
gh project create --owner venom-zen --title "VirtualRobot" --format json
# → number=2, id=PVT_..., public=false
gh project link 2 --owner venom-zen --repo venom-zen/vrobot-sim
```

### 4.2 读取内置字段 ID

```powershell
gh project field-list 2 --owner venom-zen --format json
```

内置 Status 的三个选项 ID 每次新建 Project 后都要重新读取，不要照抄旧 ID。

### 4.3 创建 Priority 字段与标签

```powershell
gh project field-create 2 --owner venom-zen --name "Priority" --data-type SINGLE_SELECT `
  --single-select-options "Now,Next,Later" --format json

gh label create "priority:now"   -R venom-zen/vrobot-sim -c d73a4a -d "Priority: Now"
gh label create "priority:next"  -R venom-zen/vrobot-sim -c fbca04 -d "Priority: Next"
gh label create "priority:later" -R venom-zen/vrobot-sim -c 0e8a16 -d "Priority: Later"
```

标签名包含冒号时按完整字符串传参，不要按冒号拆分后再拼接（本次第一版脚本就在这里建错了一个 `priority` 标签）。

### 4.4 建 Issue

```powershell
gh issue create -R venom-zen/vrobot-sim `
  --title "WI-sim-kinematics: 差速底盘运动仿真" `
  --body-file body.md --label "priority:now"
```

- 正文建议由脚本从 `backlog.md` 自动生成，末尾注明“镜像自 backlog.md，本地文档为唯一事实源”。
- 中文正文务必用 `--body-file`（UTF-8），避免命令行转义问题。

### 4.5 入板并写字段

```powershell
gh project item-add 2 --owner venom-zen --url <issue-url> --format json   # → item id
gh project item-edit --project-id <project-id> --id <item-id> `
  --field-id <priority-field-id> --single-select-option-id <option-id>
gh project item-edit --project-id <project-id> --id <item-id> `
  --field-id <status-field-id> --single-select-option-id <option-id>
```

### 4.6 验证

```powershell
gh project item-list 2 --owner venom-zen --format json --limit 50
```

逐项核对 Issue 编号、Status、Priority 与标题。本次 10 项全部符合预期。

## 5. 幂等与重跑

- **Issue 去重**按标题：先 `gh issue list --state all --json title,url` 建映射，已存在就复用 URL。
- **入板去重**按 URL：先 `gh project item-list --format json` 建 `url → item id` 映射，已入板就不再 `item-add`。
- **正文默认不覆盖**：重跑只补缺失对象、只改字段。若需要正文同步，用 `gh issue edit --body-file`，
  但要先确认没有人在 Issue 上直接编辑过，否则会覆盖人工补充。
- 字段 ID、选项 ID、Project ID 都是实例级标识，脚本应每次按名称自动发现，不要硬编码后跨项目复用。

## 6. 踩坑记录

| 现象 | 原因 | 处理 |
|------|------|------|
| `Permission to ... denied to venomwise`，403 | GCM 存了另一个账号的令牌 | 远端 URL 固定为令牌所属用户名，或清理该站点的旧凭据 |
| `gh project` 报缺少 scope | 登录时未带 `project` | `gh auth refresh -s project` 或重新 `gh auth login --scopes project` |
| 建出名为 `priority` 的错误标签 | 按冒号拆分 `priority:now` | 标签名整体传参，删除误建标签后重建 |
| 无法创建 Board 视图 | `gh` 2.103.3 无 `view-create` 子命令，GitHub 未开放视图 API | 网页里手动添加视图（本次未完成，留作后续） |
| 非交互 shell 登录挂起 | `gh auth login --web` 需要用户确认 | 由用户用 `!` 或独立终端执行 |
| 公开仓库的 Issue 对外可见 | Issue 继承仓库可见性 | 同步前显式确认；介意时改用私有 Project 的 draft item |
| `git` 提示 LF→CRLF | Windows `core.autocrlf` | 预期行为，不影响内容 |
| 每次新建 Project 的字段 ID 不同 | 字段 ID 含实例前缀 | 运行时读取，不写死 |

## 7. 维护流程

每次项目状态发生变化时：

1. **对账**：按 `review.md` / `code-review.md` / `tasks.md` / `exec-evidence.md` 的真实证据修正
   `backlog.md` 的 Status、Spec、Status evidence、Current Focus。没有证据不改状态。
2. **同步**：运行同步脚本，只改有差异的字段；新 WI 建 Issue，变更的 WI 改 Priority / Status。
3. **提交**：backlog 变更与同步在同一次提交里说明清楚，避免本地与远端文档不一致。
4. **确认**：`gh project item-list` 与 `backlog.md` 表格逐行比对。

状态证据的来源优先级：

- `design.md` 是否存在且通过 design-review（`review.md` 的 Current Readiness 为 Go）
- `tasks.md` 的 checkbox 是否全部完成
- `exec-evidence.md` 的测试结果
- `code-review.md` 的 Overall Result 与 Merge readiness

## 8. 可直接并入 brainstorming 的规则草案

> 以下条目按“技能规则”的口吻写，可直接改写进 `brainstorming` 的 Workflow / Safety 章节。

### 触发与定位

- 当用户要求在 GitHub Projects、看板或 Issue 中跟踪项目进度时，视为**外部同步请求**，
  不改变本地项目规划内容；同步只是 `project.md` / `backlog.md` 的镜像。
- 外部同步不修改 Goals、MVP、work item 拆分或优先级；出现范围变化时先回到 `replan`。
- 本技能不主动创建外部对象；用户明确要求后，作为独立步骤执行，并在完成后回到本地文档。

### 同步前

- 必须先用交付证据 reconcile 状态，再同步；没有证据的 work item 保持原状态。
- 必须让用户确认两件事：目标 GitHub 账号 / 仓库，以及公开性（公开 Issue 还是私有 draft item）。
- 必须确认 `gh` 已安装、已登录目标账号、令牌含 `project` scope。

### 同步时

- 一个 work item 对应一个 Issue；Issue 标题带稳定 `WI-*`，正文镜像 work item 段落并注明本地文档为事实源。
- Priority 用单选项字段，Status 用内置 Status；细状态保留在正文，不扩展成自定义状态机。
- 所有对象 ID（Project、字段、选项）按名称运行时发现，不硬编码。
- 同步必须幂等：按标题去重 Issue，按 URL 去重 project item。

### 同步后

- 把 Issue URL 回填到 work item 的 `External ref`，形成双向可追溯。
- 用 `gh project item-list` 与 backlog 表格逐行核对。
- 记录未完成项（例如看板视图需手工创建）并交给用户确认。
- 本地文档变更与同步结果一起提交，保持仓库与看板一致。

## 9. 验收清单

- [ ] `gh auth status` 显示目标账号，scopes 含 `project`
- [ ] Project 为私有，已关联目标仓库
- [ ] Priority 字段与三个标签存在
- [ ] 每个 work item 都有对应 Issue，标题含 `WI-*`
- [ ] 所有 Issue 已入板，Priority 与 Status 与 backlog 一致
- [ ] `WI-*` 的 `External ref` 回填 Issue URL
- [ ] backlog.md 已提交推送，仓库内状态与看板一致
- [ ] 看板视图（Board 按 Status、Table 按 Priority）已手工创建或明确记为待办

## 10. 附录：参考同步脚本

脚本本次是一次性实现，位于 `%TEMP%\sync_vrobot_project.py`；若要长期使用，建议移到仓库
`scripts/sync_github_project.py` 并加上下面的自动发现逻辑。核心流程：

```python
# 1. 解析 backlog.md：按 "### WI-" 切段，正则提取 Priority / Status
# 2. 按标题查已有 Issue，按 URL 查已有 project item，保证幂等
# 3. 建缺失 Issue（--body-file 写 UTF-8 正文，打 priority 标签）
# 4. item-add 后写 Priority 与 Status 字段
```

运行时先自动发现 Project、字段与选项：

```python
projects = json.loads(gh("project", "list", "--owner", OWNER, "--format", "json"))["projects"]
project = next(p for p in projects if p["title"] == PROJECT_TITLE)
fields = json.loads(gh("project", "field-list", str(project["number"]),
                       "--owner", OWNER, "--format", "json"))["fields"]
status_field = next(f for f in fields if f["name"] == "Status")
priority_field = next((f for f in fields if f["name"] == "Priority"), None)  # 没有就 field-create
```

完整实现按第 4–5 节的命令顺序组合即可；注意所有 `gh` 调用检查 returncode，失败时打印 stdout / stderr 并停止，
不要静默跳过——本次多次调用中，任何一次失败都会让看板与文档不一致。
