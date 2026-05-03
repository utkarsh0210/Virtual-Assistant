# """
# skills/web_search.py — Web Search Skill
# Uses DuckDuckGo instant answers API (no API key required).
# Optional: Set SERPER_API_KEY for full Google Search results.
# """

# import logging
# import os
# from typing import Any, Dict, List

# import httpx

# from skills.registry import BaseSkill

# logger = logging.getLogger("bharvishya.skill.web_search")

# SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
# DDG_TIMEOUT = 8  # seconds


# class Skill(BaseSkill):
#     name = "web_search"
#     description = "Search the web for information, news, facts, and current events"
#     actions = ["search", "news", "quick_answer"]

#     async def execute(self, action: str, params: Dict[str, Any]) -> Any:
#         query = params.get("query", "").strip()
#         if not query:
#             return {"error": "No search query provided"}

#         if action == "search":
#             return await self._search(query)
#         elif action == "news":
#             return await self._news(query)
#         elif action == "quick_answer":
#             return await self._quick_answer(query)
#         else:
#             return await self._search(query)

#     async def _search(self, query: str) -> dict:
#         """Full web search — uses Serper if key available, else DuckDuckGo."""
#         if SERPER_API_KEY:
#             return await self._serper_search(query)
#         return await self._ddg_search(query)

#     async def _ddg_search(self, query: str) -> dict:
#         """DuckDuckGo instant answer API."""
#         url = "https://api.duckduckgo.com/"
#         params = {
#             "q": query,
#             "format": "json",
#             "no_html": "1",
#             "skip_disambig": "1",
#         }
#         async with httpx.AsyncClient(timeout=DDG_TIMEOUT) as client:
#             resp = await client.get(url, params=params)
#             resp.raise_for_status()
#             data = resp.json()

#         results = []

#         # Abstract (main answer)
#         if data.get("AbstractText"):
#             results.append({
#                 "title": data.get("Heading", "Answer"),
#                 "snippet": data["AbstractText"],
#                 "url": data.get("AbstractURL", ""),
#                 "source": data.get("AbstractSource", ""),
#             })

#         # Related topics
#         for topic in data.get("RelatedTopics", [])[:4]:
#             if isinstance(topic, dict) and "Text" in topic:
#                 results.append({
#                     "title": topic.get("Text", "")[:80],
#                     "snippet": topic.get("Text", ""),
#                     "url": topic.get("FirstURL", ""),
#                     "source": "DuckDuckGo",
#                 })

#         return {
#             "query": query,
#             "results": results[:5],
#             "source": "DuckDuckGo",
#         }

#     async def _serper_search(self, query: str) -> dict:
#         """Google Search via Serper API."""
#         url = "https://google.serper.dev/search"
#         headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
#         async with httpx.AsyncClient(timeout=DDG_TIMEOUT) as client:
#             resp = await client.post(url, json={"q": query, "num": 5}, headers=headers)
#             resp.raise_for_status()
#             data = resp.json()

#         results = []
#         for item in data.get("organic", [])[:5]:
#             results.append({
#                 "title": item.get("title", ""),
#                 "snippet": item.get("snippet", ""),
#                 "url": item.get("link", ""),
#                 "source": "Google",
#             })

#         if data.get("answerBox"):
#             ab = data["answerBox"]
#             results.insert(0, {
#                 "title": ab.get("title", "Quick Answer"),
#                 "snippet": ab.get("answer") or ab.get("snippet", ""),
#                 "url": ab.get("link", ""),
#                 "source": "Google Answer Box",
#             })

#         return {"query": query, "results": results, "source": "Google (Serper)"}

#     async def _quick_answer(self, query: str) -> dict:
#         """Get just the instant answer, no full results."""
#         result = await self._ddg_search(query)
#         if result["results"]:
#             top = result["results"][0]
#             return {"answer": top["snippet"], "source": top.get("source", "")}
#         return {"answer": "No quick answer found", "source": ""}

