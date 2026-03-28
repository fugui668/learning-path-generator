#!/usr/bin/env python3
"""
个性化学习路径生成器 v3.5
Personalized Learning Path Generator

使用方法:
  python3 learning_path.py            # 交互式生成
  python3 learning_path.py --demo     # 运行示例
  python3 learning_path.py --track    # 进度追踪 + 动态调整（自动推算当前周）
  python3 learning_path.py --log      # 记录今日学习（自动关联步骤）
  python3 learning_path.py --show-log # 查看历史学习日志
  python3 learning_path.py --chart    # ASCII 进度图表（ANSI 颜色）
  python3 learning_path.py --export   # 导出 PDF 报告
  python3 learning_path.py --list-domains  # 查看所有领域
  python3 learning_path.py --add-domain    # 新增自定义领域
  python3 learning_path.py --version       # 查看版本号
"""

__version__ = "3.5"

import json
import os
import sys
from datetime import datetime

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
PATH_FILE = os.path.join(BASE_DIR, "my_path.json")
LOG_FILE  = os.path.join(BASE_DIR, "learning_log.json")

MIN_STAGE_WEEKS = 3   # 低于此值不展开该阶段
LOG_DISPLAY_LIMIT = 20  # --show-log 展示条数


# ─────────────────────────────────────────────────────────────────────────────
# 领域注册表 — 从 domains.json 加载
# 结构：每个领域 = { "priority": int, "keywords": [...], "stages": { 入门/进阶/高级: [...] } }
# priority：关键词命中数相同时，priority 高的领域优先（数字越大越优先）。
# 新增领域：直接编辑 domains.json，或使用 --add-domain 命令，无需修改代码。
# ─────────────────────────────────────────────────────────────────────────────

DOMAINS_FILE = os.path.join(BASE_DIR, "domains.json")

def _load_domains() -> tuple[dict, dict, dict]:
    """从 domains.json 加载领域注册表、资源推荐表、掌握度检验表。"""
    if not os.path.exists(DOMAINS_FILE):
        print(f"❌ 找不到领域配置文件：{DOMAINS_FILE}")
        print("   请确保 domains.json 与 learning_path.py 在同一目录下。")
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
    import re as _re

    # 否定词模式：否定词 + 紧跟的一个词（不跨标点/空格/逗号）
    # 只遮掉 "不想学Python" 这一片，不贪心吃掉后续句子
    _NEG_PATTERN = _re.compile(
        r"(不想|不学|不做|不需要|不打算|不考虑|don'?t\s+want|not\s+(?:learn|study|do))"
        r"[\s的]?[^\s，,。！？!?]{0,8}",
        _re.IGNORECASE,
    )
    g = goal.lower()
    # 把否定片段替换为占位符，避免其中的关键词被命中
    masked = _NEG_PATTERN.sub("__NEG__", g)

    scores: dict[str, tuple[int, int]] = {}   # domain -> (hit_count, priority)
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
                          tmpl_weeks: dict) -> dict[str, int]:
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
    active: list[str] = []
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
    alloc: dict[str, int] = {}
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
                 template_steps: list, week_cursor: int) -> tuple[list, int]:
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
        # 名称保留两者，里程碑拼接摘要（各取前20字）
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
    domain     = detect_domain(goal)
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


def adjust_for_delay(delay_weeks: int) -> list[str]:
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
# 输出格式化
# ─────────────────────────────────────────────────────────────────────────────

