# workbuddy-rename

把 WorkBuddy 里一堆 `2026-08-24-21-12-20` 这类时间戳工作空间，原地改成一目了然的「日期-主题」，并同步修好对话记录索引，让任务一眼能找到、点开有对话。

WorkBuddy 每次开会话都在工作根目录建一个时间戳文件夹。几个月后就是几十个看不出内容的目录，
产出物（图片 / md / 视频）散落各处，想找上次做的东西基本靠缘分。这个 skill 解决的就是这件事。

## 能做什么

| 步骤 | 脚本 | 作用 |
|---|---|---|
| 1 扫描 | `scripts/scan_workspaces.py` | 盘点所有工作空间：大小、文件数、是否空目录，并读取 `.workbuddy/memory/*.md` 推断主题 |
| 2 执行 | `scripts/apply_plan.py` | 按 `plan.json` 原地改名，清理空目录，生成可回滚的对照表 |
| 3 同步对话 | `scripts/sync_projects.py` | 同步重命名 `~/.workbuddy/projects/` 对话记录目录（最易漏、最关键） |
| 4 修库 | `scripts/fix_session_paths.py` | 修复移动后 `workbuddy.db` 里失效的会话路径 |
| 5 体检 | `scripts/check_integrity.py` | 检查失效会话、残留时间戳目录、projects 目录一致性 |

## 命名规则

- 文件夹：`YYYY-MM-DD-主题关键词`，例 `2026-09-06-胶片场景58分镜`
- **原地改名、保持一级目录**：禁止嵌套到 `NN-类型-项目名` 二级分类——WorkBuddy 会话工作区只认根目录一层，嵌套会让任务「找不到/打不开」
- 空间内部：`01_outputs/`（交付物）、`02_assets/`（素材）、`03_scripts/`（脚本）、`04_temp/`（中间产物）

## 快速开始

```bash
# 1. 扫描
python scripts/scan_workspaces.py F:\workbuddy --out scan.json

# 2. 写 plan.json（to 写原地改名后的一级目录名），先体检
python scripts/apply_plan.py F:\workbuddy plan.json --dry-run

# 3. 执行改名
python scripts/apply_plan.py F:\workbuddy plan.json

# 4. 同步对话记录目录（关键，漏了会「暂无对话记录」）
python scripts/sync_projects.py --map plan.json --root F:\workbuddy --apply

# 5. 修数据库（先体检，再加 --apply）
python scripts/fix_session_paths.py --map plan.json --root F:\workbuddy
python scripts/fix_session_paths.py --map plan.json --root F:\workbuddy --apply

# 6. 体检
python scripts/check_integrity.py F:\workbuddy
```

## 三个最容易踩的坑

1. **对话记录不在会话目录里，在 `~/.workbuddy/projects/`**。WorkBuddy 的对话存成 `<sessionId>.jsonl`，
   目录名是「路径平铺化」（`C:`→`c`、`\`→`-`、中文保留，前缀 `c-Users-snowf-WorkBuddy-`+工作区名）。
   改名工作区后**漏掉同步 projects 目录**，点开任务就是「暂无对话记录」。这是第 4 步，最不能省。
2. **当天的活动会话会被锁定**。`mv` 报 `Permission denied`，改不了也删不掉。脚本会跳过并写进对照表的待办，下次启动应用后补做。
3. **`du -sm` 的数字是虚高的**。它会把每个文件向上取整到 1MB，几 KB 的小文件也算 1MB，
   几万张小图的目录能虚高好几倍。要真实体量用脚本里的 Python 统计（已加 Windows 长路径容错）。

## 安全设计

- 只做移动/改名，不删任何含内容的文件
- 空目录只删核实为 0 文件的，用 `os.rmdir`（非空直接失败，不会误删）
- 改数据库前自动备份 `workbuddy.db.bak-<时间戳>`
- 每次执行都输出对照表 md，可逐条回滚

## 实测

- 2026-09-05 在 `F:\workbuddy` 首次跑通（当时的「嵌套分类」做法已废弃）。
- 2026-09-19 在 `C:\Users\snowf\WorkBuddy`：106 个时间戳目录原地改成「日期-主题」，52 个空壳清理，
  465 条会话路径全部修复，24 个 projects 对话目录同步改名，零文件损失、零失效。

## 许可

MIT