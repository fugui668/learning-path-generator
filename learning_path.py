#!/usr/bin/env python3
"""
个性化学习路径生成器 v2.0
Personalized Learning Path Generator

使用方法:
  python3 learning_path.py            # 交互式生成
  python3 learning_path.py --demo     # 运行示例
  python3 learning_path.py --track    # 进度追踪 + 动态调整
  python3 learning_path.py --log      # 记录今日学习
  python3 learning_path.py --chart    # ASCII 进度图表
  python3 learning_path.py --export   # 导出 PDF 报告
"""

import json
import os
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PATH_FILE = os.path.join(BASE_DIR, "my_path.json")
LOG_FILE  = os.path.join(BASE_DIR, "learning_log.json")

# ─────────────────────────────────────────────
# 阶段模板库（9 个领域）
# ─────────────────────────────────────────────

STAGE_TEMPLATES = {
    "编程": {
        "入门": [
            {"name": "环境搭建与基础语法",   "weeks": 1, "milestone": "能写出 Hello World 并理解变量/循环/函数"},
            {"name": "数据结构基础",         "weeks": 2, "milestone": "掌握列表、字典、集合的使用"},
            {"name": "面向对象编程",         "weeks": 2, "milestone": "能独立设计简单类并实现继承"},
        ],
        "进阶": [
            {"name": "算法与数据结构",       "weeks": 3, "milestone": "能解决 LeetCode Easy 级别题目"},
            {"name": "框架与工程实践",       "weeks": 3, "milestone": "独立完成一个 CRUD Web 应用"},
            {"name": "综合项目实战",         "weeks": 2, "milestone": "上线一个完整项目并写 README"},
        ],
        "高级": [
            {"name": "系统设计基础",         "weeks": 3, "milestone": "能设计 10万 QPS 的简单系统"},
            {"name": "性能优化与源码阅读",   "weeks": 3, "milestone": "提交一个开源项目 PR"},
            {"name": "专项深耕（选方向）",   "weeks": 4, "milestone": "在选定方向产出技术博客或开源项目"},
        ],
    },
    "数据分析": {
        "入门": [
            {"name": "数据思维与 Excel 基础",  "weeks": 1, "milestone": "能用 Excel 完成数据透视表分析"},
            {"name": "Python 数据分析基础",    "weeks": 2, "milestone": "用 Pandas 完成一份数据清洗报告"},
            {"name": "数据可视化入门",         "weeks": 1, "milestone": "用 Matplotlib/Seaborn 绘制 5 种常见图表"},
        ],
        "进阶": [
            {"name": "统计学基础",             "weeks": 2, "milestone": "能做 A/B 测试并解读显著性"},
            {"name": "机器学习入门",           "weeks": 3, "milestone": "用 sklearn 完成分类/回归项目"},
            {"name": "业务分析实战",           "weeks": 2, "milestone": "完成一份完整的业务分析报告"},
        ],
        "高级": [
            {"name": "深度学习基础",           "weeks": 4, "milestone": "用 PyTorch 训练一个图像分类模型"},
            {"name": "大数据工具栈",           "weeks": 3, "milestone": "能独立搭建 Spark 数据处理流水线"},
            {"name": "数据产品设计",           "weeks": 3, "milestone": "输出完整数据产品方案文档"},
        ],
    },
    "英语": {
        "入门": [
            {"name": "音标与基础词汇（1000词）", "weeks": 2, "milestone": "能听懂慢速英语新闻标题"},
            {"name": "基础语法与短句",           "weeks": 2, "milestone": "能写出语法正确的5句话自我介绍"},
            {"name": "听力训练入门",             "weeks": 2, "milestone": "能听懂 VOA 慢速英语 60%"},
        ],
        "进阶": [
            {"name": "词汇扩展（3000词）与阅读", "weeks": 3, "milestone": "能独立阅读英文简版新闻"},
            {"name": "口语与写作训练",           "weeks": 3, "milestone": "能进行 5 分钟日常英语对话"},
            {"name": "听说综合强化",             "weeks": 2, "milestone": "能看懂 70% 的 TED 演讲"},
        ],
        "高级": [
            {"name": "学术/商务英语",           "weeks": 3, "milestone": "能写一篇 500 词英文邮件/报告"},
            {"name": "大量原版输入",             "weeks": 4, "milestone": "能无字幕看懂英美剧 80%"},
            {"name": "专项备考（IELTS/TOEFL）", "weeks": 3, "milestone": "模拟测试达到目标分数"},
        ],
    },
    "中文": {
        "入门": [
            {"name": "汉字基础与拼音（300字）", "weeks": 2, "milestone": "能认读 300 个常用汉字，掌握拼音拼写"},
            {"name": "基础词汇与简单对话",       "weeks": 2, "milestone": "能进行日常打招呼、购物等简单对话"},
            {"name": "基础语法与书写",           "weeks": 2, "milestone": "能写出 3~5 句语法正确的中文句子"},
        ],
        "进阶": [
            {"name": "词汇扩展（1500字）与阅读", "weeks": 3, "milestone": "能阅读简体中文新闻标题并理解大意"},
            {"name": "口语表达与听力训练",       "weeks": 3, "milestone": "能进行 5 分钟日常中文对话"},
            {"name": "写作与成语学习",           "weeks": 2, "milestone": "能写一篇 200 字的中文短文"},
        ],
        "高级": [
            {"name": "文言文与古典文学入门",     "weeks": 3, "milestone": "能理解常见文言文短句并翻译"},
            {"name": "书面语与正式写作",         "weeks": 3, "milestone": "能撰写正式中文邮件或报告"},
            {"name": "HSK 备考（目标 HSK5/6）", "weeks": 4, "milestone": "模拟测试达到目标分数"},
        ],
    },
    "西班牙语": {
        "入门": [
            {"name": "发音规则与基础词汇（500词）",      "weeks": 2, "milestone": "掌握西班牙语发音规则，能朗读简单句子"},
            {"name": "基础语法：名词性别、动词变位",     "weeks": 2, "milestone": "能用 ser/estar/tener 造句"},
            {"name": "日常对话入门",                     "weeks": 2, "milestone": "能进行问候、自我介绍等基础对话"},
        ],
        "进阶": [
            {"name": "词汇扩展（2000词）与阅读",         "weeks": 3, "milestone": "能阅读西语简版新闻并理解大意"},
            {"name": "口语与写作训练",                   "weeks": 3, "milestone": "能进行 5 分钟日常西语对话"},
            {"name": "听力强化与文化背景",               "weeks": 2, "milestone": "能听懂慢速西班牙语播客 70%"},
        ],
        "高级": [
            {"name": "虚拟语气与高级语法",               "weeks": 3, "milestone": "能正确使用虚拟语气表达愿望/假设"},
            {"name": "大量原版输入（剧集/书籍）",         "weeks": 4, "milestone": "能无字幕看懂西语剧 70%"},
            {"name": "DELE 备考（目标 B2/C1）",          "weeks": 3, "milestone": "模拟测试达到目标分数"},
        ],
    },
    "设计": {
        "入门": [
            {"name": "设计基础理论（色彩/排版/构图）", "weeks": 2, "milestone": "能分析一张海报的设计原则"},
            {"name": "工具入门（Figma/PS）",           "weeks": 2, "milestone": "独立完成一张名片或 Banner 设计"},
            {"name": "临摹与模仿练习",                 "weeks": 2, "milestone": "临摹 5 个优秀设计案例"},
        ],
        "进阶": [
            {"name": "UI/UX 设计原则",                 "weeks": 3, "milestone": "完成一个 App 的 3 个核心页面设计"},
            {"name": "设计系统与组件库",               "weeks": 2, "milestone": "搭建一套包含 20+ 组件的设计系统"},
            {"name": "交互原型与用户测试",             "weeks": 3, "milestone": "完成可点击原型并收集用户反馈"},
        ],
        "高级": [
            {"name": "品牌设计与视觉系统",             "weeks": 3, "milestone": "为一个虚拟品牌输出完整 VI 手册"},
            {"name": "动效设计与创意实验",             "weeks": 3, "milestone": "完成 3 个动效演示并发布 Dribbble"},
            {"name": "设计评审与作品集",               "weeks": 4, "milestone": "输出完整个人作品集网站"},
        ],
    },
    "产品": {
        "入门": [
            {"name": "产品思维与方法论",               "weeks": 2, "milestone": "能用 AARRR 分析一款产品"},
            {"name": "需求分析与用户研究",             "weeks": 2, "milestone": "完成一份 5 人用户访谈报告"},
            {"name": "原型设计基础",                   "weeks": 2, "milestone": "用 Figma 完成一个功能的低保真原型"},
        ],
        "进阶": [
            {"name": "数据分析与 A/B 测试",           "weeks": 3, "milestone": "设计并分析一个完整的 A/B 实验"},
            {"name": "产品规划与路线图",               "weeks": 2, "milestone": "输出一份完整的季度产品路线图"},
            {"name": "跨职能协作与 PRD 写作",         "weeks": 3, "milestone": "完成一份完整的 PRD 文档并通过评审"},
        ],
        "高级": [
            {"name": "增长策略与商业模式",             "weeks": 3, "milestone": "完成一份产品商业模式分析报告"},
            {"name": "0→1 产品规划",                  "weeks": 4, "milestone": "输出一份完整的新产品立项方案"},
            {"name": "产品领导力与团队管理",           "weeks": 3, "milestone": "主导一次完整的产品发布"},
        ],
    },
    "写作": {
        "入门": [
            {"name": "写作基础：结构与逻辑",           "weeks": 2, "milestone": "能写出结构清晰的 500 字文章"},
            {"name": "描写与叙述技巧",                 "weeks": 2, "milestone": "完成一篇有细节描写的 800 字短文"},
            {"name": "阅读积累与素材库建立",           "weeks": 2, "milestone": "建立包含 50 条素材的写作素材库"},
        ],
        "进阶": [
            {"name": "非虚构写作（评论/报道）",       "weeks": 3, "milestone": "完成一篇 1500 字深度评论文章"},
            {"name": "写作风格塑造",                   "weeks": 2, "milestone": "形成可辨识的个人写作风格"},
            {"name": "连续创作与反馈迭代",             "weeks": 3, "milestone": "连续发布 10 篇文章并收到有效反馈"},
        ],
        "高级": [
            {"name": "长篇写作策划与结构",             "weeks": 3, "milestone": "完成一本书或专栏的大纲与首章"},
            {"name": "写作变现与读者运营",             "weeks": 3, "milestone": "获得第一笔写作收入或 1000 名订阅者"},
            {"name": "出版与品牌建设",                 "weeks": 4, "milestone": "完成一部完整作品并提交出版社/平台"},
        ],
    },
    "通用": {
        "入门": [
            {"name": "基础概念学习", "weeks": 2, "milestone": "能用自己的话解释核心概念"},
            {"name": "基础技能练习", "weeks": 2, "milestone": "完成 5 个基础练习题/任务"},
            {"name": "小项目实践",   "weeks": 2, "milestone": "独立完成一个入门级作品"},
        ],
        "进阶": [
            {"name": "系统性深入学习", "weeks": 3, "milestone": "能解决中等难度问题"},
            {"name": "实战项目",       "weeks": 3, "milestone": "完成一个中等复杂度项目"},
            {"name": "查漏补缺",       "weeks": 2, "milestone": "通过综合测验"},
        ],
        "高级": [
            {"name": "高级技巧与最佳实践", "weeks": 3, "milestone": "能指导初学者"},
            {"name": "综合实战",           "weeks": 3, "milestone": "完成高质量综合项目"},
            {"name": "持续精进",           "weeks": 4, "milestone": "在社区分享成果"},
        ],
    },
}

