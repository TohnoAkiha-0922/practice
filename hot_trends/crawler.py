"""
Multi-platform hot trends crawler.
Actively searches for AI content + monitors hot lists.
"""

import asyncio
import re
import httpx

# ─────── AI Keywords for searching ───────
# Used to actively search each platform for AI content
AI_SEARCH_QUERIES = [
    "人工智能", "AI技术", "大模型", "机器学习", "深度学习",
    "ChatGPT", "AIGC", "自动驾驶", "机器人",
    "AI绘画", "AI视频", "AI编程",
]

# ─────── AI Keywords for filtering hot lists ───────
# Broad set to catch any AI-related trending topics
HOTLIST_AI_KEYWORDS = [
    # Core AI
    "人工智能", "AI", "大模型", "大语言模型", "机器学习", "深度学习",
    "神经网络", "AIGC", "生成式", "智能体", "多模态",
    "自然语言", "计算机视觉", "语音识别",

    # AI products & companies
    "ChatGPT", "OpenAI", "Claude", "Gemini", "Copilot", "Sora",
    "文心一言", "通义千问", "豆包", "智谱", "讯飞星火",
    "Kimi", "天工AI", "混元", "百川", "零一万物", "月之暗面",
    "DeepSeek", "Stable Diffusion", "Midjourney", "DALL-E",

    # AI application areas
    "自动驾驶", "无人驾驶", "智能驾驶", "机器人", "数字人",
    "AI搜索", "AI编程", "AI绘画", "AI视频", "AI音乐",
    "AI助手", "AI助理", "智能客服", "推荐算法",

    # Tech infrastructure
    "算力", "芯片", "GPU", "昇腾", "英伟达", "NVIDIA",
    "大语言", "语言模型", "视觉模型", "LLM", "RAG",

    # Broader tech that often involves AI
    "算法", "智能", "数字化", "自动化", "数据",
    "上线", "发布", "更新", "新功能",

    # Current hot tech topics
    "鸿蒙", "HarmonyOS", "iOS 19", "华为", "苹果AI",
    "小米", "字节跳动", "腾讯", "阿里", "百度",

    # English keywords
    "GPT-", "Transformer", "Diffusion", "Neural Network",
    "Agent", "AGI", "NLP", "ASR", "TTS",
]

# ─────── Headers ───────
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/125.0.0.0 Safari/537.36",
    "Referer": "https://www.google.com/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def _match_hotlist_ai(text: str) -> bool:
    """Check if text matches any AI-related keyword (broad matching for hotlists)."""
    t = text.lower()
    for kw in HOTLIST_AI_KEYWORDS:
        if kw.lower() in t:
            return True
    return False


def _clean_title(title: str) -> str:
    """Remove HTML tags from API responses."""
    return re.sub(r'<[^>]+>', '', title)


# ════════════════════ Bilibili ════════════════════

async def _bilibili_search(client: httpx.AsyncClient, keyword: str, limit: int = 20) -> list[dict]:
    """Search Bilibili for videos matching a keyword."""
    results = []
    try:
        r = await client.get(
            "https://api.bilibili.com/x/web-interface/search/type",
            params={
                "search_type": "video",
                "keyword": keyword,
                "page": 1,
                "order": "click",  # sort by popularity
            },
            headers={**HEADERS, "Referer": "https://www.bilibili.com/"},
        )
        if r.status_code == 200:
            data = r.json()
            for item in data.get("data", {}).get("result", [])[:limit]:
                title = _clean_title(item.get("title", ""))
                bvid = item.get("bvid", "")
                if not title or not bvid:
                    continue
                results.append({
                    "title": title,
                    "desc": item.get("description", "")[:120],
                    "hot_value": f"{item.get('play', 0):,} 播放",
                    "url": f"https://www.bilibili.com/video/{bvid}",
                    "author": item.get("author", ""),
                    "keyword": keyword,
                })
    except Exception:
        pass
    return results


async def fetch_bilibili() -> list[dict]:
    """Primary: search AI keywords. Fallback: hot list."""
    seen_titles = set()
    results = []

    async with httpx.AsyncClient(timeout=10) as client:
        # ── AI Search (primary) ──
        search_tasks = []
        for kw in AI_SEARCH_QUERIES:
            search_tasks.append(_bilibili_search(client, kw, limit=15))

        all_search_results = await asyncio.gather(*search_tasks)

        for kw_results in all_search_results:
            for item in kw_results:
                if item["title"] not in seen_titles:
                    seen_titles.add(item["title"])
                    results.append({
                        "platform": "bilibili",
                        "rank": len(results) + 1,
                        "title": item["title"],
                        "desc": item.get("desc", ""),
                        "hot_value": item.get("hot_value", ""),
                        "url": item["url"],
                        "author": item.get("author", ""),
                        "ai": True,
                    })

        # ── Hot list (supplemental) ──
        try:
            r = await client.get(
                "https://api.bilibili.com/x/web-interface/popular",
                headers={**HEADERS, "Referer": "https://www.bilibili.com/"},
            )
            if r.status_code == 200:
                data = r.json()
                for item in data.get("data", {}).get("list", []):
                    title = item.get("title", "")
                    if title in seen_titles:
                        continue
                    desc = item.get("desc", "")
                    is_ai = _match_hotlist_ai(title) or _match_hotlist_ai(desc)
                    seen_titles.add(title)
                    results.append({
                        "platform": "bilibili",
                        "rank": len(results) + 1,
                        "title": title,
                        "desc": desc.strip(),
                        "hot_value": f"{item.get('stat', {}).get('view', 0):,} 播放",
                        "url": f"https://www.bilibili.com/video/{item.get('bvid', '')}",
                        "author": item.get("owner", {}).get("name", ""),
                        "ai": is_ai,
                    })
        except Exception as e:
            pass  # Search results are the main source, so hot list failure is ok

    return results


