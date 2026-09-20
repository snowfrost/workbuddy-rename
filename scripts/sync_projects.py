# -*- coding: utf-8 -*-
r"""同步 workbuddy-rename 改名操作后 ~/.workbuddy/projects/ 目录名。（plan 驱动版）

> 首选 `fix_projects_dirs.py`：它直接读 db 的 `sessions.cwd` 反推目标目录名，
> 能自动处理「整目录改名 / 合并 / 拆分」，还会顺带修 `app/sessions.json` 的 workDir。
> 本脚本是 plan 驱动版，适合 db 不可用、或想严格照 plan 走的场景。两者择一即可，别同时跑。

WorkBuddy 的对话记录存在 ~/.workbuddy/projects/<路径平铺化>/ 下（<sessionId>.jsonl）。
改名工作区目录后，若不同步重命名 projects 目录，点开任务会显示「暂无对话记录」。

路径平铺化规则：盘符 C: → 小写 c，路径分隔符 \ / 和冒号 : → -，中文原样保留。
例如 C:\Users\snowf\WorkBuddy\2026-08-16-22-28-02 → c-Users-snowf-WorkBuddy-2026-08-16-22-28-02

用法:
    python sync_projects.py --map plan.json --root C:\Users\snowf\WorkBuddy [--apply]
不加 --apply 只体检预览。
"""
import os
import sys
import json
import shutil
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: E402



def flatten(abspath):
    """把绝对路径平铺化为 projects 目录名。"""
    p = os.path.normpath(abspath)
    drive = p[:1].lower()
    rest = p[1:].replace(":", "").replace("\\", "-").replace("/", "-")
    return drive + rest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", required=True, help="apply_plan.py 使用的 plan.json")
    ap.add_argument("--root", default=None)
    ap.add_argument("--projects", default=os.path.expanduser("~/.workbuddy/projects"))
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    if not args.root:
        args.root = paths.detect_root()

    plan = json.load(open(args.map, encoding="utf-8"))
    root = os.path.abspath(args.root)
    proj = os.path.abspath(args.projects)

    pairs = []  # (old_proj_dir, new_proj_dir, old_ws, new_ws)
    for mv in plan.get("moves", []):
        src = mv["from"]
        dst = mv["to"].replace("/", os.sep)
        old_ws = os.path.normpath(os.path.join(root, src))
        new_ws = os.path.normpath(os.path.join(root, dst))
        old_dir = os.path.join(proj, flatten(old_ws))
        new_dir = os.path.join(proj, flatten(new_ws))
        if flatten(old_ws) == flatten(new_ws):
            continue
        pairs.append((old_dir, new_dir, old_ws, new_ws))

    done, skip, locked = [], [], []
    for old_dir, new_dir, old_ws, new_ws in pairs:
        if not os.path.isdir(old_dir):
            skip.append((old_dir, "旧 projects 目录不存在"))
            continue
        if os.path.isdir(new_dir):
            skip.append((old_dir, "新 projects 目录已存在"))
            continue
        if not os.path.isdir(new_ws):
            # 工作区还没真的改成新名（可能被锁），projects 也别动
            skip.append((old_dir, "工作区尚未改名"))
            continue
        if args.apply:
            try:
                shutil.move(old_dir, new_dir)
                done.append((old_dir, new_dir))
                print("[OK ] %s -> %s" % (os.path.basename(old_dir), os.path.basename(new_dir)))
            except OSError as e:
                locked.append((old_dir, str(e)))
                print("[LOCKED] %s: %s" % (old_dir, e))
        else:
            print("[DRY] %s -> %s" % (os.path.basename(old_dir), os.path.basename(new_dir)))

    print("\n需同步 projects %d 个，成功 %d，跳过 %d，锁定 %d" % (len(pairs), len(done), len(skip), len(locked)))
    for d, why in skip:
        print("  skip: %s（%s）" % (os.path.basename(d), why))
    if not args.apply:
        print("（预览模式，加 --apply 执行）")


if __name__ == "__main__":
    sys.exit(main())