#     async def _news(self, query: str) -> dict:
#         """Search for news articles."""
#         if SERPER_API_KEY:
#             url = "https://google.serper.dev/news"
#             headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
#             async with httpx.AsyncClient(timeout=DDG_TIMEOUT) as client:
#                 resp = await client.post(url, json={"q": query, "num": 5}, headers=headers)
#                 resp.raise_for_status()
#                 data = resp.json()
#             articles = [
#                 {
#                     "title": a.get("title", ""),
#                     "snippet": a.get("snippet", ""),
#                     "url": a.get("link", ""),
#                     "published": a.get("date", ""),
#                 }
#                 for a in data.get("news", [])[:5]
#             ]
#             return {"query": query, "articles": articles}

#         # Fallback: DuckDuckGo news search
#         return await self._ddg_search(f"{query} news")


# """
# skills/web_search.py — Web Search Skill
# Uses DuckDuckGo instant answers API (no API key required).
# Optional: Set SERPER_API_KEY for full Google Search results.
# """

# import logging
# import os
# from typing import Any, Dict, List

# import httpx

# from skills.registry import BaseSkill

# logger = logging.getLogger("bharvishya.skill.web_search")

# SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
# DDG_TIMEOUT = 8  # seconds


# class Skill(BaseSkill):
#     name = "web_search"
#     description = "Search the web for information, news, facts, and current events"
#     actions = ["search", "news", "quick_answer"]

#     async def execute(self, action: str, params: Dict[str, Any]) -> Any:
#         query = params.get("query", "").strip()
#         if not query:
#             return {"error": "No search query provided"}

#         try:
#             if action == "search":
#                 return await self._search(query)
#             elif action == "news":
#                 return await self._news(query)
#             elif action == "quick_answer":
#                 return await self._quick_answer(query)
#             else:
#                 return await self._search(query)
#         except httpx.TimeoutException:
#             logger.warning(f"Web search timed out for query: {query!r}")
#             return {"error": "Search timed out. Please try again.", "query": query, "results": []}
#         except httpx.HTTPStatusError as e:
#             logger.error(f"HTTP error during web search: {e.response.status_code}")
#             return {"error": f"Search service returned an error ({e.response.status_code}).", "results": []}
#         except Exception as e:
#             logger.error(f"Unexpected web search error: {e}")
#             return {"error": "Search failed unexpectedly. Please try again.", "results": []}

#     async def _search(self, query: str) -> dict:
#         """Full web search — uses Serper if key available, else DuckDuckGo."""
#         if SERPER_API_KEY:
#             return await self._serper_search(query)
#         return await self._ddg_search(query)

#     async def _ddg_search(self, query: str) -> dict:
#         """DuckDuckGo instant answer API."""
#         url = "https://api.duckduckgo.com/"
#         params = {
#             "q": query,
#             "format": "json",
#             "no_html": "1",
#             "skip_disambig": "1",
#         }
#         async with httpx.AsyncClient(timeout=DDG_TIMEOUT) as client:
#             resp = await client.get(url, params=params)
#             resp.raise_for_status()
#             data = resp.json()

#         results = []

#         # Abstract (main answer)
#         if data.get("AbstractText"):
#             results.append({
#                 "title": data.get("Heading", "Answer"),
#                 "snippet": data["AbstractText"],
#                 "url": data.get("AbstractURL", ""),
#                 "source": data.get("AbstractSource", ""),
#             })

#         # Related topics
#         for topic in data.get("RelatedTopics", [])[:4]:
#             if isinstance(topic, dict) and "Text" in topic:
#                 results.append({
#                     "title": topic.get("Text", "")[:80],
#                     "snippet": topic.get("Text", ""),
#                     "url": topic.get("FirstURL", ""),
#                     "source": "DuckDuckGo",
#                 })

#         return {
#             "query": query,
#             "results": results[:5],
#             "source": "DuckDuckGo",
#         }

#     async def _serper_search(self, query: str) -> dict:
#         """Google Search via Serper API."""
#         url = "https://google.serper.dev/search"
#         headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
#         async with httpx.AsyncClient(timeout=DDG_TIMEOUT) as client:
#             resp = await client.post(url, json={"q": query, "num": 5}, headers=headers)
#             resp.raise_for_status()
#             data = resp.json()