RESOURCE_MAP = {
    "入门": [
        "📚 入门书籍（选 1 本经典教材，系统打基础）",
        "🎬 视频课程（B站/YouTube 免费课，适合碎片化学习）",
        "✏️  跟练习题（每学完一节立刻做题，巩固记忆）",
        "🤝 学习社群（加入同阶段群，互相打卡问答）",
    ],
    "进阶": [
        "📖 进阶书籍/文档（官方文档 + 1本深度书）",
        "🛠️  动手项目（边做边学，比看教程效果强 3 倍）",
        "🎯 专项练习平台（LeetCode/Kaggle/语言学习App）",
        "📝 技术博客（输出倒逼输入，写笔记加深理解）",
    ],
    "高级": [
        "🔬 论文/源码（读经典论文或优秀开源项目源码）",
        "🏆 竞赛/开源贡献（Kaggle 竞赛、GitHub PR）",
        "💬 技术分享（输出演讲/文章，建立个人影响力）",
        "👥 导师/同行交流（找领域大牛 1on1 或加入专业圈子）",
    ],
}

CHECKPOINTS = {
    "入门": [
        "概念自测：不看资料能否用自己的话解释本阶段核心概念？",
        "实操验证：完成配套练习题，正确率 ≥ 70%？",
        "小作品：完成阶段里程碑任务并能展示给他人？",
    ],
    "进阶": [
        "独立解题：遇到新问题是否能独立拆解并找到解法？",
        "项目复盘：项目中遇到最大的坑是什么？如何解决的？",
        "教学测试：能否向零基础朋友清晰讲解本阶段知识？",
    ],
    "高级": [
        "边界认知：清楚知道自己还不懂什么，有具体学习计划？",
        "社区贡献：输出了可被他人使用/参考的成果？",
        "实战验证：成果经过真实场景或他人检验？",
    ],
}

