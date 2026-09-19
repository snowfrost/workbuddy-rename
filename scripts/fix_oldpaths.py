# -*- coding: utf-8 -*-
"""修复 WorkBuddy 各类索引中写死的旧工作区绝对路径。

背景：工作区改名后，artifact-index / changes-index / changes-detail /
automation-backups 里仍指向旧路径，导致「产物卡片能看到、点开找不到」。

用法:
    python fix_oldpaths.py            # 预览
    python fix_oldpaths.py --apply    # 执行（自动备份）
"""
import os
import os.path as osp
import re
import json
import shutil
import time
import sys
import collections

HOME = osp.expanduser('~/.workbuddy')
APPLY = '--apply' in sys.argv
STAMP = time.strftime('%Y%m%d-%H%M%S')
BAK = osp.join(HOME, '_pathfix-backup-' + STAMP)

# 旧目录名 -> 新相对路径（相对 F:\workbuddy）
MAP = {
    # ---- 2026-09-05 整理 ----
    '2026-08-09-11-22-25': '01-项目-文明之旅/2026-08-09-文明图片素材',
    '2026-08-09-11-31-59': '01-项目-文明之旅/2026-08-09-金句长图与封面对',
    '2026-08-16-17-24-52': '02-项目-女团MV/2026-08-16-ASTRA女团角色设定',
    '2026-08-16-17-54-41': '02-项目-女团MV/2026-08-16-撒野RUN_WILD歌词',
    '2026-08-24-21-49-43': '02-项目-女团MV/2026-08-24-提示词之外Suno歌词',
    '2026-08-24-22-15-19': '02-项目-女团MV/2026-08-24-提示词之外MV分镜',
    '2026-08-16-10-15-02': '03-项目-牛来电影/2026-08-16-十二生肖角色图',
    '2026-08-16-21-35-30': '03-项目-牛来电影/2026-08-16-牛来公众号文章',
    '2026-08-09-10-36-37': '05-工作-办公与汇报/2026-08-09-总局调研汇报PPT',
    '2026-08-24-19-00-16': '05-工作-办公与汇报/2026-08-24-团队投票平台',
    '2026-08-08-16-41-14': '06-创作-提示词与文案/2026-08-08-水彩绘本云鲤视频提示词',
    '2026-08-08-19-02-45': '06-创作-提示词与文案/2026-08-08-公众号WX智能排版推文',
    '2026-08-15-15-25-52': '06-创作-提示词与文案/2026-08-15-韩青辰AIGC改编方案',
    '2026-08-15-18-17-35': '06-创作-提示词与文案/2026-08-15-古装打戏提示词',
    '2026-08-09-11-16-06': '07-儿童互动页/2026-08-09-彩虹脑洞乐园',
    '2026-08-09-11-30-09': '07-儿童互动页/2026-08-09-喵喵品种学院',
    '2026-08-08-18-02-10': '08-工具与环境/2026-08-08-skill安装aesthetic-extractor',
    '2026-08-24-21-12-20': '08-工具与环境/2026-08-24-SUNO工具指南整理',
    '2026-08-24-22-17-11': '08-工具与环境/2026-08-24-RunningHub技能核验',
    '2026-08-25-22-16-16': '08-工具与环境/2026-08-25-即梦CLI安装',
    # ---- 2026-09-19 整理 ----
    '2026-09-05-12-06-14': '04-项目-BoBee插画/2026-09-05-BoBee磨刀石插画',
    '2026-09-05-17-56-09': '08-工具与环境/2026-09-05-工作空间大整理',
    '2026-09-05-19-26-13': '08-工具与环境/2026-09-05-gongwen公文技能创建',
    '2026-09-05-19-56-38': '08-工具与环境/2026-09-05-GiteeMCP调研',
    '2026-09-05-20-09-12': '05-工作-办公与汇报/2026-09-05-政绩观学习心得发言稿',
    '2026-09-05-22-04-48': '08-工具与环境/2026-09-05-旧任务恢复snowfrost',
    '2026-09-13-08-20-14': '08-工具与环境/2026-09-13-WorkBuddy迁移F盘',
    '2026-09-13-09-57-05': '08-工具与环境/2026-09-13-导入历史任务',
    '2026-09-13-10-05-21': '05-工作-办公与汇报/2026-09-13-数字员工研究PPT',
    '2026-09-13-10-15-06': '09-临时与测试/2026-09-13-公益项目咨询',
    '2026-09-13-13-10-47': '08-工具与环境/2026-09-13-xxd-art双技能提炼',
    '2026-09-13-16-15-45': '08-工具与环境/2026-09-13-GitHub凭据更新',
    '2026-09-18-17-47-30': '10-项目-AI训练营/2026-09-18-AI-Passport倒计时',
    '2026-09-19-11-34-40': '11-项目-北京动画周/2026-09-19-翻页参赛方案',
    '文明之旅': '01-项目-文明之旅/2026-09-12-文明之旅定时更新',
    # ---- 早期被删后归档到 _归档-空会话 ----
    '2026-07-31-10-01-40': '_归档-空会话/2026-07-31-10-01-40',
    '2026-08-09-10-01-45': '_归档-空会话/2026-08-09-10-01-45',
    '2026-08-11-16-03-53': '_归档-空会话/2026-08-11-16-03-53',
    '2026-08-15-10-11-10': '_归档-空会话/2026-08-15-10-11-10',
    '2026-08-15-10-17-33': '_归档-空会话/2026-08-15-10-17-33',
    '2026-08-19-19-21-46': '_归档-空会话/2026-08-19-19-21-46',
    '2026-08-22-12-37-41': '_归档-空会话/2026-08-22-12-37-41',
    '2026-08-24-18-58-49': '_归档-空会话/2026-08-24-18-58-49',
    '2026-08-24-19-17-18': '_归档-空会话/2026-08-24-19-17-18',
    '2026-08-24-19-53-31': '_归档-空会话/2026-08-24-19-53-31',
    '2026-08-24-23-08-44': '_归档-空会话/2026-08-24-23-08-44',
    '2026-08-25-20-14-26': '_归档-空会话/2026-08-25-20-14-26',
    '2026-08-28-08-09-04': '_归档-空会话/2026-08-28-08-09-04',
}

