"""
resources.py — 动态资源集成模块

提供：
  - fetch_youtube_resources: 直接抓取 YouTube 搜索页，解析 ytInitialData
  - CURATED_RESOURCES: 按领域精选资源库（静态兜底）
  - get_resources: 统一对外接口，支持在线/离线两种模式
"""

import json
import re
import urllib.error
import urllib.parse
import urllib.request

# ─────────────────────────────────────────────────────────────────────────────
# 精选资源库（静态兜底，覆盖 domains.json 全部领域）
# ─────────────────────────────────────────────────────────────────────────────

CURATED_RESOURCES: dict[str, list[dict]] = {
    "编程": [
        {
            "title": "Python 编程：从入门到实践（视频课）",
            "url": "https://www.bilibili.com/video/BV1qW4y1a7fU",
            "source": "B站",
        },
        {
            "title": "freeCodeCamp - Responsive Web Design",
            "url": "https://www.freecodecamp.org/learn/2022/responsive-web-design/",
            "source": "freeCodeCamp",
        },
        {
            "title": "CS50's Introduction to Computer Science",
            "url": "https://cs50.harvard.edu/x/",
            "source": "Harvard",
        },
        {
            "title": "MDN Web Docs - JavaScript 指南",
            "url": "https://developer.mozilla.org/zh-CN/docs/Web/JavaScript/Guide",
            "source": "MDN",
        },
    ],
    "数据分析": [
        {
            "title": "Python数据分析与机器学习实战",
            "url": "https://www.bilibili.com/video/BV1Bx411S7iW",
            "source": "B站",
        },
        {
            "title": "Kaggle Learn - Pandas",
            "url": "https://www.kaggle.com/learn/pandas",
            "source": "Kaggle",
        },
        {
            "title": "CS50's Introduction to Programming with Python",
            "url": "https://cs50.harvard.edu/python/",
            "source": "Harvard",
        },
        {
            "title": "Google Data Analytics Professional Certificate",
            "url": "https://www.coursera.org/professional-certificates/google-data-analytics",
            "source": "Coursera",
        },
    ],
    "英语": [
        {
            "title": "英语兔 - 英语语法精讲合集",
            "url": "https://www.bilibili.com/video/BV1XY411J7aG",
            "source": "B站",
        },
        {
            "title": "BBC Learning English - 6 Minute English",
            "url": "https://www.bbc.co.uk/learningenglish/english/features/6-minute-english",
            "source": "BBC",
        },
        {
            "title": "Coursera - English for Career Development",
            "url": "https://www.coursera.org/learn/careerdevelopment",
            "source": "Coursera",
        },
        {
            "title": "TED Talks - Ideas Worth Spreading",
            "url": "https://www.ted.com/talks",
            "source": "TED",
        },
    ],
    "中文": [
        {
            "title": "HSK 标准教程配套视频课",
            "url": "https://www.bilibili.com/video/BV1ts411e7fH",
            "source": "B站",
        },
        {
            "title": "Coursera - Chinese for Beginners",
            "url": "https://www.coursera.org/learn/learn-chinese",
            "source": "Coursera",
        },
        {
            "title": "YoYo Chinese - Beginner Conversational Chinese",
            "url": "https://www.yoyochinese.com/chinese-learning-video/Beginner-Mandarin-Chinese-Lesson",
            "source": "YoYo Chinese",
        },
        {
            "title": "Chinese Grammar Wiki",
            "url": "https://resources.allsetlearning.com/chinese/grammar/",
            "source": "AllSet Learning",
        },
    ],
    "西班牙语": [
        {
            "title": "西班牙语零基础入门（全120讲）",
            "url": "https://www.bilibili.com/video/BV1ms411D7zg",
            "source": "B站",
        },
        {
            "title": "Coursera - Learn Spanish: Basic Spanish Vocabulary",
            "url": "https://www.coursera.org/specializations/learn-spanish",
            "source": "Coursera",
        },
        {
            "title": "SpanishPod101 - Absolute Beginner Spanish",
            "url": "https://www.spanishpod101.com/",
            "source": "SpanishPod101",
        },
        {
            "title": "Dreaming Spanish - Comprehensible Input",
            "url": "https://www.dreaminspanish.com/",
            "source": "Dreaming Spanish",
        },
    ],
    "设计": [
        {
            "title": "Figma 从零到一完整入门教程",
            "url": "https://www.bilibili.com/video/BV1Gg4y1p7GT",
            "source": "B站",
        },
        {
            "title": "Google UX Design Professional Certificate",
            "url": "https://www.coursera.org/professional-certificates/google-ux-design",
            "source": "Coursera",
        },
        {
            "title": "Figma Official Learn Hub",
            "url": "https://help.figma.com/hc/en-us/categories/360002051613",
            "source": "Figma",
        },
        {
            "title": "Canva Design School",
            "url": "https://www.canva.com/learn/design/",
            "source": "Canva",
        },
    ],
    "产品": [
        {
            "title": "人人都是产品经理 - 产品经理入门课",
            "url": "https://www.bilibili.com/video/BV1ux411V7tM",
            "source": "B站",
        },
        {
            "title": "Coursera - Digital Product Management",
            "url": "https://www.coursera.org/specializations/uva-darden-digital-product-management",
            "source": "Coursera",
        },
        {
            "title": "Product School - Free PM Resources",
            "url": "https://productschool.com/resources/",
            "source": "Product School",
        },
        {
            "title": "Reforge - Product Strategy",
            "url": "https://www.reforge.com/blog",
            "source": "Reforge",
        },
    ],
    "写作": [
        {
            "title": "写作课：如何写出好文章（系统讲解）",
            "url": "https://www.bilibili.com/video/BV1x54y1B7RE",
            "source": "B站",
        },
        {
            "title": "Coursera - Creative Writing Specialization",
            "url": "https://www.coursera.org/specializations/creative-writing",
            "source": "Coursera",
        },
        {
            "title": "The Writer's Workshop - University of Chicago",
            "url": "https://writingprogram.uchicago.edu/",
            "source": "UChicago",
        },
        {
            "title": "Hemingway Editor - 写作辅助工具",
            "url": "https://hemingwayapp.com/",
            "source": "Hemingway",
        },
    ],
    "通用": [
        {
            "title": "Coursera - Learning How to Learn",
            "url": "https://www.coursera.org/learn/learning-how-to-learn",
            "source": "Coursera",
        },
        {
            "title": "Khan Academy - Free Courses on Any Subject",
            "url": "https://www.khanacademy.org/",
            "source": "Khan Academy",
        },
        {
            "title": "MIT OpenCourseWare - Free MIT Courses",
            "url": "https://ocw.mit.edu/",
            "source": "MIT OCW",
        },
        {
            "title": "YouTube EDU - 精选教育频道",
            "url": "https://www.youtube.com/channel/UCVTlvUkGslCV_h-nSAId8Sw",
            "source": "YouTube",
        },
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# YouTube 搜索（直接抓 HTML，解析 ytInitialData）
# ─────────────────────────────────────────────────────────────────────────────

def fetch_youtube_resources(query: str, max_results: int = 3) -> list[dict]:
    """
    通过 YouTube 搜索页获取课程视频。

    参数：
        query: 搜索关键词
        max_results: 最多返回条数，默认 3

    返回格式：
        [{"title": "...", "url": "https://youtu.be/...", "channel": "..."}]

    失败时返回 []，不崩溃。超时设置为 5 秒。
    """
    try:
        encoded = urllib.parse.quote_plus(query)
        # sp=EgIQAw%3D%3D 过滤课程视频（YouTube filter: type=Video, duration=Long）
        url = f"https://www.youtube.com/results?search_query={encoded}&sp=EgIQAw%3D%3D"

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
        )

        with urllib.request.urlopen(req, timeout=5) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        # 提取 ytInitialData JSON
        match = re.search(r"var ytInitialData\s*=\s*(\{.+?\});\s*</script>", html, re.DOTALL)
        if not match:
            # 兼容另一种嵌入格式
            match = re.search(r"ytInitialData\s*=\s*(\{.+?\});\s*(?:var |window\[)", html, re.DOTALL)
        if not match:
            return []

        data = json.loads(match.group(1))
        results: list[dict] = []

        # 深度遍历 JSON 结构，提取 videoRenderer
        contents = (
            data.get("contents", {})
            .get("twoColumnSearchResultsRenderer", {})
            .get("primaryContents", {})
            .get("sectionListRenderer", {})
            .get("contents", [])
        )
        for section in contents:
            items = (
                section.get("itemSectionRenderer", {}).get("contents", [])
            )
            for item in items:
                vr = item.get("videoRenderer")
                if not vr:
                    continue
                video_id = vr.get("videoId", "")
                if not video_id:
                    continue

                # 标题
                title_runs = vr.get("title", {}).get("runs", [])
                title = "".join(r.get("text", "") for r in title_runs).strip()

                # 频道名
                channel_runs = (
                    vr.get("ownerText", {}).get("runs", [])
                    or vr.get("shortBylineText", {}).get("runs", [])
                )
                channel = "".join(r.get("text", "") for r in channel_runs).strip()

                if title and video_id:
                    results.append({
                        "title": title,
                        "url": f"https://youtu.be/{video_id}",
                        "channel": channel,
                    })
                    if len(results) >= max_results:
                        return results

        return results

    except Exception:  # noqa: BLE001
        return []


# ─────────────────────────────────────────────────────────────────────────────
# 主接口
# ─────────────────────────────────────────────────────────────────────────────

def get_resources(
    domain: str,
    step_name: str,
    use_online: bool = False,
) -> list[dict]:
    """
    获取指定领域 + 步骤的学习资源。

    参数：
        domain:     领域名，对应 CURATED_RESOURCES 的 key（如 "编程"、"数据分析"）
        step_name:  步骤名称，用于构造 YouTube 搜索词
        use_online: True 时先尝试 YouTube 搜索，失败降级到精选库；
                    False 时直接返回精选库资源

    返回：
        list[dict]，每项至少含 title、url 字段
    """
    fallback = CURATED_RESOURCES.get(domain) or CURATED_RESOURCES.get("通用", [])

    if not use_online:
        return fallback

    # 在线模式：构造 YouTube 搜索词，失败降级
    query = f"{domain} {step_name} 教程"
    online = fetch_youtube_resources(query, max_results=3)
    if online:
        return online

    return fallback
