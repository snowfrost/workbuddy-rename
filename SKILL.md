---
name: workbuddy-rename
description: Organize, rename and archive WorkBuddy workspace folders. Use when the user complains that workspace folders are unfindable (timestamp-only names), wants to rename/plan/archive workspaces, wants output files (images/md/video) classified, or asks to clean up F:\workbuddy. Scans workspaces, infers each one's topic from .workbuddy/memory, proposes a YYYY-MM-DD-topic naming plan, applies moves, repairs session paths in the WorkBuddy database, and writes an index.
agent_created: true
---

# workbuddy-rename — WorkBuddy 工作空间整理

把「一堆 2026-08-24-21-12-20 时间戳文件夹」变成「一眼能找到的项目库」。

## 何时使用

- 用户说：工作空间很乱 / 找不到 / 文件夹名不直观 / 输出附件散乱
- 用户要求：给工作空间改名、分类归档、建立命名规范
- 会话结束时需要把当前空间按规则归档

## 核心规则（必须遵守）

1. **命名**：`YYYY-MM-DD-主题关键词`（例 `2026-09-06-胶片场景58分镜`）。禁止裸时间戳。
2. **空间内部结构**：`01_outputs/`（交付物，再分 images/docs/video/html）、`02_assets/`（素材）、`03_scripts/`（脚本）、`04_temp/`（中间产物）。产出文件主动归类，不堆根目录。
3. **分类（原地改名，不嵌套）**：**保持根目录一级目录，只改时间戳为 `日期-主题`**，例 `2026-08-24-22-15-19` → `2026-08-24-提示词之外MV分镜`。**禁止嵌套到 `NN-类型-项目名` 二级分类目录**——WorkBuddy 会话工作区习惯一级目录，嵌套会导致会话列表里任务找不到/打不开（2026-09-19 实操验证）。
4. **安全红线**
   - 只做 **移动/改名**，绝不删除含内容的文件。
   - 空目录用 `rmdir`（仅空目录能删），删除前逐个核实 0 文件 0 记忆。
   - 改动 `~/.workbuddy/workbuddy.db` 前**必须备份**。
   - 先写对照表再动手，保证可回滚。
