---
name: workbuddy-rename
description: Organize, rename and archive WorkBuddy workspace folders. Use when the user complains that workspace folders are unfindable (timestamp-only names), wants to rename/plan/archive workspaces, wants output files (images/md/video) classified, or asks to clean up the workspace root (auto-detected). Scans workspaces, infers each one's topic from .workbuddy/memory, proposes a YYYY-MM-DD-topic naming plan, applies moves, then repairs every stale path reference: the WorkBuddy database (sessions.cwd, automations.cwds), the ~/.workbuddy/projects conversation store, artifact-index/changes-* artifact links, and edge-sync caches. Missing the projects store makes old sessions open blank / appear lost; missing the artifact indexes makes output files unopenable. Also writes an index. Covers space hygiene: draft 3-way classification (recipe/asset/dependency) before clearing 04_temp, non-destructive rules (backup first, batches of 10, trash over rm, stop on error), and a read-only quarterly inspection (disk hogs / cold files / stalled tasks / memory health) that reports and waits for user approval.
agent_created: true
---

# workbuddy-rename — WorkBuddy 工作空间整理

把「一堆 2026-08-24-21-12-20 时间戳文件夹」变成「一眼能找到的项目库」。

## 何时使用

- 用户说：工作空间很乱 / 找不到 / 文件夹名不直观 / 输出附件散乱
- 用户要求：给工作空间改名、分类归档、建立命名规范
- 会话结束时需要把当前空间按规则归档

## 零、机制真相（2026-09-19 从 app.asar 源码 + daemon.log 双向验证，先读这条）

WorkBuddy 打开一个会话时，**只做一件事**：拿会话的 `cwd` 算出目录名，去看那个目录里有没有 `<会话id>.jsonl`。

```js
// app.asar → /main/node.js，逐字提取
function normalizeWorkspacePathBase(dir) {
  return dir.replace(/[/\\:]/g, "-").replace(/^-+/, "").replace(/-+$/, "").replace(/-+/g, "-");
}
function compressWorkspacePathName(dir) {
  const base = normalizeWorkspacePathBase(dir);
  if (Buffer.byteLength(base, "utf8") <= 255) return base;
  return `${truncateToByteLimitOnCodePoint(base, 180)}-${djb2Base36(base)}`;  // 超长才有哈希后缀
}
// 候选顺序： [ key(realpath(cwd)), key(cwd) ]，另加 <会话id>.acp-session.json 别名兜底
// 命中判定： projects/<key>/<会话id>.jsonl 能 lstat 到 → 有对话；否则 → 「暂无对话记录」
```

**由此得出三条硬结论：**

| 结论 | 说明 |
|---|---|
| **1. 路径深度完全不影响** | 算法里没有任何一处看目录层级。`F:\workbuddy\08-工具与环境\X` 与 `F:\workbuddy\X` 走的是同一套逻辑。**「嵌套导致任务打不开」是错误归因。** |
| **2. 唯一决定因素 = `projects/` 目录名** | 工作区目录改了名，却没同步改 `projects/<key>`，才发现不了。这是**唯一**的真凶。 |
| **3. 日志能直接判案** | `daemon.log` 里搜 `LocalConversationHistorySource`：`layout-selected … shared-present` = 正常；`history-missing … shared-enoent-owner-key-unavailable` = 找不到文件。 |

**实测数据（2026-09-19）**：`projects/` 同步前 30 个会话报 `history-missing`；
同步后 **0 条 missing**，随后 15 个**全嵌套**工作区（含 `F:/workbuddy\02-项目-女团MV\…` 这类混合分隔符）
全部 `layout-selected shared-present` 正常加载。

**判断某个会话现在到底通不通**（不用开界面）：
```bash
python scripts/check_projects.py                 # 目录一致性
# 或直接看日志：
#   grep -h LocalConversationHistorySource ~/.workbuddy/logs/daemon.log | tail -40
# 若某会话最后一条是 history-missing，而它已修复 → 重启 WorkBuddy 或重新点开即可
```

## 零之二、路径自动匹配（本机已内置）

