"""News and announcement retrieval tools for AI Weekly workflows.

These tools focus on structured press/company announcement collection with
strong date filtering, direct page scraping, RSS feeds for blocked sites,
and web-search fallback.
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


_CURATED_AI_NEWS_SOURCES: List[Dict[str, str]] = [
    # ── AI / ML / Foundation Models (primary, authoritative) ──
    {"name": "OpenAI Blog", "url": "https://openai.com/blog"},
    {"name": "Google AI Blog", "url": "https://ai.googleblog.com"},
    {"name": "Google Cloud AI Blog", "url": "https://cloud.google.com/blog/products/ai-machine-learning"},
    {"name": "Google Research Blog", "url": "https://research.google/blog"},
    {"name": "DeepMind Blog", "url": "https://deepmind.google/discover/blog"},
    {"name": "Microsoft AI Blog", "url": "https://www.microsoft.com/en-us/ai/blog"},
    {"name": "Microsoft Research Blog", "url": "https://www.microsoft.com/en-us/research/blog"},
    {"name": "Azure AI Blog", "url": "https://azure.microsoft.com/en-us/blog"},
    {"name": "Anthropic News", "url": "https://www.anthropic.com/news"},
    {"name": "Meta AI Blog", "url": "https://ai.meta.com/blog"},
    {"name": "Meta Engineering Blog", "url": "https://engineering.fb.com"},
    {"name": "AWS ML Blog", "url": "https://aws.amazon.com/blogs/machine-learning"},
    {"name": "Hugging Face Blog", "url": "https://huggingface.co/blog"},
    # ── Hardware & Compute ──
    {"name": "NVIDIA Blog", "url": "https://blogs.nvidia.com"},
    {"name": "NVIDIA Developer Blog", "url": "https://developer.nvidia.com/blog"},
    {"name": "Intel AI", "url": "https://www.intel.com/content/www/us/en/artificial-intelligence/posts.html"},
    {"name": "AMD AI Blog", "url": "https://www.amd.com/en/blogs"},
    # ── Robotics ──
    {"name": "Boston Dynamics Blog", "url": "https://www.bostondynamics.com/blog"},
    {"name": "IEEE Robotics", "url": "https://spectrum.ieee.org/robotics"},
    # ── Quantum Computing ──
    {"name": "Google Quantum AI", "url": "https://quantumai.google"},
    {"name": "IBM Quantum", "url": "https://research.ibm.com/quantum"},
    {"name": "Microsoft Quantum", "url": "https://azure.microsoft.com/en-us/products/quantum"},
    {"name": "Quantinuum News", "url": "https://www.quantinuum.com/news"},

    # ── Cloud & Enterprise AI ──
    {"name": "Oracle AI Blog", "url": "https://blogs.oracle.com/ai-and-datascience"},
    {"name": "Oracle Cloud Blog", "url": "https://blogs.oracle.com/cloud-infrastructure"},
    # ── AI news dashboards ──
    {"name": "AI News", "url": "https://artificialintelligence-news.com"}
]


# Official news/blog pages for major AI companies — used for web-search
# fallback when RSS feeds return zero items for a company.
_OFFICIAL_NEWS_PAGES: Dict[str, List[str]] = {
    # ── AI / ML / Foundation Models ──
    "openai": [
        "https://openai.com/blog",
        "https://openai.com/news/",
        "https://openai.com/index/",
    ],
    "google": [
        "https://ai.googleblog.com",
        "https://blog.google/technology/ai/",
        "https://cloud.google.com/blog/products/ai-machine-learning",
        "https://research.google/blog/",
    ],
    "deepmind": [
        "https://deepmind.google/discover/blog/",
    ],
    "microsoft": [
        "https://www.microsoft.com/en-us/ai/blog",
        "https://blogs.microsoft.com/ai/",
        "https://azure.microsoft.com/en-us/blog/",
        "https://www.microsoft.com/en-us/research/blog/",
    ],
    "anthropic": [
        "https://www.anthropic.com/news",
        "https://www.anthropic.com/research",
        "https://www.anthropic.com/engineering",
        "https://www.anthropic.com/customers",
    ],
    "meta": [
        "https://ai.meta.com/blog/",
        "https://about.fb.com/news/",
        "https://engineering.fb.com/",
        "https://ai.meta.com/research/",
    ],
    "amazon": [
        "https://aws.amazon.com/blogs/machine-learning/",
        "https://www.aboutamazon.com/news/aws",
    ],
    "huggingface": [
        "https://huggingface.co/blog",
    ],
    # ── Hardware & Compute ──
    "nvidia": [
        "https://blogs.nvidia.com",
        "https://nvidianews.nvidia.com/",
        "https://developer.nvidia.com/blog",
    ],
    "intel": [
        "https://www.intel.com/content/www/us/en/artificial-intelligence/posts.html",
        "https://newsroom.intel.com/",
    ],
    "amd": [
        "https://www.amd.com/en/blogs",
    ],
    "apple": [
        "https://machinelearning.apple.com/",
        "https://www.apple.com/newsroom/",
    ],
    # ── Robotics ──
    "bostondynamics": [
        "https://www.bostondynamics.com/blog",
    ],
    # ── Quantum Computing ──
    "google_quantum": [
        "https://quantumai.google",
    ],
    "ibm": [
        "https://research.ibm.com/quantum",
        "https://newsroom.ibm.com/artificial-intelligence",
        "https://research.ibm.com/blog",
    ],
    "quantinuum": [
        "https://www.quantinuum.com/news",
    ],
    # ── Cloud & Enterprise AI ──
    "oracle": [
        "https://blogs.oracle.com/ai-and-datascience/",
        "https://blogs.oracle.com/cloud-infrastructure/",
        "https://www.oracle.com/news/",
    ],
    # ── Other tech companies ──
    "samsung": [
        "https://news.samsung.com/global/",
        "https://research.samsung.com/blog",
    ],
    "salesforce": [
        "https://www.salesforce.com/news/",
        "https://blog.salesforceairesearch.com/",
    ],
}


# RSS/Atom feeds for companies whose websites block direct scraping.
# These are official first-party feeds maintained by the companies themselves.
_COMPANY_RSS_FEEDS: Dict[str, List[str]] = {
    "openai": [
        # OpenAI blocks both direct scraping and RSS; rely on web-search fallback
    ],
    "google": [
        "https://blog.google/technology/ai/rss/",
        "https://research.google/feeds/blog.xml",
    ],
    "deepmind": [
        "https://deepmind.google/blog/rss.xml",
    ],
    "microsoft": [
        "https://blogs.microsoft.com/feed/",
        "https://www.microsoft.com/en-us/research/feed/",
        "https://azure.microsoft.com/en-us/blog/feed/",
    ],
    "meta": [
        "https://engineering.fb.com/feed/",
        "https://ai.meta.com/blog/rss/",
    ],
    "nvidia": [
        "https://blogs.nvidia.com/feed/",
        "https://developer.nvidia.com/blog/feed/",
    ],
    "amazon": [
        "https://aws.amazon.com/blogs/machine-learning/feed/",
    ],
    "apple": [
        "https://machinelearning.apple.com/rss.xml",
    ],
    "ibm": [
        "https://research.ibm.com/blog/rss",
    ],
    "oracle": [
        "https://blogs.oracle.com/ai-and-datascience/rss",
        "https://blogs.oracle.com/cloud-infrastructure/rss",
    ],
    "anthropic": [
        "https://www.anthropic.com/rss/news",
    ],
    "bostondynamics": [
        "https://www.bostondynamics.com/blog/feed",
    ],
}


def _fetch_rss_items(feed_url: str, company: str, from_date: str = "", to_date: str = "") -> List[Dict]:
    """Fetch and parse an RSS/Atom feed, returning normalised item dicts.

    Uses feedparser if available, otherwise falls back to basic XML regex parsing.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; MARSBot/1.0)",
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
    }
    xml = _safe_get_text(feed_url, headers=headers)
    if not xml or len(xml) < 100:
        return []

    items: List[Dict] = []

    # Try feedparser first (best quality)
    try:
        import feedparser
        feed = feedparser.parse(xml)
        for entry in (feed.entries or []):
            title = (entry.get("title") or "").strip()
            link = (entry.get("link") or "").strip()
            if not title or not link:
                continue
            # Parse publication date
            pub_str = entry.get("published") or entry.get("updated") or ""
            pub_dt = _parse_pub_datetime(pub_str)
            if not _in_range(pub_dt, from_date, to_date):
                continue
            items.append({
                "title": title,
                "url": link,
                "source": company,
                "published_at": pub_dt.isoformat() if pub_dt else None,
                "summary": (entry.get("summary") or "")[:300].strip(),
                "engine": "rss",
            })
        return items
    except ImportError:
        pass

    # Fallback: basic regex XML parsing (no feedparser)
    # Works for most RSS 2.0 feeds
    item_blocks = re.findall(r"<item[^>]*>(.*?)</item>", xml, re.S | re.I)
    if not item_blocks:
        # Try Atom format
        item_blocks = re.findall(r"<entry[^>]*>(.*?)</entry>", xml, re.S | re.I)

    for block in item_blocks:
        title_m = re.search(r"<title[^>]*>(.*?)</title>", block, re.S | re.I)
        link_m = re.search(r"<link[^>]*href=[\"']([^\"']+)[\"']", block, re.I) or \
                 re.search(r"<link[^>]*>(.*?)</link>", block, re.S | re.I)
        pub_m = re.search(r"<(?:pubDate|published|updated)[^>]*>(.*?)</(?:pubDate|published|updated)>",
                          block, re.S | re.I)

        title = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", (title_m.group(1) if title_m else "")).strip()
        link = ""
        if link_m:
            link = link_m.group(1).strip()
        if not title or not link or not link.startswith("http"):
            continue

        pub_str = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", (pub_m.group(1) if pub_m else "")).strip()
        pub_dt = _parse_pub_datetime(pub_str)
        if from_date and not _in_range(pub_dt, from_date, to_date):
            continue

        items.append({
            "title": unescape(title),
            "url": link,
            "source": company,
            "published_at": pub_dt.isoformat() if pub_dt else None,
            "summary": "",
            "engine": "rss",
        })

    return items


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


