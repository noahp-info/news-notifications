import json

import feedparser
import jmespath
from bs4 import BeautifulSoup


def parse(html: str, scrape_type: str, selector: str, max_items: int) -> list[str]:
    if scrape_type == "css":
        return _parse_css(html, selector, max_items)
    elif scrape_type == "rss":
        return _parse_rss(html, selector, max_items)
    elif scrape_type == "json":
        return _parse_json(html, selector, max_items)
    else:
        raise ValueError(f"Unknown scrape_type: {scrape_type!r}")


def _parse_css(html: str, selector: str, max_items: int) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    elements = soup.select(selector)[:max_items]
    return [
        el.get_text(separator=" ", strip=True)
        for el in elements
        if el.get_text(strip=True)
    ]


def _parse_rss(content: str, field: str, max_items: int) -> list[str]:
    feed = feedparser.parse(content)
    entries = feed.entries[:max_items]
    return [getattr(entry, field, "") for entry in entries if getattr(entry, field, "")]


def _parse_json(json_str: str, jmespath_expr: str, max_items: int) -> list[str]:
    data = json.loads(json_str)
    results = jmespath.search(jmespath_expr, data) or []
    return [str(r) for r in results[:max_items]]
