"""
resources.py — 动态资源集成模块

提供：
  - fetch_youtube_resources: 多策略降级链抓取视频资源（YouTube库/ytInitialData/B站），含缓存
  - CURATED_RESOURCES: 按领域精选资源库（静态兜底）
  - get_resources: 统一对外接口，支持在线/离线两种模式
"""

import concurrent.futures
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

# ─────────────────────────────────────────────────────────────────────────────
# 缓存配置
# ─────────────────────────────────────────────────────────────────────────────

_THIS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_FILE = os.path.join(_THIS_DIR, "resource_cache.json")
CACHE_TTL = 86400  # 24 小时


def _load_cache() -> dict:
    """加载磁盘缓存，失败返回空字典。"""
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, encoding="utf-8") as f:
                return json.load(f)
    except Exception:  # noqa: BLE001
        pass
    return {}


def _save_cache(cache: dict) -> None:
    """持久化缓存到磁盘，失败静默忽略。"""
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception:  # noqa: BLE001
        pass

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
# YouTube / 视频资源搜索（多策略降级链 + 缓存 + 超时保护）
# ─────────────────────────────────────────────────────────────────────────────

_REQUEST_TIMEOUT = 3  # 每次网络请求超时（秒）


def _strategy1_youtube_search_python(query: str, max_results: int) -> list[dict]:
    """策略1：使用 youtube-search-python 库（需单独安装）。"""
    from youtubesearchpython import VideosSearch  # type: ignore
    vs = VideosSearch(query, limit=max_results)
    result = vs.result()
    items = result.get("result", [])
    out = []
    for item in items[:max_results]:
        title = item.get("title", "")
        link = item.get("link", "")
        channel = (item.get("channel") or {}).get("name", "")
        if title and link:
            out.append({"title": title, "url": link, "channel": channel})
    return out


def _strategy2_ytInitialData(query: str, max_results: int) -> list[dict]:
    """策略2：解析 YouTube 搜索页的 ytInitialData JSON（更健壮的异常处理）。"""
    encoded = urllib.parse.quote_plus(query)
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
    with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
        html = resp.read().decode("utf-8", errors="replace")

    # 提取 ytInitialData JSON（兼容多种嵌入格式）
    match = re.search(r"var ytInitialData\s*=\s*(\{.+?\});\s*</script>", html, re.DOTALL)
    if not match:
        match = re.search(r"ytInitialData\s*=\s*(\{.+?\});\s*(?:var |window\[)", html, re.DOTALL)
    if not match:
        return []

    data = json.loads(match.group(1))
    results: list[dict] = []

    contents = (
        data.get("contents", {})
        .get("twoColumnSearchResultsRenderer", {})
        .get("primaryContents", {})
        .get("sectionListRenderer", {})
        .get("contents", [])
    )
    for section in contents:
        items = section.get("itemSectionRenderer", {}).get("contents", [])
        for item in items:
            vr = item.get("videoRenderer")
            if not vr:
                continue
            video_id = vr.get("videoId", "")
            if not video_id:
                continue
            title_runs = vr.get("title", {}).get("runs", [])
            title = "".join(r.get("text", "") for r in title_runs).strip()
            channel_runs = (
                vr.get("ownerText", {}).get("runs", [])
                or vr.get("shortBylineText", {}).get("runs", [])
            )
            channel = "".join(r.get("text", "") for r in channel_runs).strip()
            if title and video_id:
                results.append({"title": title, "url": f"https://youtu.be/{video_id}", "channel": channel})
                if len(results) >= max_results:
                    return results
    return results


def _strategy3_bilibili(query: str, max_results: int) -> list[dict]:
    """策略3：搜索 B站，解析搜索结果页。"""
    encoded = urllib.parse.quote_plus(query)
    url = f"https://search.bilibili.com/all?keyword={encoded}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9",
        },
    )
    with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
        html = resp.read().decode("utf-8", errors="replace")

    # 从 B站搜索页提取视频链接和标题（基于页面 JSON 数据）
    results: list[dict] = []

    # 尝试提取 __INITIAL_STATE__ 或 window.__initialState__
    match = re.search(r"__INITIAL_STATE__\s*=\s*(\{.+?\});\s*(?:\(function|</script>)", html, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            video_list = (
                data.get("videoList", {}).get("result", [])
                or data.get("result", [])
            )
            for item in video_list[:max_results]:
                title = re.sub(r"<[^>]+>", "", item.get("title", "")).strip()
                bvid = item.get("bvid", "")
                author = item.get("author", "")
                if title and bvid:
                    results.append({
                        "title": title,
                        "url": f"https://www.bilibili.com/video/{bvid}",
                        "channel": author,
                    })
            if results:
                return results
        except Exception:  # noqa: BLE001
            pass

    # 降级：正则提取 bvid 和标题
    bvids = re.findall(r'"bvid"\s*:\s*"(BV[A-Za-z0-9]+)"', html)
    titles_raw = re.findall(r'"title"\s*:\s*"([^"]{5,})"', html)
    for i, bvid in enumerate(bvids[:max_results]):
        title = titles_raw[i] if i < len(titles_raw) else bvid
        title = re.sub(r"<[^>]+>", "", title).strip()
        results.append({
            "title": title,
            "url": f"https://www.bilibili.com/video/{bvid}",
            "channel": "",
        })
    return results


def _run_with_timeout(fn, *args, timeout: float = _REQUEST_TIMEOUT + 1) -> list[dict]:
    """在线程中运行 fn，超时或异常时返回 []。"""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(fn, *args)
        try:
            return future.result(timeout=timeout)
        except Exception:  # noqa: BLE001
            return []


def fetch_youtube_resources(query: str, max_results: int = 3) -> list[dict]:
    """
    多策略降级链获取视频资源，含 24 小时磁盘缓存。

    策略顺序：
      1. youtube-search-python 库（如已安装）
      2. 解析 YouTube ytInitialData HTML
      3. 搜索 B 站
      4. 全部失败 → 返回 []

    参数：
        query: 搜索关键词
        max_results: 最多返回条数，默认 3

    返回格式：
        [{"title": "...", "url": "...", "channel": "..."}]

    失败时返回 []，不崩溃。每次网络请求超时 3 秒。
    """
    # ── 检查缓存 ────────────────────────────────────────────────────────────
    cache = _load_cache()
    cache_key = f"{query}::{max_results}"
    entry = cache.get(cache_key)
    if entry and isinstance(entry, dict):
        ts = entry.get("ts", 0)
        if time.time() - ts < CACHE_TTL:
            return entry.get("data", [])

    # ── 策略1：youtube-search-python ────────────────────────────────────────
    try:
        result = _run_with_timeout(_strategy1_youtube_search_python, query, max_results)
        if result:
            cache[cache_key] = {"ts": time.time(), "data": result}
            _save_cache(cache)
            return result
    except Exception:  # noqa: BLE001
        pass

    # ── 策略2：ytInitialData ─────────────────────────────────────────────────
    try:
        result = _run_with_timeout(_strategy2_ytInitialData, query, max_results)
        if result:
            cache[cache_key] = {"ts": time.time(), "data": result}
            _save_cache(cache)
            return result
    except Exception:  # noqa: BLE001
        pass

    # ── 策略3：B 站搜索 ──────────────────────────────────────────────────────
    try:
        result = _run_with_timeout(_strategy3_bilibili, query, max_results)
        if result:
            cache[cache_key] = {"ts": time.time(), "data": result}
            _save_cache(cache)
            return result
    except Exception:  # noqa: BLE001
        pass

    # ── 策略4：全部失败 ──────────────────────────────────────────────────────
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
