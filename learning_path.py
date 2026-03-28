#!/usr/bin/env python3
"""
个性化学习路径生成器
Personalized Learning Path Generator

使用方法:
  python3 learning_path.py          # 交互式生成
  python3 learning_path.py --demo   # 运行3个示例
  python3 learning_path.py --track  # 进度追踪模式
"""

import json
import os
import sys
from datetime import datetime

# ─────────────────────────────────────────────
# 配置：阶段模板库
# ─────────────────────────────────────────────

STAGE_TEMPLATES = {
    "编程": {
        "入门": [
            {"name": "环境搭建与基础语法", "weeks": 1, "milestone": "能写出 Hello World 并理解变量/循环/函数"},
            {"name": "数据结构基础", "weeks": 2, "milestone": "掌握列表、字典、集合的使用"},
            {"name": "面向对象编程", "weeks": 2, "milestone": "能独立设计简单类并实现继承"},
        ],
        "进阶": [
            {"name": "算法与数据结构", "weeks": 3, "milestone": "能解决 LeetCode Easy 级别题目"},
            {"name": "框架与工程实践", "weeks": 3, "milestone": "独立完成一个 CRUD Web 应用"},
            {"name": "综合项目实战", "weeks": 2, "milestone": "上线一个完整项目并写 README"},
        ],
        "高级": [
            {"name": "系统设计基础", "weeks": 3, "milestone": "能设计 10万 QPS 的简单系统"},
            {"name": "性能优化与源码阅读", "weeks": 3, "milestone": "提交一个开源项目 PR"},
            {"name": "专项深耕（选方向）", "weeks": 4, "milestone": "在选定方向产出技术博客或开源项目"},
        ],
    },
    "数据分析": {
        "入门": [
            {"name": "数据思维与 Excel 基础", "weeks": 1, "milestone": "能用 Excel 完成数据透视表分析"},
            {"name": "Python 数据分析基础", "weeks": 2, "milestone": "用 Pandas 完成一份数据清洗报告"},
            {"name": "数据可视化入门", "weeks": 1, "milestone": "用 Matplotlib/Seaborn 绘制 5 种常见图表"},
        ],
        "进阶": [
            {"name": "统计学基础", "weeks": 2, "milestone": "能做 A/B 测试并解读显著性"},
            {"name": "机器学习入门", "weeks": 3, "milestone": "用 sklearn 完成分类/回归项目"},
            {"name": "业务分析实战", "weeks": 2, "milestone": "完成一份完整的业务分析报告"},
        ],
        "高级": [
            {"name": "深度学习基础", "weeks": 4, "milestone": "用 PyTorch 训练一个图像分类模型"},
            {"name": "大数据工具栈", "weeks": 3, "milestone": "能独立搭建 Spark 数据处理流水线"},
            {"name": "数据产品设计", "weeks": 3, "milestone": "输出完整数据产品方案文档"},
        ],
    },
    "英语": {
        "入门": [
            {"name": "音标与基础词汇（1000词）", "weeks": 2, "milestone": "能听懂慢速英语新闻标题"},
            {"name": "基础语法与短句", "weeks": 2, "milestone": "能写出语法正确的5句话自我介绍"},
            {"name": "听力训练入门", "weeks": 2, "milestone": "能听懂 VOA 慢速英语 60%"},
        ],
        "进阶": [
            {"name": "词汇扩展（3000词）与阅读", "weeks": 3, "milestone": "能独立阅读英文简版新闻"},
            {"name": "口语与写作训练", "weeks": 3, "milestone": "能进行 5 分钟日常英语对话"},
            {"name": "听说综合强化", "weeks": 2, "milestone": "能看懂 70% 的 TED 演讲"},
        ],
        "高级": [
            {"name": "学术/商务英语", "weeks": 3, "milestone": "能写一篇 500 词英文邮件/报告"},
            {"name": "大量原版输入", "weeks": 4, "milestone": "能无字幕看懂英美剧 80%"},
            {"name": "专项备考（如 IELTS/TOEFL）", "weeks": 3, "milestone": "模拟测试达到目标分数"},
        ],
    },
    "通用": {
        "入门": [
            {"name": "基础概念学习", "weeks": 2, "milestone": "能用自己的话解释核心概念"},
            {"name": "基础技能练习", "weeks": 2, "milestone": "完成 5 个基础练习题/任务"},
            {"name": "小项目实践", "weeks": 2, "milestone": "独立完成一个入门级作品"},
        ],
        "进阶": [
            {"name": "系统性深入学习", "weeks": 3, "milestone": "能解决中等难度问题"},
            {"name": "实战项目", "weeks": 3, "milestone": "完成一个中等复杂度项目"},
            {"name": "查漏补缺", "weeks": 2, "milestone": "通过综合测验"},
        ],
        "高级": [
            {"name": "高级技巧与最佳实践", "weeks": 3, "milestone": "能指导初学者"},
            {"name": "综合实战", "weeks": 3, "milestone": "完成高质量综合项目"},
            {"name": "持续精进", "weeks": 4, "milestone": "在社区分享成果"},
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


# ─────────────────────────────────────────────
# 核心生成逻辑
# ─────────────────────────────────────────────

def detect_domain(goal: str) -> str:
    """根据学习目标猜测领域"""
    goal_lower = goal.lower()
    if any(k in goal_lower for k in ["编程", "python", "java", "代码", "开发", "前端", "后端", "算法"]):
        return "编程"
    if any(k in goal_lower for k in ["数据", "分析", "机器学习", "ai", "统计"]):
        return "数据分析"
    if any(k in goal_lower for k in ["英语", "english", "雅思", "托福", "口语"]):
        return "英语"
    return "通用"


def generate_path(goal: str, level: str, hours_per_week: int, total_weeks: int) -> dict:
    """生成个性化学习路径"""
    domain = detect_domain(goal)
    stages_template = STAGE_TEMPLATES.get(domain, STAGE_TEMPLATES["通用"])
    
    # 根据当前水平决定从哪个阶段开始
    level_map = {"零基础": "入门", "初级": "入门", "中级": "进阶", "高级": "高级"}
    start_stage = level_map.get(level, "入门")
    stage_order = ["入门", "进阶", "高级"]
    start_idx = stage_order.index(start_stage)
    
    # 计算每阶段应分配的周数（按模板权重均匀分配）
    active_stages = stage_order[start_idx:]
    stage_template_weeks = {
        s: sum(step["weeks"] for step in stages_template[s])
        for s in active_stages
    }
    total_template_weeks = sum(stage_template_weeks.values())
    
    # 按权重预分配各阶段周数，确保每阶段至少 2 周
    stage_alloc = {}
    leftover = total_weeks
    for s in active_stages[:-1]:
        alloc = max(2, round(total_weeks * stage_template_weeks[s] / total_template_weeks))
        stage_alloc[s] = alloc
        leftover -= alloc
    stage_alloc[active_stages[-1]] = max(2, leftover)

    remaining_weeks = total_weeks
    path_stages = []
    week_cursor = 0  # 全局周数游标，用于显示正确的周次范围

    for stage_name in active_stages:
        if remaining_weeks <= 0:
            break

        alloc_weeks = stage_alloc[stage_name]
        template_steps = stages_template[stage_name]
        total_stage_weeks = sum(s["weeks"] for s in template_steps)

        # 按比例压缩/扩展本阶段步骤周数（限制在 0.5x~2x）
        scale = max(0.5, min(alloc_weeks / total_stage_weeks, 2.0))

        steps = []
        stage_weeks_used = 0
        for i, step in enumerate(template_steps):
            adjusted_weeks = max(1, round(step["weeks"] * scale))
            if i == len(template_steps) - 1:
                # 最后一步消耗本阶段剩余周数，防止累积误差
                adjusted_weeks = max(1, alloc_weeks - stage_weeks_used)

            start_week = week_cursor + stage_weeks_used + 1
            end_week = start_week + adjusted_weeks - 1
            steps.append({
                "step": len(steps) + 1,
                "name": step["name"],
                "weeks": adjusted_weeks,
                "week_range": f"第 {start_week}~{end_week} 周",
                "hours_total": adjusted_weeks * hours_per_week,
                "milestone": step["milestone"],
                "resources": RESOURCE_MAP[stage_name],
                "checkpoints": CHECKPOINTS[stage_name],
            })
            stage_weeks_used += adjusted_weeks

        week_cursor += stage_weeks_used
        path_stages.append({
            "stage": stage_name,
            "weeks": stage_weeks_used,
            "steps": steps,
        })
        remaining_weeks -= stage_weeks_used
    
    return {
        "goal": goal,
        "domain": domain,
        "level": level,
        "hours_per_week": hours_per_week,
        "total_weeks": total_weeks,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "stages": path_stages,
    }


def adjust_for_delay(path: dict, delay_weeks: int) -> list:
    """进度落后时的动态调整建议"""
    suggestions = []
    if delay_weeks <= 1:
        suggestions.append("⚡ 本周增加 20% 学习时间，优先完成里程碑任务")
        suggestions.append("✂️  暂时跳过「扩展阅读」内容，只做核心练习")
    elif delay_weeks <= 3:
        suggestions.append("🔄 重新评估目标期限，适当延长 2~3 周")
        suggestions.append("📉 降低当前阶段深度要求，以「够用」为标准推进")
        suggestions.append("⏰ 把每天学习时间分散成 2~3 个 25 分钟番茄钟")
        suggestions.append("🤝 找学习伙伴，互相问责打卡")
    else:
        suggestions.append("🔁 建议重新规划整体路径，重新设定里程碑")
        suggestions.append("🎯 重新确认学习目标是否仍然有效")
        suggestions.append("📊 分析落后原因：时间不足？难度过高？动力不足？")
        suggestions.append("✅ 从最近一个完成的里程碑重新出发，小步快跑")
    return suggestions


# ─────────────────────────────────────────────
# 输出格式化
# ─────────────────────────────────────────────

def print_path(path: dict):
    """打印学习路径"""
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
# 交互式界面
# ─────────────────────────────────────────────

def interactive_mode():
    """交互式信息收集"""
    print("\n" + "═" * 60)
    print("  🤖 个性化学习路径生成器")
    print("═" * 60)
    
    goal = input("\n📌 你的学习目标是什么？（例：学会 Python 数据分析）\n> ").strip()
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
    
    # 保存到当前目录
    save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "my_path.json")
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(path, f, ensure_ascii=False, indent=2)
    print(f"  💾 路径已保存至：{save_path}\n")


def track_mode():
    """进度追踪模式"""
    save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "my_path.json")
    if not os.path.exists(save_path):
        print("❌ 未找到已保存的学习路径，请先运行交互式模式生成路径。")
        return
    
    with open(save_path, encoding="utf-8") as f:
        path = json.load(f)
    
    print(f"\n📂 已加载学习路径：{path['goal']}")
    delay_input = input("⚠️  当前落后进度（周数，0 表示正常）：\n> ").strip()
    delay_weeks = int(delay_input) if delay_input.isdigit() else 0
    
    if delay_weeks == 0:
        print("\n✅ 进度正常，继续按计划推进，加油！")
    else:
        suggestions = adjust_for_delay(path, delay_weeks)
        print(f"\n📋 落后 {delay_weeks} 周，动态调整建议：")
        for s in suggestions:
            print(f"  {s}")
    print()


def demo_mode():
    """运行3个示例"""
    demos = [
        {
            "goal": "零基础学 Python 编程，目标做数据分析",
            "level": "零基础",
            "hours_per_week": 10,
            "total_weeks": 16,
        },
        {
            "goal": "提升英语口语，备考雅思 7 分",
            "level": "初级",
            "hours_per_week": 8,
            "total_weeks": 20,
        },
        {
            "goal": "深入学习机器学习，达到可参加 Kaggle 竞赛水平",
            "level": "中级",
            "hours_per_week": 15,
            "total_weeks": 12,
        },
    ]
    
    print("\n🎬 运行 3 个学习路径示例...\n")
    for i, demo in enumerate(demos, 1):
        print(f"\n{'▶' * 3} 示例 {i}：{demo['goal']}")
        path = generate_path(**demo)
        print_path(path)
        input("  按 Enter 查看下一个示例...")


# ─────────────────────────────────────────────
# 入口
# ─────────────────────────────────────────────

if __name__ == "__main__":
    if "--demo" in sys.argv:
        demo_mode()
    elif "--track" in sys.argv:
        track_mode()
    else:
        interactive_mode()
