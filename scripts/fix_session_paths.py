# -*- coding: utf-8 -*-
r"""修复 workbuddy.db 中因移动工作空间而失效的会话路径。

移动文件夹后，sessions.cwd / workspaces.path 仍指向旧位置，
打开旧会话会提示目录不存在。本脚本按 plan.json 的映射重指向。

用法:
    python fix_session_paths.py --db "%USERPROFILE%\.workbuddy\workbuddy.db" --map plan.json --apply
不加 --apply 则只体检不改动。
"""
import os
import sys
import json
import time
import shutil
import sqlite3
import argparse


def norm(p):
    return os.path.normpath(p).rstrip(os.sep).lower()


def load_map(plan_path, root):
    """plan.json -> {旧目录名: 新相对路径}"""
    plan = json.load(open(plan_path, encoding='utf-8'))
    mapping = {}
    for mv in plan.get('moves', []):
        src = os.path.basename(norm(mv['from']).replace('/', os.sep))
        mapping[src] = mv['to']
    return mapping, plan.get('delete_empty', [])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', default=os.path.expanduser('~/.workbuddy/workbuddy.db'))
    ap.add_argument('--map', required=True, help='apply_plan.py 使用的 plan.json')
    ap.add_argument('--root', default=r'F:\workbuddy')
    ap.add_argument('--archive', default=r'F:\workbuddy\_归档-空会话')
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    mapping, deleted = load_map(args.map, args.root)
    root = os.path.abspath(args.root)

    if not os.path.isfile(args.db):
        print('数据库不存在: %s' % args.db)
        return 1

    conn = sqlite3.connect('file:%s?mode=ro' % args.db.replace('\\', '/'), uri=True)
    rows = conn.execute('select id, cwd from sessions').fetchall()
    wrows = conn.execute('select path from workspaces').fetchall()
    conn.close()

    def resolve(cwd):
        """返回 (新路径, 类别) 类别: mapped / archived / ok / skip"""
        if not cwd:
            return None, 'skip'
        if os.path.isdir(cwd):
            return None, 'ok'
        base = os.path.basename(norm(cwd))
        if base in mapping:
            target = os.path.join(root, mapping[base])
            # 目标本身也被删了（例如临时文件已清理）则退回归档区
            if os.path.isdir(target):
                return target, 'mapped'
        if norm(cwd).startswith(norm(root)):
            return os.path.join(args.archive, base), 'archived'
        return None, 'skip'

    stats = {'mapped': 0, 'archived': 0, 'ok': 0, 'skip': 0}
    plan_updates, plan_ws = [], []
    for sid, cwd in rows:
        new, kind = resolve(cwd)
        stats[kind] += 1
        if new:
            plan_updates.append((new, sid))
    for (path,) in wrows:
        new, kind = resolve(path)
        if new:
            plan_ws.append((new, path))

    print('会话总数 %d：已正确 %d / 需重指向 %d / 需归档 %d / 无关 %d' % (
        len(rows), stats['ok'], stats['mapped'], stats['archived'], stats['skip']))
    print('workspaces 表需更新：%d 条' % len(plan_ws))

    if not args.apply:
        print('\n（体检模式，未改动。加 --apply 执行）')
        for new, sid in plan_updates[:10]:
            print('  %s -> %s' % (sid[:8], new))
        return 0

    backup = args.db + '.bak-' + time.strftime('%Y%m%d-%H%M%S')
    shutil.copyfile(args.db, backup)
    print('\n已备份数据库 -> %s' % backup)

    conn = sqlite3.connect(args.db, timeout=20)
    for new, sid in plan_updates:
        conn.execute('update sessions set cwd=? where id=?', (new, sid))
    for new, old in plan_ws:
        conn.execute('update workspaces set path=? where path=?', (new, old))
    # 归档目录建空壳，保证旧会话可打开
    for new, sid in plan_updates:
        if new.startswith(args.archive):
            os.makedirs(new, exist_ok=True)
    conn.commit()

    remain = [c for (_, c) in conn.execute('select id, cwd from sessions')
              if c and norm(c).startswith(norm(root)) and not os.path.isdir(c)]
    conn.close()
    print('更新会话 %d 条，workspaces %d 条' % (len(plan_updates), len(plan_ws)))
    print('仍失效会话：%d' % len(remain))
    return 0


if __name__ == '__main__':
    sys.exit(main())
