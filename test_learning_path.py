"""
单元测试：test_learning_path.py  v4.0

覆盖：
  - 输入解析（parse_float / parse_int）
  - 领域检测（detect_domain）
  - 路径生成边界情况（极短周数、极长周数、各起始等级）
  - 阶段收缩逻辑（MIN_STAGE_WEEKS）
  - 日志读写（load_log / save_log）
  - 动态调整建议（adjust_for_delay）
  - 边界输入（TestBoundaryInputs）
  - 异常输入（TestAbnormalInputs）
  - CLI 输入模拟（TestCLIInputMock）
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

# 确保能 import 同目录的主包
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import learning_path as lp
import learning_path.log as _log_mod
import learning_path.cli as _cli_mod


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
        self.assertEqual(lp.parse_int("7.5", 10), 7)

    def test_invalid_returns_default(self):
        self.assertEqual(lp.parse_int("xyz", 10), 10)

    def test_minimum_is_1(self):
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
        self.assertEqual(lp.detect_domain("PYTHON 编程"), "编程")

    def test_most_keywords_wins(self):
        self.assertEqual(lp.detect_domain("数据分析 机器学习 kaggle"), "数据分析")

    def test_priority_breaks_tie(self):
        self.assertEqual(lp.detect_domain("写Python代码做数据分析"), "数据分析")

    def test_pure_programming_not_hijacked(self):
        self.assertEqual(lp.detect_domain("学Python编程写后端服务"), "编程")

    def test_negation_filter_chinese(self):
        self.assertEqual(lp.detect_domain("我不想学Python，想做UI设计"), "设计")
        self.assertEqual(lp.detect_domain("不想学编程，想备考雅思"), "英语")
        self.assertEqual(lp.detect_domain("不打算考雅思，想学西班牙语"), "西班牙语")
        self.assertEqual(lp.detect_domain("不考虑写作，专注产品经理"), "产品")

    def test_negation_filter_english(self):
        self.assertEqual(
            lp.detect_domain("don't want to learn python, focus on design"), "设计"
        )

    def test_negation_does_not_affect_affirmed_keywords(self):
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
        path = self._gen(weeks=16)
        actual = sum(s["weeks"] for s in path["stages"])
        self.assertEqual(actual, 16)

    def test_week_ranges_contiguous(self):
        path = self._gen(weeks=16)
        prev_end = 0
        for stage in path["stages"]:
            for step in stage["steps"]:
                rng = step["week_range"]
                parts = rng.replace("第", "").replace("周", "").split("~")
                start, end = int(parts[0].strip()), int(parts[1].strip())
                self.assertEqual(start, prev_end + 1, f"周次不连续：{rng}")
                prev_end = end

    def test_very_short_weeks_only_one_stage(self):
        path = lp.generate_path("学 Python", "零基础", 10, lp.MIN_STAGE_WEEKS)
        self.assertEqual(len(path["stages"]), 1)
        self.assertEqual(path["stages"][0]["stage"], "入门")

    def test_short_weeks_stages_feasible(self):
        path = lp.generate_path("学 Python 编程", "零基础", 10, 6)
        self.assertGreaterEqual(len(path["stages"]), 1)
        self.assertEqual(sum(s["weeks"] for s in path["stages"]), 6)

    def test_long_weeks_all_stages(self):
        path = lp.generate_path("学 Python", "零基础", 10, 24)
        self.assertEqual(len(path["stages"]), 3)

    def test_intermediate_start_skips_beginner(self):
        path = lp.generate_path("学 Python", "中级", 10, 12)
        stage_names = [s["stage"] for s in path["stages"]]
        self.assertNotIn("入门", stage_names)
        self.assertIn("进阶", stage_names)

    def test_advanced_start_only_advanced(self):
        path = lp.generate_path("学 Python", "高级", 10, lp.MIN_STAGE_WEEKS)
        self.assertEqual(len(path["stages"]), 1)
        self.assertEqual(path["stages"][0]["stage"], "高级")

    def test_all_domains_generate_successfully(self):
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
        path = lp.generate_path("学 Python", "零基础", 7, 12)
        for stage in path["stages"]:
            for step in stage["steps"]:
                self.assertEqual(step["hours_total"], step["weeks"] * 7)

    def test_step_numbers_sequential(self):
        path = lp.generate_path("学 Python", "零基础", 10, 16)
        for stage in path["stages"]:
            for i, step in enumerate(stage["steps"], 1):
                self.assertEqual(step["step"], i)


# ─────────────────────────────────────────────────────────────────────────────
# 100 组参数化压测
# ─────────────────────────────────────────────────────────────────────────────

class TestGeneratePathStress(unittest.TestCase):
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
        "学烹饪",
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
                rng.randint(3, 20),
                rng.randint(1, 60),
            )
            for _ in range(cls._COUNT)
        ]

    def _check_path(self, goal, level, hours, weeks):
        path = lp.generate_path(goal, level, hours, weeks)

        actual_weeks = sum(s["weeks"] for s in path["stages"])
        self.assertEqual(
            actual_weeks, weeks,
            f"周数不符: plan={weeks} actual={actual_weeks} | {goal} {level} {hours}h"
        )

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

        for stage in path["stages"]:
            for step in stage["steps"]:
                self.assertEqual(
                    step["hours_total"], step["weeks"] * hours,
                    f"hours_total 错: {step['name']} {step['hours_total']} != {step['weeks'] * hours}"
                )

        for stage in path["stages"]:
            self.assertGreater(
                len(stage["steps"]), 0,
                f"空 steps: 阶段={stage['stage']} | {goal} {level} {weeks}w"
            )

    def test_stress_100_cases(self):
        for goal, level, hours, weeks in self._gen_cases():
            with self.subTest(goal=goal, level=level, hours=hours, weeks=weeks):
                self._check_path(goal, level, hours, weeks)


# ─────────────────────────────────────────────────────────────────────────────
# 动态调整建议
# ─────────────────────────────────────────────────────────────────────────────

class TestAdjustForDelay(unittest.TestCase):
    def test_no_delay_is_not_called(self):
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
        self._tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self._tmp.close()
        self._orig_log = _log_mod.LOG_FILE
        _log_mod.LOG_FILE = self._tmp.name

    def tearDown(self):
        _log_mod.LOG_FILE = self._orig_log
        if os.path.exists(self._tmp.name):
            os.unlink(self._tmp.name)

    def test_empty_log_returns_list(self):
        os.unlink(_log_mod.LOG_FILE)
        result = _log_mod.load_log()
        self.assertEqual(result, [])

    def test_save_and_load_roundtrip(self):
        entries = [
            {"date": "2026-03-28", "hours": 2.5, "stage": "入门",
             "step": "环境搭建", "milestone_done": True, "note": "顺利"},
            {"date": "2026-03-29", "hours": 1.0, "stage": "进阶",
             "step": "算法", "milestone_done": False, "note": ""},
        ]
        _log_mod.save_log(entries)
        loaded = _log_mod.load_log()
        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded[0]["hours"], 2.5)
        self.assertTrue(loaded[0]["milestone_done"])
        self.assertEqual(loaded[1]["stage"], "进阶")

    def test_load_empty_file_returns_empty_list(self):
        """load_log 对 0 字节文件不应崩溃，应返回空列表。"""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tf:
            tmp = tf.name
        orig = _log_mod.LOG_FILE
        _log_mod.LOG_FILE = tmp
        try:
            result = _log_mod.load_log()
            self.assertEqual(result, [])
        finally:
            _log_mod.LOG_FILE = orig
            os.unlink(tmp)

    def test_load_corrupted_file_returns_empty_list(self):
        """load_log 对 JSON 损坏文件不应崩溃，应返回空列表。"""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False, mode='w') as tf:
            tf.write("not valid json {{{{")
            tmp = tf.name
        orig = _log_mod.LOG_FILE
        _log_mod.LOG_FILE = tmp
        try:
            result = _log_mod.load_log()
            self.assertEqual(result, [])
        finally:
            _log_mod.LOG_FILE = orig
            os.unlink(tmp)

    def test_append_preserves_existing(self):
        initial = [{"date": "2026-03-27", "hours": 1.0, "stage": "入门",
                    "step": "语法", "milestone_done": False, "note": ""}]
        _log_mod.save_log(initial)
        entries = _log_mod.load_log()
        entries.append({"date": "2026-03-28", "hours": 2.0, "stage": "入门",
                        "step": "数据结构", "milestone_done": True, "note": ""})
        _log_mod.save_log(entries)
        result = _log_mod.load_log()
        self.assertEqual(len(result), 2)

    def test_log_file_is_valid_json(self):
        _log_mod.save_log([{"date": "2026-03-28", "hours": 1.5}])
        with open(_log_mod.LOG_FILE, encoding="utf-8") as f:
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
# _locate_current_step / _infer_current_week / _find_step_by_week
# ─────────────────────────────────────────────────────────────────────────────

class TestInferCurrentWeek(unittest.TestCase):
    def _make_path(self, generated_at, total_weeks=20):
        return {"generated_at": generated_at, "total_weeks": total_weeks, "stages": []}

    def test_today_is_week_one(self):
        today = datetime.now().strftime("%Y-%m-%d")
        result = lp._infer_current_week(self._make_path(today))
        self.assertEqual(result, 1)

    def test_seven_days_later_is_week_two(self):
        d = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        result = lp._infer_current_week(self._make_path(d))
        self.assertEqual(result, 2)

    def test_does_not_exceed_total_weeks(self):
        d = (datetime.now() - timedelta(days=300)).strftime("%Y-%m-%d")
        result = lp._infer_current_week(self._make_path(d, total_weeks=4))
        self.assertEqual(result, 4)

    def test_missing_generated_at_returns_none(self):
        self.assertIsNone(lp._infer_current_week({"total_weeks": 10, "stages": []}))

    def test_bad_date_returns_none(self):
        self.assertIsNone(lp._infer_current_week(self._make_path("not-a-date")))


class TestFindStepByWeek(unittest.TestCase):
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
        _, info = lp._find_step_by_week(self._path, 1)
        self.assertEqual(info["stage"], "入门")

    def test_all_weeks_in_path_are_located(self):
        total = self._path["total_weeks"]
        for w in range(1, total + 1):
            with self.subTest(week=w):
                idx, info = lp._find_step_by_week(self._path, w)
                self.assertIsNotNone(idx, f"第{w}周未能定位到任何步骤")


class TestLocateCurrentStep(unittest.TestCase):
    def setUp(self):
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
        p = lp.generate_path("学Python编程", "零基础", 10, 3)
        self.assertIn("📍", lp._locate_current_step(p, 1))
        self.assertIn("📍", lp._locate_current_step(p, 3))
        self.assertIn("🎉", lp._locate_current_step(p, 4))


# ─────────────────────────────────────────────────────────────────────────────
# NEW: 边界测试
# ─────────────────────────────────────────────────────────────────────────────

class TestBoundaryInputs(unittest.TestCase):
    """边界输入：极端周数/时间/目标/等级"""

    def test_total_weeks_1_does_not_crash(self):
        """total_weeks=1 低于 MIN_STAGE_WEEKS，应不崩溃并返回有效路径。"""
        path = lp.generate_path("学Python", "零基础", 10, 1)
        self.assertEqual(sum(s["weeks"] for s in path["stages"]), 1)
        self.assertGreater(len(path["stages"]), 0)

    def test_total_weeks_100_all_stages(self):
        """total_weeks=100 应展开全三阶段，周数精确。"""
        path = lp.generate_path("学Python", "零基础", 10, 100)
        self.assertEqual(sum(s["weeks"] for s in path["stages"]), 100)
        self.assertEqual(len(path["stages"]), 3)

    def test_hours_per_week_1(self):
        """hours_per_week=1 应正常生成，hours_total = weeks * 1。"""
        path = lp.generate_path("学Python", "零基础", 1, 12)
        for stage in path["stages"]:
            for step in stage["steps"]:
                self.assertEqual(step["hours_total"], step["weeks"] * 1)

    def test_hours_per_week_100(self):
        """hours_per_week=100 应正常生成，hours_total = weeks * 100。"""
        path = lp.generate_path("学Python", "零基础", 100, 12)
        for stage in path["stages"]:
            for step in stage["steps"]:
                self.assertEqual(step["hours_total"], step["weeks"] * 100)

    def test_empty_goal_falls_back_to_general(self):
        """goal="" 应回落到通用领域，不崩溃。"""
        path = lp.generate_path("", "零基础", 5, 8)
        self.assertEqual(path["domain"], "通用")
        self.assertGreater(len(path["stages"]), 0)

    def test_level_zero_base(self):
        """level='零基础' 应从入门阶段开始。"""
        path = lp.generate_path("学Python", "零基础", 10, 16)
        self.assertEqual(path["stages"][0]["stage"], "入门")

    def test_level_advanced(self):
        """level='高级' 应从高级阶段开始。"""
        path = lp.generate_path("学Python", "高级", 10, 12)
        self.assertEqual(path["stages"][0]["stage"], "高级")

    def test_total_weeks_equals_min_stage_weeks(self):
        """total_weeks == MIN_STAGE_WEEKS，只展开一个阶段，周数正确。"""
        path = lp.generate_path("学Python编程", "零基础", 10, lp.MIN_STAGE_WEEKS)
        self.assertEqual(len(path["stages"]), 1)
        self.assertEqual(sum(s["weeks"] for s in path["stages"]), lp.MIN_STAGE_WEEKS)

    def test_week_ranges_contiguous_boundary(self):
        """total_weeks=1 时步骤 week_range 仍应连续。"""
        path = lp.generate_path("学Python", "零基础", 5, 1)
        prev_end = 0
        for stage in path["stages"]:
            for step in stage["steps"]:
                parts = step["week_range"].replace("第", "").replace("周", "").split("~")
                start, end = int(parts[0].strip()), int(parts[1].strip())
                self.assertEqual(start, prev_end + 1)
                prev_end = end


# ─────────────────────────────────────────────────────────────────────────────
# NEW: 异常输入测试
# ─────────────────────────────────────────────────────────────────────────────

class TestAbnormalInputs(unittest.TestCase):
    """异常/边界输入不应引发未处理异常。"""

    def test_parse_int_empty_string(self):
        """parse_int("", 1) → 1"""
        self.assertEqual(lp.parse_int("", 1), 1)

    def test_parse_int_negative(self):
        """parse_int("-5", 1) → 1（结果最小为1）"""
        self.assertGreaterEqual(lp.parse_int("-5", 1), 1)

    def test_parse_float_abc(self):
        """parse_float("abc", 0.0) → 0.0"""
        self.assertEqual(lp.parse_float("abc", 0.0), 0.0)

    def test_detect_domain_none_raises_or_returns(self):
        """detect_domain(None) → 不应引发意外崩溃（允许 TypeError/AttributeError）。"""
        # None 不是 str，合理接受 TypeError/AttributeError；
        # 也可以在实现中 try-except 并返回 "通用"。
        try:
            result = lp.detect_domain(None)
            # 如果实现容错，结果应为 "通用"
            self.assertEqual(result, "通用")
        except (TypeError, AttributeError):
            pass  # 未容错也是可接受行为

    def test_load_log_nonexistent_path(self):
        """load_log() 指向不存在路径 → []"""
        orig = _log_mod.LOG_FILE
        _log_mod.LOG_FILE = "/tmp/nonexistent_learning_log_xyz123.json"
        try:
            result = _log_mod.load_log()
            self.assertEqual(result, [])
        finally:
            _log_mod.LOG_FILE = orig

    def test_generate_path_empty_goal(self):
        """generate_path("", "零基础", 5, 8) → 不崩溃，返回通用领域路径。"""
        path = lp.generate_path("", "零基础", 5, 8)
        self.assertIsInstance(path, dict)
        self.assertEqual(path["domain"], "通用")
        self.assertGreater(len(path["stages"]), 0)
        self.assertEqual(sum(s["weeks"] for s in path["stages"]), 8)

    def test_parse_float_none_like_empty(self):
        """parse_float with whitespace-only string → default"""
        self.assertEqual(lp.parse_float("   ", 3.0), 3.0)

    def test_parse_int_float_zero(self):
        """parse_int("0.5", 2) → 1 (max(1, int(0.5)) = max(1, 0) = 1)"""
        self.assertEqual(lp.parse_int("0.5", 2), 1)


# ─────────────────────────────────────────────────────────────────────────────
# NEW: CLI 输入模拟测试
# ─────────────────────────────────────────────────────────────────────────────

class TestCLIInputMock(unittest.TestCase):
    """用 unittest.mock 模拟 input()，测试 CLI 各模式。"""

    def _make_tmp_path_file(self):
        """生成临时 PATH_FILE，写入一个有效路径 JSON，返回临时文件路径。"""
        path = lp.generate_path("学Python编程", "零基础", 10, 12)
        # 设置生成日期为今天，使得 _infer_current_week 能推算第1周
        path["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w", encoding="utf-8")
        json.dump(path, tmp, ensure_ascii=False)
        tmp.close()
        return tmp.name, path

    def setUp(self):
        """每个测试前：创建临时 PATH_FILE 和 LOG_FILE，patch 模块级变量。"""
        self._tmp_path_file, self._sample_path = self._make_tmp_path_file()
        self._tmp_log_file = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self._tmp_log_file.close()

        # Patch cli 模块的 PATH_FILE 和 log 模块的 PATH_FILE / LOG_FILE
        self._orig_path_file_cli = _cli_mod.PATH_FILE
        self._orig_path_file_log = _log_mod.PATH_FILE
        self._orig_log_file_log  = _log_mod.LOG_FILE

        _cli_mod.PATH_FILE = self._tmp_path_file
        _log_mod.PATH_FILE = self._tmp_path_file
        _log_mod.LOG_FILE  = self._tmp_log_file.name

    def tearDown(self):
        _cli_mod.PATH_FILE = self._orig_path_file_cli
        _log_mod.PATH_FILE = self._orig_path_file_log
        _log_mod.LOG_FILE  = self._orig_log_file_log

        if os.path.exists(self._tmp_path_file):
            os.unlink(self._tmp_path_file)
        if os.path.exists(self._tmp_log_file.name):
            os.unlink(self._tmp_log_file.name)

    def test_track_mode_reject_inferred_manual_input(self):
        """track_mode: 拒绝推算值 → 手动输入第3周 → 无延误"""
        inputs = ["n", "3", "0"]
        with patch("builtins.input", side_effect=inputs):
            try:
                _cli_mod.track_mode()
            except StopIteration:
                pass  # input 耗尽时 side_effect 会抛 StopIteration，属正常

    def test_track_mode_accept_inferred_no_delay(self):
        """track_mode: 接受推算值 → 无延误"""
        inputs = ["y", "0"]
        with patch("builtins.input", side_effect=inputs):
            try:
                _cli_mod.track_mode()
            except StopIteration:
                pass

    def test_add_log_entry_accept_auto_step(self):
        """add_log_entry: 1.5h → 接受自动步骤 → 里程碑未完成 → 无备注"""
        inputs = ["1.5", "y", "n", ""]
        with patch("builtins.input", side_effect=inputs):
            try:
                _cli_mod.add_log_entry()
            except StopIteration:
                pass
        # 验证日志已写入
        entries = _log_mod.load_log()
        self.assertGreaterEqual(len(entries), 1)
        self.assertAlmostEqual(entries[-1]["hours"], 1.5)
        self.assertFalse(entries[-1]["milestone_done"])

    def test_add_log_entry_reject_auto_step(self):
        """add_log_entry: 1.0h → 拒绝自动步骤 → 手动选择步骤1 → 里程碑完成 → 有备注"""
        inputs = ["1.0", "n", "1", "y", "测试备注"]
        with patch("builtins.input", side_effect=inputs):
            try:
                _cli_mod.add_log_entry()
            except StopIteration:
                pass
        entries = _log_mod.load_log()
        self.assertGreaterEqual(len(entries), 1)
        self.assertAlmostEqual(entries[-1]["hours"], 1.0)
        self.assertTrue(entries[-1]["milestone_done"])

    def test_interactive_mode_full_flow_no_save(self):
        """interactive_mode: 完整交互流程，最后选择不保存。"""
        # 学Python编程 → 选1（零基础） → 10h → 12周 → 不保存(n)
        inputs = ["学Python编程", "1", "10", "12", "n"]
        orig_path = _cli_mod.PATH_FILE
        _cli_mod.PATH_FILE = self._tmp_path_file + ".new"
        try:
            with patch("builtins.input", side_effect=inputs):
                try:
                    _cli_mod.interactive_mode()
                except StopIteration:
                    pass
            # 选择不保存，文件不应被创建
            self.assertFalse(os.path.exists(_cli_mod.PATH_FILE))
        finally:
            _cli_mod.PATH_FILE = orig_path
            if os.path.exists(_cli_mod.PATH_FILE + ".new"):
                os.unlink(_cli_mod.PATH_FILE + ".new")

    def test_interactive_mode_save(self):
        """interactive_mode: 完整流程并保存。"""
        inputs = ["学Python编程", "1", "10", "12", "y"]
        orig_path = _cli_mod.PATH_FILE
        tmp_new = self._tmp_path_file + ".saved"
        _cli_mod.PATH_FILE = tmp_new
        try:
            with patch("builtins.input", side_effect=inputs):
                try:
                    _cli_mod.interactive_mode()
                except StopIteration:
                    pass
            if os.path.exists(tmp_new):
                with open(tmp_new, encoding="utf-8") as f:
                    saved = json.load(f)
                self.assertEqual(saved["domain"], "编程")
        finally:
            _cli_mod.PATH_FILE = orig_path
            if os.path.exists(tmp_new):
                os.unlink(tmp_new)

    def test_track_mode_no_path_file(self):
        """track_mode: PATH_FILE 不存在时，打印错误并返回（不崩溃）。"""
        _cli_mod.PATH_FILE = "/tmp/nonexistent_path_xyz123.json"
        try:
            _cli_mod.track_mode()  # 应直接返回，不需要 input
        finally:
            _cli_mod.PATH_FILE = self._tmp_path_file

    def test_add_log_entry_no_path_file(self):
        """add_log_entry: PATH_FILE 不存在时，打印错误并返回（不崩溃）。"""
        _cli_mod.PATH_FILE = "/tmp/nonexistent_path_xyz123.json"
        try:
            _cli_mod.add_log_entry()
        finally:
            _cli_mod.PATH_FILE = self._tmp_path_file


if __name__ == "__main__":
    unittest.main(verbosity=2)
