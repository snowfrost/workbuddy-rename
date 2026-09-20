# -*- coding: utf-8 -*-
"""扫描 workbuddy.db / edge-sync-mapping*.db 中含旧工作区路径的文本字段。只读。

映射表来自 scripts/path_map.py。
"""
import os
import os.path as osp
import sys
import sqlite3

sys.path.insert(0, osp.dirname(osp.abspath(__file__)))
from path_map import PATS  # noqa: E402

HOME = osp.expanduser('~/.workbuddy')
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
                if not isinstance(val, str) or 'orkbuddy' not in val:
                    continue
                h = set()
                for pat, _new in PATS:
                    for m in pat.finditer(val):
                        h.add(m.group(0))
                if h:
                    found_any = True
                    print('  [%s] rowid=%s col=%s  (共 %d 处)' % (
                        t, row[0], cols[i - 1], len(h)))
                    for x in sorted(h)[:4]:
                        print('       %s' % x)
    if not found_any:
        print('  [ok] 未发现旧路径')
    conn.close()