MIN_STAGE_WEEKS = 3  # 低于此值不展开该阶段


# ─────────────────────────────────────────────
# 核心生成逻辑
# ─────────────────────────────────────────────

def detect_domain(goal: str) -> str:
    g = goal.lower()
    if any(k in g for k in ["编程", "python", "java", "代码", "开发", "前端", "后端", "算法", "programming", "coding"]):
        return "编程"
    if any(k in g for k in ["数据", "分析", "机器学习", "ai", "统计", "data"]):
        return "数据分析"
    if any(k in g for k in ["英语", "english", "雅思", "托福", "ielts", "toefl"]):
        return "英语"
    if any(k in g for k in ["中文", "汉语", "普通话", "hsk", "chinese"]):
        return "中文"
    if any(k in g for k in ["西班牙语", "español", "spanish", "dele"]):
        return "西班牙语"
    if any(k in g for k in ["设计", "ui", "ux", "figma", "photoshop", "design", "排版", "视觉"]):
        return "设计"
    if any(k in g for k in ["产品", "product", "prd", "需求", "原型", "用户研究"]):
        return "产品"
    if any(k in g for k in ["写作", "writing", "文章", "创作", "小说", "博客"]):
        return "写作"
    return "通用"


def generate_path(goal: str, level: str, hours_per_week: int, total_weeks: int) -> dict:
    domain = detect_domain(goal)
    stages_template = STAGE_TEMPLATES.get(domain, STAGE_TEMPLATES["通用"])

    level_map = {"零基础": "入门", "初级": "入门", "中级": "进阶", "高级": "高级"}
    start_stage = level_map.get(level, "入门")
    stage_order = ["入门", "进阶", "高级"]
    start_idx = stage_order.index(start_stage)
    all_active = stage_order[start_idx:]

    # 按周数决定实际展开多少阶段（不足 MIN_STAGE_WEEKS 则不展开）
    active_stages = []
    remaining_budget = total_weeks
    total_tmpl_all = sum(
        sum(s["weeks"] for s in stages_template[ss]) for ss in all_active
    )
    for s in all_active:
        tmpl_w = sum(step["weeks"] for step in stages_template[s])
        est = max(MIN_STAGE_WEEKS, round(total_weeks * tmpl_w / total_tmpl_all))
        if remaining_budget >= MIN_STAGE_WEEKS:
            active_stages.append(s)
            remaining_budget -= est
        else:
            break
    if not active_stages:
        active_stages = [all_active[0]]

    # 按权重预分配周数
    tmpl_w_map = {s: sum(step["weeks"] for step in stages_template[s]) for s in active_stages}
    total_tmpl = sum(tmpl_w_map.values())
    stage_alloc = {}
    leftover = total_weeks
    for s in active_stages[:-1]:
        alloc = max(MIN_STAGE_WEEKS, round(total_weeks * tmpl_w_map[s] / total_tmpl))
        stage_alloc[s] = alloc
        leftover -= alloc
    stage_alloc[active_stages[-1]] = max(MIN_STAGE_WEEKS, leftover)

    path_stages = []
    week_cursor = 0
    for stage_name in active_stages:
        alloc_weeks = stage_alloc[stage_name]
        template_steps = stages_template[stage_name]
        total_stage_w = sum(s["weeks"] for s in template_steps)
        scale = max(0.5, min(alloc_weeks / total_stage_w, 2.0))

        steps = []
        stage_used = 0
        for i, step in enumerate(template_steps):
            adj = max(1, round(step["weeks"] * scale))
            if i == len(template_steps) - 1:
                adj = max(1, alloc_weeks - stage_used)
            s_week = week_cursor + stage_used + 1
            e_week = s_week + adj - 1
            steps.append({
                "step":        len(steps) + 1,
                "name":        step["name"],
                "weeks":       adj,
                "week_range":  f"第 {s_week}~{e_week} 周",
                "hours_total": adj * hours_per_week,
                "milestone":   step["milestone"],
                "resources":   RESOURCE_MAP[stage_name],
                "checkpoints": CHECKPOINTS[stage_name],
            })
            stage_used += adj

        week_cursor += stage_used
        path_stages.append({"stage": stage_name, "weeks": stage_used, "steps": steps})

    return {
        "goal": goal, "domain": domain, "level": level,
        "hours_per_week": hours_per_week, "total_weeks": total_weeks,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "stages": path_stages,
    }


