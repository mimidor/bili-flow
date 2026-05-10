from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
import json
import re
import xml.etree.ElementTree as ET

import requests

from config import Config


@dataclass(slots=True)
class WeWeFeedInfo:
    feed_id: str
    title: str
    homepage_url: str | None = None
    atom_url: str | None = None
    rss_url: str | None = None
    json_url: str | None = None
    raw: dict[str, Any] | None = None


@dataclass(slots=True)
class WeWeFeedEntry:
    entry_id: str
    feed_id: str
    title: str
    link: str
    pub_date: datetime | None
    author: str | None
    content_text: str
    content_html: str | None
    raw: dict[str, Any]


class WeWeRssError(RuntimeError):
    pass


class _FeedCatalogParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.items: list[dict[str, str]] = []
        self._current_href: str | None = None
        self._current_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attr_map = {key.lower(): value or "" for key, value in attrs}
        href = attr_map.get("href")
        if href:
            self._current_href = href
            self._current_text = []

    def handle_data(self, data: str) -> None:
        if self._current_href:
            self._current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self._current_href:
            return
        text = "".join(self._current_text).strip()
        self.items.append({"href": self._current_href, "text": text})
        self._current_href = None
        self._current_text = []


def _strip_html(value: str | None) -> str:
    if not value:
        return ""
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", value, flags=re.I | re.S)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def _ensure_base_url(base_url: str | None = None) -> str:
    url = (base_url or Config.WEWE_RSS_BASE_URL or "").strip().rstrip("/")
    return url


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is None else value.astimezone(timezone.utc).replace(tzinfo=None)
    if isinstance(value, (int, float)):
        try:
            ts = float(value)
            if ts > 10_000_000_000:
                ts = ts / 1000.0
            return datetime.utcfromtimestamp(ts)
        except Exception:
            return None
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        try:
            ts = int(text)
            if ts > 10_000_000_000:
                ts = ts // 1000
            return datetime.utcfromtimestamp(ts)
        except Exception:
            return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except Exception:
        pass
    try:
        parsed = parsedate_to_datetime(text)
        if parsed is None:
            return None
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except Exception:
        return None


def _coalesce_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            text = value.strip()
        else:
            text = str(value).strip()
        if text:
            return text
    return ""


