"""News and announcement retrieval tools for AI Weekly workflows.

These tools focus on structured press/company announcement collection with
strong date filtering and deterministic official-source RSS coverage.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import feedparser
import structlog

logger = structlog.get_logger(__name__)


_DEFAULT_TIMEOUT_SECONDS = 20

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