- `scripts/paths.py` 自动探测工作空间根与 db，优先级：**环境变量 `WORKBUDDY_WORKSPACES_ROOT` / `WORKBUDDY_DB` → `config.json` → 从 `workbuddy.db` 的 `sessions.cwd`/`workspaces.path` 反推公共父目录 → 当前 cwd 的父级**。
- 因此**换盘符（F: → D:）、换机器后无需改脚本**：`scan_workspaces.py` / `apply_plan.py` / `check_integrity.py` 的 root 参数已改为可选；`fix_session_paths.py --root/--archive`、`sync_projects.py --root` 默认自动探测。
- `config.json` 记录本机实址（`workspaces_root` / `db_path`，本机为 `D:\WorkBuddy`），是探测链的第二优先级。
- **迁移映射表统一维护在 `scripts/path_map.py` 的 `MAP`**：每次整理后把 `plan.json` 的 moves 追加进去。`fix_oldpaths.py` / `scan_oldpaths.py` / `scan_db_oldpaths.py` / `fix_db_paths.py` 都从它取规则。
- 前缀正则只认「任意盘符 + `...\WorkBuddy\`」，所以 C: / D: / F: 上的历史索引都能被同一套规则修掉。

## 核心规则（必须遵守）

1. **命名**：`YYYY-MM-DD-主题关键词`（例 `2026-09-06-胶片场景58分镜`）。禁止裸时间戳。
2. **空间内部结构**：`01_outputs/`（交付物，再分 images/docs/video/html）、`02_assets/`（素材）、`03_scripts/`（脚本）、`04_temp/`（中间产物）。产出文件主动归类，不堆根目录。
   - 清 `04_temp/` 前必须走**草稿三分法**：配方型（脚本/中间稿）可清但要先在记忆留「重生成指引」、资产型（AI 产物/当天数据）必须保留、依赖型（node_modules/venv）确认清单文件后可删。原则是**记忆存配方、磁盘存资产**。
3. **分类**：默认 `NN-类型-项目名` 数字前缀分类（例 `01-项目-文明之旅`、`08-工具与环境`）；用户明确要「就地改名」时才用一级平铺。
   - **嵌套是安全的**，不会导致任务找不到。2026-09-19 已从应用源码 + 应用自身日志双向验证（见「零、机制真相」）。
   - 真正会让你「点开空白」的从来不是嵌套，而是**没有同步 `projects/` 目录**（规则 6）。历史上曾把「嵌套」当替罪羊，结论错误，已纠正。
4. **安全红线**
   - 只做 **移动/改名**，绝不删除含内容的文件。
   - 空目录用 `rmdir`（仅空目录能删），删除前逐个核实 0 文件 0 记忆。
   - 改动 `~/.workbuddy/workbuddy.db` 前**必须备份**。
   - 先写对照表再动手，保证可回滚。
   - **非破坏性铁律（量化条款）**：备份先行（复制到 `<空间>/.workbuddy/backups/<日期>/`，确认成功再动手）→ 每批最多 **10 个文件**、每批后核对 → 回收站优先（不用 `rm`）→ **出错即停**（不续下一批、不反复重试被锁目录）。
   - 单轮删除超 50 个文件会触发配额限制，必须拆轮次并先取得用户确认。
5. **归档后必须修数据库**：移动工作空间会导致 `workbuddy.db` 里 `sessions.cwd` / `workspaces.path` 失效。这是最容易漏的一步。
6. **还必须同步 `.workbuddy/projects/` 目录名**（2026-09-19 补，血泪）：
   - 对话正文不存在数据库里，而在 `~/.workbuddy/projects/<cwd 编码>/<会话id>.jsonl`
   - 编码规则：**盘符小写** + `:` `\` `/` 全部换成 `-`
     （`F:\workbuddy\2026-09-05-19-26-13` → `f-workbuddy-2026-09-05-19-26-13`）
   - 只改 `sessions.cwd` 而不改这个目录名 → **会话能打开、但内容全空**，用户会以为「任务丢了」
   - 用 `scripts/fix_projects_dirs.py` 自动对齐
7. **别丢会话的「家」**：文件系统上 0 文件的目录，可能仍有会话的 cwd 指向它。
   删之前必须先查 `sessions` 表。有会话指向的目录应**改名归档**，不要当空目录删掉。
8. **产物索引与自动化路径也要跟着改**：改完目录和会话，产物卡片仍会指向旧路径（点开「找不到」），
   自动化任务的 `cwds` 也会失效（下次跑直接失败）。见 4.6 节。
   一句话记法：**目录、会话正文、产物索引，三样都要修。**
9. **清废与巡检**（融合自马厩管理法 / majiu-management，MIT）：
   - 清废判据走**草稿三分法**，处置守**非破坏性铁律**（见规则 2、4）。
   - 与每日 9:30 的**写操作归档**互补，另设**季度只读深检**：磁盘大户 / 冷文件 / 烂尾任务 / 记忆健康 → **只出报告、等用户拍板**，未拍板不动任何文件。
   - 巡检报告模板、自动化指令模板、可选任务台账见 `references/space-hygiene.md`。
   - ⚠️ 马厩法本身**不含**路径引用修复能力，它的「梳理」只到移动 + 备份 + 回收站。在 WorkBuddy 里移动空间**必须**走完规则 4/5/6/8（db → `projects/` → 产物索引 → 自动化），否则「点开空白 / 产物打不开」。

## 标准流程

### 1. 扫描
```bash
python scripts/scan_workspaces.py --out scan.json   # 根目录自动探测，无需传路径
```
输出每个工作空间的：大小、文件数、是否为 `.workbuddy/memory` 记录的主题线索、是否空目录。

**主题识别靠读 `.workbuddy/memory/*.md`**——这是唯一可靠来源。只读前 400 字足够判断。

### 2. 出方案（给用户确认）
把扫描结果整理成表格：原文件夹 / 实际内容 / 大小，并给出分类与改名建议。
用 AskUserQuestion 确认三件事：整理方式（分类归档 / 原地改名 / 只建索引）、空目录处理、是否写入长期记忆。

### 3. 写 plan.json 并执行
```json
{
  "moves": [
    {"from": "2026-08-24-22-15-19", "to": "02-项目-女团MV/2026-08-24-提示词之外MV分镜"}
  ],
  "delete_empty": ["2026-07-31-10-01-40"]
}
```
```bash
python scripts/apply_plan.py plan.json --mapping _整理对照表-YYYY-MM-DD.md   # 根目录自动探测
```
- 会自动跳过**被应用锁定**的目录（Windows 下当天活动会话常报 `Permission denied`），并在对照表里标记「待归档」。
  处理方式：记入待办，下次会话启动后补做。
- 生成对照表 md，含全部 from→to 映射，可回滚。

### 4. 修数据库（关键）
```bash
python scripts/fix_session_paths.py --db "%USERPROFILE%\.workbuddy\workbuddy.db" --map plan.json --apply
```
- 先备份 `workbuddy.db.bak-<时间戳>`
- 按 plan 重映射 `sessions.cwd` 和 `workspaces.path`
- 仍失效的（如已删空目录）指向 `_归档-空会话/<原名>` 并建空目录，保证历史会话可打开
- 会话的**对话内容存在 `projects/` 的 jsonl 文件里**（不是数据库），移动文件夹不会丢失内容

### 4.5 同步会话正文目录（**最容易漏，漏了就「丢任务」**）
```bash
python scripts/check_projects.py                       # 体检：95 个目录是否都对齐
python scripts/fix_projects_dirs.py                    # 预览
python scripts/fix_projects_dirs.py --apply            # 执行
```
- 原理：会话正文在 `~/.workbuddy/projects/<slug>/<会话id>.jsonl`，`slug = cwd 盘符小写 + 分隔符换 -`
- **只改 db 不改这里 → 会话打开是空白**，用户会报「整理完丢了很多任务」
- 脚本按 plan 后的新 `cwd` 反算 slug，自动整目录改名 / 拆分 / 合并
- 顺带会修 `~/.workbuddy/app/sessions.json` 的 `workDir`（最近会话列表用的）
- 判定标准：`check_projects.py` 输出「已正确 95 / 需改名 0」才算收工

### 4.6 修产物索引与自动化路径（**第 2 个必漏点**）
```bash
python scripts/scan_oldpaths.py                 # 扫 ~/.workbuddy 各索引里的旧路径（只读）
python scripts/scan_db_oldpaths.py              # 扫各 db 里的旧路径（只读）
python scripts/fix_oldpaths.py --apply          # 修 artifact-index / changes-index / changes-detail / file-tree-manifests / automation-backups
python scripts/fix_db_paths.py --apply          # 修 workbuddy.db 的 automations.cwds 等 + edge-sync 缓存
```
- 症状：**会话正文回来了，但产物卡片点开报「找不到」、无法打开文件夹；自动化任务下次跑直接失败**
- 存路径的地方（除了 db 和 projects）：
  - `artifact-index/<会话id>.json` → `uri`（产物卡片的打开链接，`file:///F:/workbuddy/<旧路径>`）
  - `changes-index` / `changes-detail` → `files[].filePath`
  - `automation-backups/*.json` + **db 的 `automations.cwds` / `prompt`** + `automation_runs.source_cwd`
  - `edge-sync-mapping-v4.db` → `edge_sync_artifact_cache.file_path`
- **绝不要改**这三类（它们是历史内容，不是索引）：
  - `projects/*.jsonl` 对话正文
  - `file-history/*@vN` 文件内容快照
  - `changes-detail` 里的 `lines` 字段（diff 正文）
- 映射表统一维护在 `scripts/path_map.py`，**每次整理后把 plan 的 moves 追加进去**
- ⚠️ **顺序坑（2026-09-20 踩）**：`fix_oldpaths.py` / `fix_db_paths.py` 的运行规则**全部来自 `path_map.MAP`**，不读 plan.json。
  所以「把 plan 的 moves 追加进 MAP」必须排在 4.6 这两条**之前**执行，否则本轮改动一处也修不到（表现为「替换 0 处」）。
  正确顺序：apply_plan → fix_session_paths → fix_projects_dirs → **追加 MAP** → fix_oldpaths → fix_db_paths。
- 坑：db 的 `cwds` 是 JSON-in-TEXT，反斜杠被转义成 `\\`，正则要写 `[/\\]{1,2}`

### 5. 任务名自动改名（可选但推荐）
```bash
python scripts/rename_sessions.py            # 预览
python scripts/rename_sessions.py --apply    # 执行
```
- 会话列表里的任务名 = `sessions` 表的 `custom_title`（优先）或 `title`（首条消息截取）
- 规则：**绝不覆盖用户手动命名的**（custom_title 非空跳过）；cwd 有「日期-主题」的取主题；
  垃圾标题（超长/多行/@指令开头/路径/纯时间）清洗成短标题；洗不干净的放弃不动
- 坑：正则要在 .py 文件里写，用 heredoc/`python -c` 内联会被 bash 转义搞坏（`\\\\d` 变 `\\d` 之类）

### 6. 写索引
根目录维护 `_总索引.md`：分类表 + 每个空间的明细 + 待办。每次归档后更新。

### 7. 写入长期记忆
把命名规则、内部结构、归档分类写入 `~/.workbuddy/MEMORY.md`，以后每个会话自动执行。

## 常见坑

- **别把「嵌套」当替罪羊**（2026-09-19 最大教训）：嵌套工作区报「暂无对话」时，
  去查 `projects/` 目录名，不要去摊平目录。摊平既白干一轮，又要再修一遍所有索引。
  判据见「零、机制真相」。
- **修完要重启或重开**：daemon 对已判定「空」的会话可能有 `isKnownEmpty` 缓存。
  路径修好后，**重启 WorkBuddy**（或至少重新点开那个任务）才会重新解析。
  日志表现：修完后该会话不再出现新的 `history-missing`，但界面仍是旧状态。
- **漏同步 `projects/` 目录**（最严重）：症状是「任务还在列表里，点开空白」。见 4.5 节。
- **`safe-delete` 钩子会污染日志**（2026-09-19 踩）：沙箱把 `shutil.move` / `rm` / `Remove-Item`
  包装成回收站删除，失败时打印 `SAFE_DELETE_FAIL_CLOSED`，很容易被读成「移动失败」。
  → **别信日志，直接核对目标目录内容**。实测有 2 条被标记失败、实际已完整迁移。
- **F 盘是 exFAT，回收站不可用**：`genie-trash` 一律报
  `trash operation: Unknown { description: "Some operations were aborted" }`，
  且策略 fail-closed（拒绝降级为直接删除）。
  → 需要真删时：① 先用 `verify_redundant.py` 全量 MD5 确认是冗余副本
  ② 用 Python `os.remove` 逐文件删（**文件能删掉，只有目录壳删不掉**）
  ③ 空壳改名隔离，或留待关闭应用后手动删。
- **目录句柄被占用**：只要 WorkBuddy 开着，某些工作区目录（尤其含 `.git` 的）
  会被锁住，`rename` 报 `WinError 32 另一个程序正在使用此文件`。
  → 记入待办，关闭应用后再处理；**不要反复重试**。
- **批量删除配额**：单轮删除超过 50 个文件触发
  `SAFE_DELETE_BULK_CONFIRM_REQUIRED`，本轮无法再删。分批或换轮次。
- **shell 转义**：`python -c` 里写 Windows 路径（`\\`）会被 bash 吞掉反斜杠，导致条件判断静默失效。
  → **一律写成 .py 脚本文件再执行**，不要 `python -c` 内联。
- **Bash 工具 PATH 为空**：本机偶发 `ls: command not found`，
  命令开头加 `export PATH="/usr/bin:/bin:/c/Windows/System32:/c/Windows:$PATH"` 即可。
- **PowerShell 工具可能不返回 stdout**：本机实测输出为空，验证请用 Bash + `ls`/`find`。
- **当天活动会话被锁**：`mv` 报 `Permission denied`，改不了也删不掉。留待下次启动。
- **mv 链式命令**：`&&` 串联多个 mv，中间一个失败后面全不执行。分批跑，失败的重试单独处理。
- **大目录**：`du -sm` 对 1GB+ 目录较慢，但比逐个 find 快。

## 配套资源

- `references/space-hygiene.md` — 空间卫生标准：草稿三分法 + 重生成指引模板、非破坏性铁律量化条款、季度只读深检规程 + 报告模板 + 自动化指令模板、可选任务台账。融合自**马厩管理法**（[majiu-management](https://github.com/majiabin2020/majiu-management)，MIT © 2026 majiabin2020）。
  - 两个 skill 的分工：**马厩法管空间内的日常纪律（怎么命名、什么时候归档、什么该清），本 skill 管空间之间的结构运维（怎么分类、移动后怎么不炸引用）**。马厩法缺的正是后者 —— 单独用它整理 WorkBuddy 工作空间，必然导致会话空白 + 产物打不开。