def _normalize_title(value: str) -> str:
    text = (value or "").lower().strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^a-z0-9\s]", "", text)
    return text


def _canonical_item_key(item: Dict) -> tuple:
    title = _normalize_title(item.get("title", ""))
    source = (item.get("source") or "").lower().strip()
    date_part = (item.get("published_at") or "")[:10]
    url = (item.get("url") or "").strip().lower()
    return (title, source, date_part, url)


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


def multi_engine_web_search(query: str, max_results: int = 10, from_date: str = "", to_date: str = "") -> Dict:
    """Search the web using the duckduckgo_search SDK, falling back to
    HTML scraping of Bing/Yahoo/Brave when the SDK returns nothing.

    Args:
        query: Search query string.
        max_results: Maximum number of results to return.
        from_date: Optional YYYY-MM-DD start date. Results will be hinted
            to this range via search operators when possible.
        to_date: Optional YYYY-MM-DD end date.

    This gives planner workflows a resilient no-key fallback path.
    """
    q = (query or "").strip()
    if not q:
        return {"provider": "multi_engine_web_search", "query": query, "count": 0, "items": [], "errors": ["empty query"]}

    # Append date-range hint so search engines prefer items within the window.
    # DuckDuckGo/Bing understand "after:YYYY-MM-DD before:YYYY-MM-DD" loosely.
    if from_date and to_date and from_date not in q and to_date not in q:
        q = f"{q} after:{from_date} before:{to_date}"

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


