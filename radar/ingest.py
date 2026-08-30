"""从公开 API / RSS 拉条目。不破登录、不绕 robots 去抓需登录正文。"""

from __future__ import annotations

import json
import os
import ssl
import time
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
    if kind in {"zhihu_search", "global_search"}:
        return fetch_zhihu_open_search(spec)
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


def fetch_zhihu_open_search(spec: dict) -> list[RawItem]:
    """Use Zhihu's authorized search APIs; never scrape Zhihu or WeChat pages."""
    secret = (os.environ.get(str(spec.get("credential_env") or "ZHIHU_ACCESS_SECRET")) or "").strip()
    if not secret:
        return []
    kind = str(spec.get("kind") or "zhihu_search")
    endpoint = "global_search" if kind == "global_search" else "zhihu_search"
    base = (os.environ.get("ZHIHU_OPENAPI_BASE_URL") or "https://developer.zhihu.com").rstrip("/")
    limit = max(1, min(20 if kind == "global_search" else 10, int(spec.get("max") or 8)))
    searches = spec.get("searches") or [spec.get("search")]
    searches = [str(value).strip() for value in searches if str(value or "").strip()]
    if not searches:
        return []
    allowed = [str(host).lower() for host in (spec.get("allowed_hosts") or [])]
    items: list[RawItem] = []
    seen: set[str] = set()
    for search in searches:
        per_query_limit = min(10, limit)
        params = {"Query": search, "Count": per_query_limit}
        if kind == "global_search" and spec.get("filter"):
            params["Filter"] = str(spec["filter"])
        if kind == "global_search" and spec.get("search_db"):
            params["SearchDB"] = str(spec["search_db"])
        query = urllib.parse.urlencode(params)
        payload = _get_json(
            f"{base}/api/v1/content/{endpoint}?{query}",
            {
                "Authorization": f"Bearer {secret}",
                "X-Request-Timestamp": str(int(time.time())),
                "Content-Type": "application/json",
            },
        )
        for row in _search_result_rows(payload):
            url = _first_text(row, "Url", "url", "URL", "link", "href", "source_url", "content_url")
            title = _first_text(row, "title", "Title", "name", "question")
            if not url or not title or url in seen or not _host_allowed(url, allowed):
                continue
            seen.add(url)
            metadata = {
                "author_name": _first_text(row, "AuthorName", "author_name", "author"),
                "author_badge_text": _first_text(row, "AuthorBadgeText", "author_badge_text"),
                "vote_up_count": _as_int(row.get("VoteUpCount", row.get("vote_up_count"))),
                "comment_count": _as_int(row.get("CommentCount", row.get("comment_count"))),
                "authority_level": _first_text(row, "AuthorityLevel", "authority_level"),
                "ranking_score": _as_float(row.get("RankingScore", row.get("ranking_score"))),
                "content_id": _first_text(row, "ContentID", "content_id"),
            }
            if len(searches) > 1:
                metadata["search_query"] = search
            items.append(
                RawItem(
                    source_id=spec["id"],
                    source_name=spec.get("name") or ("微信公众号" if kind == "global_search" else "知乎"),
                    channel=spec.get("channel", "work"),
                    title=_clean(title),
                    summary=_clean(_first_text(row, "ContentText", "summary", "snippet", "excerpt", "description", "content", "abstract"))[:280],
                    source_url=url,
                    published_at=_search_published_at(row),
                    item_type=_platform_content_type(row, spec),
                    metadata=metadata,
                )
            )
            if len(items) >= limit:
                return items
    return items


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


def _get_json(url: str, headers: dict[str, str]) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **headers})
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=_CTX) as resp:
        payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    if not isinstance(payload, dict):
        raise ValueError("search API returned a non-object response")
    code = payload.get("Code", payload.get("code", 0))
    if code not in (0, "0", None):
        raise ValueError(str(payload.get("Message") or payload.get("message") or code))
    return payload


def _search_result_rows(value) -> list[dict]:
    rows: list[dict] = []
    if isinstance(value, dict):
        if any(value.get(key) for key in ("Url", "url", "URL", "link", "href", "source_url", "content_url")):
            rows.append(value)
        for child in value.values():
            rows.extend(_search_result_rows(child))
    elif isinstance(value, list):
        for child in value:
            rows.extend(_search_result_rows(child))
    return rows


def _first_text(row: dict, *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _search_published_at(row: dict) -> str:
    value = row.get("EditTime")
    if isinstance(value, (int, float)) and value > 0:
        from datetime import datetime, timezone

        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
    return _first_text(row, "published_at", "publish_time", "created_at", "date", "time")


def _platform_content_type(row: dict, spec: dict) -> str:
    raw = _first_text(row, "ContentType", "content_type").lower()
    return {"article": "article", "answer": "article", "question": "article"}.get(raw, spec.get("type") or "article")


def _as_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _as_float(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _host_allowed(url: str, allowed: list[str]) -> bool:
    try:
        host = (urllib.parse.urlparse(url).hostname or "").lower()
    except ValueError:
        return False
    return bool(host) and (not allowed or any(host == domain or host.endswith(f".{domain}") for domain in allowed))


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