def _extract_json_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("feeds", "items", "data", "list", "results", "entries"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = _extract_json_list(value)
            if nested:
                return nested
    return []


def _extract_json_text(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        for key in ("content_text", "content", "description", "summary", "text"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        for key in ("content_html", "contentHtml", "content_html", "html"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return _strip_html(value)
    return ""


def _parse_feed_id_from_url(url: str) -> str | None:
    try:
        parsed = urlparse(url)
        match = re.search(r"/feeds/([^/?#]+)\.(?:atom|rss|json)$", parsed.path)
        if match:
            return match.group(1)
    except Exception:
        return None
    return None


def _parse_feed_catalog_html(base_url: str, body: str) -> list[WeWeFeedInfo]:
    parser = _FeedCatalogParser()
    parser.feed(body)
    items: list[WeWeFeedInfo] = []
    seen: set[str] = set()
    for anchor in parser.items:
        href = anchor.get("href") or ""
        text = _coalesce_text(anchor.get("text"))
        absolute = urljoin(base_url.rstrip("/") + "/", href)
        feed_id = _parse_feed_id_from_url(absolute)
        if not feed_id or feed_id in seen:
            continue
        seen.add(feed_id)
        homepage_url = absolute
        if homepage_url.endswith((".atom", ".rss", ".json")):
            homepage_url = homepage_url.rsplit(".", 1)[0]
        title = text or feed_id
        items.append(
            WeWeFeedInfo(
                feed_id=feed_id,
                title=title,
                homepage_url=homepage_url,
                atom_url=urljoin(base_url.rstrip("/") + "/", f"feeds/{feed_id}.atom"),
                rss_url=urljoin(base_url.rstrip("/") + "/", f"feeds/{feed_id}.rss"),
                json_url=urljoin(base_url.rstrip("/") + "/", f"feeds/{feed_id}.json"),
                raw={"href": href, "text": text},
            )
        )
    return items


def _parse_feed_catalog_json(base_url: str, payload: Any) -> list[WeWeFeedInfo]:
    items: list[WeWeFeedInfo] = []
    seen: set[str] = set()
    for item in _extract_json_list(payload):
        feed_id = _coalesce_text(
            item.get("feedId"),
            item.get("feed_id"),
            item.get("id"),
            item.get("sourceId"),
            item.get("source_id"),
            item.get("accountId"),
            item.get("account_id"),
        )
        if not feed_id or feed_id in seen:
            continue
        seen.add(feed_id)
        title = _coalesce_text(
            item.get("name"),
            item.get("title"),
            item.get("alias"),
            item.get("displayName"),
            item.get("display_name"),
            feed_id,
        )
        homepage_url = _coalesce_text(item.get("homepage_url"), item.get("url"), item.get("link"), item.get("homepageUrl"))
        if not homepage_url:
            homepage_url = urljoin(base_url.rstrip("/") + "/", f"feeds/{feed_id}.atom")
        items.append(
            WeWeFeedInfo(
                feed_id=feed_id,
                title=title,
                homepage_url=homepage_url,
                atom_url=urljoin(base_url.rstrip("/") + "/", f"feeds/{feed_id}.atom"),
                rss_url=urljoin(base_url.rstrip("/") + "/", f"feeds/{feed_id}.rss"),
                json_url=urljoin(base_url.rstrip("/") + "/", f"feeds/{feed_id}.json"),
                raw=item,
            )
        )
    return items


def _find_xml_text(element: ET.Element, paths: list[str]) -> str:
    for path in paths:
        found = element.find(path)
        if found is not None and found.text and found.text.strip():
            return found.text.strip()
    return ""


def _first_xml_attr(element: ET.Element, paths: list[str], attr_name: str) -> str:
    for path in paths:
        found = element.find(path)
        if found is not None:
            value = found.attrib.get(attr_name)
            if value:
                return value.strip()
    return ""


def _parse_xml_entries(base_url: str, body: str, *, feed_id: str, format_hint: str) -> list[WeWeFeedEntry]:
    try:
        root = ET.fromstring(body)
    except Exception as exc:
        raise WeWeRssError(f"invalid XML feed: {exc}") from exc

    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "rss": "http://purl.org/rss/1.0/",
        "content": "http://purl.org/rss/1.0/modules/content/",
        "dc": "http://purl.org/dc/elements/1.1/",
        "media": "http://search.yahoo.com/mrss/",
    }

    entries: list[WeWeFeedEntry] = []
    if root.tag.endswith("feed"):
        entry_nodes = list(root.findall("atom:entry", ns)) or list(root.findall("entry"))
        for entry in entry_nodes:
            entry_id = _find_xml_text(entry, ["atom:id", "id", "guid"])
            title = _find_xml_text(entry, ["atom:title", "title"]) or entry_id
            link = ""
            for link_node in entry.findall("atom:link", ns) + entry.findall("link"):
                href = link_node.attrib.get("href") or ""
                rel = (link_node.attrib.get("rel") or "").lower()
                if href and (not rel or rel == "alternate"):
                    link = href
                    break
            if not link:
                link = entry_id
            published = _find_xml_text(entry, ["atom:published", "published", "updated"])
            author = _find_xml_text(entry, ["atom:author/atom:name", "author/name", "dc:creator", "creator"])
            summary = _find_xml_text(entry, ["atom:summary", "summary"])
            content = _find_xml_text(entry, ["atom:content", "content"])
            content_html = content or summary
            content_text = _strip_html(content or summary)
            if not content_text:
                content_text = _coalesce_text(summary, content)
            entries.append(
                WeWeFeedEntry(
                    entry_id=_coalesce_text(entry_id, link, f"{feed_id}:{title}"),
                    feed_id=feed_id,
                    title=title,
                    link=link,
                    pub_date=_parse_datetime(published),
                    author=author or None,
                    content_text=content_text,
                    content_html=content_html or None,
                    raw={"format": format_hint, "xml": title, "entry": entry_id},
                )
            )
        return entries

    item_nodes = list(root.findall("./channel/item")) or list(root.findall("item"))
    for item in item_nodes:
        guid = _find_xml_text(item, ["guid"])
        title = _find_xml_text(item, ["title"]) or guid
        link = _find_xml_text(item, ["link"]) or guid
        published = _find_xml_text(item, ["pubDate", "dc:date", "{http://purl.org/dc/elements/1.1/}date"])
        author = _find_xml_text(item, ["author", "dc:creator", "{http://purl.org/dc/elements/1.1/}creator"])
        summary = _find_xml_text(item, ["description", "{http://purl.org/rss/1.0/modules/content/}encoded"])
        content_html = summary
        content_text = _strip_html(summary)
        if not content_text:
            content_text = _coalesce_text(summary, title)
        entries.append(
            WeWeFeedEntry(
                entry_id=_coalesce_text(guid, link, f"{feed_id}:{title}"),
                feed_id=feed_id,
                title=title,
                link=link,
                pub_date=_parse_datetime(published),
                author=author or None,
                content_text=content_text,
                content_html=content_html or None,
                raw={"format": format_hint, "xml": title, "guid": guid},
            )
        )
    return entries


def _parse_json_entries(feed_id: str, payload: Any, *, format_hint: str) -> list[WeWeFeedEntry]:
    items = _extract_json_list(payload)
    if not items and isinstance(payload, dict):
        items = _extract_json_list(payload.get("feed") or {})

    entries: list[WeWeFeedEntry] = []
    for item in items:
        entry_id = _coalesce_text(
            item.get("id"),
            item.get("guid"),
            item.get("entry_id"),
            item.get("url"),
            item.get("link"),
            item.get("title"),
        )
        title = _coalesce_text(item.get("title"), item.get("headline"), item.get("name"), entry_id)
        link = _coalesce_text(item.get("url"), item.get("link"), item.get("homepage_url"), entry_id)
        author = _coalesce_text(
            item.get("author"),
            item.get("author_name"),
            item.get("creator"),
            item.get("publisher"),
        )
        published = _parse_datetime(
            item.get("date_published")
            or item.get("published")
            or item.get("pubDate")
            or item.get("updated")
            or item.get("date_modified")
        )
        content_html = _coalesce_text(item.get("content_html"), item.get("contentHtml"), item.get("html"))
        content_text = _coalesce_text(
            item.get("content_text"),
            item.get("content"),
            item.get("description"),
            item.get("summary"),
        )
        if content_html and not content_text:
            content_text = _strip_html(content_html)
        if not content_text:
            content_text = _strip_html(content_html) or title
        entries.append(
            WeWeFeedEntry(
                entry_id=entry_id,
                feed_id=feed_id,
                title=title,
                link=link,
                pub_date=published,
                author=author or None,
                content_text=content_text,
                content_html=content_html or None,
                raw=item,
            )
        )
    return entries


class WeWeRssClient:
    def __init__(self, base_url: str | None = None, *, auth_code: str | None = None, timeout: int = 30) -> None:
        self.base_url = _ensure_base_url(base_url)
        self.auth_code = (auth_code or "").strip()
        self.timeout = timeout
        self.session = requests.Session()

    def close(self) -> None:
        try:
            self.session.close()
        except Exception:
            pass

    def _build_url(self, path: str) -> str:
        if not self.base_url:
            raise WeWeRssError("WEWE_RSS_BASE_URL is not configured")
        return f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"

    def _auth_headers(self) -> dict[str, str]:
        if not self.auth_code:
            return {}
        return {
            "X-Auth-Code": self.auth_code,
            "AUTH_CODE": self.auth_code,
            "Authorization": f"Bearer {self.auth_code}",
        }

    def request(self, method: str, path: str, *, params: dict[str, Any] | None = None) -> requests.Response:
        url = self._build_url(path)
        response = self.session.request(method, url, params=params, timeout=self.timeout, headers=self._auth_headers())
        response.raise_for_status()
        return response

    def list_feeds(self) -> list[WeWeFeedInfo]:
        response = self.request("GET", "/feeds/")
        content_type = (response.headers.get("content-type") or "").lower()
        text = response.text or ""

        if "application/json" in content_type or text.lstrip().startswith(("{", "[")):
            try:
                payload = response.json()
            except Exception as exc:
                raise WeWeRssError(f"invalid JSON catalog: {exc}") from exc
            return _parse_feed_catalog_json(self.base_url, payload)

        if "xml" in content_type or text.lstrip().startswith("<?xml") or "<feed" in text[:200].lower():
            try:
                root = ET.fromstring(text)
                payload = {"root": root.tag}
                return _parse_feed_catalog_json(self.base_url, payload)
            except Exception:
                pass

        return _parse_feed_catalog_html(self.base_url, text)

    def fetch_feed_entries(
        self,
        feed_id: str,
        *,
        format: str = "atom",
        limit: int = 10,
        page: int = 1,
        mode: str = "summary",
        update: bool = False,
    ) -> list[WeWeFeedEntry]:
        suffix = {"atom": "atom", "rss": "rss", "json": "json"}.get((format or "atom").lower(), "atom")
        params: dict[str, Any] = {
            "limit": int(limit),
            "page": int(page),
        }
        if mode:
            params["mode"] = mode
        if update:
            params["update"] = "true"
        response = self.request("GET", f"/feeds/{feed_id}.{suffix}", params=params)
        content_type = (response.headers.get("content-type") or "").lower()
        text = response.text or ""

        if suffix == "json" or "application/feed+json" in content_type or text.lstrip().startswith(("{", "[")):
            try:
                payload = response.json()
            except Exception as exc:
                raise WeWeRssError(f"invalid JSON feed: {exc}") from exc
            return _parse_json_entries(feed_id, payload, format_hint=suffix)

        return _parse_xml_entries(self.base_url, text, feed_id=feed_id, format_hint=suffix)


def build_feed_urls(base_url: str, feed_id: str) -> dict[str, str]:
    normalized = base_url.rstrip("/")
    return {
        "homepage_url": f"{normalized}/feeds/{feed_id}",
        "atom_url": f"{normalized}/feeds/{feed_id}.atom",
        "rss_url": f"{normalized}/feeds/{feed_id}.rss",
        "json_url": f"{normalized}/feeds/{feed_id}.json",
    }