def curated_ai_sources_search(query: str, limit: int = 40, from_date: str = "", to_date: str = "") -> Dict:
    """Search across curated AI sources with resilient multi-engine fallback.

    Args:
        query: Search query string.
        limit: Maximum number of results.
        from_date: Optional YYYY-MM-DD start date for date-range hinting.
        to_date: Optional YYYY-MM-DD end date.

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
        found = multi_engine_web_search(scoped_query, max_results=4, from_date=from_date, to_date=to_date)

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


def announcements_noauth(
    query: str = "",
    company: str = "",
    from_date: str = "",
    to_date: str = "",
    limit: int = 100,
) -> Dict:
    """Keyless press/company announcement retrieval.

    Uses only free, no-auth sources:
    1) Official company news/blog pages (web-search based)
    2) Curated AI news sources
    """
    # Scrape official news pages for the company (or all companies)
    official_result = scrape_official_news_pages(
        company=company,
        from_date=from_date,
        to_date=to_date,
        limit=200,
    )
    official_items = official_result.get("items") or []

    merged: List[Dict] = []
    seen = set()
    for item in official_items:
        key = _canonical_item_key(item)
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


def _direct_scrape_page_links(page_url: str, company: str) -> List[Dict]:
    """Fetch an official news/blog page directly and extract article links.

    This bypasses search engines entirely — it fetches the HTML of the company
    news page and pulls out <a href> links that look like individual articles.
    Aggressively filters navigation links to avoid polluting results.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }
    html = _safe_get_text(page_url, headers=headers)
    if not html or len(html) < 500:
        return []

    parsed_base = urlparse(page_url)
    base_domain = parsed_base.netloc.lower().replace("www.", "")

    # Extract all anchor links
    link_pattern = re.compile(
        r'<a[^>]*\bhref=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', re.I | re.S
    )
    items: List[Dict] = []
    seen_urls: set = set()

    # Patterns that indicate a navigation/product link (not an article)
    _NAV_SKIP_PATTERNS = [
        r"^/$", r"/category/", r"/tag/", r"/page/\d", r"/author/",
        r"/search", r"/login", r"/signup", r"/contact", r"/about$",
        r"/privacy", r"/terms", r"/sitemap", r"\.(css|js|png|jpg|svg|ico)$",
        r"/store/", r"/shop/", r"/pricing", r"/download", r"/install",
        r"/products?/", r"/solutions/", r"/services/", r"/support/",
        r"/careers", r"/jobs", r"/legal", r"/compliance",
        r"/account", r"/settings", r"/profile", r"/dashboard",
    ]
    # Patterns that indicate an article URL
    _ARTICLE_PATH_SIGNALS = [
        r"/blog/", r"/news/", r"/research/", r"/index/", r"/post/",
        r"/article/", r"/press-release", r"/announcement",
        r"/20\d{2}/", r"/20\d{2}-",  # Date in path
    ]
    # Generic nav labels to skip
    _NAV_TITLES = {
        "read more", "learn more", "see all", "view all", "click here",
        "more", "next", "previous", "sign in", "sign up", "log in",
        "create account", "get started", "try free", "contact us",
        "small business", "microsoft teams", "accessories", "windows",
        "xbox", "surface", "microsoft 365", "developer tools",
        "autonomous machines", "cloud & data center", "deep learning & ai",
        "design & pro visualization", "healthcare", "gaming",
        "conditions of use", "privacy policy", "cookie policy",
    }

    for href, title_html in link_pattern.findall(html):
        href = href.strip()
        # Resolve relative URLs
        if href.startswith("/"):
            href = f"{parsed_base.scheme}://{parsed_base.netloc}{href}"
        if not href.startswith("http"):
            continue
        link_domain = urlparse(href).netloc.lower().replace("www.", "")
        # Must be same domain (or subdomain)
        if base_domain not in link_domain and link_domain not in base_domain:
            continue

        path = urlparse(href).path.lower()

        # Skip obvious navigation/product pages
        if any(re.search(pat, path) for pat in _NAV_SKIP_PATTERNS):
            continue

        # Require some path depth (at least /segment/something)
        path_parts = [p for p in path.split("/") if p]
        if len(path_parts) < 2:
            continue

        url_key = href.lower().rstrip("/")
        if url_key in seen_urls:
            continue
        seen_urls.add(url_key)

        title = re.sub(r"<[^>]+>", "", unescape(title_html)).strip()
        # Collapse whitespace
        title = re.sub(r"\s+", " ", title).strip()

        # Skip links with no meaningful title text
        if not title or len(title) < 15 or len(title) > 300:
            continue
        # Skip generic navigation text
        if title.lower().strip() in _NAV_TITLES:
            continue

        # Prefer links with article path signals — if the page has many links,
        # only keep those that look like articles
        has_article_signal = any(re.search(pat, path) for pat in _ARTICLE_PATH_SIGNALS)

        # Try to extract date from URL path (common patterns: /2026/03/ or /2026-03-)
        pub_date = None
        date_match = re.search(r"/(20\d{2})[/-](0[1-9]|1[0-2])[/-](\d{2})?", href)
        if date_match:
            y, m = date_match.group(1), date_match.group(2)
            d = date_match.group(3) or "15"
            try:
                pub_date = datetime(int(y), int(m), int(d), tzinfo=timezone.utc).isoformat()
            except ValueError:
                pass
            has_article_signal = True  # Date in URL is a strong article signal

        # Only include links with article signals to avoid nav-link pollution
        if not has_article_signal:
            continue

        items.append({
            "title": title,
            "url": href,
            "source": company,
            "published_at": pub_date,
            "summary": "",
            "engine": "direct_scrape",
        })

    return items


