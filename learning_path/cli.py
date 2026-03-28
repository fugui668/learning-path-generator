"""
cli.py — 命令行交互入口模块

提供：interactive_mode, track_mode, add_log_entry, show_log,
      demo_mode, add_domain, list_domains, main()
"""

import json
import os
import sys
from datetime import datetime

from .core import (
    generate_path, adjust_for_delay,
    _locate_current_step, _infer_current_week, _find_step_by_week,
    parse_float, parse_int,
)
from .domains import DOMAIN_REGISTRY, DOMAINS_FILE
from .log import load_log, save_log, PATH_FILE
from .render import print_path, show_chart, export_pdf
from ._version import __version__

LOG_DISPLAY_LIMIT = 20  # --show-log 展示条数


# ─────────────────────────────────────────────────────────────────────────────
# 交互式生成
# ─────────────────────────────────────────────────────────────────────────────

def interactive_mode() -> None:
    print("\n" + "═" * 60)
    print("  🤖 个性化学习路径生成器 v" + __version__)
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

    save_ans = input("  💾 是否保存路径？(y/n，默认 y)\n> ").strip().lower()
    if save_ans != "n":
        with open(PATH_FILE, "w", encoding="utf-8") as f:
            json.dump(path, f, ensure_ascii=False, indent=2)
        print(f"  💾 路径已保存至：{PATH_FILE}\n")


# ─────────────────────────────────────────────────────────────────────────────
# 进度追踪
# ─────────────────────────────────────────────────────────────────────────────

def track_mode() -> None:
    if not os.path.exists(PATH_FILE):
        print("❌ 未找到已保存的学习路径，请先运行交互式模式生成路径。")
        return
    with open(PATH_FILE, encoding="utf-8") as f:
        path = json.load(f)
    print(f"\n📂 已加载学习路径：{path['goal']}")
    print(f"   生成日期：{path.get('generated_at', '未知')[:10]}  |  计划总周数：{path['total_weeks']} 周")

    inferred = _infer_current_week(path)
    if inferred:
        print(f"\n🗓  根据生成日期自动推算：当前约第 {inferred} 周")
        ans = input("   是否使用此推算值？(y/n，默认 y)\n> ").strip().lower()
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


# ─────────────────────────────────────────────────────────────────────────────
# 学习日志
# ─────────────────────────────────────────────────────────────────────────────

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

    step_global, step_map = 0, {}
    for stage in path["stages"]:
        for step in stage["steps"]:
            step_global += 1
            step_map[step_global] = {"stage": stage["stage"], "name": step["name"]}

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
# Demo 模式
# ─────────────────────────────────────────────────────────────────────────────

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
# 领域管理
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
    priority = 6

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
    print("  💡 新增领域：python3 -m learning_path --add-domain")
    print("  💡 手动编辑：直接修改 domains.json\n")


# ─────────────────────────────────────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
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


if __name__ == "__main__":
    main()
