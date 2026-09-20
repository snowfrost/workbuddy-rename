# -*- coding: utf-8 -*-
r"""自动匹配 WorkBuddy 工作空间根目录与数据库路径。

优先级（从高到低）：
  1. 环境变量 WORKBUDDY_WORKSPACES_ROOT / WORKBUDDY_DB
  2. 本 skill 的 config.json（workspaces_root / db_path）
  3. 从 workbuddy.db 反推：workspaces.path 与 sessions.cwd 的公共父目录
  4. 兜底：当前工作目录的父目录（如 D:\WorkBuddy\skill -> D:\WorkBuddy）

这样换机器 / 换盘符（F: -> D:）后无需改代码，只要 config.json 或数据库在即可。
"""
import os
import json
import sqlite3

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))            # .../workbuddy-rename/scripts
CONFIG = os.path.join(os.path.dirname(SKILL_DIR), 'config.json')   # .../workbuddy-rename/config.json
DEFAULT_DB = os.path.expanduser('~/.workbuddy/workbuddy.db')


def _load_config():
    if os.path.isfile(CONFIG):
        try:
            with open(CONFIG, encoding='utf-8') as fh:
                return json.load(fh)
        except Exception:
            return {}
    return {}


def detect_db():
    """返回 workbuddy.db 的实际路径（存在则优先用 config 指定）。"""
    cfg = _load_config()
    if cfg.get('db_path') and os.path.isfile(cfg['db_path']):
        return cfg['db_path']
    if os.path.isfile(DEFAULT_DB):
        return DEFAULT_DB
    return DEFAULT_DB


def detect_root():
    """返回工作空间根目录（绝对、规范化）。"""
    env = os.environ.get('WORKBUDDY_WORKSPACES_ROOT')
    if env and os.path.isdir(env):
        return os.path.normpath(env)

    cfg = _load_config()
    if cfg.get('workspaces_root') and os.path.isdir(cfg['workspaces_root']):
        return os.path.normpath(cfg['workspaces_root'])

    # 从数据库反推公共父目录（最稳的“自动匹配”）
    db = detect_db()
    if os.path.isfile(db):
        try:
            conn = sqlite3.connect('file:%s?mode=ro' % db.replace('\\', '/'), uri=True)
            paths = []
            try:
                paths += [r[0] for r in conn.execute('select path from workspaces') if r[0]]
            except Exception:
                pass
            try:
                paths += [r[0] for r in conn.execute('select cwd from sessions') if r[0]]
            except Exception:
                pass
            conn.close()
            norm = [os.path.normpath(p) for p in paths if p]
            if norm:
                # 只取确实存在的目录参与公共前缀计算，避免脏数据拉偏
                existing = [p for p in norm if os.path.isdir(p)]
                if not existing:
                    existing = norm
                return os.path.normpath(os.path.commonpath(existing))
        except Exception:
            pass

    # 兜底：cwd 的父目录（D:\WorkBuddy\skill -> D:\WorkBuddy）
    cwd_parent = os.path.dirname(os.getcwd())
    if os.path.isdir(cwd_parent):
        return os.path.normpath(cwd_parent)
    return os.path.normpath(os.getcwd())


if __name__ == '__main__':
    print('workspaces_root =', detect_root())
    print('db_path         =', detect_db())
