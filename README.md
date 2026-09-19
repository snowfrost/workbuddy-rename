# workbuddy-rename

把 WorkBuddy 里一堆 `2026-08-24-21-12-20` 这类时间戳工作空间，整理成一眼能找到的项目库，
**并且保证历史会话点开有对话、产物卡片点开能打开**。

WorkBuddy 每次开会话都在工作根目录建一个时间戳文件夹。几个月后就是几十个看不出内容的目录，
产出物（图片 / md / 视频）散落各处，想找上次做的东西基本靠缘分。这个 skill 解决的就是这件事。

## ⚠️ 先搞清楚机制（2026-09-19 从 app.asar 源码验证）

WorkBuddy 打开会话时只看一个地方：

```
<configDir>/projects/<key>/<会话id>.jsonl      # key = cwd 的路径平铺化
```

```js
// app.asar → /main/node.js 逐字提取
function normalizeWorkspacePathBase(dir) {
  return dir.replace(/[/\\:]/g, "-").replace(/^-+/, "").replace(/-+$/, "").replace(/-+/g, "-");
}
```

**关键结论：算法里没有任何一处看目录层级。**
`F:\workbuddy\08-工具与环境\X` 和 `F:\workbuddy\X` 走的是同一套逻辑。

> 2026-09-19 实测：`projects/` 目录同步前 30 个会话报 `history-missing`；
> 同步后 **0 条 missing**，随后 15 个**全部嵌套**的工作区（含 `F:/workbuddy\02-项目-女团MV\…`
> 这类混合分隔符路径）全部 `layout-selected shared-present` 正常加载。
>
> 所以：**「嵌套分类会导致任务打不开」是错误归因。** 真凶永远是 `projects/` 目录名没跟着改。

## 能做什么

| 步骤 | 脚本 | 作用 |
|---|---|---|
| 1 扫描 | `scripts/scan_workspaces.py` | 盘点所有工作空间：大小、文件数、是否空目录，并读 `.workbuddy/memory/*.md` 推断主题 |
| 2 执行 | `scripts/apply_plan.py` | 按 `plan.json` 分类归档/改名，清空目录，生成可回滚的对照表 |
| 3 修库 | `scripts/fix_session_paths.py` | 修 `workbuddy.db` 里的 `sessions.cwd` / `workspaces.path` |
| 4 同步对话 | `scripts/fix_projects_dirs.py` | 同步 `~/.workbuddy/projects/` 目录名（**漏了就是「暂无对话记录」**）+ 修 `app/sessions.json` |
| 5 修产物索引 | `scripts/scan_oldpaths.py` / `fix_oldpaths.py` / `fix_db_paths.py` | 修产物卡片链接、自动化 `cwds`、edge-sync 缓存（**漏了就是「产物打不开」**） |
| 6 体检 | `scripts/check_projects.py` / `check_integrity.py` | projects 目录一致性、失效会话、残留时间戳目录 |

## 命名规则

- 文件夹：`YYYY-MM-DD-主题关键词`，例 `2026-09-06-胶片场景58分镜`
- 根目录分类：`NN-类型-项目名`（数字前缀排序），例 `01-项目-文明之旅`、`08-工具与环境`
  - 嵌套**安全**，前提是走完第 4、5 步
- 空间内部：`01_outputs/`（交付物）、`02_assets/`（素材）、`03_scripts/`（脚本）、`04_temp/`（中间产物）

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

# 5. 同步对话目录（关键，漏了 = 点开空白）
python scripts/check_projects.py
python scripts/fix_projects_dirs.py --apply

# 6. 修产物索引与自动化路径（漏了 = 产物打不开 / 自动化跑挂）
python scripts/scan_oldpaths.py
python scripts/fix_oldpaths.py --apply
python scripts/fix_db_paths.py --apply

# 7. 体检
python scripts/check_integrity.py F:\workbuddy
```

## 排障：某个任务点开是空白

不用开界面，看应用自己的日志就能判案：

```bash
grep -h LocalConversationHistorySource ~/.workbuddy/logs/daemon.log | tail -40
```

| 日志 | 含义 |
|---|---|
| `layout-selected … shared-present` | 正常，找到 jsonl 了 |
| `history-missing … shared-enoent-owner-key-unavailable` | `projects/<key>/<id>.jsonl` 不存在 → 去查 `projects/` 目录名 |

修好后**重启 WorkBuddy**（daemon 对已判定「空」的会话有缓存），或至少重新点开一次那个任务。

## 四个容易踩的坑

1. **对话正文不在数据库里，在 `~/.workbuddy/projects/<key>/<会话id>.jsonl`**。
   只改 db 的 `sessions.cwd` 而不改这个目录名，会话能打开但内容是空白 —— 用户会以为「任务丢了」。
   这是最容易被漏、后果最严重的一步（见上面的机制说明）。
2. **产物索引是另一套绝对路径**。`artifact-index/*.json` 的 `uri`、`changes-*` 的 `filePath`、
   db 的 `automations.cwds`、`edge-sync-mapping-v4.db` 的 `file_path` 都写死了旧路径。
   不动它们，会话正文回来了、产物卡片却点开「找不到」。
3. **当天的活动会话会被锁定**。`mv` 报 `Permission denied`，改不了也删不掉。脚本会跳过并写进对照表待办，下次启动应用后补做。
4. **`du -sm` 的数字是虚高的**。它把每个文件向上取整到 1MB，几 KB 的小文件也算 1MB，
   几万张小图的目录能虚高好几倍。要真实体量用脚本里的 Python 统计（已加 Windows 长路径容错）。

## 安全设计

- 只做移动/改名，不删任何含内容的文件
- 空目录只删核实为 0 文件的，用 `os.rmdir`（非空直接失败，不会误删）
- 删目录前先查 `sessions` 表：**0 文件的目录可能仍有会话指向它**，应改名归档而不是删掉
- 改数据库前自动备份 `workbuddy.db.bak-<时间戳>`
- 每次执行都输出对照表 md，可逐条回滚
- **绝不修改**这三类历史内容：`projects/*.jsonl` 对话正文、`file-history/*@vN` 文件快照、
  `changes-detail` 的 `lines` 字段（diff 正文）

## 实测

- 2026-09-05 在 `F:\workbuddy`：35 个时间戳空间 → 9 个分类，22 个改名归档，12 个空目录清理，42 条失效会话路径修复。
- 2026-09-19 在 `F:\workbuddy`：15 个目录归档进 11 个分类，**50 组 `projects/` 目录同步**（95/95 对齐），
  16 条 `sessions.cwd` + 8 条 `app/sessions.json` 修复，**179 个产物索引文件/字段共 1989 处路径更新**，
  顺手修好一个 ACTIVE 状态的自动化任务（它的 `cwds` 还指向已移走的目录，下次执行必失败）。零文件损失。
- 同日修复后的 15 个**全嵌套**工作区全部正常加载对话（daemon 日志零 `history-missing` 验证）。

## 许可

MIT
