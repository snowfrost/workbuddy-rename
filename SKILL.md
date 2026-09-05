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
3. **分类**：根目录用 `NN-类型-项目名` 数字前缀（排序用），例 `01-项目-文明之旅`、`08-工具与环境`。新主题新建分类。
4. **安全红线**
   - 只做 **移动/改名**，绝不删除含内容的文件。
   - 空目录用 `rmdir`（仅空目录能删），删除前逐个核实 0 文件 0 记忆。
   - 改动 `~/.workbuddy/workbuddy.db` 前**必须备份**。
   - 先写对照表再动手，保证可回滚。
5. **归档后必须修数据库**：移动工作空间会导致 `workbuddy.db` 里 `sessions.cwd` / `workspaces.path` 失效。这是最容易漏的一步。

## 标准流程

### 1. 扫描
```bash
python scripts/scan_workspaces.py F:\workbuddy --out scan.json
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
python scripts/apply_plan.py F:\workbuddy plan.json --mapping _整理对照表-YYYY-MM-DD.md
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
- 会话的**对话内容存在数据库里**，移动文件夹不会丢失记录，只是路径失效

### 5. 写索引
根目录维护 `_总索引.md`：分类表 + 每个空间的明细 + 待办。每次归档后更新。

### 6. 写入长期记忆
把命名规则、内部结构、归档分类写入 `~/.workbuddy/MEMORY.md`，以后每个会话自动执行。

## 常见坑

- **shell 转义**：`python -c` 里写 Windows 路径（`\\\\`）会被 bash 吞掉反斜杠，导致条件判断静默失效。
  → **一律写成 .py 脚本文件再执行**，不要 `python -c` 内联。
- **当天活动会话被锁**：`mv` 报 `Permission denied`，改不了也删不掉。留待下次启动。
- **mv 链式命令**：`&&` 串联多个 mv，中间一个失败后面全不执行。分批跑，失败的重试单独处理。
- **回收站**：本沙箱的删除会进回收站，误删可救。确认前先查 `F:\$RECYCLE.BIN` 的 `$I*` 元数据（路径在偏移 28 字节，UTF-16LE）。
- **大目录**：`du -sm` 对 1GB+ 目录较慢，但比逐个 find 快。
