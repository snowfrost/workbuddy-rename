# -*- coding: utf-8 -*-
"""扫描 workbuddy.db（及 edge-sync-mapping*.db）中所有含旧工作区路径的文本字段。只读。"""
import os
import os.path as osp
import re
import sqlite3

HOME = osp.expanduser('~/.workbuddy')
PAT = re.compile(r'[Ff]:[/\\]workbuddy[/\\](20\d\d-\d\d-\d\d-\d\d-\d\d-\d\d|文明之旅|Claw)'
                 r'(?=[/\\"\'},]|$)')

DBS = ['workbuddy.db', 'edge-sync-mapping-v4.db', 'edge-sync-mapping-v3.db',
       'edge-sync-mapping-v2.db', 'edge-sync-mapping.db']

for db in DBS:
    p = osp.join(HOME, db)
    if not osp.isfile(p):
        continue
    print('=' * 60)
    print('DB: %s' % db)
    try:
        conn = sqlite3.connect('file:%s?mode=ro' % p.replace('\\', '/'), uri=True)
        tables = [r[0] for r in conn.execute(
            "select name from sqlite_master where type='table'")]
    except Exception as e:
        print('  打开失败: %s' % e)
        continue
    found_any = False
    for t in tables:
        try:
            cols = [r[1] for r in conn.execute('pragma table_info("%s")' % t)]
        except Exception:
            continue
        if not cols:
            continue
        try:
            rows = conn.execute('select rowid, * from "%s"' % t).fetchall()
        except Exception as e:
            print('  跳过 %s: %s' % (t, e))
            continue
        for row in rows:
            for i, val in enumerate(row[1:], start=1):
                if not isinstance(val, str) or 'workbuddy' not in val:
                    continue
                hits = set(m.group(0) for m in PAT.finditer(val))
                if hits:
                    found_any = True
                    print('  [%s] rowid=%s col=%s  (共 %d 处)' % (
                        t, row[0], cols[i - 1], len(hits)))
                    for h in list(hits)[:4]:
                        print('       %s' % h)
    if not found_any:
        print('  [ok] 未发现旧路径')
    conn.close()
