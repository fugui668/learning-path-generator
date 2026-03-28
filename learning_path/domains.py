"""
domains.py — 领域注册表加载模块

从 learning_path/domains.json 加载领域配置，暴露：
  DOMAIN_REGISTRY, RESOURCE_MAP, CHECKPOINTS
  DOMAINS_FILE, BASE_DIR
"""

import json
import os
import sys

# 包目录（learning_path/），domains.json 随包走
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOMAINS_FILE = os.path.join(BASE_DIR, "domains.json")


def _load_domains() -> tuple:
    """从 domains.json 加载领域注册表、资源推荐表、掌握度检验表。"""
    if not os.path.exists(DOMAINS_FILE):
        print(f"❌ 找不到领域配置文件：{DOMAINS_FILE}")
        print("   请确保 domains.json 与 learning_path/ 包在同一目录下。")
        sys.exit(1)
    try:
        with open(DOMAINS_FILE, encoding="utf-8") as _f:
            _data = json.load(_f)
        return _data["domain_registry"], _data["resource_map"], _data["checkpoints"]
    except (json.JSONDecodeError, KeyError) as _e:
        print(f"❌ domains.json 格式错误：{_e}")
        print("   请检查 JSON 格式，或删除文件后重新生成。")
        sys.exit(1)


DOMAIN_REGISTRY, RESOURCE_MAP, CHECKPOINTS = _load_domains()
