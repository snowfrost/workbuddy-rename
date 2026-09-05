# -*- coding: utf-8 -*-
r"""通过 GitHub Contents API 推送本地目录（git push 被代理拦截时的备用通道）。

空仓库也能用：第一个文件会自动创建 main 分支和初始提交。

用法:
    python push_via_api.py <本地目录> <owner/repo> <token> [分支] [提交信息]
"""
import os
import sys
import json
import base64
import urllib.request

API = 'https://api.github.com'
SKIP = {'.git', '__pycache__', '.DS_Store'}


def req(method, path, token, body=None):
    data = json.dumps(body).encode('utf-8') if body is not None else None
    r = urllib.request.Request(API + path, data=data, method=method, headers={
        'Authorization': 'Bearer ' + token,
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'workbuddy-rename',
    })
    try:
        raw = urllib.request.urlopen(r, timeout=90).read()
        return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        return {'__error__': exc.code,
                '__body__': exc.read()[:200].decode('utf-8', 'ignore')}


def collect(src):
    out = []
    for root, dirs, names in os.walk(src):
        dirs[:] = [d for d in dirs if d not in SKIP]
        for n in names:
            if n in SKIP or n.endswith('.pyc'):
                continue
            full = os.path.join(root, n)
            out.append((os.path.relpath(full, src).replace('\\', '/'), full))
    return out


def main():
    src, repo, token = sys.argv[1], sys.argv[2], sys.argv[3]
    branch = sys.argv[4] if len(sys.argv) > 4 else 'main'
    message = sys.argv[5] if len(sys.argv) > 5 else 'chore: update via API'

    files = collect(src)
    print('待推送 %d 个文件 -> %s@%s' % (len(files), repo, branch))

    ok = skipped = failed = 0
    for rel, full in files:
        with open(full, 'rb') as fh:
            content = base64.b64encode(fh.read()).decode()
        existing = req('GET', '/repos/%s/contents/%s?ref=%s' % (repo, rel, branch), token)
        body = {'message': message, 'content': content, 'branch': branch}
        if isinstance(existing, dict) and 'sha' in existing:
            # 内容一致就跳过
            if existing.get('content', '').replace('\n', '') == content:
                print('  = %s（无变化）' % rel)
                skipped += 1
                continue
            body['sha'] = existing['sha']
        res = req('PUT', '/repos/%s/contents/%s' % (repo, rel), token, body)
        if '__error__' in res:
            print('  x %s -> HTTP %s %s' % (rel, res['__error__'], res['__body__']))
            failed += 1
        else:
            print('  ok %s' % rel)
            ok += 1

    print('\n新增/更新 %d，无变化 %d，失败 %d' % (ok, skipped, failed))
    print('https://github.com/%s' % repo)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
