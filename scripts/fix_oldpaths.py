# -*- coding: utf-8 -*-
"""修复 WorkBuddy 各类索引中写死的旧工作区绝对路径。

症状：会话正文正常，但产物卡片点开报「找不到」、无法打开文件夹；
      自动化任务下次跑直接失败。

覆盖：artifact-index / changes-index / changes-detail / automation-backups
不碰：projects/*.jsonl 对话正文、file-history 快照、changes-detail 的 lines（diff 正文）

映射表统一维护在 scripts/path_map.py。

用法:
    python fix_oldpaths.py            # 预览
    python fix_oldpaths.py --apply    # 执行（自动备份）
"""
import os
import os.path as osp
import json
import shutil
import time
import sys

sys.path.insert(0, osp.dirname(osp.abspath(__file__)))
from path_map import fix_paths_in_text as fix_str, ROOT, MAP  # noqa: E402

HOME = osp.expanduser('~/.workbuddy')
APPLY = '--apply' in sys.argv
STAMP = time.strftime('%Y%m%d-%H%M%S')
BAK = osp.join(HOME, '_pathfix-backup-' + STAMP)

TARGETS = ['artifact-index', 'changes-index', 'changes-detail', 'automation-backups',
           'file-tree-manifests']

# diff 正文 / 消息正文属于历史内容，绝不改写
SKIP_KEYS = {'lines', 'text', 'content', 'prompt', 'oldtext', 'newtext', 'summary'}


def fix_obj(node, key=None):
    n = 0
    if isinstance(node, str):
        if key is not None and key.lower() in SKIP_KEYS:
            return node, 0
        return fix_str(node)
    if isinstance(node, list):
        out = []
        for x in node:
            v, k = fix_obj(x, key)
            out.append(v)
            n += k
        return out, n
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            v2, k2 = fix_obj(v, k)
            out[k] = v2
            n += k2
        return out, n
    return node, 0


def walk_fix(raw):
    """解析后按字段替换；解析失败则退回纯文本替换。"""
    try:
        data = json.loads(raw)
    except ValueError:
        return fix_str(raw)
    new, hits = fix_obj(data)
    return json.dumps(new, ensure_ascii=False, indent=2), hits


changed, total_hits, failed = 0, 0, []
for t in TARGETS:
    base = osp.join(HOME, t)
    if not osp.isdir(base):
        continue
    for r, _d, files in os.walk(base):
        for f in files:
            if not f.endswith('.json'):
                continue
            p = osp.join(r, f)
            try:
                raw = open(p, encoding='utf-8').read()
            except OSError:
                continue
            if 'orkbuddy' not in raw:
                continue
            new_raw, hits = walk_fix(raw)
            if hits == 0:
                continue
            try:
                json.loads(new_raw)
            except ValueError as e:
                failed.append((p, '替换后 JSON 非法: %s' % e))
                continue
            changed += 1
            total_hits += hits
            print('[%s] %s  (%d 处)' % ('改 ' if APPLY else '预览', osp.relpath(p, HOME), hits))
            if APPLY:
                dst = osp.join(BAK, osp.relpath(p, HOME))
                os.makedirs(osp.dirname(dst), exist_ok=True)
                shutil.copyfile(p, dst)
                open(p, 'w', encoding='utf-8', newline='').write(new_raw)

print('\n工作空间根: %s ｜ 映射 %d 条' % (ROOT, len(MAP)))
print('文件 %d 个，替换 %d 处，失败 %d' % (changed, total_hits, len(failed)))
for p, why in failed[:8]:
    print('  [FAIL] %s : %s' % (p, why))
if APPLY and changed:
    print('备份目录: %s' % BAK)
elif not APPLY:
    print('（预览模式，加 --apply 执行）')