def adjust_for_delay(delay_weeks: int) -> list:
    if delay_weeks <= 1:
        return [
            "⚡ 本周增加 20% 学习时间，优先完成里程碑任务",
            "✂️  暂时跳过「扩展阅读」内容，只做核心练习",
        ]
    elif delay_weeks <= 3:
        return [
            "🔄 重新评估目标期限，适当延长 2~3 周",
            "📉 降低当前阶段深度要求，以「够用」为标准推进",
            "⏰ 把每天学习时间分散成 2~3 个 25 分钟番茄钟",
            "🤝 找学习伙伴，互相问责打卡",
        ]
    else:
        return [
            "🔁 建议重新规划整体路径，重新设定里程碑",
            "🎯 重新确认学习目标是否仍然有效",
            "📊 分析落后原因：时间不足？难度过高？动力不足？",
            "✅ 从最近一个完成的里程碑重新出发，小步快跑",
        ]


# ─────────────────────────────────────────────
# 输出格式化
# ─────────────────────────────────────────────

def print_path(path: dict):
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


# ─────────────────────────────────────────────
# 学习日志（持久化）
# ─────────────────────────────────────────────

def load_log() -> list:
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, encoding="utf-8") as f:
            return json.load(f)
    return []


def save_log(entries: list):
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


