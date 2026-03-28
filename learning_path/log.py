"""
log.py — 学习日志持久化模块

提供：load_log, save_log
文件路径：PATH_FILE, LOG_FILE（指向包的父目录，即用户工作目录）
"""

import json
import os

# 指向包的父目录（学习路径生成器项目根目录）
_PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH_FILE = os.path.join(_PARENT_DIR, "my_path.json")
LOG_FILE  = os.path.join(_PARENT_DIR, "learning_log.json")


def load_log() -> list:
    """加载学习日志，文件不存在或损坏时返回空列表。"""
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, encoding="utf-8") as f:
                content = f.read().strip()
            if not content:
                return []
            return json.loads(content)
        except (json.JSONDecodeError, OSError):
            return []
    return []


def save_log(entries: list) -> None:
    """将日志列表保存到 LOG_FILE。"""
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
