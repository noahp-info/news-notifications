import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "scraper"))

from parser import _parse_css, _parse_json, _parse_rss, parse

SAMPLE_HTML = """
<html><body>
  <div class="statuses">
    <div class="status">
      <div class="status__content"><p>First post text</p></div>
    </div>
    <div class="status">
      <div class="status__content"><p>Second post text</p></div>
    </div>
    <div class="status">
      <div class="status__content"><p>Third post text</p></div>
    </div>
  </div>
</body></html>
"""

SAMPLE_RSS = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item><title>Item One</title></item>
    <item><title>Item Two</title></item>
  </channel>
</rss>"""

SAMPLE_JSON = '{"posts": [{"text": "Hello"}, {"text": "World"}]}'


def test_parse_css_returns_text():
    result = _parse_css(SAMPLE_HTML, "div.status__content p", 5)
    assert result == ["First post text", "Second post text", "Third post text"]


def test_parse_css_respects_max_items():
    result = _parse_css(SAMPLE_HTML, "div.status__content p", 1)
    assert len(result) == 1
    assert result[0] == "First post text"


def test_parse_css_empty_selector():
    result = _parse_css(SAMPLE_HTML, "div.nonexistent", 5)
    assert result == []


def test_parse_css_skips_empty_elements():
    html = "<html><body><p></p><p>real content</p></body></html>"
    result = _parse_css(html, "p", 5)
    assert result == ["real content"]


def test_parse_dispatches_to_css():
    result = parse(SAMPLE_HTML, "css", "div.status__content p", 5)
    assert len(result) == 3


def test_parse_rss_titles():
    result = _parse_rss(SAMPLE_RSS, "title", 5)
    assert "Item One" in result
    assert "Item Two" in result


def test_parse_rss_respects_max_items():
    result = _parse_rss(SAMPLE_RSS, "title", 1)
    assert len(result) == 1


def test_parse_json_jmespath():
    result = _parse_json(SAMPLE_JSON, "posts[].text", 5)
    assert result == ["Hello", "World"]


def test_parse_json_respects_max_items():
    result = _parse_json(SAMPLE_JSON, "posts[].text", 1)
    assert result == ["Hello"]


def test_parse_unknown_type_raises():
    with pytest.raises(ValueError, match="Unknown scrape_type"):
        parse("<html/>", "xml", "//div", 5)
