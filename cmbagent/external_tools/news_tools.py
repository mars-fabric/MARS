"""News and announcement retrieval tools for AI Weekly workflows.

These tools focus on structured press/company announcement collection with
strong date filtering and deterministic official-source RSS coverage.
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Dict, List, Optional
from urllib.parse import urlencode, urlparse, parse_qs, unquote
from urllib.request import Request, urlopen

import feedparser
import structlog

logger = structlog.get_logger(__name__)


_DEFAULT_TIMEOUT_SECONDS = 8

_QUERY_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how",
    "in", "into", "is", "it", "latest", "new", "news", "of", "on", "or", "that",
    "the", "their", "these", "this", "to", "updates", "what", "with",
}

_AI_KEYWORDS = {
    "ai", "artificial intelligence", "machine learning", "ml", "llm", "model", "models",
    "genai", "generative", "foundation model", "multimodal", "inference", "agent",
    "vision model", "language model",
}

_NOISE_KEYWORDS = {
    "securities fraud lawsuit", "investors have opportunity", "class action",
    "law firm", "shareholder", "litigation", "bankruptcy", "earnings call",
}


_DEFAULT_RSS_FEEDS: Dict[str, List[str]] = {
    "openai": ["https://openai.com/news/rss.xml"],
    "google": ["https://blog.google/rss/"],
    "microsoft": ["https://blogs.microsoft.com/feed/"],
    "meta": ["https://ai.meta.com/blog/rss/"],
    "anthropic": ["https://www.anthropic.com/news/rss.xml"],
    "nvidia": ["https://nvidianews.nvidia.com/releases?pagetemplate=rss"],
    "prnewswire": ["https://www.prnewswire.com/rss/news-releases-list.rss"],
}

_CURATED_AI_NEWS_SOURCES: List[Dict[str, str]] = [
    {
        "name": "Axios AI",
        "url": "https://www.axios.com/technology/axios-ai",
        "focus": "Breaking news and executive-level insights",
    },
    {
        "name": "The Batch by DeepLearning.AI",
        "url": "https://www.deeplearning.ai/the-batch",
        "focus": "Weekly deep-dive analysis from Andrew Ng",
    },
    {
        "name": "Last Week in AI",
        "url": "https://lastweekin.ai",
        "focus": "Weekly AI news roundup",
    },
    {
        "name": "State of AI Report",
        "url": "https://www.stateof.ai",
        "focus": "Annual comprehensive AI analysis",
    },
    {
        "name": "Google AI Blog",
        "url": "http://blog.google/technology/ai",
        "focus": "Major AI developments from Google",
    },
    {
        "name": "Anthropic News",
        "url": "https://www.anthropic.com/news",
        "focus": "Claude developments and AI safety",
    },
    {
        "name": "Hugging Face Blog",
        "url": "https://huggingface.co/blog",
        "focus": "Open-source AI and model releases",
    },
    {
        "name": "What did OpenAI do this week?",
        "url": "https://www.whatdidopenaido.com",
        "focus": "OpenAI-focused weekly updates",
    },
    {
        "name": "Stanford AI Index",
        "url": "https://aiindex.stanford.edu/report",
        "focus": "Annual AI progress and trends",
    },
    {
        "name": "Gary Marcus on AI",
        "url": "https://garymarcus.substack.com",
        "focus": "Critical AI analysis and research",
    },
    {
        "name": "Goldman Sachs AI Insights",
        "url": "https://www.goldmansachs.com/insights/topics/ai-generated-insights",
        "focus": "Business impact analysis",
    },
    {
        "name": "Sequoia Capital",
        "url": "https://www.sequoiacap.com/article/generative-ai",
        "focus": "Investment trends and startup insights",
    },
    {
        "name": "Exponential View",
        "url": "https://www.exponentialview.co",
        "focus": "AI impact, risks, and regulation",
    },
    {
        "name": "The Rundown AI",
        "url": "https://www.therundown.ai",
        "focus": "Daily AI newsletter (quick summaries)",
    },
    {
        "name": "The Neuron",
        "url": "https://www.theneurondaily.com",
        "focus": "Daily AI insights for weekly compilation",
    },
]


def _parse_iso_date(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        normalized = value.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _parse_pub_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None

    iso_dt = _parse_iso_date(value)
    if iso_dt:
        return iso_dt

    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _normalize_query_terms(query: str) -> List[str]:
    """Extract meaningful query terms from natural-language tool queries."""
    if not query:
        return []

    cleaned = re.sub(r"[()\[\]{}\"']", " ", query.lower())
    raw_terms = re.findall(r"[a-z0-9][a-z0-9+_.-]*", cleaned)

    terms: List[str] = []
    for term in raw_terms:
        if term in {"or", "and", "not"}:
            continue
        if term in _QUERY_STOPWORDS:
            continue
        if len(term) < 2:
            continue
        terms.append(term)
    return terms


def _query_matches_text(text: str, query: str) -> bool:
    """Return True when text plausibly matches the user query.

    Supports practical inputs like:
    - "openai OR anthropic"
    - natural language phrases from planner prompts
    """
    if not query.strip():
        return True

    hay = (text or "").lower()
    q = query.strip().lower()

    # Respect explicit OR expressions first.
    if " or " in q:
        alternatives = [part.strip() for part in re.split(r"\bor\b", q) if part.strip()]
        if alternatives:
            return any(_query_matches_text(hay, alt) for alt in alternatives)

    # If a quoted phrase exists, match phrase directly.
    quoted = re.findall(r'"([^"]+)"', query)
    if quoted and any(phrase.lower() in hay for phrase in quoted):
        return True

    terms = _normalize_query_terms(q)
    if not terms:
        # Fall back to permissive substring match for short/simple query strings.
        return q in hay

    # Require at least one meaningful term to match. This is robust for long natural prompts.
    return any(term in hay for term in terms)


def _is_ai_relevant(item: Dict) -> bool:
    """Lightweight AI relevance check to avoid PR wire false positives."""
    hay = f"{item.get('title', '')} {item.get('summary', '')}".lower()
    if any(keyword in hay for keyword in _NOISE_KEYWORDS):
        return False
    return any(keyword in hay for keyword in _AI_KEYWORDS)


def _in_range(pub_dt: Optional[datetime], from_date: Optional[str], to_date: Optional[str]) -> bool:
    if not pub_dt:
        return False

    from_dt = _parse_iso_date(f"{from_date}T00:00:00+00:00") if from_date else None
    to_dt = _parse_iso_date(f"{to_date}T23:59:59+00:00") if to_date else None

    if from_dt and pub_dt < from_dt:
        return False
    if to_dt and pub_dt > to_dt:
        return False
    return True


def _safe_get_json(url: str, params: Dict[str, str], headers: Optional[Dict[str, str]] = None) -> Dict:
    query = urlencode(params)
    full_url = f"{url}?{query}" if query else url
    req = Request(full_url, headers=headers or {})

    try:
        with urlopen(req, timeout=_DEFAULT_TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8", errors="replace")
            return json.loads(body)
    except Exception as err:
        logger.warning("news_api_request_failed", url=full_url, error=str(err))
        return {"error": str(err), "url": full_url}


def _safe_get_text(url: str, headers: Optional[Dict[str, str]] = None) -> str:
    req = Request(url, headers=headers or {})
    try:
        with urlopen(req, timeout=_DEFAULT_TIMEOUT_SECONDS) as response:
            return response.read().decode("utf-8", errors="replace")
    except Exception as err:
        logger.warning("web_search_request_failed", url=url, error=str(err))
        return ""


def _extract_search_items(html: str, engine: str) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    seen = set()

    if not html:
        return items

    if engine == "duckduckgo":
        pattern = re.compile(r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
        for href, title_html in pattern.findall(html):
            url = unquote(href).strip()
            title = re.sub(r"<[^>]+>", "", unescape(title_html)).strip()
            if not url.startswith("http"):
                continue
            key = (url.lower(), title.lower())
            if key in seen:
                continue
            seen.add(key)
            items.append({"title": title or url, "url": url, "engine": engine})
        return items

    # Generic anchor extraction works reasonably well for Google/Bing/Yahoo fallback.
    for href, title_html in re.findall(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.I | re.S):
        candidate = href.strip()
        if not candidate:
            continue

        if engine == "google" and candidate.startswith("/url?"):
            parsed = urlparse(candidate)
            qs = parse_qs(parsed.query)
            candidate = (qs.get("q") or [""])[0]

        if candidate.startswith("/"):
            continue
        if candidate.startswith("http://") or candidate.startswith("https://"):
            blocked_domains = {
                "google.com", "www.google.com", "bing.com", "www.bing.com",
                "search.yahoo.com", "yahoo.com", "duckduckgo.com", "www.duckduckgo.com",
                "search.brave.com", "brave.com", "www.brave.com",
            }
            domain = (urlparse(candidate).netloc or "").lower()
            if domain in blocked_domains:
                continue

            title = re.sub(r"<[^>]+>", "", unescape(title_html)).strip()
            key = (candidate.lower(), title.lower())
            if key in seen:
                continue
            seen.add(key)
            items.append({"title": title or candidate, "url": candidate, "engine": engine})

    return items


def _ddgs_text_search(query: str, max_results: int = 10) -> List[Dict[str, str]]:
    """Search using the ddgs SDK package (formerly duckduckgo_search).

    Returns a normalised list of {title, url, engine} dicts or an empty list on
    any failure (rate-limit, timeout, etc.).
    """
    try:
        from ddgs import DDGS

        raw = DDGS().text(query, max_results=max(1, max_results), backend="html")
        if not raw:
            return []
        return [
            {
                "title": r.get("title") or r.get("href", ""),
                "url": r.get("href") or r.get("link", ""),
                "engine": "ddgs",
            }
            for r in raw
            if (r.get("href") or r.get("link"))
        ]
    except Exception as err:
        logger.warning("ddgs_sdk_search_failed", query=query, error=str(err))
        return []


def multi_engine_web_search(query: str, max_results: int = 10) -> Dict:
    """Search the web using the duckduckgo_search SDK, falling back to
    HTML scraping of Bing/Yahoo/Brave when the SDK returns nothing.

    This gives planner workflows a resilient no-key fallback path.
    """
    q = (query or "").strip()
    if not q:
        return {"provider": "multi_engine_web_search", "query": query, "count": 0, "items": [], "errors": ["empty query"]}

    errors: List[str] = []
    used_engines: List[str] = []

    # --- Primary: duckduckgo_search SDK (handles rate-limits / retries internally) ---
    sdk_items = _ddgs_text_search(q, max_results=max_results)
    if sdk_items:
        return {
            "provider": "multi_engine_web_search",
            "query": q,
            "engines_used": ["duckduckgo_sdk"],
            "count": len(sdk_items),
            "items": sdk_items,
            "errors": [],
        }
    errors.append("duckduckgo_sdk returned no results")

    # --- Fallback: HTML scraping of Bing/Yahoo/Brave (skip Google to avoid 429) ---
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    }
    fallback_engines = [
        ("bing", f"https://www.bing.com/search?{urlencode({'q': q})}"),
        ("yahoo", f"https://search.yahoo.com/search?{urlencode({'p': q})}"),
        ("brave", f"https://search.brave.com/search?{urlencode({'q': q})}"),
    ]

    aggregated: List[Dict[str, str]] = []
    seen: set = set()

    for engine_name, url in fallback_engines:
        html = _safe_get_text(url, headers=headers)
        if not html:
            errors.append(f"{engine_name} request failed")
            continue
        used_engines.append(engine_name)
        for item in _extract_search_items(html, engine_name):
            key = ((item.get("url") or "").lower(), (item.get("title") or "").lower())
            if key in seen:
                continue
            seen.add(key)
            aggregated.append(item)
            if len(aggregated) >= max(1, max_results):
                break
        if len(aggregated) >= max(1, max_results):
            break

    return {
        "provider": "multi_engine_web_search",
        "query": q,
        "engines_used": used_engines,
        "count": len(aggregated),
        "items": aggregated,
        "errors": errors,
    }


def curated_ai_sources_catalog() -> Dict:
    """Return curated AI news sources for planner/researcher tool guidance."""
    return {
        "provider": "curated_ai_sources_catalog",
        "count": len(_CURATED_AI_NEWS_SOURCES),
        "sources": _CURATED_AI_NEWS_SOURCES,
    }


# Delay (seconds) between per-source searches to respect rate limits.
_CURATED_SEARCH_INTER_SOURCE_DELAY = 1.0


def curated_ai_sources_search(query: str, limit: int = 40) -> Dict:
    """Search across curated AI sources with resilient multi-engine fallback.

    Uses the duckduckgo_search SDK (preferred) with a short inter-source
    delay to stay within rate limits.  Falls back to HTML scraping when
    the SDK returns nothing.
    """
    q = (query or "").strip()
    results: List[Dict[str, str]] = []
    seen = set()
    cap = max(1, min(limit, 100))

    for idx, source in enumerate(_CURATED_AI_NEWS_SOURCES):
        if len(results) >= cap:
            break

        source_url = source.get("url", "")
        domain = (urlparse(source_url).netloc or "").lower().replace("www.", "")
        if not domain:
            continue

        # Polite delay between sources (skip before the first request).
        if idx > 0:
            time.sleep(_CURATED_SEARCH_INTER_SOURCE_DELAY)

        scoped_query = f"site:{domain} {q}".strip()
        found = multi_engine_web_search(scoped_query, max_results=4)

        for item in found.get("items") or []:
            item_url = item.get("url") or ""
            # Accept results whose URL contains the target domain.
            if domain not in (urlparse(item_url).netloc or "").lower():
                continue
            key = (item_url.lower(), (item.get("title") or "").lower())
            if key in seen:
                continue
            seen.add(key)
            results.append(
                {
                    "title": item.get("title") or item_url,
                    "url": item_url,
                    "source": source.get("name"),
                    "focus": source.get("focus"),
                    "engine": item.get("engine"),
                    "source_home": source_url,
                }
            )
            if len(results) >= cap:
                break

    return {
        "provider": "curated_ai_sources_search",
        "query": q,
        "count": len(results),
        "items": results,
        "sources_considered": len(_CURATED_AI_NEWS_SOURCES),
    }


def _normalize_articles(raw_items: List[Dict], from_date: Optional[str], to_date: Optional[str], source: str) -> List[Dict]:
    normalized: List[Dict] = []
    seen = set()

    for item in raw_items:
        url = item.get("url") or item.get("link") or ""
        title = (item.get("title") or "").strip()
        published_at = item.get("publishedAt") or item.get("pubDate") or item.get("published")
        pub_dt = _parse_pub_datetime(published_at)

        if not url or not title:
            continue
        if not _in_range(pub_dt, from_date, to_date):
            continue

        key = (url.strip().lower(), title.lower())
        if key in seen:
            continue
        seen.add(key)

        source_name = source
        if isinstance(item.get("source"), dict):
            source_name = item["source"].get("name") or source

        normalized.append(
            {
                "title": title,
                "url": url,
                "source": source_name,
                "published_at": pub_dt.isoformat() if pub_dt else None,
                "summary": (item.get("description") or item.get("summary") or "").strip(),
            }
        )

    normalized.sort(key=lambda x: x.get("published_at") or "", reverse=True)
    return normalized


def newsapi_search(
    query: str,
    from_date: str,
    to_date: str,
    domains: str = "",
    language: str = "en",
    page_size: int = 50,
) -> Dict:
    """Search NewsAPI for structured articles in a strict date range.

    Requires: NEWSAPI_KEY
    """
    api_key = os.getenv("NEWSAPI_KEY", "").strip()
    if not api_key:
        return {"error": "NEWSAPI_KEY not configured", "articles": []}

    params = {
        "q": query,
        "from": from_date,
        "to": to_date,
        "language": language,
        "sortBy": "publishedAt",
        "pageSize": str(max(1, min(page_size, 100))),
        "apiKey": api_key,
    }
    if domains.strip():
        params["domains"] = domains.strip()

    payload = _safe_get_json("https://newsapi.org/v2/everything", params)
    if payload.get("error"):
        return {"error": payload["error"], "articles": []}

    raw_articles = payload.get("articles") or []
    return {
        "provider": "newsapi",
        "query": query,
        "count": len(raw_articles),
        "articles": _normalize_articles(raw_articles, from_date, to_date, "NewsAPI"),
    }


def gnews_search(
    query: str,
    from_date: str,
    to_date: str,
    in_sites: str = "",
    language: str = "en",
    max_results: int = 50,
) -> Dict:
    """Search GNews for structured articles in a strict date range.

    Requires: GNEWS_API_KEY
    """
    api_key = os.getenv("GNEWS_API_KEY", "").strip()
    if not api_key:
        return {"error": "GNEWS_API_KEY not configured", "articles": []}

    q = query.strip()
    if in_sites.strip():
        q = f"{q} {in_sites.strip()}"

    params = {
        "q": q,
        "from": f"{from_date}T00:00:00Z",
        "to": f"{to_date}T23:59:59Z",
        "lang": language,
        "max": str(max(1, min(max_results, 100))),
        "apikey": api_key,
    }

    payload = _safe_get_json("https://gnews.io/api/v4/search", params)
    if payload.get("error"):
        return {"error": payload["error"], "articles": []}

    raw_articles = payload.get("articles") or []
    return {
        "provider": "gnews",
        "query": q,
        "count": len(raw_articles),
        "articles": _normalize_articles(raw_articles, from_date, to_date, "GNews"),
    }


def rss_company_announcements(
    company: str = "",
    from_date: str = "",
    to_date: str = "",
    limit: int = 50,
) -> Dict:
    """Collect official company/newsroom announcements from curated RSS feeds."""
    key = company.strip().lower()
    selected: Dict[str, List[str]]

    if key:
        urls = _DEFAULT_RSS_FEEDS.get(key)
        if not urls:
            return {
                "error": f"Unknown company '{company}'. Supported: {', '.join(sorted(_DEFAULT_RSS_FEEDS.keys()))}",
                "items": [],
            }
        selected = {key: urls}
    else:
        selected = _DEFAULT_RSS_FEEDS

    items: List[Dict] = []
    dedupe = set()

    for source_name, urls in selected.items():
        for feed_url in urls:
            parsed = feedparser.parse(feed_url)
            for entry in parsed.entries:
                link = (entry.get("link") or "").strip()
                title = (entry.get("title") or "").strip()
                published = entry.get("published") or entry.get("updated") or ""
                pub_dt = _parse_pub_datetime(published)

                if not link or not title or not _in_range(pub_dt, from_date or None, to_date or None):
                    continue

                dedupe_key = (link.lower(), title.lower())
                if dedupe_key in dedupe:
                    continue
                dedupe.add(dedupe_key)

                items.append(
                    {
                        "title": title,
                        "url": link,
                        "source": source_name,
                        "published_at": pub_dt.isoformat() if pub_dt else None,
                        "summary": (entry.get("summary") or "").strip(),
                        "feed": feed_url,
                    }
                )

    items.sort(key=lambda x: x.get("published_at") or "", reverse=True)
    return {
        "provider": "official_rss",
        "company": key or "all",
        "count": len(items),
        "items": items[: max(1, min(limit, 200))],
    }


def prwire_search(query: str, from_date: str = "", to_date: str = "", limit: int = 50) -> Dict:
    """Search PR wire announcements using curated PR Newswire RSS feed.

    This keeps integration deterministic without requiring proprietary paid SDKs.
    """
    base_items = rss_company_announcements(company="prnewswire", from_date=from_date, to_date=to_date, limit=200)
    items = base_items.get("items") or []

    # PR feeds can contain large amounts of finance/legal noise; keep AI-relevant items.
    items = [item for item in items if _is_ai_relevant(item)]

    q = query.strip()
    if q:
        items = [
            item for item in items
            if _query_matches_text(f"{item.get('title', '')} {item.get('summary', '')}", q)
        ]

    return {
        "provider": "prwire_rss",
        "query": query,
        "count": len(items),
        "items": items[: max(1, min(limit, 200))],
    }


def announcements_noauth(
    query: str = "",
    company: str = "",
    from_date: str = "",
    to_date: str = "",
    limit: int = 100,
) -> Dict:
    """Keyless press/company announcement retrieval.

    Uses only free, no-auth sources:
    1) Official company newsroom/blog RSS feeds
    2) PR Newswire RSS feed
    """
    rss_result = rss_company_announcements(
        company=company,
        from_date=from_date,
        to_date=to_date,
        limit=200,
    )

    rss_items = rss_result.get("items") or []
    # Pass query through so PR filtering can leverage user intent and avoid generic noise.
    pr_result = prwire_search(query=query, from_date=from_date, to_date=to_date, limit=200)
    pr_items = pr_result.get("items") or []

    merged: List[Dict] = []
    seen = set()
    for item in rss_items + pr_items:
        key = ((item.get("url") or "").lower(), (item.get("title") or "").lower())
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)

    q = query.strip()
    if q:
        merged = [
            item for item in merged
            if _query_matches_text(f"{item.get('title', '')} {item.get('summary', '')}", q)
        ]

    merged.sort(key=lambda x: x.get("published_at") or "", reverse=True)

    return {
        "provider": "announcements_noauth",
        "query": query,
        "company": company or "all",
        "count": len(merged),
        "items": merged[: max(1, min(limit, 300))],
    }