def add_log_entry():
    """记录今日学习情况"""
    if not os.path.exists(PATH_FILE):
        print("❌ 未找到学习路径，请先生成路径。")
        return
    with open(PATH_FILE, encoding="utf-8") as f:
        path = json.load(f)

    print(f"\n📝 记录学习日志（目标：{path['goal']}）")
    date_str = datetime.now().strftime("%Y-%m-%d")

    hours_input = input("⏰ 今天学了多少小时？\n> ").strip()
    hours = float(hours_input) if hours_input.replace(".", "").isdigit() else 0.0

    print("\n📋 选择今天学习的步骤（输入编号）：")
    step_global = 0
    step_map = {}
    for stage in path["stages"]:
        for step in stage["steps"]:
            step_global += 1
            print(f"  {step_global}. [{stage['stage']}] {step['name']}")
            step_map[str(step_global)] = {"stage": stage["stage"], "name": step["name"]}
    step_choice = input("> ").strip()
    step_info = step_map.get(step_choice, {"stage": "未知", "name": "自由学习"})

    done = input("\n✅ 今天的里程碑完成了吗？(y/n)\n> ").strip().lower() == "y"
    note = input("\n📝 备注（可选，回车跳过）：\n> ").strip()

    entry = {
        "date":           date_str,
        "hours":          hours,
        "stage":          step_info["stage"],
        "step":           step_info["name"],
        "milestone_done": done,
        "note":           note,
    }
    entries = load_log()
    entries.append(entry)
    save_log(entries)
    print(f"\n✅ 已记录 {date_str} 的学习日志（{hours}h）\n")


