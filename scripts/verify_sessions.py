# -*- coding: utf-8 -*-
"""验证：每个会话按当前 cwd 都能找到自己的 jsonl 正文。只读。"""
import os
import os.path as osp
import sqlite3

DB = osp.expanduser('~/.workbuddy/workbuddy.db')
PROJ = osp.expanduser('~/.workbuddy/projects')


def slug(p):
    p = osp.normpath(p)
    if len(p) >= 2 and p[1] == ':':
        p = p[0].lower() + p[2:]
    return p.replace('\\', '-').replace('/', '-')


conn = sqlite3.connect('file:%s?mode=ro' % DB.replace('\\', '/'), uri=True)
rows = conn.execute('select id, cwd, title, custom_title from sessions').fetchall()
conn.close()

ok, bad, samples = 0, 0, []
for sid, cwd, title, ct in rows:
    if not cwd:
        continue
    d = osp.join(PROJ, slug(cwd))
    f = osp.join(d, sid + '.jsonl')
    if osp.isfile(f):
        ok += 1
        if len(samples) < 8 and osp.getsize(f) > 20000:
            samples.append(((ct or title or '')[:26], osp.basename(d), round(osp.getsize(f) / 1024)))
    else:
        bad += 1
        print('  [找不到] %s  %s' % (sid[:8], (title or '')[:30]))

print('会话正文可直接打开: %d / %d   找不到: %d' % (ok, ok + bad, bad))
print()
print('抽样（标题 -> 正文目录  大小）:')
for t, d, kb in samples:
    print('  %-26s -> %s  (%d KB)' % (t, d[:60], kb))
