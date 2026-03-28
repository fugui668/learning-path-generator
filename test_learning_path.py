"""
单元测试：test_learning_path.py

覆盖：
  - 输入解析（parse_float / parse_int）
  - 领域检测（detect_domain）
  - 路径生成边界情况（极短周数、极长周数、各起始等级）
  - 阶段收缩逻辑（MIN_STAGE_WEEKS）
  - 日志读写（load_log / save_log）
  - 动态调整建议（adjust_for_delay）
"""

import json
import os
import sys
import tempfile
import unittest

# 确保能 import 同目录的主模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import learning_path as lp


# ─────────────────────────────────────────────────────────────────────────────
# 输入解析
# ─────────────────────────────────────────────────────────────────────────────

class TestParseFloat(unittest.TestCase):
    def test_integer_string(self):
        self.assertEqual(lp.parse_float("10", 5.0), 10.0)

    def test_float_string(self):
        self.assertAlmostEqual(lp.parse_float("7.5", 5.0), 7.5)

    def test_invalid_returns_default(self):
        self.assertEqual(lp.parse_float("abc", 5.0), 5.0)

    def test_empty_returns_default(self):
        self.assertEqual(lp.parse_float("", 5.0), 5.0)

    def test_zero_returns_default(self):
        self.assertEqual(lp.parse_float("0", 5.0), 5.0)

    def test_negative_returns_default(self):
        self.assertEqual(lp.parse_float("-3", 5.0), 5.0)


class TestParseInt(unittest.TestCase):
    def test_integer_string(self):
        self.assertEqual(lp.parse_int("12", 10), 12)

    def test_float_string_truncates(self):
        # 7.5 -> int(7.5) = 7
        self.assertEqual(lp.parse_int("7.5", 10), 7)

    def test_invalid_returns_default(self):
        self.assertEqual(lp.parse_int("xyz", 10), 10)

    def test_minimum_is_1(self):
        # parse_int always returns at least 1
        self.assertGreaterEqual(lp.parse_int("0.1", 1), 1)


# ─────────────────────────────────────────────────────────────────────────────
# 领域检测
# ─────────────────────────────────────────────────────────────────────────────

class TestDetectDomain(unittest.TestCase):
    def test_programming(self):
        self.assertEqual(lp.detect_domain("学 Python 编程写代码"), "编程")

    def test_data_analysis(self):
        self.assertEqual(lp.detect_domain("深入学习机器学习，参加 Kaggle"), "数据分析")

    def test_english(self):
        self.assertEqual(lp.detect_domain("备考雅思 7 分"), "英语")

    def test_chinese(self):
        self.assertEqual(lp.detect_domain("学汉语备考 HSK"), "中文")

    def test_spanish(self):
        self.assertEqual(lp.detect_domain("零基础学西班牙语目标 DELE"), "西班牙语")

    def test_design(self):
        self.assertEqual(lp.detect_domain("学习 Figma 做 UI 设计"), "设计")

    def test_product(self):
        self.assertEqual(lp.detect_domain("成为产品经理，写好 PRD"), "产品")

    def test_writing(self):
        self.assertEqual(lp.detect_domain("提升写作水平，开写作博客"), "写作")

    def test_unknown_falls_back_to_general(self):
        self.assertEqual(lp.detect_domain("学习烹饪"), "通用")

    def test_case_insensitive(self):
        # 关键词全大写也能匹配
        self.assertEqual(lp.detect_domain("PYTHON 编程"), "编程")

    def test_most_keywords_wins(self):
        # 命中数多的领域胜出：数据分析 3 次 vs 编程 0 次
        self.assertEqual(lp.detect_domain("数据分析 机器学习 kaggle"), "数据分析")

    def test_priority_breaks_tie(self):
        # 「写Python代码做数据分析」：
        # 编程命中 python/代码 (2次 priority=5)
        # 数据分析命中 数据分析/做数据 (2次 priority=8) → priority 决胜
        self.assertEqual(lp.detect_domain("写Python代码做数据分析"), "数据分析")

    def test_pure_programming_not_hijacked(self):
        # 纯编程目标（不含数据分析关键词）仍应识别为编程
        self.assertEqual(lp.detect_domain("学Python编程写后端服务"), "编程")

    def test_negation_filter_chinese(self):
        # 「不想学Python」应过滤掉 python，转而识别实际目标
        self.assertEqual(lp.detect_domain("我不想学Python，想做UI设计"), "设计")
        self.assertEqual(lp.detect_domain("不想学编程，想备考雅思"), "英语")
        self.assertEqual(lp.detect_domain("不打算考雅思，想学西班牙语"), "西班牙语")
        # 否定词不应贪心吃掉后续句子（「不考虑写作」不能把「产品经理」也遮掉）
        self.assertEqual(lp.detect_domain("不考虑写作，专注产品经理"), "产品")

    def test_negation_filter_english(self):
        # 英文否定词也应过滤
        self.assertEqual(
            lp.detect_domain("don't want to learn python, focus on design"), "设计"
        )

    def test_negation_does_not_affect_affirmed_keywords(self):
        # 没有否定词时正常识别
        self.assertEqual(lp.detect_domain("学Python编程写后端"), "编程")
        self.assertEqual(lp.detect_domain("备考雅思7分"), "英语")


