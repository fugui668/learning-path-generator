"""
core.py — 核心路径生成逻辑

包含：parse_float, parse_int, detect_domain,
      _select_and_allocate, _build_steps, generate_path,
      adjust_for_delay, _locate_current_step,
      _infer_current_week, _find_step_by_week

常量：MIN_STAGE_WEEKS, LEVEL_TO_STAGE, STAGE_ORDER
"""

import re as _re
from datetime import datetime

from .domains import DOMAIN_REGISTRY, RESOURCE_MAP, CHECKPOINTS

MIN_STAGE_WEEKS = 3   # 低于此值不展开该阶段

LEVEL_TO_STAGE = {"零基础": "入门", "初级": "入门", "中级": "进阶", "高级": "高级"}
STAGE_ORDER    = ["入门", "进阶", "高级"]


# ─────────────────────────────────────────────────────────────────────────────
# 输入解析工具
# ─────────────────────────────────────────────────────────────────────────────

def parse_float(s: str, default: float) -> float:
    """宽松解析数字字符串，支持整数和浮点数。"""
    try:
        v = float(s.strip())
        return v if v > 0 else default
    except (ValueError, AttributeError):
        return default


def parse_int(s: str, default: int) -> int:
    """宽松解析整数字符串，支持浮点输入（取整）。"""
    return max(1, int(parse_float(s, float(default))))


# ─────────────────────────────────────────────────────────────────────────────
# 领域检测
# ─────────────────────────────────────────────────────────────────────────────

def detect_domain(goal: str) -> str:
    """
    基于 DOMAIN_REGISTRY 关键词匹配领域。
    排序规则（优先级从高到低）：
      1. 命中关键词数量（越多越优先）
      2. 领域 priority 字段（数字越大越优先，解决平局）
    无命中则返回「通用」。

    否定词过滤：「不想/不学/不做/不需要/不打算/不考虑/don't/not」
    前面的关键词不算命中，避免「我不想学Python」误识别为编程。
    """
    # 否定词模式：否定词 + 紧跟的一个词（不跨标点/空格/逗号）
    _NEG_PATTERN = _re.compile(
        r"(不想|不学|不做|不需要|不打算|不考虑|don'?t\s+want|not\s+(?:learn|study|do))"
        r"[\s的]?[^\s，,。！？!?]{0,8}",
        _re.IGNORECASE,
    )
    g = goal.lower()
    # 把否定片段替换为占位符，避免其中的关键词被命中
    masked = _NEG_PATTERN.sub("__NEG__", g)

    scores: dict = {}   # domain -> (hit_count, priority)
    for domain, info in DOMAIN_REGISTRY.items():
        if domain == "通用":
            continue
        hit = sum(1 for kw in info["keywords"] if kw in masked)
        if hit > 0:
            scores[domain] = (hit, info.get("priority", 0))
    if not scores:
        return "通用"
    return max(scores, key=lambda d: scores[d])


# ─────────────────────────────────────────────────────────────────────────────
# 路径生成：拆分为独立子函数
# ─────────────────────────────────────────────────────────────────────────────

def _select_and_allocate(start_stage: str, total_weeks: int,
                          tmpl_weeks: dict) -> dict:
    """
    一次性决定展开哪些阶段、各分配多少周，保证分配总和严格等于 total_weeks。

    算法：
      1. 从 start_stage 开始，贪心地加入阶段，直到剩余预算不足 MIN_STAGE_WEEKS。
         至少保留 1 个阶段。
      2. 按模板比例分配周数，尾阶段吸收舍入误差，前段每阶段至少 1 周。
    """
    all_candidates = STAGE_ORDER[STAGE_ORDER.index(start_stage):]
    total_tmpl_all = sum(tmpl_weeks[s] for s in all_candidates)

    # 步骤1：决定展开哪些阶段
    active: list = []
    budget = total_weeks
    for s in all_candidates:
        est = max(1, round(total_weeks * tmpl_weeks[s] / total_tmpl_all))
        if budget >= MIN_STAGE_WEEKS or not active:   # 至少保留第一个
            active.append(s)
            budget -= est
            if budget < MIN_STAGE_WEEKS:
                break
    if not active:
        active = [all_candidates[0]]

    # 步骤2：按比例精确分配，总和严格等于 total_weeks
    total_tmpl = sum(tmpl_weeks[s] for s in active)
    alloc: dict = {}
    leftover = total_weeks

    for s in active[:-1]:
        remaining_after = len(active) - len(alloc) - 1   # 后续还剩几个阶段
        w = max(1, round(total_weeks * tmpl_weeks[s] / total_tmpl))
        w = min(w, leftover - remaining_after)            # 给后续留足 1 周/阶段
        alloc[s] = max(1, w)
        leftover -= alloc[s]

    alloc[active[-1]] = max(1, leftover)   # 尾阶段吸收误差
    return alloc


