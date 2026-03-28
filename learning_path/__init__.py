"""
learning_path — 个性化学习路径生成器包

公共 API：
  generate_path(goal, level, hours_per_week, total_weeks) -> dict
  detect_domain(goal) -> str
  adjust_for_delay(delay_weeks) -> list
  print_path(path) -> None
  load_log() -> list
  save_log(entries) -> None

常量：
  __version__, MIN_STAGE_WEEKS, LEVEL_TO_STAGE, STAGE_ORDER
  DOMAIN_REGISTRY, RESOURCE_MAP, CHECKPOINTS
  PATH_FILE, LOG_FILE
"""

from ._version import __version__
from .core import (
    generate_path,
    detect_domain,
    adjust_for_delay,
    parse_float,
    parse_int,
    _locate_current_step,
    _infer_current_week,
    _find_step_by_week,
    MIN_STAGE_WEEKS,
    LEVEL_TO_STAGE,
    STAGE_ORDER,
)
from .domains import (
    DOMAIN_REGISTRY,
    RESOURCE_MAP,
    CHECKPOINTS,
    DOMAINS_FILE,
    BASE_DIR,
)
from .log import load_log, save_log, PATH_FILE, LOG_FILE
from .render import print_path, show_chart, export_pdf

__all__ = [
    "__version__",
    "generate_path", "detect_domain", "adjust_for_delay",
    "parse_float", "parse_int",
    "_locate_current_step", "_infer_current_week", "_find_step_by_week",
    "MIN_STAGE_WEEKS", "LEVEL_TO_STAGE", "STAGE_ORDER",
    "DOMAIN_REGISTRY", "RESOURCE_MAP", "CHECKPOINTS",
    "DOMAINS_FILE", "BASE_DIR",
    "load_log", "save_log", "PATH_FILE", "LOG_FILE",
    "print_path", "show_chart", "export_pdf",
]