def show_log():
    """查看历史学习日志"""
    entries = load_log()
    if not entries:
        print("\n📭 暂无学习日志，使用 --log 开始记录。\n")
        return
    print(f"\n📖 学习日志（共 {len(entries)} 条）")
    print("─" * 56)
    total_hours = 0.0
    for e in entries[-20:]:  # 最近 20 条
        milestone_tag = "✅" if e.get("milestone_done") else "  "
        print(f"  {e['date']}  {milestone_tag}  {e['hours']:4.1f}h  [{e['stage']}] {e['step']}")
        if e.get("note"):
            print(f"              💬 {e['note']}")
        total_hours += e.get("hours", 0)
    print("─" * 56)
    print(f"  总学习时长：{total_hours:.1f}h  |  已完成里程碑：{sum(1 for e in entries if e.get('milestone_done'))} 个\n")


# ─────────────────────────────────────────────
# ASCII 进度图表
# ─────────────────────────────────────────────

def show_chart():
    """打印 ASCII 进度图表"""
    if not os.path.exists(PATH_FILE):
        print("❌ 未找到学习路径，请先生成路径。")
        return

    with open(PATH_FILE, encoding="utf-8") as f:
        path = json.load(f)

    entries = load_log()
    total_plan_hours = path["total_weeks"] * path["hours_per_week"]
    actual_hours = sum(e.get("hours", 0) for e in entries)
    pct = min(100, int(actual_hours / total_plan_hours * 100)) if total_plan_hours > 0 else 0

    # 每日学习时长柱状图（最近 14 天）
    from collections import defaultdict
    daily = defaultdict(float)
    for e in entries:
        daily[e["date"]] += e.get("hours", 0)

    print(f"\n📊 学习进度概览")
    print("═" * 50)
    print(f"  目标：{path['goal']}")
    print(f"  计划总时长：{total_plan_hours}h  |  实际已学：{actual_hours:.1f}h")

    # 总进度条
    bar_len = 30
    filled = int(bar_len * pct / 100)
    bar = "█" * filled + "░" * (bar_len - filled)
    print(f"\n  总进度  [{bar}] {pct}%")

    # 各阶段进度
    print(f"\n  阶段分布：")
    stage_hours = defaultdict(float)
    for e in entries:
        stage_hours[e.get("stage", "未知")] += e.get("hours", 0)

    for stage in path["stages"]:
        sname = stage["stage"]
        plan_h = stage["weeks"] * path["hours_per_week"]
        actual_h = stage_hours.get(sname, 0)
        s_pct = min(100, int(actual_h / plan_h * 100)) if plan_h > 0 else 0
        s_filled = int(20 * s_pct / 100)
        s_bar = "█" * s_filled + "░" * (20 - s_filled)
        print(f"  {sname:6s}  [{s_bar}] {s_pct:3d}%  ({actual_h:.1f}/{plan_h}h)")

    # 最近 7 天每日柱状图
    if daily:
        print(f"\n  最近 7 天学习时长：")
        sorted_days = sorted(daily.keys())[-7:]
        max_h = max(daily[d] for d in sorted_days) or 1
        for d in sorted_days:
            h = daily[d]
            bar_w = int(h / max_h * 20)
            print(f"  {d[-5:]}  {'█' * bar_w:<20}  {h:.1f}h")

    # 里程碑完成统计
    total_milestones = sum(len(s["steps"]) for s in path["stages"])
    done_milestones = sum(1 for e in entries if e.get("milestone_done"))
    print(f"\n  里程碑：{done_milestones}/{total_milestones} 已完成")
    print("═" * 50 + "\n")


# ─────────────────────────────────────────────
# PDF 导出
# ─────────────────────────────────────────────

