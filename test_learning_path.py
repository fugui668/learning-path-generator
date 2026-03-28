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

    def test_short_weeks_two_stages(self):
        """6 周（= 2 * MIN_STAGE_WEEKS）通常只展开两个阶段。"""
        path = lp.generate_path("学 Python", "零基础", 10, 6)
        self.assertLessEqual(len(path["stages"]), 2)

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
