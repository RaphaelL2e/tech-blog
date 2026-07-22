#!/usr/bin/env python3
"""Audit the generated Raphael Lab site against the V2 P0 release gates."""

from __future__ import annotations

import json
import re
import sys
import urllib.parse
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
POSTS = ROOT / "content" / "posts"
SERIES = ROOT / "content" / "series"
MAX_BYTES = 30 * 1024 * 1024
MIN_CONTENT_ARTICLES = 254
VALID_TOPICS = {
    "java-spring", "distributed-systems", "database-middleware",
    "system-engineering", "ai-engineering", "computer-science", "archive",
}
EXPECTED_SERIES_COUNTS = {
    "java-design-patterns": 23,
    "spring-interview": 10,
    "distributed-systems-interview": 10,
    "microservices-interview": 10,
    "database-interview": 12,
    "system-design": 9,
    "ai-llm-interview": 6,
    "computer-network": 10,
    "operating-system": 7,
}


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.h1 = 0
        self.title = 0
        self.description = False
        self.canonical = False
        self.og_title = False
        self.json_ld = 0
        self.refresh = False
        self.links: list[str] = []
        self.resources: list[str] = []
        self.post_cards = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "h1":
            self.h1 += 1
        elif tag == "title":
            self.title += 1
        elif tag == "meta":
            if values.get("name") == "description" and values.get("content"):
                self.description = True
            if values.get("property") == "og:title" and values.get("content"):
                self.og_title = True
            if values.get("http-equiv", "").lower() == "refresh":
                self.refresh = True
        elif tag == "link" and values.get("rel") == "canonical" and values.get("href"):
            self.canonical = True
        elif tag == "script" and values.get("type") == "application/ld+json":
            self.json_ld += 1
        elif tag == "a" and values.get("href"):
            self.links.append(values["href"] or "")
        if tag in {"img", "script", "source", "video", "audio", "input"} and values.get("src"):
            self.resources.append(values["src"] or "")
        classes = (values.get("class") or "").split()
        if "post-card" in classes:
            self.post_cards += 1


def front_matter(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, flags=re.S)
    if not match:
        raise ValueError("missing front matter")
    return yaml.safe_load(match.group(1)) or {}, text[match.end():]


def public_target(url: str) -> Path | None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme and parsed.netloc != "raphaell2e.github.io":
        return None
    if parsed.scheme not in ("", "http", "https"):
        return None
    path = urllib.parse.unquote(parsed.path)
    if not path.startswith("/"):
        return None
    target = PUBLIC / path.lstrip("/")
    if path.endswith("/"):
        target = target / "index.html"
    return target