# ─────────────────────────────────────────────────────────────────────────────
# 路径生成
# ─────────────────────────────────────────────────────────────────────────────

class TestGeneratePath(unittest.TestCase):

    def _gen(self, goal="学 Python", level="零基础", hours=10, weeks=16):
        return lp.generate_path(goal, level, hours, weeks)

    def test_returns_required_keys(self):
        path = self._gen()
        for key in ("goal", "domain", "level", "hours_per_week", "total_weeks",
                    "generated_at", "stages"):
            self.assertIn(key, path)

    def test_total_weeks_matches_plan(self):
        """所有阶段 weeks 之和应等于 total_weeks。"""
        path = self._gen(weeks=16)
        actual = sum(s["weeks"] for s in path["stages"])
        self.assertEqual(actual, 16)

    def test_week_ranges_contiguous(self):
        """步骤的 week_range 应连续不重叠。"""
        path = self._gen(weeks=16)
        prev_end = 0
        for stage in path["stages"]:
            for step in stage["steps"]:
                rng = step["week_range"]  # e.g. "第 1~3 周"
                parts = rng.replace("第", "").replace("周", "").split("~")
                start, end = int(parts[0].strip()), int(parts[1].strip())
                self.assertEqual(start, prev_end + 1, f"周次不连续：{rng}")
                prev_end = end

    def test_very_short_weeks_only_one_stage(self):
        """极短周数（= MIN_STAGE_WEEKS）应只展开一个阶段。"""
        path = lp.generate_path("学 Python", "零基础", 10, lp.MIN_STAGE_WEEKS)
        self.assertEqual(len(path["stages"]), 1)
        self.assertEqual(path["stages"][0]["stage"], "入门")

    def test_short_weeks_stages_feasible(self):
        """6 周时展开的阶段数应 ≥1，且总周数严格等于 6。"""
        path = lp.generate_path("学 Python 编程", "零基础", 10, 6)
        self.assertGreaterEqual(len(path["stages"]), 1)
        self.assertEqual(sum(s["weeks"] for s in path["stages"]), 6)

    def test_long_weeks_all_stages(self):
        """充足周数（24 周）应展开全三阶段。"""
        path = lp.generate_path("学 Python", "零基础", 10, 24)
        self.assertEqual(len(path["stages"]), 3)

    def test_intermediate_start_skips_beginner(self):
        """中级起始应跳过入门阶段。"""
        path = lp.generate_path("学 Python", "中级", 10, 12)
        stage_names = [s["stage"] for s in path["stages"]]
        self.assertNotIn("入门", stage_names)
        self.assertIn("进阶", stage_names)

    def test_advanced_start_only_advanced(self):
        """高级起始，周数较短时只展开高级阶段。"""
        path = lp.generate_path("学 Python", "高级", 10, lp.MIN_STAGE_WEEKS)
        self.assertEqual(len(path["stages"]), 1)
        self.assertEqual(path["stages"][0]["stage"], "高级")

    def test_all_domains_generate_successfully(self):
        """所有注册领域都能生成完整路径，不抛异常。"""
        goals = {
            "编程": "学 Python",
            "数据分析": "机器学习 kaggle",
            "英语": "备考雅思",
            "中文": "学汉语 HSK",
            "西班牙语": "学西班牙语 DELE",
            "设计": "学 Figma UI 设计",
            "产品": "成为产品经理 PRD",
            "写作": "提升写作水平博客",
            "通用": "学习烹饪",
        }
        for domain, goal in goals.items():
            with self.subTest(domain=domain):
                path = lp.generate_path(goal, "零基础", 8, 12)
                self.assertEqual(path["domain"], domain)
                self.assertGreater(len(path["stages"]), 0)

    def test_hours_total_per_step_correct(self):
        """每步骤 hours_total = weeks * hours_per_week。"""
        path = lp.generate_path("学 Python", "零基础", 7, 12)
        for stage in path["stages"]:
            for step in stage["steps"]:
                self.assertEqual(step["hours_total"], step["weeks"] * 7)

    def test_step_numbers_sequential(self):
        """Step 编号应从 1 开始在阶段内连续递增。"""
        path = lp.generate_path("学 Python", "零基础", 10, 16)
        for stage in path["stages"]:
            for i, step in enumerate(stage["steps"], 1):
                self.assertEqual(step["step"], i)


