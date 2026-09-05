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

TS = re.compile(r'^20\d\d-\d\d-\d\d-\d\d-\d\d-\d\d$')


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
    ap.add_argument('root')
    ap.add_argument('--db', default=os.path.expanduser('~/.workbuddy/workbuddy.db'))
    args = ap.parse_args()
    root = os.path.abspath(args.root)

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
        print('[!] 根目录仍有裸时间戳目录 %d 个：%s' % (len(stray), ', '.join(stray[:5])))
        problems += 1
    else:
        print('[ok] 根目录无裸时间戳目录')

    empty_cats = [n for n in sorted(os.listdir(root))
                  if os.path.isdir(os.path.join(root, n))
                  and not n.startswith('.')
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

    print('\n总体量 %s MB，发现 %d 类问题' % (total, problems))
    return 0


if __name__ == '__main__':
    sys.exit(main())
