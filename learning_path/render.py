"""
render.py — 输出渲染模块

提供：print_path, show_chart, export_pdf, _find_cn_font
"""

import os
import sys

from .log import load_log, PATH_FILE


def print_path(path: dict) -> None:
    """格式化打印学习路径。"""
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
            print("\n  📦 推荐资源类型：")
            for r in step["resources"]:
                print(f"     {r}")
            print("\n  ✅ 掌握度检验：")
            for c in step["checkpoints"]:
                print(f"     • {c}")
    print("\n" + "─" * 60)
    print("  💡 动态调整原则：")
    print("     • 落后 1 周：加密度，跳扩展，专注核心")
    print("     • 落后 3 周：重新规划里程碑，降低深度要求")
    print("     • 落后 5 周+：重评目标，从最近完成点重启")
    print("═" * 60 + "\n")


def show_chart() -> None:
    """打印美化版 ASCII 进度图表（带 ANSI 颜色 + 分级色块）。"""
    if not os.path.exists(PATH_FILE):
        print("❌ 未找到学习路径，请先生成路径。")
        return
    import json
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

    _USE_COLOR = sys.stdout.isatty()

    def _c(code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text

    def GREEN(t):  return _c("32", t)
    def YELLOW(t): return _c("33", t)
    def CYAN(t):   return _c("36", t)
    def BOLD(t):   return _c("1",  t)
    def DIM(t):    return _c("2",  t)

    def bar(pct_val: int, width: int = 30, color_fn=GREEN) -> str:
        filled = int(width * pct_val / 100)
        empty  = width - filled
        if pct_val >= 80:
            block = "█"
        elif pct_val >= 50:
            block = "▓"
        else:
            block = "▒"
        return color_fn(block * filled) + DIM("░" * empty)

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


def _find_cn_font() -> str:
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
    import json
    with open(PATH_FILE, encoding="utf-8") as f:
        path = json.load(f)

    # PDF 输出目录：PATH_FILE 的父目录（项目根）
    out_dir = os.path.dirname(PATH_FILE)

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import (SimpleDocTemplate, Paragraph,
                                        Spacer, Table, TableStyle)
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        pdf_path = os.path.join(out_dir, "learning_path_report.pdf")

        cn_font   = "Helvetica"
        font_path = _find_cn_font()
        if font_path:
            try:
                pdfmetrics.registerFont(TTFont("CNFont", font_path))
                cn_font = "CNFont"
            except Exception:
                pass

        _cn2py = None
        if cn_font == "Helvetica":
            try:
                from pypinyin import lazy_pinyin, Style
                def _make_cn2py():
                    def _fn(text: str) -> str:
                        return " ".join(lazy_pinyin(text, style=Style.TONE))
                    return _fn
                _cn2py = _make_cn2py()
            except ImportError:
                pass

        def _safe(text: str) -> str:
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
        txt_path = os.path.join(out_dir, "learning_path_report.txt")
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
        print("   安装 PDF 支持：pip install reportlab\n")