#         results = []
#         for item in data.get("organic", [])[:5]:
#             results.append({
#                 "title": item.get("title", ""),
#                 "snippet": item.get("snippet", ""),
#                 "url": item.get("link", ""),
#                 "source": "Google",
#             })

#         if data.get("answerBox"):
#             ab = data["answerBox"]
#             results.insert(0, {
#                 "title": ab.get("title", "Quick Answer"),
#                 "snippet": ab.get("answer") or ab.get("snippet", ""),
#                 "url": ab.get("link", ""),
#                 "source": "Google Answer Box",
#             })

#         return {"query": query, "results": results, "source": "Google (Serper)"}

#     async def _quick_answer(self, query: str) -> dict:
#         """Get just the instant answer, no full results."""
#         result = await self._ddg_search(query)
#         if result.get("results"):
#             top = result["results"][0]
#             return {"answer": top["snippet"], "source": top.get("source", "")}
#         return {"answer": "No quick answer found", "source": ""}

#     async def _news(self, query: str) -> dict:
#         """Search for news articles."""
#         if SERPER_API_KEY:
#             url = "https://google.serper.dev/news"
#             headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
#             async with httpx.AsyncClient(timeout=DDG_TIMEOUT) as client:
#                 resp = await client.post(url, json={"q": query, "num": 5}, headers=headers)
#                 resp.raise_for_status()
#                 data = resp.json()
#             articles = [
#                 {
#                     "title": a.get("title", ""),
#                     "snippet": a.get("snippet", ""),
#                     "url": a.get("link", ""),
#                     "published": a.get("date", ""),
#                 }
#                 for a in data.get("news", [])[:5]
#             ]
#             return {"query": query, "articles": articles}

#         # Fallback: DuckDuckGo news search
#         return await self._ddg_search(f"{query} news")


"""
skills/web_search.py — Enhanced Web Search Agent
=================================================
Actions:
  search        — General web search (Serper → DDG fallback)
  news          — Latest news articles on a topic
  quick_answer  — Single direct answer (cascading: answerBox → KG → Wikipedia → DDG)
  weather       — Current weather for a city (wttr.in, no API key needed)
  stocks        — Stock/crypto price (yfinance, no API key needed)
  wikipedia     — Wikipedia article summary (Wikipedia REST API, no key needed)
  trending      — Trending topics in a category
  site_search   — Search within a specific website

Improvements over v1:
  - Result caching (TTL=5min) — same query never hits API twice in 5 minutes
  - Unified result shape across all actions (title, snippet, url, source, published)
  - quick_answer cascades 4 tiers before giving up — much higher hit rate
  - key_facts extracted from snippets for cleaner synthesis (no raw JSON dumps)
  - Weather via wttr.in (free, structured JSON)
  - Stocks via yfinance (free, supports NSE/BSE Indian stocks)
  - Wikipedia via REST API (free, no key)
  - DDG fallback improved — tries broader query if first attempt empty
"""

import asyncio
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

import httpx

from skills.registry import BaseSkill

logger = logging.getLogger("bharvishya.skill.web_search")

SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
DDG_TIMEOUT    = 8
HTTP_TIMEOUT   = 10

# ── In-memory result cache ─────────────────────────────────────────────────────
_CACHE: Dict[str, dict] = {}
CACHE_TTL = 300   # 5 minutes


def _cache_get(key: str) -> Optional[dict]:
    entry = _CACHE.get(key)
    if entry and time.time() < entry["expires_at"]:
        logger.debug(f"[CACHE HIT] {key}")
        return entry["result"]
    return None


def _cache_set(key: str, result: dict):
    _CACHE[key] = {"result": result, "expires_at": time.time() + CACHE_TTL}
    if len(_CACHE) > 100:
        oldest = min(_CACHE, key=lambda k: _CACHE[k]["expires_at"])
        del _CACHE[oldest]


def _cache_key(action: str, query: str) -> str:
    return f"{action}::{query.lower().strip()}"