def export_pdf():
    """导出学习路径为 PDF（依赖 reportlab，无则降级为 txt）"""
    if not os.path.exists(PATH_FILE):
        print("❌ 未找到学习路径，请先生成路径。")
        return

    with open(PATH_FILE, encoding="utf-8") as f:
        path = json.load(f)

    # 尝试用 reportlab 生成 PDF
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        pdf_path = os.path.join(BASE_DIR, "learning_path_report.pdf")

        # 注册中文字体（优先找系统字体）
        font_candidates = [
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
        ]
        cn_font = "Helvetica"
        for fp in font_candidates:
            if os.path.exists(fp):
                try:
                    pdfmetrics.registerFont(TTFont("CNFont", fp))
                    cn_font = "CNFont"
                    break
                except Exception:
                    pass

        doc = SimpleDocTemplate(pdf_path, pagesize=A4,
                                leftMargin=20*mm, rightMargin=20*mm,
                                topMargin=20*mm, bottomMargin=20*mm)
        styles = getSampleStyleSheet()
        title_style   = ParagraphStyle("Title2",   fontName=cn_font, fontSize=18, spaceAfter=6,  textColor=colors.HexColor("#1a1a2e"))
        h2_style      = ParagraphStyle("H2",       fontName=cn_font, fontSize=13, spaceAfter=4,  textColor=colors.HexColor("#16213e"), spaceBefore=10)
        h3_style      = ParagraphStyle("H3",       fontName=cn_font, fontSize=11, spaceAfter=3,  textColor=colors.HexColor("#0f3460"), spaceBefore=6)
        body_style    = ParagraphStyle("Body",     fontName=cn_font, fontSize=9,  spaceAfter=2,  leading=14)
        caption_style = ParagraphStyle("Caption",  fontName=cn_font, fontSize=8,  textColor=colors.grey)

        story = []

        # 标题
        story.append(Paragraph("个性化学习路径报告", title_style))
        story.append(Spacer(1, 4*mm))

        # 基本信息表
        info_data = [
            ["学习目标", path["goal"]],
            ["当前水平", path["level"]],
            ["领域识别", path["domain"]],
            ["每周时间", f"{path['hours_per_week']} 小时"],
            ["计划周期", f"{path['total_weeks']} 周"],
            ["生成时间", path["generated_at"]],
        ]
        info_table = Table(info_data, colWidths=[35*mm, 130*mm])
        info_table.setStyle(TableStyle([
            ("FONTNAME",    (0,0), (-1,-1), cn_font),
            ("FONTSIZE",    (0,0), (-1,-1), 9),
            ("BACKGROUND",  (0,0), (0,-1), colors.HexColor("#e8f4f8")),
            ("TEXTCOLOR",   (0,0), (0,-1), colors.HexColor("#1a1a2e")),
            ("GRID",        (0,0), (-1,-1), 0.5, colors.grey),
            ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING",  (0,0), (-1,-1), 3),
            ("BOTTOMPADDING",(0,0),(-1,-1), 3),
        ]))
        story.append(info_table)
        story.append(Spacer(1, 6*mm))

        # 各阶段内容
        step_global = 0
        for stage in path["stages"]:
            story.append(Paragraph(f"【{stage['stage']}阶段】（约 {stage['weeks']} 周）", h2_style))
            for step in stage["steps"]:
                step_global += 1
                story.append(Paragraph(f"Step {step_global}：{step['name']}", h3_style))
                story.append(Paragraph(f"📅 {step['week_range']}  |  共 {step['hours_total']}h", caption_style))
                story.append(Paragraph(f"🏆 里程碑：{step['milestone']}", body_style))
                story.append(Spacer(1, 1*mm))

                res_text = "  推荐资源：" + "  /  ".join(r.split("（")[0] for r in step["resources"])
                story.append(Paragraph(res_text, caption_style))

                chk_text = "  掌握度检验：" + "；".join(c.split("：")[0] for c in step["checkpoints"])
                story.append(Paragraph(chk_text, caption_style))
                story.append(Spacer(1, 2*mm))

        # 动态调整原则
        story.append(Paragraph("动态调整原则", h2_style))
        for line in ["落后 1 周：加密度，跳扩展，专注核心",
                     "落后 3 周：重新规划里程碑，降低深度要求",
                     "落后 5 周+：重评目标，从最近完成点重启"]:
            story.append(Paragraph(f"• {line}", body_style))

        doc.build(story)
        print(f"\n✅ PDF 已导出：{pdf_path}\n")

    except ImportError:
        # 降级为 txt
        txt_path = os.path.join(BASE_DIR, "learning_path_report.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(f"个性化学习路径报告\n{'='*60}\n")
            f.write(f"目标：{path['goal']}\n")
            f.write(f"水平：{path['level']}  领域：{path['domain']}\n")
            f.write(f"每周：{path['hours_per_week']}h  周期：{path['total_weeks']}周\n")
            f.write(f"生成：{path['generated_at']}\n\n")
            step_global = 0
            for stage in path["stages"]:
                f.write(f"\n【{stage['stage']}阶段】（{stage['weeks']}周）\n")
                f.write("─"*50 + "\n")
                for step in stage["steps"]:
                    step_global += 1
                    f.write(f"\nStep {step_global}：{step['name']}\n")
                    f.write(f"  {step['week_range']}  共{step['hours_total']}h\n")
                    f.write(f"  里程碑：{step['milestone']}\n")
                    f.write(f"  资源：{'  /  '.join(r.split('（')[0] for r in step['resources'])}\n")
        print(f"\n⚠️  未安装 reportlab，已降级导出 TXT：{txt_path}")
        print(f"   安装 PDF 支持：pip install reportlab\n")


# ─────────────────────────────────────────────
# 交互式 & 模式入口
# ─────────────────────────────────────────────

def interactive_mode():
    print("\n" + "═" * 60)
    print("  🤖 个性化学习路径生成器 v2.0")
    print("═" * 60)

    goal = input("\n📌 你的学习目标是什么？\n   （例：学会 Python / 备考雅思 / 学西班牙语）\n> ").strip()
    if not goal:
        goal = "学习编程"

    print("\n📊 当前水平（选择数字）：")
    levels = ["零基础", "初级", "中级", "高级"]
    for i, l in enumerate(levels, 1):
        print(f"  {i}. {l}")
    level_input = input("> ").strip()
    if level_input.isdigit() and 1 <= int(level_input) <= 4:
        level = levels[int(level_input) - 1]
    else:
        print("  ⚠️  输入无效，默认使用「零基础」")
        level = "零基础"

    hours_input = input("\n⏰ 每周可用学习时间（小时，建议 5~20）：\n> ").strip()
    hours_per_week = int(hours_input) if hours_input.isdigit() else 10

    weeks_input = input("\n📅 期望完成周期（周数，建议 8~24）：\n> ").strip()
    total_weeks = int(weeks_input) if weeks_input.isdigit() else 12

    path = generate_path(goal, level, hours_per_week, total_weeks)
    print_path(path)

    with open(PATH_FILE, "w", encoding="utf-8") as f:
        json.dump(path, f, ensure_ascii=False, indent=2)
    print(f"  💾 路径已保存至：{PATH_FILE}\n")


def track_mode():
    if not os.path.exists(PATH_FILE):
        print("❌ 未找到已保存的学习路径，请先运行交互式模式生成路径。")
        return
    with open(PATH_FILE, encoding="utf-8") as f:
        path = json.load(f)
    print(f"\n📂 已加载学习路径：{path['goal']}")
    delay_input = input("⚠️  当前落后进度（周数，0 表示正常）：\n> ").strip()
    delay_weeks = int(delay_input) if delay_input.isdigit() else 0
    if delay_weeks == 0:
        print("\n✅ 进度正常，继续按计划推进，加油！")
    else:
        suggestions = adjust_for_delay(delay_weeks)
        print(f"\n📋 落后 {delay_weeks} 周，动态调整建议：")
        for s in suggestions:
            print(f"  {s}")
    print()


def demo_mode():
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
        path = generate_path(**demo)
        print_path(path)
        input("  按 Enter 查看下一个示例...")


# ─────────────────────────────────────────────
# 入口
# ─────────────────────────────────────────────

if __name__ == "__main__":
    args = sys.argv[1:]
    if "--demo" in args:
        demo_mode()
    elif "--track" in args:
        track_mode()
    elif "--log" in args:
        add_log_entry()
    elif "--show-log" in args:
        show_log()
    elif "--chart" in args:
        show_chart()
    elif "--export" in args:
        export_pdf()
    else:
        interactive_mode()
