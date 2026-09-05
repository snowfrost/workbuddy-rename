# -*- coding: utf-8 -*-
r"""按 plan.json 执行工作空间的移动/改名与空目录清理，并生成可回滚的对照表。

用法:
    python apply_plan.py F:\workbuddy plan.json --mapping _整理对照表-2026-09-05.md

plan.json 格式:
{
  "moves": [{"from": "2026-08-24-22-15-19", "to": "02-项目-女团MV/2026-08-24-提示词之外MV分镜"}],
  "delete_empty": ["2026-07-31-10-01-40"]
}
"""
import os
import sys
import json
import shutil
import argparse
import datetime


def is_effectively_empty(path):
    """只有 .workbuddy 之外没有任何内容才算真空。"""
    try:
        items = [c for c in os.listdir(path) if c != '.workbuddy']
    except OSError:
        return False
    return len(items) == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('root')
    ap.add_argument('plan')
    ap.add_argument('--mapping', default=None)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    plan = json.load(open(args.plan, encoding='utf-8'))
    stamp = datetime.date.today().isoformat()
    mapping_path = args.mapping or os.path.join(root, '_整理对照表-%s.md' % stamp)

    done, failed, removed, skipped = [], [], [], []

    for mv in plan.get('moves', []):
        src = os.path.join(root, mv['from'])
        dst = os.path.join(root, mv['to'])
        if not os.path.isdir(src):
            skipped.append((mv['from'], '源目录不存在'))
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if args.dry_run:
            print('[DRY] %s -> %s' % (mv['from'], mv['to']))
            continue
        try:
            shutil.move(src, dst)
            done.append((mv['from'], mv['to']))
            print('[OK ] %s -> %s' % (mv['from'], mv['to']))
        except PermissionError:
            failed.append((mv['from'], mv['to'], '被占用锁定(Permission denied)，下次会话启动后重试'))
            print('[LOCKED] %s 无法移动' % mv['from'])
        except OSError as exc:
            failed.append((mv['from'], mv['to'], str(exc)))
            print('[FAIL] %s: %s' % (mv['from'], exc))

    for name in plan.get('delete_empty', []):
        target = os.path.join(root, name)
        if not os.path.isdir(target):
            continue
        if not is_effectively_empty(target):
            print('[SKIP] %s 非空，不删除' % name)
            skipped.append((name, '非空，拒绝删除'))
            continue
        if args.dry_run:
            print('[DRY] rmdir %s' % name)
            continue
        try:
            os.rmdir(target)  # 仅空目录可删，非空直接报错
            removed.append(name)
            print('[DEL ] %s' % name)
        except OSError as exc:
            skipped.append((name, str(exc)))
            print('[FAIL] %s: %s' % (name, exc))

    lines = [
        '# 整理对照表（%s）' % stamp,
        '',
        '> 操作类型：移动/改名 + 空目录清理，未删除任何含内容的文件。',
        '> 回滚方式：按本表把新路径改回原路径即可。',
        '',
        '## 移动改名（%d 项成功）' % len(done),
        '',
    ]
    for src, dst in done:
        lines.append('- `%s` → `%s`' % (src, dst))
    if failed:
        lines += ['', '## 待办：被锁定未能移动', '']
        for src, dst, why in failed:
            lines.append('- ⚠️ `%s` → `%s`（%s）' % (src, dst, why))
    if removed:
        lines += ['', '## 已删除的空目录（删除前逐个核实 0 文件）', '']
        for name in removed:
            lines.append('- `%s`' % name)
    if skipped:
        lines += ['', '## 跳过', '']
        for name, why in skipped:
            lines.append('- `%s`：%s' % (name, why))

    with open(mapping_path, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines) + '\n')

    print('\n移动成功 %d / 失败 %d / 删除空目录 %d / 跳过 %d' % (len(done), len(failed), len(removed), len(skipped)))
    print('对照表：%s' % mapping_path)


if __name__ == '__main__':
    main()