def main() -> int:
    errors: list[str] = []
    facts: list[str] = []
    if not PUBLIC.exists():
        print("public/ does not exist; run hugo first", file=sys.stderr)
        return 1

    size = sum(path.stat().st_size for path in PUBLIC.rglob("*") if path.is_file())
    facts.append(f"build size: {size / 1024 / 1024:.2f} MiB")
    if size >= MAX_BYTES:
        errors.append(f"build is {size / 1024 / 1024:.2f} MiB; budget is <30 MiB")
    if (PUBLIC / "tags").exists():
        errors.append("public/tags exists; noisy taxonomy output was generated")

    required = [
        "index.html", "posts/index.html", "series/index.html", "projects/index.html",
        "about/index.html", "search/index.html", "search-index.json", "404.html",
        "robots.txt", "sitemap.xml", "index.xml", "css/site.css", "js/site.js",
    ]
    for relative in required:
        if not (PUBLIC / relative).is_file():
            errors.append(f"missing required artifact: {relative}")

    html_paths = sorted(PUBLIC.rglob("*.html"))
    facts.append(f"HTML pages: {len(html_paths)}")
    parsers: dict[Path, PageParser] = {}
    all_links: list[tuple[Path, str]] = []
    all_resources: list[tuple[Path, str]] = []
    titles: Counter[str] = Counter()
    for path in html_paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        parser = PageParser()
        parser.feed(text)
        parsers[path] = parser
        if parser.refresh:
            continue
        relative = path.relative_to(PUBLIC)
        if parser.h1 != 1:
            errors.append(f"{relative}: expected one H1, found {parser.h1}")
        if parser.title != 1:
            errors.append(f"{relative}: expected one title element, found {parser.title}")
        for attr, present in (("description", parser.description), ("canonical", parser.canonical), ("og:title", parser.og_title)):
            if not present:
                errors.append(f"{relative}: missing {attr}")
        if parser.json_ld != 1:
            errors.append(f"{relative}: expected one JSON-LD block, found {parser.json_ld}")
        title_match = re.search(r"<title>(.*?)</title>", text, flags=re.S | re.I)
        if title_match:
            titles[re.sub(r"\s+", " ", title_match.group(1)).strip()] += 1
        all_links.extend((path, href) for href in parser.links)
        all_resources.extend((path, src) for src in parser.resources)

    duplicates = {title: count for title, count in titles.items() if count > 1}
    if duplicates:
        errors.append("duplicate page titles: " + ", ".join(f"{title} ({count})" for title, count in list(duplicates.items())[:8]))

    home = parsers.get(PUBLIC / "index.html")
    if home and home.post_cards > 12:
        errors.append(f"home renders {home.post_cards} post cards; maximum is 12")
    if home:
        facts.append(f"home post cards: {home.post_cards}")

    about_path = PUBLIC / "about" / "index.html"
    if about_path.exists():
        about_html = about_path.read_text(encoding="utf-8", errors="replace")
        if 'class="about-hero shell"' not in about_html:
            errors.append("about page is not using its dedicated author layout")
        if "0001-01-01" in about_html or "历史归档，部分内容可能过时" in about_html:
            errors.append("about page leaks article-only archive or zero-date metadata")

    broken: list[str] = []
    for source, href in all_links:
        target = public_target(href)
        if target is not None and not target.exists():
            broken.append(f"{source.relative_to(PUBLIC)} -> {href}")
    if broken:
        errors.append("broken internal links:\n    " + "\n    ".join(broken[:25]))

    broken_resources: list[str] = []
    for source, src in all_resources:
        target = public_target(src)
        if target is not None and not target.exists():
            broken_resources.append(f"{source.relative_to(PUBLIC)} -> {src}")
    if broken_resources:
        errors.append("broken internal resources:\n    " + "\n    ".join(broken_resources[:25]))

    content_paths = sorted(path for path in POSTS.glob("*.md") if path.name != "_index.md")
    facts.append(f"content articles: {len(content_paths)}")
    if len(content_paths) < MIN_CONTENT_ARTICLES:
        errors.append(
            f"expected at least {MIN_CONTENT_ARTICLES} content articles, found {len(content_paths)}"
        )
    topic_counts: Counter[str] = Counter()
    categories: set[str] = set()
    series_orders: defaultdict[str, list[int]] = defaultdict(list)
    for path in content_paths:
        meta, body = front_matter(path)
        for field in ("title", "date", "description", "topic", "status"):
            if not meta.get(field):
                errors.append(f"{path.name}: missing {field}")
        if len(str(meta.get("description") or "")) < 35:
            errors.append(f"{path.name}: description is too short")
        topic = meta.get("topic")
        topic_counts[topic] += 1
        if topic not in VALID_TOPICS:
            errors.append(f"{path.name}: invalid topic {topic}")
        categories.update(str(value) for value in (meta.get("categories") or []))
        if len(meta.get("tags") or []) > 5:
            errors.append(f"{path.name}: more than five tags")
        in_fence = False
        for line in body.splitlines():
            if line.strip().startswith(("```", "~~~")):
                in_fence = not in_fence
            elif not in_fence and re.match(r"^#\s+", line):
                errors.append(f"{path.name}: body-level H1 remains")
                break
        if meta.get("series"):
            if not meta.get("series_order"):
                errors.append(f"{path.name}: series without series_order")
            else:
                series_orders[str(meta["series"])].append(int(meta["series_order"]))
    if len(categories) > 7:
        errors.append(f"found {len(categories)} canonical categories; maximum is 7")
    for key, orders in series_orders.items():
        if len(orders) != len(set(orders)):
            errors.append(f"series {key} has duplicate order values")
        if not (SERIES / f"{key}.md").is_file():
            errors.append(f"series {key} has articles but no content/series/{key}.md page")
    for key, expected in EXPECTED_SERIES_COUNTS.items():
        actual = len(series_orders.get(key, []))
        if actual != expected:
            errors.append(f"series {key} has {actual} articles; expected {expected}")
    facts.append("topics: " + ", ".join(f"{key}={value}" for key, value in sorted(topic_counts.items())))
    facts.append(f"canonical categories: {len(categories)}")
    facts.append(f"ordered series: {len(series_orders)}")

    index_path = PUBLIC / "search-index.json"
    if index_path.exists():
        try:
            search_index = json.loads(index_path.read_text(encoding="utf-8"))
            if len(search_index) != len(content_paths):
                errors.append(f"search index has {len(search_index)} items; expected {len(content_paths)}")
            for item in search_index:
                for field in ("title", "url", "description", "content", "topic", "date"):
                    if not item.get(field):
                        errors.append(f"search item {item.get('title', '<unknown>')} missing {field}")
                        break
                target = public_target(str(item.get("url") or ""))
                if target is not None and not target.exists():
                    errors.append(
                        f"search item {item.get('title', '<unknown>')} points to a missing page: "
                        f"{item.get('url')}"
                    )
            facts.append(f"search index: {len(search_index)} articles")
        except Exception as exc:
            errors.append(f"search index is invalid JSON: {exc}")

    source_js = ROOT / "themes" / "simple" / "static" / "js" / "site.js"
    if source_js.exists() and "encodeURI(item.url)" in source_js.read_text(encoding="utf-8"):
        errors.append("search renderer double-encodes Hugo's already escaped article URLs")

    public_text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in html_paths)
    for secret in ("17603444963", "密码：4963", "resume.pdf"):
        if secret in public_text:
            errors.append(f"sensitive public string remains: {secret}")
    if "Raphael Tech Blog" in public_text:
        errors.append("legacy site brand remains in generated HTML")

    sitemap = (PUBLIC / "sitemap.xml").read_text(encoding="utf-8") if (PUBLIC / "sitemap.xml").exists() else ""
    for excluded in ("/search/", "/wealth/"):
        if excluded in sitemap:
            errors.append(f"noindex route remains in sitemap: {excluded}")
    robots = (PUBLIC / "robots.txt").read_text(encoding="utf-8") if (PUBLIC / "robots.txt").exists() else ""
    if "Disallow: /wealth/" not in robots or "Sitemap:" not in robots:
        errors.append("robots.txt is missing private route exclusion or sitemap declaration")

    print("V2 build audit")
    for fact in facts:
        print(f"  PASS {fact}")
    if errors:
        print(f"  FAIL {len(errors)} issue(s)")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("  PASS all release gates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
