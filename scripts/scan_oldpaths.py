# -*- coding: utf-8 -*-
"""扫描 ~/.workbuddy 下所有引用了「已迁移旧工作区路径」的文件。只读。

映射表来自 scripts/path_map.py（自动识别盘符，换机器无需改代码）。
故意不扫 projects/ 与 file-history/：那两处是对话正文与文件快照，属历史内容，绝不改。
"""
import os
import os.path as osp
import sys
import collections

sys.path.insert(0, osp.dirname(osp.abspath(__file__)))
from path_map import PATS, MAP, ROOT  # noqa: E402

HOME = osp.expanduser('~/.workbuddy')

SCAN_DIRS = ['artifact-index', 'changes-index', 'changes-detail', 'media-index',
             'file-tree-manifests', 'assistant-display',
             'local_storage', 'plans', 'brain', 'inspiration', 'memory',
             'automation-backups', 'app']
SKIP_EXT = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.mp4', '.mp3', '.zip', '.pdf',
            '.woff', '.woff2', '.ttf', '.ico', '.bin', '.wasm', '.bmp', '.svg'}

hits = collections.Counter()
detail = collections.defaultdict(list)


def scan_file(path):
    try:
        if osp.getsize(path) > 40 * 1024 * 1024:
            return
        txt = open(path, encoding='utf-8', errors='ignore').read()
    except OSError:
        return
    if 'orkbuddy' not in txt:
        return
    found = set()
    for p, _new in PATS:
        for m in p.finditer(txt):
            found.add(m.group(0))
    if found:
        rel = osp.relpath(path, HOME)
        top = rel.split(os.sep)[0]
        hits[top] += 1
        for f in sorted(found)[:3]:
            detail[top].append((rel, f))


for d in SCAN_DIRS:
    base = osp.join(HOME, d)
    if not osp.isdir(base):
        continue
    for r, dirs, files in os.walk(base):
        dirs[:] = [x for x in dirs if x not in ('node_modules', '__pycache__', 'Cache',
                                                'Code Cache', 'GPUCache', 'blobs', 'binaries')]
        for f in files:
            if osp.splitext(f)[1].lower() in SKIP_EXT:
                continue
            scan_file(osp.join(r, f))

print('工作空间根目录: %s' % ROOT)
print('映射条目: %d 条' % len(MAP))
print('=== 命中统计（按顶层目录）===')
if not hits:
    print('  无（未发现旧路径引用）')
for k, v in hits.most_common():
    print('  %-24s %d 个文件' % (k, v))
print()
for k in list(detail)[:8]:
    print('--- %s ---' % k)
    for rel, f in detail[k][:6]:
        print('   %s' % rel)
        print('      %s' % f)