# ─────────────────────────────────────────────────────────────────────────────
# 100 组参数化压测
# ─────────────────────────────────────────────────────────────────────────────

class TestGeneratePathStress(unittest.TestCase):
    """
    100 组随机参数压测，覆盖多领域 × 多等级 × 宽周数/小时数范围。
    每组断言：
      1. 阶段周数之和严格等于 total_weeks
      2. 步骤 week_range 连续不重叠
      3. 每步骤 hours_total = weeks × hours_per_week
      4. 每阶段至少 1 个步骤
      5. 生成不抛异常
    """

    # 固定 seed 保证可复现
    _SEED  = 2026
    _COUNT = 100

    _GOALS = [
        "学Python编程写后端服务",
        "用python做数据可视化",
        "备考雅思7分",
        "机器学习kaggle竞赛",
        "学汉语备考HSK",
        "零基础学西班牙语DELE",
        "学Figma做UI设计",
        "成为产品经理写PRD",
        "提升写作博客创作能力",
        "学烹饪",                  # 通用兜底
        "深度学习PyTorch项目",
        "英文写作雅思",
        "数据分析pandas sklearn",
    ]
    _LEVELS = ["零基础", "初级", "中级", "高级"]

    @classmethod
    def _gen_cases(cls):
        import random
        rng = random.Random(cls._SEED)
        return [
            (
                rng.choice(cls._GOALS),
                rng.choice(cls._LEVELS),
                rng.randint(3, 20),    # hours_per_week
                rng.randint(1, 60),    # total_weeks（含极端1周）
            )
            for _ in range(cls._COUNT)
        ]

    def _check_path(self, goal, level, hours, weeks):
        path = lp.generate_path(goal, level, hours, weeks)

        # 1. 周数精确
        actual_weeks = sum(s["weeks"] for s in path["stages"])
        self.assertEqual(
            actual_weeks, weeks,
            f"周数不符: plan={weeks} actual={actual_weeks} | {goal} {level} {hours}h"
        )

        # 2. 周次连续
        prev_end = 0
        for stage in path["stages"]:
            for step in stage["steps"]:
                parts = step["week_range"].replace("第", "").replace("周", "").split("~")
                start, end = int(parts[0].strip()), int(parts[1].strip())
                self.assertEqual(
                    start, prev_end + 1,
                    f"周次不连续: {step['week_range']} (prev_end={prev_end}) | {goal} {level} {weeks}w"
                )
                self.assertEqual(
                    end, start + step["weeks"] - 1,
                    f"week_range 与 weeks 不符: {step['week_range']} weeks={step['weeks']}"
                )
                prev_end = end

        # 3. hours_total 正确
        for stage in path["stages"]:
            for step in stage["steps"]:
                self.assertEqual(
                    step["hours_total"], step["weeks"] * hours,
                    f"hours_total 错: {step['name']} {step['hours_total']} != {step['weeks'] * hours}"
                )

        # 4. 每阶段步骤非空
        for stage in path["stages"]:
            self.assertGreater(
                len(stage["steps"]), 0,
                f"空 steps: 阶段={stage['stage']} | {goal} {level} {weeks}w"
            )

    def test_stress_100_cases(self):
        """100 组随机参数压测，全部断言通过。"""
        for goal, level, hours, weeks in self._gen_cases():
            with self.subTest(goal=goal, level=level, hours=hours, weeks=weeks):
                self._check_path(goal, level, hours, weeks)


