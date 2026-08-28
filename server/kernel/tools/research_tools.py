import os
import requests
from typing import List, Optional
from urllib.parse import urlparse
from langchain_core.tools import tool

try:
    from ddgs import DDGS
    from ddgs.exceptions import DDGSException
except ImportError:
    try:
        from duckduckgo_search import DDGS
        from duckduckgo_search.exceptions import DuckDuckGoSearchException as DDGSException
    except ImportError:
        DDGS = None
        DDGSException = Exception

# Configurable list of trusted academic, scientific, and authoritative domains
TRUSTED_DOMAINS: List[str] = [
    "arxiv.org",
    "nature.com",
    "sciencedirect.com",
    "ieee.org",
    "springer.com",
    "acm.org",
    "nih.gov",
    "ncbi.nlm.nih.gov",
    "semanticscholar.org",
    "pnas.org",
]

# User agent for Wikipedia API requests compliant with Wikimedia policy
WIKIPEDIA_USER_AGENT = "AgentOS-ResearchAgent/1.0 (https://agentos.internal; agent@agentos.internal)"


def _is_trusted_domain_url(url: str, domains: List[str]) -> bool:
    """Validate that the URL belongs to one of the specified trusted domains and is not an ad tracking link."""
    if not url:
        return False
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        if not netloc or "bing.com" in netloc or "duckduckgo.com" in netloc or "aclick" in parsed.path:
            return False
        return any(netloc == d.lower() or netloc.endswith("." + d.lower()) for d in domains if d.strip())
    except Exception:
        return False


@tool
def wikipedia_search(query: str, max_results: int = 3) -> str:
    """Search Wikipedia for encyclopedic, historical, scientific, or conceptual articles.

    Args:
        query: The search query or topic to look up on Wikipedia.
        max_results: Maximum number of article summaries to retrieve (default: 3).

    Returns:
        Structured Wikipedia summaries with titles, article URLs, and extracts.
    """
    headers = {"User-Agent": WIKIPEDIA_USER_AGENT}
    search_url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "format": "json",
        "srlimit": max_results,
    }

    try:
        response = requests.get(search_url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        return f"Error connecting to Wikipedia API: {exc}"

    search_items = data.get("query", {}).get("search", [])
    if not search_items:
        return f"No Wikipedia articles found for query: '{query}'"

    results = []
    for item in search_items:
        title = item.get("title", "")
        if not title:
            continue

        summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{requests.utils.quote(title)}"
        try:
            s_resp = requests.get(summary_url, headers=headers, timeout=10)
            if s_resp.status_code == 200:
                s_data = s_resp.json()
                extract = s_data.get("extract", item.get("snippet", ""))
                page_url = (
                    s_data.get("content_urls", {}).get("desktop", {}).get("page")
                    or f"https://en.wikipedia.org/wiki/{requests.utils.quote(title)}"
                )
                results.append(
                    f"Title: {title}\nURL: {page_url}\nSummary: {extract}"
                )
            else:
                snippet = (
                    item.get("snippet", "")
                    .replace('<span class="searchmatch">', "")
                    .replace("</span>", "")
                )
                page_url = f"https://en.wikipedia.org/wiki/{requests.utils.quote(title)}"
                results.append(f"Title: {title}\nURL: {page_url}\nSnippet: {snippet}")
        except Exception:
            snippet = (
                item.get("snippet", "")
                .replace('<span class="searchmatch">', "")
                .replace("</span>", "")
            )
            page_url = f"https://en.wikipedia.org/wiki/{requests.utils.quote(title)}"
            results.append(f"Title: {title}\nURL: {page_url}\nSnippet: {snippet}")

    return "\n\n---\n\n".join(results)


@tool
def trusted_web_search(
    query: str,
    max_results: int = 5,
    domains: Optional[List[str]] = None,
) -> str:
    """Search the web restricted exclusively to trusted academic, scientific, and verified domains.

    Filters the search query using site: restrictions for peer-reviewed and authoritative
    repositories like arXiv, Nature, ScienceDirect, IEEE, Springer, NIH, and ACM.

    Args:
        query: The search term or research question.
        max_results: Maximum number of search results to return (default: 5).
        domains: Optional custom list of domains to restrict to. If not provided,
                 defaults to TRUSTED_DOMAINS.

    Returns:
        Structured search results with titles, source links, and informative snippets.
    """
    target_domains = domains if domains is not None else TRUSTED_DOMAINS
    if not target_domains:
        target_domains = TRUSTED_DOMAINS

    if DDGS is None:
        return "DuckDuckGo search package ('ddgs' or 'duckduckgo-search') is not installed."

    raw_results = []
    cleaned_query = query.strip()

    # 1. First attempt: combined query with OR site filters
    site_filters = " OR ".join(f"site:{d.strip()}" for d in target_domains if d.strip())
    restricted_query = f"{cleaned_query} {site_filters}".strip()

    try:
        with DDGS() as ddgs:
            raw_results = list(
                ddgs.text(
                    restricted_query,
                    max_results=max_results * 2,
                    backend="html",
                )
            )
    except (DDGSException, Exception):
        raw_results = []

    # 2. Fallback attempt: query individual top trusted domains
    if not raw_results:
        for single_domain in target_domains[:4]:
            single_query = f"{cleaned_query} site:{single_domain.strip()}"
            try:
                with DDGS() as ddgs:
                    domain_results = list(
                        ddgs.text(single_query, max_results=2, backend="html")
                    )
                    raw_results.extend(domain_results)
            except (DDGSException, Exception):
                continue
            if len(raw_results) >= max_results:
                break

    results = []
    seen_urls = set()
    for item in raw_results:
        href = item.get("href", "").strip()
        if not href or href in seen_urls:
            continue
        if not _is_trusted_domain_url(href, target_domains):
            continue
        seen_urls.add(href)
        title = item.get("title", "").strip()
        body = item.get("body", "").strip()
        results.append(f"Title: {title}\nURL: {href}\nSnippet: {body}")
        if len(results) >= max_results:
            break

    if not results:
        return f"No verified results found from trusted domains ({', '.join(target_domains)}) for query: '{query}'"

    return "\n\n---\n\n".join(results)
