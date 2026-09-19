# -*- coding: utf-8 -*-
"""全量 MD5 校验：确认「源目录」的内容在「目标目录顶层」完整存在，并检查冗余嵌套副本。
用法: python verify_redundant.py <src> <dst> [--nested <嵌套子目录名>]
只读，不改任何文件。
"""
import os
import os.path as osp
import sys
import hashlib


def md5(path):
    h = hashlib.md5()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def rel_files(root):
    out = {}
    for r, _d, files in os.walk(root):
        for f in files:
            full = osp.join(r, f)
            out[osp.relpath(full, root)] = full
    return out


def main():
    src, dst = sys.argv[1], sys.argv[2]
    nested = None
    if '--nested' in sys.argv:
        nested = sys.argv[sys.argv.index('--nested') + 1]

    a = rel_files(src)
    b = rel_files(dst)
    print('源 %d 文件 / 目标 %d 文件' % (len(a), len(b)))

    missing, mismatch, ok = [], [], 0
    for rel, full in a.items():
        tgt = osp.join(dst, rel)
        if not osp.isfile(tgt):
            missing.append(rel)
            continue
        if md5(full) != md5(tgt):
            mismatch.append(rel)
        else:
            ok += 1
    print('  源文件在目标顶层：一致 %d / 缺失 %d / 内容不同 %d' % (ok, len(missing), len(mismatch)))
    for r in missing[:8]:
        print('     [缺失]', r)
    for r in mismatch[:8]:
        print('     [不同]', r)

    if nested:
        nroot = osp.join(dst, nested)
        if not osp.isdir(nroot):
            print('  嵌套目录不存在: %s' % nroot)
        else:
            c = rel_files(nroot)
            bad = 0
            for rel, full in c.items():
                tgt = osp.join(dst, rel)
                if not osp.isfile(tgt) or md5(full) != md5(tgt):
                    bad += 1
            print('  嵌套副本 %s：%d 文件，与目标顶层不一致 %d 个' % (nested, len(c), bad))

    verdict = (not missing and not mismatch)
    print('\n结论：%s' % ('源内容已在目标完整落盘，可安全清理' if verdict else '存在差异，禁止删除'))


if __name__ == '__main__':
    main()
