"""从公开 API / RSS 拉条目。不破登录、不绕 robots 去抓需登录正文。"""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from .models import RawItem

ATOM = "{http://www.w3.org/2005/Atom}"
USER_AGENT = "RadarME-secretary-demo/0.1 (research; +local)"
TIMEOUT = 10

_CTX = ssl.create_default_context()
_TYPE = {
    "arxiv": "paper",
    "github_releases": "release",
    "rss": "blog",
    "url": "page",
}


def load_source_config(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data.get("sources", []))


def fetch_all(sources: list[dict]) -> list[RawItem]:
    items: list[RawItem] = []
    for spec in sources:
        try:
            items.extend(fetch_one(spec))
        except Exception as exc:
            print(f"[ingest] {spec.get('id')} failed: {exc}")
    return dedupe([item for item in items if item.source_url.strip()])


def dedupe(items: list[RawItem]) -> list[RawItem]:
    seen: set[str] = set()
    out: list[RawItem] = []
    for item in items:
        key = item.source_url.strip().rstrip("/").split("?")[0].lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def fetch_one(spec: dict) -> list[RawItem]:
    kind = spec["kind"]
    if kind == "arxiv":
        return fetch_arxiv(spec)
    if kind == "github_releases":
        return fetch_github_releases(spec)
    if kind == "rss":
        return fetch_rss(spec)
    if kind == "url":
        return fetch_url(spec)
    raise ValueError(f"unknown kind: {kind}")


def fetch_arxiv(spec: dict) -> list[RawItem]:
    query = urllib.parse.quote(spec["search"])
    limit = int(spec.get("max", 6))
    url = (
        "http://export.arxiv.org/api/query?"
        f"search_query={query}&start=0&max_results={limit}"
        "&sortBy=submittedDate&sortOrder=descending"
    )
    xml = _get(url)
    return parse_atom(xml, spec)


def fetch_github_releases(spec: dict) -> list[RawItem]:
    repo = spec["repo"]
    limit = int(spec.get("max", 4))
    url = f"https://api.github.com/repos/{repo}/releases?per_page={limit}"
    raw = _get(url)
    payload = json.loads(raw)
    items: list[RawItem] = []
    for row in payload[:limit]:
        body = (row.get("body") or "").strip().replace("\r", "")
        summary = body.split("\n")[0][:180] if body else (row.get("name") or "")
        items.append(
            RawItem(
                source_id=spec["id"],
                source_name=spec.get("name", repo),
                channel=spec.get("channel", "work"),
                title=row.get("name") or row.get("tag_name") or "release",
                summary=summary,
                source_url=row.get("html_url") or "",
                published_at=row.get("published_at") or "",
                item_type=_item_type(spec),
            )
        )
    return items


def fetch_url(spec: dict) -> list[RawItem]:
    html = _get(spec["url"])
    title = _meta(html, r"<title[^>]*>(.*?)</title>") or spec.get("name") or spec["url"]
    desc = _meta(html, r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']') or ""
    if not desc:
        desc = _meta(html, r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\'](.*?)["\']') or ""
    return [
        RawItem(
            source_id=spec["id"],
            source_name=spec.get("name", spec["id"]),
            channel=spec.get("channel", "work"),
            title=_clean(title),
            summary=_clean(desc)[:280],
            source_url=spec["url"],
            published_at="",
            item_type=_item_type(spec),
        )
    ]


def fetch_rss(spec: dict) -> list[RawItem]:
    xml = _get(spec["url"])
    limit = int(spec.get("max", 8))
    if "<feed" in xml[:500] or ATOM in xml[:800]:
        items = parse_atom(xml, spec)
    else:
        items = parse_rss(xml, spec)
    return items[:limit]


def parse_atom(xml: str, spec: dict) -> list[RawItem]:
    root = ET.fromstring(xml)
    items: list[RawItem] = []
    for entry in root.findall(f"{ATOM}entry") or root.findall("entry"):
        title = _text(entry, f"{ATOM}title") or _text(entry, "title")
        summary = _text(entry, f"{ATOM}summary") or _text(entry, "summary")
        published = _text(entry, f"{ATOM}published") or _text(entry, "published")
        link = ""
        for node in entry.findall(f"{ATOM}link") + entry.findall("link"):
            href = node.get("href") or ""
            rel = node.get("rel") or "alternate"
            if href and rel in ("alternate", ""):
                link = href
                break
            if href and not link:
                link = href
        ident = _text(entry, f"{ATOM}id") or _text(entry, "id")
        if not link and ident and ident.startswith("http"):
            link = ident.replace("arxiv.org/abs", "arxiv.org/abs")
        items.append(
            RawItem(
                source_id=spec["id"],
                source_name=spec.get("name", spec["id"]),
                channel=spec.get("channel", "work"),
                title=_clean(title),
                summary=_clean(summary)[:280],
                source_url=link,
                published_at=published,
                item_type=_item_type(spec),
            )
        )
    return items


def parse_rss(xml: str, spec: dict) -> list[RawItem]:
    root = ET.fromstring(xml)
    channel = root.find("channel")
    nodes = channel.findall("item") if channel is not None else root.findall(".//item")
    items: list[RawItem] = []
    for node in nodes:
        title = (node.findtext("title") or "").strip()
        link = (node.findtext("link") or "").strip()
        desc = (node.findtext("description") or node.findtext("summary") or "").strip()
        pub = (node.findtext("pubDate") or "").strip()
        items.append(
            RawItem(
                source_id=spec["id"],
                source_name=spec.get("name", spec["id"]),
                channel=spec.get("channel", "interest"),
                title=_clean(title),
                summary=_clean(desc)[:280],
                source_url=link,
                published_at=pub,
                item_type=_item_type(spec),
            )
        )
    return items


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/xml,application/json,*/*"})
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=_CTX) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _text(node: ET.Element, tag: str) -> str:
    found = node.find(tag)
    if found is None or found.text is None:
        return ""
    return found.text.strip()


def _clean(text: str) -> str:
    return " ".join((text or "").split())


def _item_type(spec: dict) -> str:
    return spec.get("type") or _TYPE.get(spec.get("kind", ""), "article")


def _meta(html: str, pattern: str) -> str:
    import re

    match = re.search(pattern, html, re.I | re.S)
    return _clean(match.group(1)) if match else ""