PATS = []
for old in sorted(MAP, key=len, reverse=True):
    PATS.append((re.compile(r'([Ff]:[/\\]workbuddy[/\\])' + re.escape(old) + r'(?=[/\\]|["\']|$|\s|,)'),
                 MAP[old]))

TARGETS = ['artifact-index', 'changes-index', 'changes-detail', 'automation-backups']


def fix_str(s):
    hits = 0
    for pat, new in PATS:
        def repl(m):
            nonlocal hits
            prefix = m.group(1)
            sep = '/' if '/' in prefix else '\\'
            hits += 1
            return prefix + new.replace('/', sep)
        s = pat.sub(repl, s)
    return s, hits


# diff 正文属于历史内容，绝不改写
SKIP_KEYS = {'lines', 'text', 'content', 'prompt', 'oldText', 'newText', 'summary'}

# 只在这些字段里替换路径（大小写不敏感匹配）
PATH_KEYS = {'uri', 'filepath', 'path', 'cwd', 'workdir', 'directory', 'targetpath',
             'target', 'file', 'source', 'absolutepath', 'realpath', 'root', 'folder'}


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
    """解析后按字段白名单替换；解析失败则退回纯文本替换。"""
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
            if 'workbuddy' not in raw or 'workbuddy/' not in raw.replace('\\', '/'):
                continue
            # 解析后按字段替换（跳过 diff 正文），再校验
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

print('\n文件 %d 个，替换 %d 处，失败 %d' % (changed, total_hits, len(failed)))
for p, why in failed[:8]:
    print('  [FAIL] %s : %s' % (p, why))
if APPLY and changed:
    print('备份目录: %s' % BAK)
elif not APPLY:
    print('（预览模式，加 --apply 执行）')
