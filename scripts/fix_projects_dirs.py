# -*- coding: utf-8 -*-
"""修复 .workbuddy/projects/<slug> 目录名，使其与 sessions.cwd 一致。

背景：WorkBuddy 把对话正文存在 projects/<slugify(cwd)>/<conversationId>.jsonl。
上次整理只改了 sessions.cwd，没同步 slug 目录名，导致会话打开是空的。

用法:
    python fix_projects_dirs.py            # 预览
    python fix_projects_dirs.py --apply    # 执行
"""
import os
import os.path as osp
import shutil
import sqlite3
import json
import collections
import sys
import time

DB = osp.expanduser('~/.workbuddy/workbuddy.db')
PROJ = osp.expanduser('~/.workbuddy/projects')
SJ = osp.expanduser('~/.workbuddy/app/sessions.json')
APPLY = '--apply' in sys.argv


def slugify(p):
    p = osp.normpath(p)
    if len(p) >= 2 and p[1] == ':':
        p = p[0].lower() + p[2:]
    return p.replace('\\', '-').replace('/', '-')


def main():
    conn = sqlite3.connect('file:%s?mode=ro' % DB.replace('\\', '/'), uri=True)
    by_id = {r[0]: r[1] for r in conn.execute('select id, cwd from sessions')}
    conn.close()

    # 扫描：源目录 -> [(文件名, 目标slug)]
    plan = []      # (src_dir, target_slug, [files])
    skipped = []
    for d in sorted(os.listdir(PROJ)):
        full = osp.join(PROJ, d)
        if not osp.isdir(full):
            continue
        files = [f for f in os.listdir(full) if f.endswith(('.jsonl', '.meta.json'))]
        if not files:
            skipped.append((d, '空目录'))
            continue
        groups = collections.defaultdict(list)
        unknown = []
        for f in files:
            sid = f.replace('.meta.json', '').replace('.jsonl', '')
            cwd = by_id.get(sid)
            if not cwd:
                unknown.append(f)
                continue
            groups[slugify(cwd)].append(f)
        if unknown:
            skipped.append((d, '未知会话文件 %d 个' % len(unknown)))
        for tgt, fs in groups.items():
            plan.append((d, tgt, fs))

    todo = [p for p in plan if p[0] != p[1]]
    print('projects 目录 %d 个，需处理 %d 组，跳过 %d 个' % (
        len(os.listdir(PROJ)), len(todo), len(skipped)))
    for s, why in skipped:
        print('  [skip] %-58s %s' % (s, why))

    print('\n=== 计划 ===')
    mapping = []
    for src, tgt, fs in todo:
        full_src = osp.join(PROJ, src)
        full_tgt = osp.join(PROJ, tgt)
        whole = len(fs) == len([f for f in os.listdir(full_src)
                                if f.endswith(('.jsonl', '.meta.json'))])
        if whole and not osp.exists(full_tgt):
            mode = '整目录改名'
        elif whole:
            mode = '合并进已有目录'
        else:
            mode = '拆分 %d 个文件' % len(fs)
        print('  [%s] %s\n        -> %s' % (mode, src, tgt))
        mapping.append((src, tgt, fs, whole))

    if not APPLY:
        print('\n（预览模式，加 --apply 执行）')
        return 0

    # 备份映射
    mapfile = osp.join(osp.dirname(osp.abspath(__file__)),
                       'projects_map_%s.json' % time.strftime('%Y%m%d-%H%M%S'))
    json.dump([{'from': s, 'to': t, 'files': f, 'whole': w} for s, t, f, w in mapping],
              open(mapfile, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print('\n映射已存: %s' % mapfile)

    done, failed = 0, []
    for src, tgt, fs, whole in mapping:
        full_src = osp.join(PROJ, src)
        full_tgt = osp.join(PROJ, tgt)
        try:
            if whole and not osp.exists(full_tgt):
                os.rename(full_src, full_tgt)
                done += 1
            else:
                os.makedirs(full_tgt, exist_ok=True)
                for f in fs:
                    dst = osp.join(full_tgt, f)
                    if osp.exists(dst):
                        failed.append((f, '目标已存在'))
                        continue
                    shutil.move(osp.join(full_src, f), dst)
                done += 1
                # 源目录空了就删掉（仅空目录）
                if not os.listdir(full_src):
                    os.rmdir(full_src)
        except OSError as e:
            failed.append((src, str(e)))

    print('完成 %d 组，失败 %d' % (done, len(failed)))
    for n, why in failed:
        print('  [FAIL] %s : %s' % (n, why))

    # 修 app/sessions.json
    if osp.isfile(SJ):
        data = json.load(open(SJ, encoding='utf-8'))
        changed = 0
        for s in data.get('sessions', []):
            cwd = by_id.get(s.get('conversationId'))
            if cwd and s.get('workDir') != cwd:
                s['workDir'] = cwd
                changed += 1
        if changed:
            bak = SJ + '.bak-' + time.strftime('%Y%m%d-%H%M%S')
            shutil.copyfile(SJ, bak)
            data['updatedAt'] = time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
            json.dump(data, open(SJ, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
            print('app/sessions.json 修正 %d 条，备份: %s' % (changed, bak))
        else:
            print('app/sessions.json 无需修正')

    return 0


if __name__ == '__main__':
    sys.exit(main())