def print_path(path: dict) -> None:
    print("\n" + "═" * 60)
    print(f"  🎯 学习目标：{path['goal']}")
    print(f"  📊 当前水平：{path['level']}  |  领域识别：{path['domain']}")
    print(f"  ⏰ 每周时间：{path['hours_per_week']}h  |  计划周期：{path['total_weeks']} 周")
    print(f"  🗓  生成时间：{path['generated_at']}")
    print("═" * 60)
    step_global = 0
    for stage in path["stages"]:
        print(f"\n【{stage['stage']}阶段】（约 {stage['weeks']} 周）")
        print("─" * 50)
        for step in stage["steps"]:
            step_global += 1
            print(f"\n  Step {step_global}：{step['name']}")
            print(f"  📅 {step['week_range']}  |  共 {step['hours_total']}h")
            print(f"  🏆 里程碑：{step['milestone']}")
            print(f"\n  📦 推荐资源类型：")
            for r in step["resources"]:
                print(f"     {r}")
            print(f"\n  ✅ 掌握度检验：")
            for c in step["checkpoints"]:
                print(f"     • {c}")
    print("\n" + "─" * 60)
    print("  💡 动态调整原则：")
    print("     • 落后 1 周：加密度，跳扩展，专注核心")
    print("     • 落后 3 周：重新规划里程碑，降低深度要求")
    print("     • 落后 5 周+：重评目标，从最近完成点重启")
    print("═" * 60 + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# 学习日志（持久化）
# ─────────────────────────────────────────────────────────────────────────────

def load_log() -> list:
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, encoding="utf-8") as f:
            return json.load(f)
    return []


def save_log(entries: list) -> None:
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


def _find_step_by_week(path: dict, week: int) -> tuple[int, dict] | tuple[None, None]:
    """根据当前周，返回 (全局步骤编号, step_info dict) 或 (None, None)。"""
    idx = 0
    for stage in path["stages"]:
        for step in stage["steps"]:
            idx += 1
            wr = step.get("week_range", "")
            # 解析 "第X周" 或 "第X~Y周"
            try:
                nums = [int(n) for n in wr.replace("第","").replace("周","").replace(" ","").split("~")]
                start_w = nums[0]
                end_w   = nums[-1]
                if start_w <= week <= end_w:
                    return idx, {"stage": stage["stage"], "name": step["name"]}
            except (ValueError, IndexError):
                pass
    return None, None


def add_log_entry() -> None:
    """记录今日学习情况（自动关联当前步骤）。"""
    if not os.path.exists(PATH_FILE):
        print("❌ 未找到学习路径，请先运行交互式模式生成路径。")
        return
    with open(PATH_FILE, encoding="utf-8") as f:
        path = json.load(f)

    print(f"\n📝 记录学习日志（目标：{path['goal']}）")
    date_str = datetime.now().strftime("%Y-%m-%d")

    hours = parse_float(input("⏰ 今天学了多少小时？（支持小数，如 1.5）\n> "), 0.0)

    # 构建步骤列表（编号 → info）
    step_global, step_map = 0, {}
    for stage in path["stages"]:
        for step in stage["steps"]:
            step_global += 1
            step_map[step_global] = {"stage": stage["stage"], "name": step["name"]}

    # 自动推算当前步骤
    inferred_week = _infer_current_week(path)
    auto_idx, auto_info = (None, None)
    if inferred_week:
        auto_idx, auto_info = _find_step_by_week(path, inferred_week)

    if auto_idx and auto_info:
        print(f"\n📋 根据当前周（第 {inferred_week} 周）自动匹配到步骤：")
        print(f"   [{auto_idx}] [{auto_info['stage']}] {auto_info['name']}")
        ans = input("   使用此步骤？(y/n，默认 y)\n> ").strip().lower()
        if ans == "n":
            auto_idx = None

    if not auto_idx:
        print("\n📋 选择今天学习的步骤（输入编号）：")
        for num, info in step_map.items():
            print(f"  {num}. [{info['stage']}] {info['name']}")
        chosen = parse_int(input("> ").strip(), 0)
        auto_info = step_map.get(chosen, {"stage": "未知", "name": "自由学习"})

    step_info = auto_info

    done = input("\n✅ 今天的里程碑完成了吗？(y/n)\n> ").strip().lower() == "y"
    note = input("\n📝 备注（可选，回车跳过）：\n> ").strip()

    entries = load_log()
    entries.append({
        "date": date_str, "hours": hours,
        "stage": step_info["stage"], "step": step_info["name"],
        "milestone_done": done, "note": note,
    })
    save_log(entries)
    print(f"\n✅ 已记录 {date_str} 的学习日志（{hours}h  [{step_info['stage']}] {step_info['name']}）\n")