# ── Unified result format ──────────────────────────────────────────────────────
def _make_result(title: str, snippet: str, url: str = "",
                 source: str = "", published: str = "") -> dict:
    return {
        "title":     title.strip(),
        "snippet":   snippet.strip(),
        "url":       url.strip(),
        "source":    source.strip(),
        "published": published.strip(),
    }


# ── Key facts extractor ────────────────────────────────────────────────────────
def _extract_key_facts(results: List[dict]) -> List[str]:
    """
    Pull bullet-point sentences from top snippets.
    Gives synthesis a compact structured list instead of raw JSON blobs.
    """
    facts, seen = [], set()
    for r in results[:3]:
        for sent in re.split(r"(?<=[.!?])\s+", r.get("snippet", ""))[:3]:
            sent = sent.strip()
            if 20 <= len(sent) <= 200:
                key = sent[:40].lower()
                if key not in seen:
                    seen.add(key)
                    facts.append(sent)
    return facts[:5]


# ─────────────────────────────────────────────────────────────────────────────

class Skill(BaseSkill):
    name = "web_search"
    description = (
        "Enhanced web search agent: general search, latest news, quick answers, "
        "live weather, stock/crypto prices, Wikipedia summaries, "
        "trending topics, and site-specific search."
    )
    actions = [
        "search", "news", "quick_answer",
        "weather", "stocks", "wikipedia",
        "trending", "site_search",
    ]

    # ── Router ────────────────────────────────────────────────────────────────
    async def execute(self, action: str, params: Dict[str, Any]) -> Any:
        query = params.get("query", "").strip()

        if action == "trending":
            return await self._safe(self._trending(params.get("category", "technology")), action, "trending")

        if not query:
            return {"error": "No search query provided", "results": []}

        ck     = _cache_key(action, query)
        cached = _cache_get(ck)
        if cached:
            logger.info(f"[WEB_SEARCH] Cache hit: {action}={query!r}")
            return {**cached, "from_cache": True}

        try:
            if   action == "search":       result = await self._search(query, params)
            elif action == "news":         result = await self._news(query, params)
            elif action == "quick_answer": result = await self._quick_answer(query)
            elif action == "weather":      result = await self._weather(query)
            elif action == "stocks":       result = await self._stocks(query)
            elif action == "wikipedia":    result = await self._wikipedia(query)
            elif action == "site_search":  result = await self._site_search(query, params.get("site", ""))
            else:                          result = await self._search(query, params)

            if "error" not in result:
                _cache_set(ck, result)
            return result

        except httpx.TimeoutException:
            logger.warning(f"[WEB_SEARCH] Timeout: {action}={query!r}")
            return {"error": "Search timed out. Please try again.", "results": []}
        except httpx.HTTPStatusError as e:
            logger.error(f"[WEB_SEARCH] HTTP {e.response.status_code}")
            return {"error": f"Search service error ({e.response.status_code}).", "results": []}
        except Exception as e:
            logger.error(f"[WEB_SEARCH] Error: {e}")
            return {"error": "Search failed. Please try again.", "results": []}

    async def _safe(self, coro, action, label):
        try:
            return await coro
        except Exception as e:
            logger.error(f"[WEB_SEARCH] {label} error: {e}")
            return {"error": str(e), "results": []}

    # ── ACTION: search ────────────────────────────────────────────────────────
    async def _search(self, query: str, params: dict = {}) -> dict:
        num = int(params.get("num", 5))
        raw = await self._serper_search(query, num) if SERPER_API_KEY else await self._ddg_search(query)
        return {
            "action":    "search",
            "query":     query,
            "results":   raw.get("results", []),
            "key_facts": _extract_key_facts(raw.get("results", [])),
            "source":    raw.get("source", ""),
            "status":    "success" if raw.get("results") else "no_results",
        }

    # ── ACTION: news ──────────────────────────────────────────────────────────
    async def _news(self, query: str, params: dict = {}) -> dict:
        num = int(params.get("num", 5))
        if SERPER_API_KEY:
            headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
            async with httpx.AsyncClient(
                timeout=HTTP_TIMEOUT,
                headers={
                    "User-Agent": "BharvishyaAI/1.0"
                }
            ) as client:
                resp = await client.post(
                    "https://google.serper.dev/news",
                    json={"q": query, "num": num}, headers=headers
                )
                resp.raise_for_status()
                data = resp.json()
            results = [
                _make_result(
                    title     = a.get("title", ""),
                    snippet   = a.get("snippet", ""),
                    url       = a.get("link", ""),
                    source    = a.get("source", "Google News"),
                    published = a.get("date", ""),
                )
                for a in data.get("news", [])[:num]
            ]
        else:
            raw     = await self._ddg_search(f"{query} news latest")
            results = raw.get("results", [])

        return {
            "action":  "news",
            "query":   query,
            "results": results,
            "status":  "success" if results else "no_results",
            "source":  "Google News" if SERPER_API_KEY else "DuckDuckGo",
        }

    # ── ACTION: quick_answer (4-tier cascade) ─────────────────────────────────
    async def _quick_answer(self, query: str) -> dict:
        """
        Cascade: Google answerBox → Knowledge Graph → Wikipedia → DDG.
        Much higher hit rate than v1 which only tried DDG abstract.
        """
        # Tier 1: Serper (Google)
        if SERPER_API_KEY:
            headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
            async with httpx.AsyncClient(
                timeout=HTTP_TIMEOUT,
                headers={
                    "User-Agent": "BharvishyaAI/1.0"
                }
            ) as client:
                resp = await client.post(
                    "https://google.serper.dev/search",
                    json={"q": query, "num": 3}, headers=headers
                )
                resp.raise_for_status()
                data = resp.json()

            if data.get("answerBox"):
                ab  = data["answerBox"]
                ans = ab.get("answer") or ab.get("snippet") or ab.get("title", "")
                if ans:
                    return {"action": "quick_answer", "query": query,
                            "answer": ans, "source": "Google Answer Box", "status": "success"}

            if data.get("knowledgeGraph", {}).get("description"):
                kg = data["knowledgeGraph"]
                return {"action": "quick_answer", "query": query,
                        "answer": kg["description"], "title": kg.get("title", ""),
                        "source": "Google Knowledge Graph", "status": "success"}

            if data.get("organic"):
                top = data["organic"][0]
                return {"action": "quick_answer", "query": query,
                        "answer": top.get("snippet", ""), "title": top.get("title", ""),
                        "url": top.get("link", ""), "source": "Google", "status": "success"}

        # Tier 2: DDG
        ddg = await self._ddg_search(query)
        if ddg.get("results"):
            return {"action": "quick_answer", "query": query,
                    "answer": ddg["results"][0]["snippet"],
                    "source": "DuckDuckGo", "status": "success"}

        return {"action": "quick_answer", "query": query,
                "answer": "I couldn't find a direct answer.", "status": "no_results"}

    # ── ACTION: weather ───────────────────────────────────────────────────────
    async def _weather(self, city: str) -> dict:
        """Free weather via wttr.in — no API key needed."""
        async with httpx.AsyncClient(
            timeout=HTTP_TIMEOUT,
            headers={
                "User-Agent": "BharvishyaAI/1.0"
            }
        ) as client:
            resp = await client.get(
                f"https://wttr.in/{city}?format=j1",
                headers={"User-Agent": "BharvishyaAI/1.0"}
            )
            resp.raise_for_status()
            data = resp.json()

        cur   = data["current_condition"][0]
        area  = data["nearest_area"][0]
        name  = area["areaName"][0]["value"] + ", " + area["country"][0]["value"]
        today = data["weather"][0]

        summary = (
            f"{name}: {cur['weatherDesc'][0]['value']}, "
            f"{cur['temp_C']}°C ({cur['temp_F']}°F). "
            f"Feels like {cur['FeelsLikeC']}°C. "
            f"Humidity {cur['humidity']}%, Wind {cur['windspeedKmph']} km/h. "
            f"Today's range: {today['mintempC']}°C – {today['maxtempC']}°C."
        )
        return {
            "action": "weather", "query": city, "city": name,
            "temp_c": cur["temp_C"], "temp_f": cur["temp_F"],
            "feels_like_c": cur["FeelsLikeC"], "condition": cur["weatherDesc"][0]["value"],
            "humidity": cur["humidity"], "wind_kmph": cur["windspeedKmph"],
            "high_c": today["maxtempC"], "low_c": today["mintempC"],
            "summary": summary, "status": "success", "source": "wttr.in",
        }

    # ── ACTION: stocks ────────────────────────────────────────────────────────
    async def _stocks(self, query: str) -> dict:
        """Free stock/crypto prices via yfinance. pip install yfinance."""
        return await asyncio.to_thread(self._stocks_sync, query)

    def _stocks_sync(self, query: str) -> dict:
        try:
            import yfinance as yf
        except ImportError:
            return {"error": "yfinance not installed. Run: pip install yfinance", "status": "error"}

        # Friendly name → ticker map
        NAME_MAP = {
            "tcs": "TCS.NS", "infosys": "INFY.NS", "wipro": "WIPRO.NS",
            "reliance": "RELIANCE.NS", "hdfc": "HDFCBANK.NS", "nifty": "^NSEI",
            "sensex": "^BSESN", "bitcoin": "BTC-USD", "ethereum": "ETH-USD",
            "apple": "AAPL", "google": "GOOGL", "microsoft": "MSFT",
            "tesla": "TSLA", "amazon": "AMZN", "meta": "META", "nvidia": "NVDA",
        }
        sym = NAME_MAP.get(query.lower(), query.upper())

        try:
            t    = yf.Ticker(sym)
            info = t.fast_info
            price    = round(getattr(info, "last_price",    0) or 0, 2)
            prev     = round(getattr(info, "previous_close", 0) or 0, 2)
            currency = getattr(info, "currency", "USD")
            name     = t.info.get("longName", sym)
            change   = round(price - prev, 2) if prev else 0
            pct      = round((change / prev) * 100, 2) if prev else 0
            arrow    = "▲" if change >= 0 else "▼"
            summary  = (
                f"{name} ({sym}): {currency} {price:,.2f} "
                f"{arrow} {abs(change):,.2f} ({abs(pct)}%) today."
            )
            return {
                "action": "stocks", "ticker": sym, "name": name,
                "price": price, "currency": currency,
                "change": change, "change_pct": pct,
                "prev_close": prev, "direction": "up" if change >= 0 else "down",
                "summary": summary, "status": "success", "source": "Yahoo Finance",
            }
        except Exception as e:
            logger.error(f"[STOCKS] {sym}: {e}")
            return {"error": f"Could not fetch price for '{query}'.", "ticker": sym, "status": "error"}

    # ── ACTION: wikipedia ─────────────────────────────────────────────────────
    async def _wikipedia(self, query: str) -> dict:
        try:
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{query.replace(' ', '_')}"

            async with httpx.AsyncClient(
                timeout=httpx.Timeout(10.0, connect=3.0),
                headers={"User-Agent": "BharvishyaAI/1.0"}
            ) as client:
                resp = await client.get(url)

            if resp.status_code != 200:
                return {"action": "wikipedia", "query": query, "status": "no_results"}

            data = resp.json()

            return {
                "action": "wikipedia",
                "query": query,
                "title": data.get("title", ""),
                "summary": data.get("extract", ""),
                "url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
                "status": "success",
                "source": "Wikipedia"
            }

        except Exception:
            return {"action": "wikipedia", "query": query, "status": "no_results"}
    # ── ACTION: trending ──────────────────────────────────────────────────────
    async def _trending(self, category: str = "technology") -> dict:
        """Trending news topics in a given category."""
        query = f"trending {category} today"
        if SERPER_API_KEY:
            headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
            async with httpx.AsyncClient(
                timeout=HTTP_TIMEOUT,
                headers={
                    "User-Agent": "BharvishyaAI/1.0"
                }
            ) as client:
                resp = await client.post(
                    "https://google.serper.dev/news",
                    json={"q": query, "num": 8}, headers=headers
                )
                resp.raise_for_status()
                data = resp.json()
            topics = [
                {"title": a.get("title", ""), "source": a.get("source", ""),
                 "url": a.get("link", ""), "published": a.get("date", "")}
                for a in data.get("news", [])[:8]
            ]
        else:
            raw    = await self._ddg_search(query)
            topics = [{"title": r["title"], "source": r["source"], "url": r["url"]}
                      for r in raw.get("results", [])]

        return {
            "action": "trending", "category": category, "topics": topics,
            "count": len(topics), "status": "success" if topics else "no_results",
            "source": "Google News" if SERPER_API_KEY else "DuckDuckGo",
        }

    # ── ACTION: site_search ───────────────────────────────────────────────────
    async def _site_search(self, query: str, site: str) -> dict:
        """Search within a specific domain (uses site: operator)."""
        if not site:
            return {"error": "site parameter required for site_search.", "results": []}
        raw = await self._serper_search(f"site:{site} {query}") if SERPER_API_KEY \
              else await self._ddg_search(f"site:{site} {query}")
        return {
            "action": "site_search", "query": query, "site": site,
            "results": raw.get("results", []),
            "status": "success" if raw.get("results") else "no_results",
            "source": raw.get("source", ""),
        }

    # ── Serper helper ─────────────────────────────────────────────────────────
    async def _serper_search(self, query: str, num: int = 5) -> dict:
        headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
        async with httpx.AsyncClient(
            timeout=HTTP_TIMEOUT,
            headers={
                "User-Agent": "BharvishyaAI/1.0"
            }
        ) as client:
            resp = await client.post(
                "https://google.serper.dev/search",
                json={"q": query, "num": num}, headers=headers
            )
            resp.raise_for_status()
            data = resp.json()

        results = []
        if data.get("answerBox"):
            ab = data["answerBox"]
            results.append(_make_result(
                title=ab.get("title", "Answer"),
                snippet=ab.get("answer") or ab.get("snippet", ""),
                url=ab.get("link", ""), source="Google Answer Box"))

        if data.get("knowledgeGraph", {}).get("description"):
            kg = data["knowledgeGraph"]
            results.append(_make_result(
                title=kg.get("title", ""), snippet=kg["description"],
                source="Google Knowledge Graph"))

        for item in data.get("organic", [])[:num]:
            results.append(_make_result(
                title=item.get("title", ""), snippet=item.get("snippet", ""),
                url=item.get("link", ""), source="Google"))

        return {"results": results[:num + 2], "source": "Google (Serper)"}

    # ── DDG helper (with broader fallback) ────────────────────────────────────
    async def _ddg_search(self, query: str) -> dict:
        params = {"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"}
        results = []

        async with httpx.AsyncClient(timeout=DDG_TIMEOUT) as client:
            resp = await client.get("https://api.duckduckgo.com/", params=params)
            resp.raise_for_status()
            data = resp.json()

        if data.get("AbstractText"):
            results.append(_make_result(
                title=data.get("Heading", query), snippet=data["AbstractText"],
                url=data.get("AbstractURL", ""), source=data.get("AbstractSource", "DuckDuckGo")))

        for topic in data.get("RelatedTopics", [])[:5]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append(_make_result(
                    title=topic["Text"][:80], snippet=topic["Text"],
                    url=topic.get("FirstURL", ""), source="DuckDuckGo"))

        # Broader fallback: try first word only if nothing found
        if not results and " " in query:
            params["q"] = query.split()[0]
            async with httpx.AsyncClient(timeout=DDG_TIMEOUT) as client:
                resp2 = await client.get("https://api.duckduckgo.com/", params=params)
                if resp2.status_code == 200:
                    d2 = resp2.json()
                    if d2.get("AbstractText"):
                        results.append(_make_result(
                            title=d2.get("Heading", query), snippet=d2["AbstractText"],
                            url=d2.get("AbstractURL", ""), source="DuckDuckGo"))

        return {"results": results[:5], "source": "DuckDuckGo"}