# ─────────────────────────────────────────────────────────────────────────────
# 动态调整建议
# ─────────────────────────────────────────────────────────────────────────────

class TestAdjustForDelay(unittest.TestCase):
    def test_no_delay_is_not_called(self):
        # delay=0 逻辑在调用方处理，adjust_for_delay 不需要处理 0
        # 但传入 0 应返回 1 周以内的建议
        result = lp.adjust_for_delay(0)
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_small_delay(self):
        result = lp.adjust_for_delay(1)
        self.assertTrue(any("加密度" in s or "加 20%" in s for s in result))

    def test_medium_delay(self):
        result = lp.adjust_for_delay(2)
        self.assertTrue(any("延长" in s or "重新评估" in s for s in result))

    def test_large_delay(self):
        result = lp.adjust_for_delay(10)
        self.assertTrue(any("重新规划" in s for s in result))


# ─────────────────────────────────────────────────────────────────────────────
# 学习日志读写
# ─────────────────────────────────────────────────────────────────────────────

class TestLogIO(unittest.TestCase):
    def setUp(self):
        # 用临时文件替换全局 LOG_FILE
        self._tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self._tmp.close()
        self._orig_log = lp.LOG_FILE
        lp.LOG_FILE = self._tmp.name

    def tearDown(self):
        lp.LOG_FILE = self._orig_log
        if os.path.exists(self._tmp.name):
            os.unlink(self._tmp.name)

    def test_empty_log_returns_list(self):
        os.unlink(lp.LOG_FILE)   # 删除文件模拟首次使用
        result = lp.load_log()
        self.assertEqual(result, [])

    def test_save_and_load_roundtrip(self):
        entries = [
            {"date": "2026-03-28", "hours": 2.5, "stage": "入门",
             "step": "环境搭建", "milestone_done": True, "note": "顺利"},
            {"date": "2026-03-29", "hours": 1.0, "stage": "进阶",
             "step": "算法", "milestone_done": False, "note": ""},
        ]
        lp.save_log(entries)
        loaded = lp.load_log()
        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded[0]["hours"], 2.5)
        self.assertTrue(loaded[0]["milestone_done"])
        self.assertEqual(loaded[1]["stage"], "进阶")

    def test_append_preserves_existing(self):
        initial = [{"date": "2026-03-27", "hours": 1.0, "stage": "入门",
                    "step": "语法", "milestone_done": False, "note": ""}]
        lp.save_log(initial)
        entries = lp.load_log()
        entries.append({"date": "2026-03-28", "hours": 2.0, "stage": "入门",
                        "step": "数据结构", "milestone_done": True, "note": ""})
        lp.save_log(entries)
        result = lp.load_log()
        self.assertEqual(len(result), 2)

    def test_log_file_is_valid_json(self):
        lp.save_log([{"date": "2026-03-28", "hours": 1.5}])
        with open(lp.LOG_FILE, encoding="utf-8") as f:
            data = json.load(f)
        self.assertIsInstance(data, list)


# ─────────────────────────────────────────────────────────────────────────────
# 领域注册表完整性
# ─────────────────────────────────────────────────────────────────────────────

class TestDomainRegistry(unittest.TestCase):
    def test_all_domains_have_three_stages(self):
        for domain, info in lp.DOMAIN_REGISTRY.items():
            with self.subTest(domain=domain):
                for stage in ["入门", "进阶", "高级"]:
                    self.assertIn(stage, info["stages"],
                                  f"{domain} 缺少 {stage} 阶段")

    def test_all_stages_have_steps(self):
        for domain, info in lp.DOMAIN_REGISTRY.items():
            for stage, steps in info["stages"].items():
                with self.subTest(domain=domain, stage=stage):
                    self.assertGreater(len(steps), 0)

    def test_all_steps_have_required_fields(self):
        for domain, info in lp.DOMAIN_REGISTRY.items():
            for stage, steps in info["stages"].items():
                for step in steps:
                    with self.subTest(domain=domain, stage=stage, step=step["name"]):
                        self.assertIn("name",      step)
                        self.assertIn("weeks",     step)
                        self.assertIn("milestone", step)
                        self.assertGreater(step["weeks"], 0)


# ─────────────────────────────────────────────────────────────────────────────
# _locate_current_step 单元测试
# ─────────────────────────────────────────────────────────────────────────────