# ════════════════════ Weibo ════════════════════

async def fetch_weibo() -> list[dict]:
    """Fetch Weibo hot search & try to get AI-related content."""
    results = []
    seen = set()

    async with httpx.AsyncClient(timeout=10) as client:
        # ── Hot search list ──
        try:
            r = await client.get(
                "https://weibo.com/ajax/side/hotSearch",
                headers={**HEADERS, "Referer": "https://weibo.com/"},
            )
            if r.status_code == 200:
                data = r.json()
                for item in data.get("data", {}).get("realtime", []):
                    word = item.get("word", "")
                    if not word or word in seen:
                        continue
                    seen.add(word)
                    raw = item.get("raw_hot", 0) or 0
                    results.append({
                        "platform": "weibo",
                        "rank": item.get("rank", len(results) + 1),
                        "title": word,
                        "desc": item.get("label_name", ""),
                        "hot_value": f"{raw:,} 热" if raw else "🔥 热",
                        "url": f"https://s.weibo.com/weibo?q={word}",
                        "author": "",
                        "ai": _match_hotlist_ai(word),
                    })
        except Exception as e:
            pass  # Non-critical

        # ── Try Weibo topic/card API for AI content ──
        # (Weibo APIs generally need auth, this is best-effort)
        try:
            # Try fetching from Weibo's hot feed which sometimes has tech topics
            r = await client.get(
                "https://weibo.com/ajax/feed/hottimeline",
                params={"since_id": 0, "refresh": 2, "group_id": 102803},
                headers={**HEADERS, "Referer": "https://weibo.com/"},
                follow_redirects=True,
            )
            if r.status_code == 200:
                data = r.json()
                cards = data.get("statuses", [])
                for card in cards[:30]:
                    text = card.get("text_raw", "") or card.get("text", "")
                    if not text:
                        continue
                    text = _clean_title(text)[:100]
                    if text in seen:
                        continue
                    if _match_hotlist_ai(text):
                        seen.add(text)
                        results.append({
                            "platform": "weibo",
                            "rank": len(results) + 1,
                            "title": text,
                            "desc": "AI 相关",
                            "hot_value": "🔥",
                            "url": f"https://weibo.com/{card.get('user', {}).get('id', '')}/{card.get('mid', '')}",
                            "author": card.get("user", {}).get("screen_name", ""),
                            "ai": True,
                        })
        except Exception:
            pass  # Non-critical

    # Sort: AI first, then by rank
    results.sort(key=lambda x: (not x["ai"], x.get("rank", 999)))
    for i, item in enumerate(results):
        item["rank"] = i + 1
    return results


# ════════════════════ Douyin ════════════════════

async def fetch_douyin() -> list[dict]:
    """Fetch Douyin hot search list (search APIs are locked down)."""
    results = []
    seen = set()

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.get(
                "https://www.douyin.com/aweme/v1/web/hot/search/list/",
                params={"detail_list": "1", "source": "0"},
                headers={**HEADERS, "Referer": "https://www.douyin.com/"},
            )
            if r.status_code == 200:
                data = r.json()
                for item in data.get("data", {}).get("word_list", []):
                    word = item.get("word", "")
                    # word can be a string or dict
                    if isinstance(word, dict):
                        word = word.get("name", "")
                    if not word or word in seen:
                        continue
                    seen.add(word)
                    hot_val = item.get("hot_value", 0) or 0
                    results.append({
                        "platform": "douyin",
                        "rank": item.get("position", item.get("max_rank", len(results) + 1)),
                        "title": word,
                        "desc": "",
                        "hot_value": f"{hot_val:,}" if hot_val else "🔥 热",
                        "url": f"https://www.douyin.com/search/{word}",
                        "author": "",
                        "ai": _match_hotlist_ai(word),
                    })
        except Exception as e:
            pass  # Will fall through to backup

        # ── Fallback: tenapi ──
        if not results:
            try:
                r = await client.get(
                    "https://tenapi.cn/v2/douyinhot",
                    headers=HEADERS,
                )
                if r.status_code == 200:
                    data = r.json()
                    for item in data.get("data", []):
                        name = item.get("name", "")
                        if not name or name in seen:
                            continue
                        seen.add(name)
                        results.append({
                            "platform": "douyin",
                            "rank": item.get("rank", len(results) + 1),
                            "title": name,
                            "desc": "",
                            "hot_value": f"{item.get('hot', 0):,}" if item.get('hot') else "🔥",
                            "url": f"https://www.douyin.com/search/{name}",
                            "author": "",
                            "ai": _match_hotlist_ai(name),
                        })
            except Exception:
                pass

    # Sort: AI first, then by rank
    results.sort(key=lambda x: (not x["ai"], x.get("rank", 999)))
    for i, item in enumerate(results):
        item["rank"] = i + 1
    return results


# ════════════════════ Aggregator ════════════════════

async def fetch_all() -> dict:
    """Fetch data from all platforms concurrently."""
    bili_task = asyncio.create_task(fetch_bilibili())
    weibo_task = asyncio.create_task(fetch_weibo())
    douyin_task = asyncio.create_task(fetch_douyin())

    bili_data, weibo_data, douyin_data = await asyncio.gather(
        bili_task, weibo_task, douyin_task
    )

    return {
        "bilibili": bili_data,
        "weibo": weibo_data,
        "douyin": douyin_data,
    }


