# -*- coding: utf-8 -*-
"""扫描 ~/.workbuddy 下所有引用了「已迁移的旧工作区路径」的文件。只读。"""
import os
import os.path as osp
import re
import json
import collections

HOME = osp.expanduser('~/.workbuddy')
ROOT = 'F:/workbuddy'

# 已迁移的旧目录名 -> 新相对路径（把 / 换成 \ 用于替换）
MOVED = {}


def load_maps():
    m = {}
    # 本次整理的 slug 映射
    for p in [r'F:\workbuddy\2026-09-19-12-47-08\03_scripts\projects_map_20260919-125647.json',
              r'F:\workbuddy\2026-09-19-12-47-08\03_scripts\projects_map_20260919-130906.json']:
        if not osp.isfile(p):
            continue
        for item in json.load(open(p, encoding='utf-8')):
            old_slug, new_slug = item['from'], item['to']
            # 从 slug 反推：新 slug 去掉前缀 f-workbuddy- 就是新相对路径
            if new_slug.startswith('f-workbuddy-'):
                rel = new_slug[len('f-workbuddy-'):]
                # 旧 slug 去掉 f-workbuddy- 即旧目录名（可能还被 -归档-空会话- 包了一层）
                old = old_slug[len('f-workbuddy-'):]
                if '-' in rel and not re.match(r'^20\d\d-', rel):
                    m[old] = rel
    # 手工补：9-5 整理的主干映射（从对照表来）
    extra = {
        '2026-08-08-16-41-14': '06-创作-提示词与文案-2026-08-08-水彩绘本云鲤视频提示词',
        '2026-08-08-18-02-10': '08-工具与环境-2026-08-08-skill安装aesthetic-extractor',
        '2026-08-08-19-02-45': '06-创作-提示词与文案-2026-08-08-公众号WX智能排版推文',
        '2026-08-09-10-36-37': '05-工作-办公与汇报-2026-08-09-总局调研汇报PPT',
        '2026-08-09-11-16-06': '07-儿童互动页-2026-08-09-彩虹脑洞乐园',
        '2026-08-09-11-22-25': '01-项目-文明之旅-2026-08-09-文明图片素材',
        '2026-08-09-11-30-09': '07-儿童互动页-2026-08-09-喵喵品种学院',
        '2026-08-09-11-31-59': '01-项目-文明之旅-2026-08-09-金句长图与封面对',
        '2026-08-15-15-25-52': '06-创作-提示词与文案-2026-08-15-韩青辰AIGC改编方案',
        '2026-08-15-18-17-35': '06-创作-提示词与文案-2026-08-15-古装打戏提示词',
        '2026-08-16-10-15-02': '03-项目-牛来电影-2026-08-16-十二生肖角色图',
        '2026-08-16-17-24-52': '02-项目-女团MV-2026-08-16-ASTRA女团角色设定',
        '2026-08-16-17-54-41': '02-项目-女团MV-2026-08-16-撒野RUN_WILD歌词',
        '2026-08-16-21-35-30': '03-项目-牛来电影-2026-08-16-牛来公众号文章',
        '2026-08-24-19-00-16': '05-工作-办公与汇报-2026-08-24-团队投票平台',
        '2026-08-24-21-12-20': '08-工具与环境-2026-08-24-SUNO工具指南整理',
        '2026-08-24-21-49-43': '02-项目-女团MV-2026-08-24-提示词之外Suno歌词',
        '2026-08-24-22-15-19': '02-项目-女团MV-2026-08-24-提示词之外MV分镜',
        '2026-08-24-22-17-11': '08-工具与环境-2026-08-24-RunningHub技能核验',
        '2026-08-25-22-16-16': '08-工具与环境-2026-08-25-即梦CLI安装',
        '2026-08-24-22-15-19': '02-项目-女团MV-2026-08-24-提示词之外MV分镜',
    }
    m.update(extra)
    # 归档空会话
    try:
        arch = sorted(os.listdir(r'F:\workbuddy\_归档-空会话'))
    except OSError:
        arch = []
    for a in arch:
        m[a] = '_归档-空会话-' + a
    return m


MOVED = load_maps()
NAMES = sorted(MOVED, key=len, reverse=True)
# 只匹配「F:/workbuddy/<旧名>」或「F:\workbuddy\<旧名>」
PATS = []
for n in NAMES:
    esc = re.escape(n)
    PATS.append(re.compile(r'([Ff]:[/\\]workbuddy[/\\])' + esc + r'(?=[/\\"\']|$)'))
    PATS.append(re.compile(r'([Ff]:[/\\]workbuddy[/\\])' + re.escape(MOVED[n])))

SCAN_DIRS = ['artifact-index', 'changes-index', 'changes-detail', 'media-index',
             'file-tree-manifests', 'assistant-display', 'file-history',
             'local_storage', 'plans', 'brain', 'inspiration', 'memory', 'automation-backups',
             'app', 'projects']
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
    if 'workbuddy' not in txt:
        return
    found = set()
    for p in PATS:
        for m in p.finditer(txt):
            found.add(m.group(0))
    if found:
        rel = osp.relpath(path, HOME)
        top = rel.split(os.sep)[0]
        hits[top] += 1
        for f in list(found)[:3]:
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

print('=== 命中统计（按顶层目录）===')
for k, v in hits.most_common():
    print('  %-24s %d 个文件' % (k, v))
print()
for k in list(detail)[:8]:
    print('--- %s ---' % k)
    for rel, f in detail[k][:6]:
        print('   %s' % rel)
        print('      %s' % f)