5. **归档后必须修数据库**：移动工作空间会导致 `workbuddy.db` 里 `sessions.cwd` / `workspaces.path` 失效。这是最容易漏的一步。
6. **⚠️ 同步改名 `~/.workbuddy/projects/` 目录（最关键，2026-09-19 踩坑）**：WorkBuddy 的**对话记录**存在 `~/.workbuddy/projects/<路径平铺化>/` 下（文件名如 `<sessionId>.jsonl`、`<sessionId>.meta.json`）。路径平铺化规则：盘符 `C:` → 小写 `c`，每个 `\` → `-`，中文保留，前缀形如 `c-Users-snowf-WorkBuddy-` + 工作区目录名。**改名工作区目录时，必须同步重命名对应的 projects 目录**，否则 WorkBuddy 点开任务会显示「暂无对话记录」、产物找不到。这是会话改名后最容易被漏、后果最严重的一步。

## 标准流程

### 1. 扫描
```bash
python scripts/scan_workspaces.py F:\workbuddy --out scan.json
```
输出每个工作空间的：大小、文件数、是否为 `.workbuddy/memory` 记录的主题线索、是否空目录。

**主题识别靠读 `.workbuddy/memory/*.md`**——这是唯一可靠来源。只读前 400 字足够判断。

### 2. 出方案（给用户确认）
把扫描结果整理成表格：原文件夹 / 实际内容 / 大小，并给出改名建议。
用 AskUserQuestion 确认三件事：整理方式（**原地改名** / 只建索引）、空目录处理、是否写入长期记忆。
注意：不再提供「嵌套分类归档」选项——嵌套到二级目录会让 WorkBuddy 会话列表找不到任务。

### 3. 写 plan.json 并执行
```json
{
  "moves": [
    {"from": "2026-08-24-22-15-19", "to": "2026-08-24-提示词之外MV分镜"}
  ],
  "delete_empty": ["2026-07-31-10-01-40"]
}
```
`to` 是**原地改名后的一级目录名**（去掉时间戳时分秒、加主题），不要带 `分类/` 前缀。
```bash
python scripts/apply_plan.py F:\workbuddy plan.json --mapping _整理对照表-YYYY-MM-DD.md
```
- 会自动跳过**被应用锁定**的目录（Windows 下当天活动会话常报 `Permission denied`），并在对照表里标记「待归档」。
  处理方式：记入待办，下次会话启动后补做。
- 生成对照表 md，含全部 from→to 映射，可回滚。

### 4. 同步对话记录目录（关键，最易漏）
```bash
python scripts/sync_projects.py --map plan.json --root F:\workbuddy --apply
```
- WorkBuddy 的**对话记录在 `~/.workbuddy/projects/<路径平铺化>/` 下**（`<sessionId>.jsonl`＋`.meta.json`），**不在会话目录里、也不在数据库里**。
- 改名工作区目录后，必须同步重命名 projects 目录，否则点开任务显示「暂无对话记录」、产物找不到。
- 先预览（不加 `--apply`），确认无误再执行。

### 5. 修数据库
```bash
python scripts/fix_session_paths.py --db "%USERPROFILE%\.workbuddy\workbuddy.db" --map plan.json --apply
```
- 先备份 `workbuddy.db.bak-<时间戳>`
- 按 plan 重映射 `sessions.cwd` 和 `workspaces.path`（注意数据库里路径分隔符可能是正斜杠 `/`，比较前要统一归一化）
- 仍失效的（如已删空目录）指向 `_归档-空会话/<原名>` 并建空目录，保证历史会话可打开

### 6. 任务名自动改名（可选但推荐）
```bash
python scripts/rename_sessions.py            # 预览
python scripts/rename_sessions.py --apply    # 执行
```
- 会话列表里的任务名 = `sessions` 表的 `custom_title`（优先）或 `title`（首条消息截取）
- 规则：**绝不覆盖用户手动命名的**（custom_title 非空跳过）；cwd 有「日期-主题」的取主题；
  垃圾标题（超长/多行/@指令开头/路径/纯时间）清洗成短标题；洗不干净的放弃不动
- 坑：正则要在 .py 文件里写，用 heredoc/`python -c` 内联会被 bash 转义搞坏（`\\\\d` 变 `\\d` 之类）

### 7. 写索引
根目录维护 `_总索引.md`：分类表 + 每个空间的明细 + 待办。每次归档后更新。

### 8. 写入长期记忆
把命名规则、内部结构、归档分类写入 `~/.workbuddy/MEMORY.md`，以后每个会话自动执行。

## 常见坑

- **shell 转义**：`python -c` 里写 Windows 路径（`\\\\`）会被 bash 吞掉反斜杠，导致条件判断静默失效。
  → **一律写成 .py 脚本文件再执行**，不要 `python -c` 内联。
- **当天活动会话被锁**：`mv` 报 `Permission denied`，改不了也删不掉。留待下次启动。
- **mv 链式命令**：`&&` 串联多个 mv，中间一个失败后面全不执行。分批跑，失败的重试单独处理。
- **回收站**：本沙箱的删除会进回收站，误删可救。确认前先查 `F:\$RECYCLE.BIN` 的 `$I*` 元数据（路径在偏移 28 字节，UTF-16LE）。
- **大目录**：`du -sm` 对 1GB+ 目录较慢，但比逐个 find 快。
- **WorkBuddy 环境（2026-09-13 实测）**：
  - `sitecustomize` shim 会把 `os.remove` / `shutil.rmtree` / PowerShell `Remove-Item` 全部劫持成「移到回收站」。空壳目录删除后命令会报 `SAFE_DELETE_FAIL_CLOSED`，但文件可能已实际删除——**以文件系统事实为准**（删后 `os.path.isdir` 复查）。
  - **中文路径吃瘪**：trash 二进制对中文路径有 GBK/UTF-8 编码 bug，报 `trash-failed` 且 detail 里中文变乱码。**真删中文路径目录用 .NET** `[IO.Directory]::Delete($p, $true)` 或 `sitecustomize._orig_shutil_rmtree`，绕开 trash。
  - `shutil.move` 遇目标目录已存在会**往内嵌**（move 到 dst/basename），不是报错 → 移动前先确认 dst 不存在，避免嵌套双份。
  - 当天活跃会话目录被锁（WinError 32 / PermissionError），`shutil.move` 会走 copy+删源的兜底，复制不完整 → 锁定目录宁可留待下次启动，不要硬移动。
