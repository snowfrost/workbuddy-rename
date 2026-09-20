# -*- coding: utf-8 -*-
r"""整理后的完整性体检：分类统计、失效会话、未命名时间戳目录、空目录。

用法:
    python check_integrity.py F:\workbuddy [--db "%USERPROFILE%\.workbuddy\workbuddy.db"]
"""
import os
import re
import sys
import sqlite3
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: E402


TS = re.compile(r'^20\d\d-\d\d-\d\d-\d\d-\d\d-\d\d$')


def flatten(abspath):
    """把绝对路径平铺化为 projects 目录名：C: -> c，分隔符 -> -。"""
    p = os.path.normpath(abspath)
    return p[:1].lower() + p[1:].replace(":", "").replace("\\", "-").replace("/", "-")


def iter_files(path):
    """Windows 长路径安全的遍历：用 \\\\?\\ 前缀 + onerror 报告，避免静默漏统计。"""
    abs_path = os.path.abspath(path)
    if os.name == 'nt' and not abs_path.startswith('\\\\?\\'):
        abs_path = '\\\\?\\' + abs_path
    for root, dirs, files in os.walk(abs_path, onerror=lambda e: print('[WARN] 跳过: %s' % e)):
        for f in files:
            yield os.path.join(root, f)


def dir_size_mb(path):
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return round(total / 1024 / 1024, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('root', nargs='?', default=None)
    ap.add_argument('--db', default=os.path.expanduser('~/.workbuddy/workbuddy.db'))
    args = ap.parse_args()
    root = os.path.abspath(args.root or paths.detect_root())

    print('=== 分类目录 ===')
    total = 0
    for name in sorted(os.listdir(root)):
        full = os.path.join(root, name)
        if not os.path.isdir(full) or name.startswith('.'):
            continue
        size = dir_size_mb(full)
        total += size
        sub = [c for c in os.listdir(full) if c != '.workbuddy']
        print('%-28s %4d 项 %8s MB' % (name, len(sub), size))

    print('\n=== 问题检查 ===')
    problems = 0

    stray = [n for n in sorted(os.listdir(root))
             if os.path.isdir(os.path.join(root, n)) and TS.match(n)]
    if stray:
        print('[!] 根目录仍有裸时间戳目录 %d 个（若正被活跃会话占用属正常，待其结束由自动归档处理）：%s' % (len(stray), ', '.join(stray[:5])))
        problems += 1
    else:
        print('[ok] 根目录无裸时间戳目录')

    KEEP = {'Claw', 'skill', 'resources', 'map-creator-main', '小小东', 'auths', 'data',
            '_归档-空会话'}
    empty_cats = [n for n in sorted(os.listdir(root))
                  if os.path.isdir(os.path.join(root, n))
                  and not n.startswith('.')
                  and n not in KEEP
                  and not [c for c in os.listdir(os.path.join(root, n)) if c != '.workbuddy']]
    if empty_cats:
        print('[!] 空分类目录：%s' % ', '.join(empty_cats))
        problems += 1
    else:
        print('[ok] 无空分类目录')

    if os.path.isfile(args.db):
        conn = sqlite3.connect('file:%s?mode=ro' % args.db.replace('\\', '/'), uri=True)
        rows = conn.execute('select id, cwd from sessions').fetchall()
        conn.close()
        bad = [(i, c) for i, c in rows if c and os.path.normpath(c).lower().startswith(os.path.normpath(root).lower())
               and not os.path.isdir(c)]
        if bad:
            print('[!] 失效会话 %d 条（示例）：' % len(bad))
            for i, c in bad[:5]:
                print('      %s  %s' % (i[:8], c))
            problems += 1
        else:
            print('[ok] 会话目录路径全部有效（共 %d 条会话）' % len(rows))
    else:
        print('[--] 未找到数据库：%s' % args.db)

    # projects 对话记录目录一致性：按 sessions.cwd 反查（工作区存在但 projects/<slug> 缺失 = 改名没同步）
    # 注意：不能用「根目录下每个目录」的口径——分类目录（01-xxx）本身不是会话 cwd，
    #       真 cwd 是分类下的子目录，否则必然误报。口径与 check_projects.py 保持一致。
    proj = os.path.expanduser('~/.workbuddy/projects')
    if os.path.isdir(proj) and os.path.isfile(args.db):
        conn = sqlite3.connect('file:%s?mode=ro' % args.db.replace('\\', '/'), uri=True)
        rows = conn.execute('select id, cwd from sessions').fetchall()
        conn.close()
        missing = [(i, c) for i, c in rows
                   if c and os.path.isdir(c) and not os.path.isdir(os.path.join(proj, flatten(c)))]
        if missing:
            print('[!] 会话 cwd 存在但 projects 对话目录缺失 %d 条（改名没同步，点开会「暂无对话记录」）：' % len(missing))
            for i, c in missing[:5]:
                print('      %s  %s' % (i[:8], c))
            problems += 1
        else:
            print('[ok] projects 对话目录与全部会话 cwd 一一对应')

    print('\n总体量 %s MB，发现 %d 类问题' % (total, problems))
    return 0


if __name__ == '__main__':
    sys.exit(main())
