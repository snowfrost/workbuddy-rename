# -*- coding: utf-8 -*-
"""全量核对：projects/<slug>/*.jsonl 与 sessions.cwd 是否对得上。只读。"""
import os
import os.path as osp
import sqlite3
import collections
import json

DB = osp.expanduser('~/.workbuddy/workbuddy.db')
PROJ = osp.expanduser('~/.workbuddy/projects')
SJ = osp.expanduser('~/.workbuddy/app/sessions.json')


def slugify(p):
    p = osp.normpath(p)
    if len(p) >= 2 and p[1] == ':':
        p = p[0].lower() + p[2:]
    return p.replace('\\', '-').replace('/', '-')


def main():
    conn = sqlite3.connect('file:%s?mode=ro' % DB.replace('\\', '/'), uri=True)
    rows = conn.execute('select id, cwd, title, custom_title, deleted_at, status from sessions').fetchall()
    conn.close()
    by_id = {r[0]: r for r in rows}

    # 反向索引：期望 slug -> [session ids]
    want = collections.defaultdict(list)
    for sid, cwd, *_ in rows:
        if cwd:
            want[slugify(cwd)].append(sid)

    print('=== 磁盘 projects 目录核对 ===')
    dirs = sorted(d for d in os.listdir(PROJ) if osp.isdir(osp.join(PROJ, d)))
    print('projects 子目录 %d 个' % len(dirs))
    moved, okdir, orphan, mixed = [], [], [], []
    todo = []          # (旧目录, 旧slug, 新slug, [会话id])
    for d in dirs:
        full = osp.join(PROJ, d)
        files = [f for f in os.listdir(full) if f.endswith('.jsonl')]
        if not files:
            orphan.append((d, '空目录'))
            continue
        # 由 jsonl 文件名反查 session
        slugs = set()
        for f in files:
            sid = f[:-6]
            r = by_id.get(sid)
            if r and r[1]:
                slugs.add(slugify(r[1]))
        if not slugs:
            orphan.append((d, '%d 个 jsonl 但无对应会话记录' % len(files)))
        elif len(slugs) == 1:
            new = slugs.pop()
            if new == d:
                okdir.append(d)
            else:
                todo.append((d, new, files))
        else:
            mixed.append((d, sorted(slugs), files))

    print('  已正确 %d 个' % len(okdir))
    print('  需改名 %d 个' % len(todo))
    print('  无主（孤儿）%d 个' % len(orphan))
    print('  一对多（需拆分）%d 个' % len(mixed))

    print('\n=== 需改名清单（旧 slug -> 新 slug）===')
    for old, new, files in todo:
        print('  %s\n     -> %s   [%d 个会话文件]' % (old, new, len(files)))

    if mixed:
        print('\n=== 一对多（一个旧目录里的会话被分到多个新 cwd）===')
        for old, news, files in mixed:
            print('  %s -> %s' % (old, news))
            for f in files:
                r = by_id.get(f[:-6])
                print('      %s | %s' % (f[:-6][:8], (r[1] if r else '?')))

    if orphan:
        print('\n=== 孤儿目录 ===')
        for d, why in orphan:
            print('  %-60s %s' % (d, why))

    # 反向：sessions 里的会话有没有对应 jsonl
    print('\n=== 数据库会话 -> 磁盘文件 覆盖率 ===')
    ondisk = set()
    for d in dirs:
        for f in os.listdir(osp.join(PROJ, d)):
            if f.endswith('.jsonl'):
                ondisk.add(f[:-6])
    miss = [r for r in rows if r[0] not in ondisk]
    print('  会话总数 %d，磁盘有 jsonl 的 %d，缺文件 %d' % (len(rows), len(rows) - len(miss), len(miss)))
    for r in miss[:25]:
        print('    %s | %s | %s' % (r[0][:8], (r[2] or '')[:30].replace('\n', ' '),
                                    osp.basename(osp.normpath(r[1])) if r[1] else ''))

    # sessions.json
    print('\n=== app/sessions.json ===')
    if osp.isfile(SJ):
        data = json.load(open(SJ, encoding='utf-8'))
        for s in data.get('sessions', []):
            wd = s.get('workDir', '')
            exists = osp.isdir(wd)
            print('  %s %s  (%s)' % ('[ok]  ' if exists else '[失效]', wd, s['conversationId'][:8]))


if __name__ == '__main__':
    main()