def _build_steps(stage_name: str, alloc_weeks: int, hours_per_week: int,
                 template_steps: list, week_cursor: int) -> tuple:
    """
    将模板步骤精确压缩/扩展到 alloc_weeks 内，步骤总周数严格等于 alloc_weeks。

    当 alloc_weeks < 步骤数时，将步骤合并到 alloc_weeks 个桶中，每桶至少 1 周。
    返回 (steps_list, alloc_weeks)。
    """
    total_tmpl_w = sum(s["weeks"] for s in template_steps)

    # 若步骤数超过可用周数，合并多余步骤（末尾步骤合并）
    effective = list(template_steps)
    while len(effective) > alloc_weeks:
        last = effective.pop()
        prev = effective[-1]
        merged_milestone = f"{prev['milestone'][:20]}… / {last['milestone'][:20]}…"
        effective[-1] = {
            "name":      prev["name"] + " & " + last["name"],
            "weeks":     prev["weeks"] + last["weeks"],
            "milestone": merged_milestone,
        }

    n = len(effective)
    leftover = alloc_weeks
    steps = []

    for i, tmpl in enumerate(effective):
        remaining_steps = n - i - 1
        if i < n - 1:
            w = max(1, round(alloc_weeks * tmpl["weeks"] / total_tmpl_w))
            w = min(w, leftover - remaining_steps)   # 给后续每步留 ≥1 周
            w = max(1, w)
        else:
            w = max(1, leftover)                     # 尾步骤吸收误差

        used_so_far = alloc_weeks - leftover
        s_week = week_cursor + used_so_far + 1
        e_week = s_week + w - 1
        steps.append({
            "step":        len(steps) + 1,
            "name":        tmpl["name"],
            "weeks":       w,
            "week_range":  f"第 {s_week}~{e_week} 周",
            "hours_total": w * hours_per_week,
            "milestone":   tmpl["milestone"],
            "resources":   RESOURCE_MAP[stage_name],
            "checkpoints": CHECKPOINTS[stage_name],
        })
        leftover -= w

    return steps, alloc_weeks


def generate_path(goal: str, level: str, hours_per_week: int, total_weeks: int) -> dict:
    """生成个性化学习路径（主入口）。"""
    domain      = detect_domain(goal)
    stages_tmpl = DOMAIN_REGISTRY[domain]["stages"]
    start_stage = LEVEL_TO_STAGE.get(level, "入门")

    tmpl_weeks  = {s: sum(st["weeks"] for st in stages_tmpl[s]) for s in STAGE_ORDER}
    stage_alloc = _select_and_allocate(start_stage, total_weeks, tmpl_weeks)
    active_stages = list(stage_alloc.keys())

    path_stages, week_cursor = [], 0
    for stage_name in active_stages:
        steps, stage_used = _build_steps(
            stage_name, stage_alloc[stage_name],
            hours_per_week, stages_tmpl[stage_name], week_cursor
        )
        week_cursor += stage_used
        path_stages.append({"stage": stage_name, "weeks": stage_used, "steps": steps})

    return {
        "goal": goal, "domain": domain, "level": level,
        "hours_per_week": hours_per_week, "total_weeks": total_weeks,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "stages": path_stages,
    }


def adjust_for_delay(delay_weeks: int) -> list:
    """根据落后周数给出动态调整建议。"""
    if delay_weeks <= 1:
        return [
            "⚡ 本周增加 20% 学习时间，优先完成里程碑任务",
            "✂️  暂时跳过「扩展阅读」内容，只做核心练习",
        ]
    if delay_weeks <= 3:
        return [
            "🔄 重新评估目标期限，适当延长 2~3 周",
            "📉 降低当前阶段深度要求，以「够用」为标准推进",
            "⏰ 把每天学习时间分散成 2~3 个 25 分钟番茄钟",
            "🤝 找学习伙伴，互相问责打卡",
        ]
    return [
        "🔁 建议重新规划整体路径，重新设定里程碑",
        "🎯 重新确认学习目标是否仍然有效",
        "📊 分析落后原因：时间不足？难度过高？动力不足？",
        "✅ 从最近一个完成的里程碑重新出发，小步快跑",
    ]


# ─────────────────────────────────────────────────────────────────────────────
# 进度定位辅助函数
# ─────────────────────────────────────────────────────────────────────────────

def _find_step_by_week(path: dict, week: int) -> tuple:
    """根据当前周，返回 (全局步骤编号, step_info dict) 或 (None, None)。"""
    idx = 0
    for stage in path["stages"]:
        for step in stage["steps"]:
            idx += 1
            wr = step.get("week_range", "")
            try:
                nums = [int(n) for n in wr.replace("第","").replace("周","").replace(" ","").split("~")]
                start_w = nums[0]
                end_w   = nums[-1]
                if start_w <= week <= end_w:
                    return idx, {"stage": stage["stage"], "name": step["name"]}
            except (ValueError, IndexError):
                pass
    return None, None


def _locate_current_step(path: dict, current_week: int) -> str:
    """根据当前第几周，返回定位文本。"""
    for stage in path.get("stages", []):
        for step in stage.get("steps", []):
            parts = step["week_range"].replace("第", "").replace("周", "").split("~")
            s, e = int(parts[0].strip()), int(parts[1].strip())
            if s <= current_week <= e:
                return (f"📍 你现在在：[{stage['stage']}阶段] "
                        f"Step {step['step']} - {step['name']}（{step['week_range']}）")
    total = sum(st["weeks"] for st in path.get("stages", []))
    if current_week > total:
        return f"🎉 恭喜！你已完成全部 {total} 周计划！"
    return f"📍 第 {current_week} 周（计划共 {total} 周）"


def _infer_current_week(path: dict):
    """从 my_path.json 的生成时间推算当前第几周（基于自然日）。"""
    generated_at = path.get("generated_at", "")
    if not generated_at:
        return None
    try:
        start = datetime.strptime(generated_at[:10], "%Y-%m-%d")
        elapsed_days = (datetime.now() - start).days
        week = max(1, elapsed_days // 7 + 1)
        return min(week, path["total_weeks"])
    except (ValueError, KeyError):
        return None