def scrape_official_news_pages(
    company: str = "",
    from_date: str = "",
    to_date: str = "",
    limit: int = 20,
) -> Dict:
    """Scrape official company news/blog pages for recent AI releases.

    Uses a two-pronged approach:
    1) Direct HTML scraping of each official page to extract article links
    2) Fallback to site-scoped web search if direct scraping yields few results

    Args:
        company: Company key (e.g. "openai"). Empty = all known companies.
        from_date: YYYY-MM-DD start date.
        to_date: YYYY-MM-DD end date.
        limit: Max items to return.
    """
    key = company.strip().lower()
    if key:
        pages = _OFFICIAL_NEWS_PAGES.get(key)
        if not pages:
            return {
                "error": f"No official pages for '{company}'. "
                         f"Supported: {', '.join(sorted(_OFFICIAL_NEWS_PAGES.keys()))}",
                "items": [],
            }
        selected = {key: pages}
    else:
        selected = _OFFICIAL_NEWS_PAGES

    items: List[Dict] = []
    seen: set = set()
    cap = max(1, min(limit, 100))

    for source_name, page_urls in selected.items():
        if len(items) >= cap:
            break
        company_items_before = len(items)

        for page_url in page_urls:
            if len(items) >= cap:
                break

            # --- Primary: direct HTML scraping of the page ---
            try:
                direct_items = _direct_scrape_page_links(page_url, source_name)
                for item in direct_items:
                    item_url = (item.get("url") or "").strip()
                    url_key = item_url.lower().rstrip("/")
                    if url_key in seen or not item.get("title"):
                        continue
                    # Date filter if we have a date from the URL
                    pub_at = item.get("published_at")
                    if pub_at and from_date:
                        pub_dt = _parse_iso_date(pub_at)
                        if pub_dt and not _in_range(pub_dt, from_date, to_date):
                            continue
                    seen.add(url_key)
                    items.append(item)
                    if len(items) >= cap:
                        break
            except Exception as e:
                logger.warning("direct_scrape_failed", company=source_name,
                               page=page_url, error=str(e))

        # --- Fallback 1: RSS feeds (reliable for sites that block direct scraping) ---
        company_items_added = len(items) - company_items_before
        # Count how many items have actual dates (undated items may be stale)
        dated_items = sum(
            1 for i in items[company_items_before:]
            if i.get("published_at")
        )
        if (company_items_added < 5 or dated_items < 2) and source_name in _COMPANY_RSS_FEEDS:
            for feed_url in _COMPANY_RSS_FEEDS[source_name]:
                if len(items) >= cap:
                    break
                try:
                    rss_items = _fetch_rss_items(feed_url, source_name, from_date, to_date)
                    for item in rss_items:
                        url_key = (item.get("url") or "").lower().rstrip("/")
                        if url_key in seen or not item.get("title"):
                            continue
                        seen.add(url_key)
                        items.append(item)
                        if len(items) >= cap:
                            break
                except Exception as e:
                    logger.warning("rss_fetch_failed", company=source_name,
                                   feed=feed_url, error=str(e))

        # --- Fallback 2: web search if still <3 dated items for this company ---
        company_items_added = len(items) - company_items_before
        dated_items = sum(
            1 for i in items[company_items_before:]
            if i.get("published_at")
        )
        if company_items_added < 3 or dated_items < 2:
            for page_url in page_urls[:1]:  # Only search first URL to avoid rate-limits
                if len(items) >= cap:
                    break
                domain = (urlparse(page_url).netloc or "").lower().replace("www.", "")
                if not domain:
                    continue
                q = f"site:{domain} AI {from_date}" if from_date else f"site:{domain} AI"
                try:
                    result = multi_engine_web_search(
                        q, max_results=5, from_date=from_date, to_date=to_date,
                    )
                    for item in result.get("items") or []:
                        item_url = (item.get("url") or "").strip()
                        item_domain = (urlparse(item_url).netloc or "").lower()
                        if domain not in item_domain:
                            continue
                        title = (item.get("title") or "").strip()
                        url_key = item_url.lower().rstrip("/")
                        if url_key in seen or not title:
                            continue
                        seen.add(url_key)
                        items.append({
                            "title": title,
                            "url": item_url,
                            "source": source_name,
                            "published_at": None,
                            "summary": "",
                            "engine": item.get("engine"),
                        })
                        if len(items) >= cap:
                            break
                except Exception as e:
                    logger.warning("official_page_websearch_failed", company=source_name,
                                   page=page_url, error=str(e))

        # Polite inter-company delay
        time.sleep(0.5)

    return {
        "provider": "official_news_pages",
        "company": key or "all",
        "count": len(items),
        "items": items,
    }


