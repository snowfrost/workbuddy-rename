# -*- coding: utf-8 -*-
r"""扫描 WorkBuddy 工作空间，输出盘点 JSON。

用法:
    python scan_workspaces.py F:\workbuddy --out scan.json
"""
import os
import sys
import json
import argparse

IGNORE = {'.workbuddy'}


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
    for root, dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return round(total / 1024 / 1024, 1)


def count_files(path, cap=20000):
    n = 0
    for _ in iter_files(path):
        n += 1
        if n > cap:
            break
    return n


def read_topic(ws):
    """从 .workbuddy/memory/*.md 读取主题线索。"""
    mem_dir = os.path.join(ws, '.workbuddy', 'memory')
    notes = []
    if os.path.isdir(mem_dir):
        for name in sorted(os.listdir(mem_dir)):
            if not name.endswith('.md'):
                continue
            try:
                with open(os.path.join(mem_dir, name), encoding='utf-8', errors='ignore') as fh:
                    txt = fh.read(900).strip()
            except OSError:
                continue
            if txt:
                notes.append({'file': name, 'head': txt[:600]})
    return notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('root')
    ap.add_argument('--out', default='scan.json')
    args = ap.parse_args()

    root = args.root
    result = []
    for name in sorted(os.listdir(root)):
        full = os.path.join(root, name)
        if not os.path.isdir(full) or name in IGNORE or name.startswith('.'):
            continue
        children = [c for c in os.listdir(full) if c not in IGNORE]
        item = {
            'name': name,
            'path': full,
            'size_mb': dir_size_mb(full),
            'file_count': count_files(full),
            'top_level': children[:15],
            'is_empty': len(children) == 0 and not os.path.isdir(os.path.join(full, '.workbuddy')),
            'only_appdata': len(children) == 0 and os.path.isdir(os.path.join(full, '.workbuddy')),
            'memory': read_topic(full),
        }
        result.append(item)

    with open(args.out, 'w', encoding='utf-8') as fh:
        json.dump(result, fh, ensure_ascii=False, indent=1)

    print('%-40s %8s %6s %s' % ('NAME', 'SIZE_MB', 'FILES', 'TOP_LEVEL'))
    for it in result:
        flag = ' [EMPTY]' if it['is_empty'] else (' [APPDATA-ONLY]' if it['only_appdata'] else '')
        print('%-40s %8s %6s %s%s' % (
            it['name'][:40], it['size_mb'], it['file_count'],
            ','.join(it['top_level'])[:60], flag))
    print('\n共 %d 个工作空间，空: %d，写盘: %s' % (
        len(result), sum(1 for i in result if i['is_empty']), args.out))


if __name__ == '__main__':
    main()
