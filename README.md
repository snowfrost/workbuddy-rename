# workbuddy-rename

把 WorkBuddy 里一堆 `2026-08-24-21-12-20` 这类时间戳工作空间，整理成一眼能找到的项目库。

WorkBuddy 每次开会话都在工作根目录建一个时间戳文件夹。几个月后就是几十个看不出内容的目录，
产出物（图片 / md / 视频）散落各处，想找上次做的东西基本靠缘分。这个 skill 解决的就是这件事。

## 能做什么

| 步骤 | 脚本 | 作用 |
|---|---|---|
| 1 扫描 | `scripts/scan_workspaces.py` | 盘点所有工作空间：大小、文件数、是否空目录，并读取 `.workbuddy/memory/*.md` 推断主题 |
| 2 执行 | `scripts/apply_plan.py` | 按 `plan.json` 移动/改名，清理空目录，生成可回滚的对照表 |
| 3 修库 | `scripts/fix_session_paths.py` | 修复移动后 `workbuddy.db` 里失效的会话路径 |
| 4 体检 | `scripts/check_integrity.py` | 检查分类、失效会话、残留时间戳目录 |

## 命名规则

- 文件夹：`YYYY-MM-DD-主题关键词`，例 `2026-09-06-胶片场景58分镜`
- 空间内部：`01_outputs/`（交付物）、`02_assets/`（素材）、`03_scripts/`（脚本）、`04_temp/`（中间产物）
- 根目录分类：`NN-类型-项目名`，数字前缀用于排序

## 快速开始

```bash
# 1. 扫描
python scripts/scan_workspaces.py F:\workbuddy --out scan.json

# 2. 写 plan.json（参考 examples/plan-2026-09-05.json），先体检
python scripts/apply_plan.py F:\workbuddy plan.json --dry-run

# 3. 执行
python scripts/apply_plan.py F:\workbuddy plan.json

# 4. 修数据库（先体检，再加 --apply）
python scripts/fix_session_paths.py --map plan.json --root F:\workbuddy
python scripts/fix_session_paths.py --map plan.json --root F:\workbuddy --apply

# 5. 体检
python scripts/check_integrity.py F:\workbuddy
```

## 三个容易踩的坑

1. **移动文件夹会让会话路径失效**。`workbuddy.db` 的 `sessions.cwd` / `workbuddy.path` 存的是绝对路径，
   不改的话打开旧会话会提示目录不存在。会话的对话内容在数据库里，不会丢，但路径必须修。
   这就是为什么必须有第 3 步。
2. **当天的活动会话会被锁定**。`mv` 报 `Permission denied`，改不了也删不掉。脚本会跳过并写进对照表的待办，下次启动应用后补做。
3. **`du -sm` 的数字是虚高的**。它会把每个文件向上取整到 1MB，几 KB 的小文件也算 1MB，
   几万张小图的目录能虚高好几倍。要真实体量用脚本里的 Python 统计（已加 Windows 长路径容错）。

## 安全设计

- 只做移动/改名，不删任何含内容的文件
- 空目录只删核实为 0 文件的，用 `os.rmdir`（非空直接失败，不会误删）
- 改数据库前自动备份 `workbuddy.db.bak-<时间戳>`
- 每次执行都输出对照表 md，可逐条回滚

## 实测

2026-09-05 在 `F:\workbuddy` 上跑通：35 个时间戳空间 → 9 个分类，22 个改名归档，
12 个空目录清理，42 条失效会话路径全部修复，零文件损失。

## 许可

MIT