def verify_url(url: str) -> Dict:
    """Verify whether a URL is accessible by sending a HEAD request.

    Returns a dict with 'url', 'accessible' (bool), and 'status_code' or 'error'.
    """
    if not url or not url.startswith("http"):
        return {"url": url, "accessible": False, "error": "invalid URL"}
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    }
    req = Request(url, method="HEAD", headers=headers)
    try:
        with urlopen(req, timeout=_DEFAULT_TIMEOUT_SECONDS) as resp:
            return {"url": url, "accessible": resp.status < 400, "status_code": resp.status}
    except Exception:
        # Some servers reject HEAD; retry with GET and read only headers
        req_get = Request(url, headers=headers)
        try:
            with urlopen(req_get, timeout=_DEFAULT_TIMEOUT_SECONDS) as resp:
                return {"url": url, "accessible": resp.status < 400, "status_code": resp.status}
        except Exception as err:
            return {"url": url, "accessible": False, "error": str(err)}


def verify_reference_links(urls: List[str]) -> Dict:
    """Batch-verify a list of reference URLs for accessibility.

    Returns summary with counts and per-URL results. Use this to validate
    all reference links before including them in the final report.
    """
    if not urls:
        return {"total": 0, "accessible": 0, "inaccessible": 0, "results": []}

    results: List[Dict] = []
    for u in urls:
        results.append(verify_url(u))

    accessible_count = sum(1 for r in results if r.get("accessible"))
    return {
        "total": len(results),
        "accessible": accessible_count,
        "inaccessible": len(results) - accessible_count,
        "results": results,
    }