def show_log() -> None:
    """查看历史学习日志。"""
    entries = load_log()
    if not entries:
        print("\n📭 暂无学习日志，使用 --log 开始记录。\n")
        return

    total = len(entries)
    shown = entries[-LOG_DISPLAY_LIMIT:]
    print(f"\n📖 学习日志（共 {total} 条，显示最近 {len(shown)} 条）")
    print("─" * 58)
    total_hours = 0.0
    for e in shown:
        tag = "✅" if e.get("milestone_done") else "  "
        print(f"  {e['date']}  {tag}  {e['hours']:4.1f}h  [{e['stage']}] {e['step']}")
        if e.get("note"):
            print(f"              💬 {e['note']}")
        total_hours += e.get("hours", 0)
    print("─" * 58)
    all_hours = sum(e.get("hours", 0) for e in entries)
    done_cnt  = sum(1 for e in entries if e.get("milestone_done"))
    print(f"  累计学习：{all_hours:.1f}h  |  已完成里程碑：{done_cnt} 个\n")


# ─────────────────────────────────────────────────────────────────────────────
# ASCII 进度图表
# ─────────────────────────────────────────────────────────────────────────────

def show_chart() -> None:
    """打印美化版 ASCII 进度图表（带 ANSI 颜色 + 分级色块）。"""
    if not os.path.exists(PATH_FILE):
        print("❌ 未找到学习路径，请先生成路径。")
        return
    with open(PATH_FILE, encoding="utf-8") as f:
        path = json.load(f)

    entries = load_log()
    from collections import defaultdict
    daily: dict = defaultdict(float)
    stage_hours: dict = defaultdict(float)
    for e in entries:
        daily[e["date"]] += e.get("hours", 0)
        stage_hours[e.get("stage", "未知")] += e.get("hours", 0)

    total_plan = path["total_weeks"] * path["hours_per_week"]
    actual_h   = sum(e.get("hours", 0) for e in entries)
    pct        = min(100, int(actual_h / total_plan * 100)) if total_plan > 0 else 0

    # ── ANSI 颜色（不支持时降级为空串）────────────────────────
    _USE_COLOR = sys.stdout.isatty()
    def _c(code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text
    GREEN  = lambda t: _c("32", t)
    YELLOW = lambda t: _c("33", t)
    CYAN   = lambda t: _c("36", t)
    BOLD   = lambda t: _c("1",  t)
    DIM    = lambda t: _c("2",  t)

    # ── 进度条（按百分比选色块密度）──────────────────────────
    def bar(pct_val: int, width: int = 30, color_fn=GREEN) -> str:
        filled = int(width * pct_val / 100)
        empty  = width - filled
        # 分级色块：>80% 实心，50~80% 3/4块，<50% 1/2块
        if pct_val >= 80:
            block = "█"
        elif pct_val >= 50:
            block = "▓"
        else:
            block = "▒"
        return color_fn(block * filled) + DIM("░" * empty)

    # ── 柱状图单行（8级高度）─────────────────────────────────
    def hbar(h: float, max_h: float, width: int = 24) -> str:
        w = int(h / max_h * width) if max_h > 0 else 0
        return CYAN("█" * w) + DIM("·" * (width - w))

    W = 56
    print()
    print(BOLD("  📊 学习进度概览"))
    print("  " + "═" * W)
    print(f"  {BOLD('目标')}：{path['goal']}")
    print(f"  {BOLD('领域')}：{path['domain']}  |  水平：{path['level']}")
    print(f"  {BOLD('计划')}：{total_plan}h 总计  |  {BOLD('实际')}：{YELLOW(f'{actual_h:.1f}h')}")
    print()
    print(f"  {BOLD('总进度')}  [{bar(pct)}] {YELLOW(str(pct) + '%')}")
    print()
    print(f"  {BOLD('阶段进度：')}")
    for stage in path["stages"]:
        sn     = stage["stage"]
        plan_h = stage["weeks"] * path["hours_per_week"]
        act_h  = stage_hours.get(sn, 0)
        sp     = min(100, int(act_h / plan_h * 100)) if plan_h > 0 else 0
        label  = f"{sn:3s}"
        ratio  = f"({act_h:.1f}/{plan_h}h)"
        print(f"  {label}  [{bar(sp, 20)}] {sp:3d}%  {DIM(ratio)}")

    if daily:
        print()
        print(f"  {BOLD('最近 7 天：')}")
        sorted_days = sorted(daily.keys())[-7:]
        max_h = max(daily[d] for d in sorted_days) or 1
        for d in sorted_days:
            h = daily[d]
            print(f"  {DIM(d[-5:])}  {hbar(h, max_h)}  {YELLOW(f'{h:.1f}h')}")

    total_ms = sum(len(s["steps"]) for s in path["stages"])
    done_ms  = sum(1 for e in entries if e.get("milestone_done"))
    ms_color = GREEN if done_ms == total_ms else YELLOW
    print()
    print(f"  {BOLD('里程碑')}：{ms_color(f'{done_ms}/{total_ms}')} 已完成"
          + (GREEN("  🎉 全部完成！") if done_ms == total_ms else ""))
    print("  " + "═" * W + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# PDF 导出
# ─────────────────────────────────────────────────────────────────────────────

def _find_cn_font() -> str | None:
    """查找系统中可用的中文字体，返回路径或 None。"""
    candidates = [
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/Windows/Fonts/simhei.ttf",
        "/Windows/Fonts/msyh.ttc",
    ]
    return next((p for p in candidates if os.path.exists(p)), None)


def export_pdf() -> None:
    """导出学习路径为 PDF；未安装 reportlab 时降级为 TXT。"""
    if not os.path.exists(PATH_FILE):
        print("❌ 未找到学习路径，请先生成路径。")
        return
    with open(PATH_FILE, encoding="utf-8") as f:
        path = json.load(f)

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        pdf_path = os.path.join(BASE_DIR, "learning_path_report.pdf")

        # 注册中文字体；找不到时尝试 pypinyin 转拼音兜底
        cn_font   = "Helvetica"
        _cn2py    = None    # 拼音转换函数，None 表示直接用原文
        font_path = _find_cn_font()
        if font_path:
            try:
                pdfmetrics.registerFont(TTFont("CNFont", font_path))
                cn_font = "CNFont"
            except Exception:
                pass   # 字体加载失败则尝试拼音兜底

        if cn_font == "Helvetica":
            # 没有中文字体 → 尝试 pypinyin 将中文转为带声调拼音
            try:
                from pypinyin import lazy_pinyin, Style
                def _cn2py(text: str) -> str:
                    return " ".join(lazy_pinyin(text, style=Style.TONE))
            except ImportError:
                # pypinyin 也没有 → 保留原文（中文字符显示为方框，但不崩溃）
                _cn2py = None

        def _safe(text: str) -> str:
            """若需要转拼音则转，否则直接返回原文。"""
            return _cn2py(text) if _cn2py else text

        def style(name, **kw):
            return ParagraphStyle(name, fontName=cn_font, **kw)

        title_s   = style("T",  fontSize=18, spaceAfter=6,  textColor=colors.HexColor("#1a1a2e"))
        h2_s      = style("H2", fontSize=13, spaceAfter=4,  textColor=colors.HexColor("#16213e"), spaceBefore=10)
        h3_s      = style("H3", fontSize=11, spaceAfter=3,  textColor=colors.HexColor("#0f3460"), spaceBefore=6)
        body_s    = style("B",  fontSize=9,  spaceAfter=2,  leading=14)
        caption_s = style("C",  fontSize=8,  textColor=colors.grey)

        doc   = SimpleDocTemplate(pdf_path, pagesize=A4,
                                  leftMargin=20*mm, rightMargin=20*mm,
                                  topMargin=20*mm, bottomMargin=20*mm)
        story = [Paragraph(_safe("个性化学习路径报告"), title_s), Spacer(1, 4*mm)]

        info_data = [
            [_safe("学习目标"), _safe(path["goal"])],
            [_safe("当前水平"), _safe(path["level"])],
            [_safe("领域识别"), _safe(path["domain"])],
            [_safe("每周时间"), f"{path['hours_per_week']} h"],
            [_safe("计划周期"), f"{path['total_weeks']} " + _safe("周")],
            [_safe("生成时间"), path["generated_at"]],
        ]
        t = Table(info_data, colWidths=[35*mm, 130*mm])
        t.setStyle(TableStyle([
            ("FONTNAME",      (0,0), (-1,-1), cn_font),
            ("FONTSIZE",      (0,0), (-1,-1), 9),
            ("BACKGROUND",    (0,0), (0,-1),  colors.HexColor("#e8f4f8")),
            ("GRID",          (0,0), (-1,-1), 0.5, colors.grey),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING",    (0,0), (-1,-1), 3),
            ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ]))
        story += [t, Spacer(1, 6*mm)]

        step_global = 0
        for stage in path["stages"]:
            story.append(Paragraph(
                _safe(f"【{stage['stage']}阶段】") + f"（{_safe('约')} {stage['weeks']} {_safe('周')}）", h2_s))
            for step in stage["steps"]:
                step_global += 1
                story.append(Paragraph(f"Step {step_global}：{_safe(step['name'])}", h3_s))
                story.append(Paragraph(f"{step['week_range']}  |  {step['hours_total']}h", caption_s))
                story.append(Paragraph(_safe(f"里程碑：{step['milestone']}"), body_s))
                res  = _safe("推荐：") + "  /  ".join(_safe(r.split("（")[0]) for r in step["resources"])
                chk  = _safe("检验：") + "；".join(_safe(c.split("：")[0]) for c in step["checkpoints"])
                story += [Paragraph(res, caption_s), Paragraph(chk, caption_s), Spacer(1, 2*mm)]

        story.append(Paragraph(_safe("动态调整原则"), h2_s))
        for line in ["落后 1 周：加密度，跳扩展，专注核心",
                     "落后 3 周：重新规划里程碑，降低深度要求",
                     "落后 5 周+：重评目标，从最近完成点重启"]:
            story.append(Paragraph(f"• {_safe(line)}", body_s))

        doc.build(story)
        print(f"\n✅ PDF 已导出：{pdf_path}\n")

    except ImportError:
        txt_path = os.path.join(BASE_DIR, "learning_path_report.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(f"个性化学习路径报告\n{'='*60}\n")
            f.write(f"目标：{path['goal']}\n水平：{path['level']}  领域：{path['domain']}\n")
            f.write(f"每周：{path['hours_per_week']}h  周期：{path['total_weeks']}周\n")
            f.write(f"生成：{path['generated_at']}\n\n")
            step_global = 0
            for stage in path["stages"]:
                f.write(f"\n【{stage['stage']}阶段】（{stage['weeks']}周）\n{'─'*50}\n")
                for step in stage["steps"]:
                    step_global += 1
                    f.write(f"\nStep {step_global}：{step['name']}\n")
                    f.write(f"  {step['week_range']}  共{step['hours_total']}h\n")
                    f.write(f"  里程碑：{step['milestone']}\n")
        print(f"\n⚠️  未安装 reportlab，已降级导出 TXT：{txt_path}")
        print(f"   安装 PDF 支持：pip install reportlab\n")


# ─────────────────────────────────────────────────────────────────────────────
# 交互式 & 各模式入口
# ─────────────────────────────────────────────────────────────────────────────

def interactive_mode() -> None:
    print("\n" + "═" * 60)
    print("  🤖 个性化学习路径生成器 v3.0")
    print("═" * 60)

    goal  = input("\n📌 你的学习目标是什么？\n   （例：学会 Python / 备考雅思 / 学西班牙语）\n> ").strip() or "学习编程"

    print("\n📊 当前水平（选择数字）：")
    levels = ["零基础", "初级", "中级", "高级"]
    for i, l in enumerate(levels, 1):
        print(f"  {i}. {l}")
    raw = input("> ").strip()
    level = levels[int(raw) - 1] if raw.isdigit() and 1 <= int(raw) <= 4 else "零基础"

    hours_per_week = parse_int(input("\n⏰ 每周可用学习时间（小时，支持小数，建议 5~20）：\n> "), 10)
    total_weeks    = parse_int(input("\n📅 期望完成周期（周数，建议 8~24）：\n> "), 12)

    path = generate_path(goal, level, hours_per_week, total_weeks)
    print_path(path)

    with open(PATH_FILE, "w", encoding="utf-8") as f:
        json.dump(path, f, ensure_ascii=False, indent=2)
    print(f"  💾 路径已保存至：{PATH_FILE}\n")


def _locate_current_step(path: dict, current_week: int) -> str:
    """根据当前第几周，返回「📍 你现在在：[阶段] StepN - 步骤名（第X~Y周）」定位文本。"""
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


def _infer_current_week(path: dict) -> int | None:
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


def track_mode() -> None:
    if not os.path.exists(PATH_FILE):
        print("❌ 未找到已保存的学习路径，请先运行交互式模式生成路径。")
        return
    with open(PATH_FILE, encoding="utf-8") as f:
        path = json.load(f)
    print(f"\n📂 已加载学习路径：{path['goal']}")
    print(f"   生成日期：{path.get('generated_at', '未知')[:10]}  |  计划总周数：{path['total_weeks']} 周")

    # 自动推算当前周
    inferred = _infer_current_week(path)
    if inferred:
        print(f"\n🗓  根据生成日期自动推算：当前约第 {inferred} 周")
        ans = input(f"   是否使用此推算值？(y/n，默认 y)\n> ").strip().lower()
        if ans == "n":
            current_week = parse_int(input("📅 请手动输入当前第几周：\n> "), 1)
        else:
            current_week = inferred
    else:
        current_week = parse_int(input("📅 你目前进行到第几周了？\n> "), 1)

    print(f"\n{_locate_current_step(path, current_week)}")

    delay_weeks = parse_int(input("\n⚠️  当前落后进度（周数，0 表示正常）：\n> "), 0)
    if delay_weeks == 0:
        print("\n✅ 进度正常，继续按计划推进，加油！")
    else:
        print(f"\n📋 落后 {delay_weeks} 周，动态调整建议：")
        for s in adjust_for_delay(delay_weeks):
            print(f"  {s}")
    print()


def demo_mode() -> None:
    demos = [
        {"goal": "零基础学 Python 编程，目标做数据分析", "level": "零基础", "hours_per_week": 10, "total_weeks": 16},
        {"goal": "提升英语口语，备考雅思 7 分",           "level": "初级",  "hours_per_week": 8,  "total_weeks": 20},
        {"goal": "深入学习机器学习，达到可参加 Kaggle 竞赛水平", "level": "中级", "hours_per_week": 15, "total_weeks": 12},
        {"goal": "零基础学西班牙语，目标 DELE B1",        "level": "零基础", "hours_per_week": 6,  "total_weeks": 24},
        {"goal": "学中文，备考 HSK 5 级",                 "level": "初级",  "hours_per_week": 8,  "total_weeks": 20},
    ]
    print("\n🎬 运行 5 个学习路径示例...\n")
    for i, demo in enumerate(demos, 1):
        print(f"\n{'▶' * 3} 示例 {i}：{demo['goal']}")
        print_path(generate_path(**demo))
        input("  按 Enter 查看下一个示例...")


# ─────────────────────────────────────────────────────────────────────────────
# 入口
# ─────────────────────────────────────────────────────────────────────────────

def add_domain() -> None:
    """交互式向 domains.json 新增一个自定义领域。"""
    print("\n➕ 新增自定义领域")
    print("─" * 40)
    name = input("领域名称（如：日语、摄影）：").strip()
    if not name:
        print("❌ 名称不能为空。")
        return
    if name in DOMAIN_REGISTRY:
        print(f"⚠️  领域「{name}」已存在，如需修改请直接编辑 domains.json。")
        return

    kw_raw   = input("关键词（逗号分隔，如：日语,japanese,jlpt,n1）：").strip()
    keywords = [k.strip().lower() for k in kw_raw.split(",") if k.strip()]
    priority = 6   # 默认优先级（中等）

    print("\n请依次输入入门 / 进阶 / 高级三个阶段的步骤（每步格式：步骤名|参考周数|里程碑）")
    print("每阶段至少 2 步，输入空行结束该阶段。")

    stages: dict = {}
    for stage in ["入门", "进阶", "高级"]:
        steps = []
        print(f"\n  [{stage}阶段]（至少 2 步）")
        while True:
            raw = input(f"    步骤 {len(steps)+1}（名称|周数|里程碑）或空行结束：").strip()
            if not raw:
                if len(steps) < 2:
                    print("    ⚠️  至少需要 2 步，请继续输入。")
                    continue
                break
            parts = [p.strip() for p in raw.split("|")]
            if len(parts) < 3:
                print("    格式错误，请用 | 分隔名称、周数、里程碑。")
                continue
            try:
                w = max(1, int(parts[1]))
            except ValueError:
                print("    周数必须是整数，已自动设为 2。")
                w = 2
            steps.append({"name": parts[0], "weeks": w, "milestone": parts[2]})
        stages[stage] = steps

    new_entry = {"priority": priority, "keywords": keywords, "stages": stages}

    # 写回 domains.json
    with open(DOMAINS_FILE, encoding="utf-8") as f:
        data = json.load(f)
    data["domain_registry"][name] = new_entry
    with open(DOMAINS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 已添加领域「{name}」到 domains.json，共 {len(data['domain_registry'])} 个领域。")
    print("   下次运行时即可自动识别该领域。")


def list_domains() -> None:
    """列出所有可用领域及关键词数量。"""
    print(f"\n📚 当前领域列表（共 {len(DOMAIN_REGISTRY)} 个，来源：domains.json）")
    print("─" * 52)
    for name, info in DOMAIN_REGISTRY.items():
        kw_count = len(info["keywords"])
        steps    = sum(len(s) for s in info["stages"].values())
        print(f"  {name:8s}  priority={info['priority']}  关键词 {kw_count:2d} 个  步骤模板 {steps} 条")
    print("─" * 52)
    print(f"  💡 新增领域：python3 learning_path.py --add-domain")
    print(f"  💡 手动编辑：直接修改 domains.json\n")


if __name__ == "__main__":
    args = sys.argv[1:]
    if   "--version"      in args: print(f"个性化学习路径生成器 v{__version__}")
    elif "--demo"         in args: demo_mode()
    elif "--track"        in args: track_mode()
    elif "--log"          in args: add_log_entry()
    elif "--show-log"     in args: show_log()
    elif "--chart"        in args: show_chart()
    elif "--export"       in args: export_pdf()
    elif "--add-domain"   in args: add_domain()
    elif "--list-domains" in args: list_domains()
    else: interactive_mode()