class TestInferCurrentWeek(unittest.TestCase):
    """覆盖 _infer_current_week 的各类边界情况。"""

    def _make_path(self, generated_at: str, total_weeks: int = 20) -> dict:
        return {"generated_at": generated_at, "total_weeks": total_weeks, "stages": []}

    def test_today_is_week_one(self):
        today = lp.datetime.now().strftime("%Y-%m-%d")
        result = lp._infer_current_week(self._make_path(today))
        self.assertEqual(result, 1)

    def test_seven_days_later_is_week_two(self):
        from datetime import timedelta
        d = (lp.datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        result = lp._infer_current_week(self._make_path(d))
        self.assertEqual(result, 2)

    def test_does_not_exceed_total_weeks(self):
        from datetime import timedelta
        # 300天前，但总周数只有4，不能超过4
        d = (lp.datetime.now() - timedelta(days=300)).strftime("%Y-%m-%d")
        result = lp._infer_current_week(self._make_path(d, total_weeks=4))
        self.assertEqual(result, 4)

    def test_missing_generated_at_returns_none(self):
        self.assertIsNone(lp._infer_current_week({"total_weeks": 10, "stages": []}))

    def test_bad_date_returns_none(self):
        self.assertIsNone(lp._infer_current_week(self._make_path("not-a-date")))


class TestFindStepByWeek(unittest.TestCase):
    """覆盖 _find_step_by_week 的定位逻辑。"""

    def setUp(self):
        self._path = lp.generate_path("备考雅思7分", "初级", 8, 20)

    def test_week_1_returns_step_1(self):
        idx, info = lp._find_step_by_week(self._path, 1)
        self.assertEqual(idx, 1)
        self.assertIsNotNone(info)

    def test_beyond_total_weeks_returns_none(self):
        idx, info = lp._find_step_by_week(self._path, 999)
        self.assertIsNone(idx)

    def test_returns_correct_stage_name(self):
        # 第1周应该是入门阶段
        _, info = lp._find_step_by_week(self._path, 1)
        self.assertEqual(info["stage"], "入门")

    def test_all_weeks_in_path_are_located(self):
        total = self._path["total_weeks"]
        for w in range(1, total + 1):
            with self.subTest(week=w):
                idx, info = lp._find_step_by_week(self._path, w)
                self.assertIsNotNone(idx, f"第{w}周未能定位到任何步骤")


class TestLocateCurrentStep(unittest.TestCase):
    """覆盖 _locate_current_step 的各类边界情况。"""

    def setUp(self):
        # 固定路径：英语 初级 8h/20周 → 入门+进阶+高级三段
        self._path = lp.generate_path("备考雅思7分", "初级", 8, 20)
        self._total = sum(s["weeks"] for s in self._path["stages"])

    def test_first_week_located(self):
        loc = lp._locate_current_step(self._path, 1)
        self.assertIn("📍", loc)
        self.assertIn("Step 1", loc)

    def test_last_week_located(self):
        loc = lp._locate_current_step(self._path, self._total)
        self.assertIn("📍", loc)

    def test_beyond_total_weeks_congratulation(self):
        loc = lp._locate_current_step(self._path, self._total + 1)
        self.assertIn("🎉", loc)
        self.assertIn(str(self._total), loc)

    def test_middle_week_shows_correct_stage(self):
        # 找第一个进阶步骤的开始周，验证识别为进阶阶段
        for stage in self._path["stages"]:
            if stage["stage"] == "进阶":
                first_step = stage["steps"][0]
                w = int(first_step["week_range"].replace("第","").replace("周","").split("~")[0].strip())
                loc = lp._locate_current_step(self._path, w)
                self.assertIn("进阶阶段", loc)
                break

    def test_all_weeks_return_non_empty_string(self):
        for w in range(1, self._total + 3):
            with self.subTest(week=w):
                loc = lp._locate_current_step(self._path, w)
                self.assertIsInstance(loc, str)
                self.assertGreater(len(loc), 0)

    def test_short_path_single_stage(self):
        # 极短路径（3周），只有一个阶段，第1周和第3周都应定位到
        p = lp.generate_path("学Python编程", "零基础", 10, 3)
        self.assertIn("📍", lp._locate_current_step(p, 1))
        self.assertIn("📍", lp._locate_current_step(p, 3))
        self.assertIn("🎉", lp._locate_current_step(p, 4))


if __name__ == "__main__":
    unittest.main(verbosity=2)
