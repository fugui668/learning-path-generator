"""
app.py — Flask Web 界面主程序

路由：
  GET  /           首页（输入生成参数）
  POST /generate   生成学习路径 → 保存 my_path.json → 重定向 /path
  GET  /path       路径详情页
  GET  /progress   进度追踪 + 打卡
  POST /log        保存打卡记录
  GET  /chart      学习进度图表
  GET  /export     导出 PDF

启动：python3 web/app.py  或  python3 -m learning_path --web
"""

import json
import os
import sys
from datetime import datetime, date

# ── 确保能 import learning_path ────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import (Flask, render_template, request, redirect,
                   url_for, flash, send_file)

from learning_path.core import (
    generate_path, _infer_current_week, _locate_current_step,
    _find_step_by_week,
)
from learning_path.log import load_log, save_log, PATH_FILE
from learning_path.render import export_pdf as _export_pdf
from learning_path._version import __version__

# ── Flask 应用 ─────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__,
            template_folder=os.path.join(BASE_DIR, "templates"),
            static_folder=os.path.join(BASE_DIR, "static"))
app.secret_key = "learning-path-secret-2024"


# ── 辅助函数 ───────────────────────────────────────────────────────────────

def _load_path():
    """读取 my_path.json，不存在返回 None。"""
    if os.path.exists(PATH_FILE):
        try:
            with open(PATH_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None
    return None


def _save_path(path: dict):
    with open(PATH_FILE, "w", encoding="utf-8") as f:
        json.dump(path, f, ensure_ascii=False, indent=2)


# ── 路由 ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """首页：输入学习目标 + 参数。"""
    path_exists = os.path.exists(PATH_FILE)
    return render_template("index.html",
                           version=__version__,
                           path_exists=path_exists)


@app.route("/generate", methods=["POST"])
def generate():
    """接收表单 → 生成路径 → 保存 → 跳转 /path。"""
    goal           = request.form.get("goal", "").strip() or "学习编程"
    level          = request.form.get("level", "零基础")
    hours_per_week = int(request.form.get("hours_per_week", 10))
    total_weeks    = int(request.form.get("total_weeks", 12))

    # 参数范围保护
    hours_per_week = max(1, min(hours_per_week, 100))
    total_weeks    = max(1, min(total_weeks, 104))

    path = generate_path(goal, level, hours_per_week, total_weeks)
    _save_path(path)
    flash("学习路径已生成并保存 🎉", "success")
    return redirect(url_for("path_detail"))


@app.route("/path")
def path_detail():
    """路径详情页。"""
    path = _load_path()
    if path is None:
        flash("暂无学习路径，请先在首页生成路径。", "warning")
        return redirect(url_for("index"))

    # 为每个 step 附加全局序号
    step_global = 0
    for stage in path["stages"]:
        for step in stage["steps"]:
            step_global += 1
            step["_index"] = step_global

    return render_template("path.html", path=path, version=__version__)


@app.route("/progress")
def progress():
    """进度追踪 + 打卡页。"""
    path = _load_path()
    if path is None:
        flash("暂无学习路径，请先生成路径。", "warning")
        return redirect(url_for("index"))

    # 推算当前周 & 步骤
    current_week = _infer_current_week(path) or 1
    step_info_text = _locate_current_step(path, current_week)

    # 当前步骤详细信息（供模板使用）
    step_idx, step_detail = _find_step_by_week(path, current_week)

    # 最近5条日志
    entries = load_log()
    recent = entries[-5:][::-1]  # 最新在前

    return render_template("progress.html",
                           path=path,
                           current_week=current_week,
                           step_info_text=step_info_text,
                           step_detail=step_detail,
                           recent=recent,
                           today=date.today().isoformat(),
                           version=__version__)


@app.route("/log", methods=["POST"])
def log_entry():
    """接收打卡表单 → 追加到 learning_log.json。"""
    path = _load_path()
    if path is None:
        flash("未找到学习路径，请先生成路径。", "warning")
        return redirect(url_for("index"))

    hours         = float(request.form.get("hours", 0) or 0)
    milestone_done = request.form.get("milestone_done") == "on"
    note          = request.form.get("note", "").strip()
    date_str      = datetime.now().strftime("%Y-%m-%d")

    # 当前步骤
    current_week = _infer_current_week(path) or 1
    step_idx, step_detail = _find_step_by_week(path, current_week)
    stage_name = step_detail["stage"] if step_detail else "未知"
    step_name  = step_detail["name"]  if step_detail else "自由学习"

    entries = load_log()
    entries.append({
        "date": date_str,
        "hours": hours,
        "stage": stage_name,
        "step": step_name,
        "milestone_done": milestone_done,
        "note": note,
    })
    save_log(entries)
    flash(f"已记录 {date_str} 的学习打卡（{hours}h）✅", "success")
    return redirect(url_for("progress"))


@app.route("/chart")
def chart():
    """图表页：Chart.js 渲染学习数据。"""
    entries = load_log()

    # 最近14天的每日学习时长
    from collections import defaultdict
    daily_map = defaultdict(float)
    for e in entries:
        daily_map[e["date"]] += e.get("hours", 0)

    # 生成最近14天日期列表（包含无记录的日期填0）
    from datetime import timedelta
    today = date.today()
    days_14 = [(today - timedelta(days=i)).isoformat() for i in range(13, -1, -1)]
    daily_labels = days_14
    daily_values = [round(daily_map.get(d, 0), 2) for d in days_14]

    # 累计进度（按日累加总学习时长 / 计划总时长）
    path = _load_path()
    total_plan = (path["total_weeks"] * path["hours_per_week"]) if path else 0

    cumulative_labels = []
    cumulative_values = []
    if entries and total_plan > 0:
        sorted_entries = sorted(entries, key=lambda e: e["date"])
        cum = 0.0
        seen_dates = {}
        for e in sorted_entries:
            cum += e.get("hours", 0)
            seen_dates[e["date"]] = round(min(100, cum / total_plan * 100), 1)
        cumulative_labels = list(seen_dates.keys())
        cumulative_values = list(seen_dates.values())

    return render_template("chart.html",
                           daily_labels=json.dumps(daily_labels),
                           daily_values=json.dumps(daily_values),
                           cumulative_labels=json.dumps(cumulative_labels),
                           cumulative_values=json.dumps(cumulative_values),
                           total_entries=len(entries),
                           total_hours=round(sum(e.get("hours", 0) for e in entries), 1),
                           version=__version__)


@app.route("/export")
def export():
    """导出 PDF / TXT。"""
    # 调用 render.export_pdf()（它会直接写文件并打印）
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        _export_pdf()

    # 查找生成的文件
    project_dir = os.path.dirname(PATH_FILE)
    pdf_path = os.path.join(project_dir, "learning_path_report.pdf")
    txt_path = os.path.join(project_dir, "learning_path_report.txt")

    if os.path.exists(pdf_path):
        return send_file(pdf_path,
                         as_attachment=True,
                         download_name="learning_path_report.pdf",
                         mimetype="application/pdf")
    elif os.path.exists(txt_path):
        return send_file(txt_path,
                         as_attachment=True,
                         download_name="learning_path_report.txt",
                         mimetype="text/plain")
    else:
        flash("导出失败，请先生成学习路径。", "danger")
        return redirect(url_for("path_detail"))


# ── 启动 ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n🌐 学习路径生成器 Web 界面 v" + __version__)
    print("   访问：http://localhost:5000")
    print("   按 Ctrl+C 停止\n")
    app.run(debug=True, host="0.0.0.0", port=5000)
