# -*- coding: utf-8 -*-
"""修复数据库里写死的旧工作区路径。

- workbuddy.db  automations.cwds / prompt、automation_runs.source_cwd / thread_title / runs_json
- edge-sync-mapping-v4.db  edge_sync_artifact_cache.file_path

用法:
    python fix_db_paths.py            # 预览
    python fix_db_paths.py --apply    # 执行（自动备份）
"""
import os
import os.path as osp
import sqlite3
import shutil
import time
import sys

sys.path.insert(0, osp.dirname(osp.abspath(__file__)))
from path_map import fix_paths_in_text  # noqa: E402

H = osp.expanduser('~/.workbuddy')
APPLY = '--apply' in sys.argv
STAMP = time.strftime('%Y%m%d-%H%M%S')

TARGETS = [
    ('workbuddy.db', 'automations', ['cwds', 'prompt']),
    ('workbuddy.db', 'automation_runs', ['source_cwd', 'thread_title', 'runs_json']),
    ('edge-sync-mapping-v4.db', 'edge_sync_artifact_cache', ['file_path']),
]

total_files, total_hits = 0, 0
for db, table, cols in TARGETS:
    path = osp.join(H, db)
    if not osp.isfile(path):
        print('[skip] %s 不存在' % db)
        continue
    conn = sqlite3.connect('file:%s?mode=ro' % path.replace('\\', '/'), uri=True)
    have = [r[1] for r in conn.execute('pragma table_info("%s")' % table)]
    use = [c for c in cols if c in have]
    if not use:
        print('[skip] %s.%s 无目标列' % (db, table))
        conn.close()
        continue
    rows = conn.execute('select rowid, %s from "%s"' % (', '.join(use), table)).fetchall()
    conn.close()

    updates = []
    for row in rows:
        rid = row[0]
        for i, col in enumerate(use, start=1):
            val = row[i]
            if not isinstance(val, str) or 'workbuddy' not in val:
                continue
            new, hits = fix_paths_in_text(val)
            if hits:
                updates.append((col, new, rid, hits))

    if not updates:
        print('[ok] %s.%s 无旧路径' % (db, table))
        continue

    print('--- %s.%s : %d 个字段待改' % (db, table, len(updates)))
    for col, new, rid, hits in updates[:6]:
        print('    rowid=%s %s (%d 处) -> %s...' % (rid, col, hits, new[:90]))

    if APPLY:
        bak = path + '.bak-' + STAMP
        if not osp.isfile(bak):
            shutil.copyfile(path, bak)
            print('    已备份 -> %s' % bak)
        w = sqlite3.connect(path, timeout=20)
        for col, new, rid, _h in updates:
            w.execute('update "%s" set %s=? where rowid=?' % (table, col), (new, rid))
        w.commit()
        w.close()
        print('    已写入 %d 处' % len(updates))
    total_files += len(updates)
    total_hits += sum(u[3] for u in updates)

print('\n合计 %d 个字段 / %d 处' % (total_files, total_hits))
if not APPLY:
    print('（预览模式，加 --apply 执行）')
