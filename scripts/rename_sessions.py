# -*- coding: utf-8 -*-
r"""批量整理 WorkBuddy 会话标题（任务名）。

规则（按优先级）：
1. 绝不覆盖用户已手动命名的会话（custom_title 非空的跳过）。
2. cwd 指向「日期-主题」工作空间的 -> custom_title = 主题（去掉日期前缀）。
3. 标题本身是垃圾的（超长/多行/空/"开始新会话"）-> 清洗成短标题。
4. 清洗结果若仍像路径/指令/太短 -> 放弃，保留原标题。
5. 执行前自动备份数据库。

用法:
    python rename_sessions.py            # 预览
    python rename_sessions.py --apply    # 执行
"""
import os
import re
import sys
import time
import shutil
import sqlite3
import argparse

DB = os.path.expanduser('~/.workbuddy/workbuddy.db')
MEANINGLESS = {'开始新会话', '新会话', 'untitled', 'none', '用', '好的', '继续'}
DATE_PREFIX = re.compile(r'^20\d\d-\d\d-\d\d-')
PURE_TIME = re.compile(r'^[\d\-]+$')
BAD_BASES = {'workbuddy', 'skill', 'temp', '新建文件夹', 'worktmp'}


def has_content(s):
    """至少含一个中文或英文字母（排除纯数字/符号名）。"""
    return bool(re.search(r'[\u4e00-\u9fffA-Za-z]', s))


def derive_from_cwd(cwd):
    """从工作空间目录名提取主题（去掉日期前缀）。提不出来的返回 None。"""
    if not cwd:
        return None
    base = os.path.basename(os.path.normpath(cwd))
    if base.lower() in BAD_BASES or re.match(r'^task[-_]?\d+$', base.lower()):
        return None
    if DATE_PREFIX.match(base):
        topic = DATE_PREFIX.sub('', base)
        if not topic or PURE_TIME.match(topic) or not has_content(topic):
            return None
        if topic.lower() in BAD_BASES or re.match(r'^task[-_]?\d+$', topic.lower()):
            return None
        return topic
    return None


def clean_title(title):
    """从原始标题清洗短标题；洗不出有意义的返回 None。"""
    if not title:
        return None
    t = title.strip()
    if t.lower() in MEANINGLESS:
        return None
    line = t.splitlines()[0].strip()
    line = re.sub(r'^(任务目标|任务|目标)[:：\s]*', '', line)
    # 去掉开头连续的 @指令 token（@skill:xxx、@"路径"、@image#1:"..."）
    parts = line.split()
    drop = 0
    for p in parts[:4]:
        if p.startswith('@'):
            drop += 1
        else:
            break
    if drop and len(parts) > drop:
        line = ' '.join(parts[drop:])
    # 在第一个句读处截断（保留至少 6 字）
    for ch in '。，；、！？':
        idx = line.find(ch)
        if idx > 6:
            line = line[:idx]
            break
    line = line.strip().rstrip('，。；、：:-—').strip()
    if len(line) > 24:
        line = line[:24].rstrip('，。；、')
    # 垃圾结果过滤：路径、URL、@指令、引号/key、太短
    if len(line) < 3 or not has_content(line):
        return None
    if re.search(r'[\\/:]', line) or line.startswith('@') or line.lower().startswith('http'):
        return None
    if '"' in line or "'" in line or re.search(r'\b(ak_|sk-|token|key)\b', line, re.I):
        return None
    return line


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', default=DB)
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    if not os.path.isfile(args.db):
        print('数据库不存在: %s' % args.db)
        return 1

    conn = sqlite3.connect(args.db, timeout=20)
    rows = conn.execute('select id, title, custom_title, cwd from sessions').fetchall()

    changes, kept, skipped = [], 0, 0
    for sid, title, ct, cwd in rows:
        if ct:  # 用户手动命名的绝不动
            kept += 1
            continue
        new = derive_from_cwd(cwd)
        if not new:
            t = (title or '').strip()
            messy = (not t) or len(t) > 24 or ('\n' in t) or (t in MEANINGLESS)
            if not messy:
                skipped += 1  # 原标题本身短且干净，不动
                continue
            new = clean_title(title)
        if new and new != (title or '').strip():
            changes.append((new, sid))
        else:
            skipped += 1

    print('总会话 %d | 已有自定义名(保留) %d | 待改名 %d | 不动 %d'
          % (len(rows), kept, len(changes), skipped))
    by_id = {r[0]: (r[1],) for r in rows}
    for new, sid in changes[:40]:
        old = (by_id[sid][0] or '').replace('\n', ' ')[:38]
        print('  %s | %s -> %s' % (sid[:8], old, new))
    if len(changes) > 40:
        print('  ... 其余 %d 条' % (len(changes) - 40))

    if not args.apply:
        print('\n（预览模式，未改动。加 --apply 执行）')
        conn.close()
        return 0

    backup = args.db + '.bak-' + time.strftime('%Y%m%d-%H%M%S')
    conn.close()
    shutil.copyfile(args.db, backup)
    print('\n已备份 -> %s' % backup)

    conn = sqlite3.connect(args.db, timeout=20)
    for new, sid in changes:
        conn.execute('update sessions set custom_title=? where id=?', (new, sid))
    conn.commit()
    n = conn.execute('select count(*) from sessions where custom_title is not null').fetchone()[0]
    conn.close()
    print('完成：改名 %d 条，当前共 %d 条有自定义名' % (len(changes), n))
    return 0


if __name__ == '__main__':
    sys.exit(main())
