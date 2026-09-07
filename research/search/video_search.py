"""Multi-source adult and web video search provider aggregating all major tubes."""

from __future__ import annotations

import concurrent.futures
import json
import logging
import re
from typing import Any
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup
import httpx

try:
    from curl_cffi import requests as cffi_requests
except ImportError:
    cffi_requests = None

from ddgs import DDGS

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


class VideoSearchProvider:
    """Searches across all major adult video platforms and web video indexes in parallel."""

    def __init__(self, timeout: int = 12) -> None:
        self.timeout = timeout
        self.client = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            timeout=timeout,
        )
        self.session = None
        if cffi_requests is not None:
            try:
                self.session = cffi_requests.Session(impersonate="chrome124")
            except Exception:
                self.session = None

    def _get(self, url: str, params: dict | None = None, timeout: int = 8) -> str | None:
        """Fast HTTP GET using curl_cffi or httpx."""
        if self.session:
            try:
                r = self.session.get(url, params=params, timeout=timeout)
                if r.status_code == 200:
                    return r.text
            except Exception:
                pass

        try:
            r = self.client.get(url, params=params, timeout=timeout)
            if r.status_code == 200:
                return r.text
        except Exception:
            pass

        return None

    def search_videos(self, query: str, max_results: int = 36, source: str | None = None) -> list[dict[str, Any]]:
        """Search videos across HDThot, Pornhub, Eporner, SpankBang, XHamster, RedTube, YouPorn, and DDG."""
        results_by_source: dict[str, list[dict[str, Any]]] = {}
        per_source = max(8, max_results // 4)

        all_sources = [
            ("HDThot", lambda: self._search_hdthot(query, max_results if source and source.lower() == "hdthot" else per_source)),
            ("PimpBunny", lambda: self._search_pimpbunny(query, max_results if source and source.lower() == "pimpbunny" else per_source)),
            ("Bunkr", lambda: self._search_bunkr(query, max_results if source and source.lower() == "bunkr" else per_source)),
            ("Pornhub", lambda: self._search_pornhub(query, max_results if source and source.lower() == "pornhub" else per_source)),
            ("RedTube", lambda: self._search_redtube(query, max_results if source and source.lower() == "redtube" else per_source)),
            ("YouPorn", lambda: self._search_youporn(query, max_results if source and source.lower() == "youporn" else per_source)),
            ("SpankBang", lambda: self._search_spankbang(query, max_results if source and source.lower() == "spankbang" else per_source)),
            ("XHamster", lambda: self._search_xhamster(query, max_results if source and source.lower() == "xhamster" else per_source)),
            ("DuckDuckGo", lambda: self._search_ddg_videos(query, per_source)),
        ]

        # Filter by requested source if specified
        if source and source.lower() != "all":
            active_sources = [s for s in all_sources if s[0].lower() == source.lower()]
            if not active_sources:
                active_sources = all_sources
        else:
            active_sources = all_sources

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(active_sources)) as executor:
            future_to_source = {executor.submit(fn): name for name, fn in active_sources}
            for future in concurrent.futures.as_completed(future_to_source):
                src_name = future_to_source[future]
                try:
                    res = future.result()
                    results_by_source[src_name] = res
                except Exception as e:
                    logger.debug("Source %s failed: %s", src_name, e)
                    results_by_source[src_name] = []

        # If single source requested, return its results directly
        if source and source.lower() != "all" and len(active_sources) == 1:
            return list(results_by_source.values())[0][:max_results] if results_by_source else []

        # Interleave results across sources for diverse platform representation
        combined: list[dict[str, Any]] = []
        max_len = max((len(v) for v in results_by_source.values()), default=0)

        seen_urls: set[str] = set()
        for idx in range(max_len):
            for src_name, items in results_by_source.items():
                if idx < len(items):
                    item = items[idx]
                    u = item.get("url", "").lower().rstrip("/")
                    if u and u not in seen_urls:
                        seen_urls.add(u)
                        combined.append(item)
                        if len(combined) >= max_results:
                            break
            if len(combined) >= max_results:
                break

        return combined

    def _search_hdthot(self, query: str, limit: int) -> list[dict[str, Any]]:
        """HDThot adult video aggregator search."""
        videos: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        # 1. Fast JSON suggest endpoint
        try:
            suggest_url = f"https://hdthot.com/search/suggest?s={quote_plus(query)}"
            text = self._get(suggest_url, timeout=5)
            if text:
                data = json.loads(text)
                for item in data.get("videos", []):
                    title = item.get("title", "").strip()
                    url = item.get("url", "").strip()
                    if url and title and url not in seen_urls:
                        seen_urls.add(url)
                        videos.append({
                            "title": title,
                            "url": url,
                            "thumbnail": item.get("image", ""),
                            "duration": str(item.get("duration", "")),
                            "views": item.get("views", "—"),
                            "site": "HDThot",
                        })
        except Exception:
            pass

        # 2. Full HTML search page
        if len(videos) < limit:
            try:
                search_url = f"https://hdthot.com/?s={quote_plus(query)}"
                html = self._get(search_url, timeout=7)
                if html:
                    soup = BeautifulSoup(html, "html.parser")
                    posts = soup.select(".post, article.post, .video-item")
                    for post in posts:
                        link_el = post.select_one("a.post-thumb, a[href*='hdthot.com/']")
                        if not link_el:
                            continue
                        url = link_el.get("href", "").strip()
                        title = link_el.get("title", "").strip()

                        img = post.select_one("img.thumb, img")
                        thumb = img.get("src", "").strip() if img else ""

                        dur_el = post.select_one(".duration, .video-duration, div.play-icon + div")
                        dur = dur_el.get_text(strip=True) if dur_el else ""

                        views_el = post.select_one(".views, .video-views")
                        views = views_el.get_text(strip=True) if views_el else "—"

                        if not title:
                            title_el = post.select_one("h2, .title, .post-title")
                            if title_el:
                                title = title_el.get_text(strip=True)

                        if url and title and url not in seen_urls:
                            seen_urls.add(url)
                            videos.append({
                                "title": title,
                                "url": url,
                                "thumbnail": thumb,
                                "duration": dur,
                                "views": views,
                                "site": "HDThot",
                            })
                            if len(videos) >= limit:
                                break
            except Exception:
                pass

        return videos

    def _search_eporner(self, query: str, limit: int) -> list[dict[str, Any]]:
        """Official Eporner JSON API."""
        url = f"https://www.eporner.com/api/v2/video/search/?query={quote_plus(query)}&per_page={limit}&thumbsize=big&order=top-weekly"
        text = self._get(url, timeout=6)
        if not text:
            return []

        try:
            data = json.loads(text)
        except Exception:
            return []

        videos: list[dict[str, Any]] = []
        for v in data.get("videos", []):
            title = v.get("title", "")
            video_url = v.get("url", "")
            thumb = v.get("default_thumb", {}).get("src") or (v.get("thumbs", [{}])[0].get("src") if v.get("thumbs") else "")
            dur = v.get("length_min", "") or f"{v.get('length_sec', 0)//60}:{v.get('length_sec', 0)%60:02d}"
            views = v.get("views", 0)

            if not video_url or not title:
                continue

            videos.append({
                "title": title,
                "url": video_url,
                "thumbnail": thumb,
                "duration": dur,
                "views": views,
                "site": "Eporner",
            })
            if len(videos) >= limit:
                break

        return videos

    def _search_pornhub(self, query: str, limit: int) -> list[dict[str, Any]]:
        """Pornhub search scraper with strict deduplication."""
        url = f"https://www.pornhub.com/video/search?search={quote_plus(query)}"
        html = self._get(url, timeout=8)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select("li[data-video-vkey], .videoBlock, .pcVideoListItem")
        videos: list[dict[str, Any]] = []
        seen_vkeys: set[str] = set()
        seen_urls: set[str] = set()

        for card in cards:
            link = card.select_one("a[href*='/view_video.php']")
            if not link:
                continue
            raw_href = link.get("href", "")
            if not raw_href:
                continue

            vkey_match = re.search(r"viewkey=([a-zA-Z0-9]+)", raw_href)
            vkey = vkey_match.group(1) if vkey_match else raw_href
            if vkey in seen_vkeys:
                continue
            seen_vkeys.add(vkey)

            video_url = f"https://www.pornhub.com/view_video.php?viewkey={vkey}" if vkey_match else urljoin("https://www.pornhub.com", raw_href)
            if video_url in seen_urls:
                continue
            seen_urls.add(video_url)

            title = link.get("title") or link.get_text(strip=True)
            if not title:
                title_el = card.select_one(".title a, .title, span.title")
                if title_el:
                    title = title_el.get("title") or title_el.get_text(strip=True)

            img = card.select_one("img[src], img[data-src], img[data-thumb_url], img[data-image]")
            thumb = ""
            if img:
                thumb = img.get("data-src") or img.get("data-thumb_url") or img.get("data-image") or img.get("src") or ""
                if thumb.startswith("//"):
                    thumb = "https:" + thumb

            dur_el = card.select_one(".duration, var.duration")
            dur = dur_el.get_text(strip=True) if dur_el else ""

            views_el = card.select_one(".views var, .views, span.views")
            views = views_el.get_text(strip=True) if views_el else "—"

            if not video_url or not title or len(title) < 3:
                continue

            videos.append({
                "title": title,
                "url": video_url,
                "thumbnail": thumb,
                "duration": dur,
                "views": views,
                "site": "Pornhub",
            })
            if len(videos) >= limit:
                break

        return videos

    def _search_spankbang(self, query: str, limit: int) -> list[dict[str, Any]]:
        """SpankBang video search."""
        url = f"https://spankbang.com/s/{quote_plus(query)}/"
        html = self._get(url, timeout=7)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(".video-item")
        videos: list[dict[str, Any]] = []

        for card in cards:
            link = card.select_one("a.thumb, a.n, a[href*='/video/']")
            if not link:
                continue
            video_url = urljoin("https://spankbang.com", link["href"])
            title_el = card.select_one("a.n, .title, a[title]")
            title = title_el.get_text(strip=True) if title_el else link.get("title", "")
            
            img = card.select_one("img[src], img[data-src]")
            thumb = img.get("data-src") or img.get("src") or "" if img else ""
            if thumb.startswith("//"):
                thumb = "https:" + thumb

            dur_el = card.select_one(".l, .length")
            dur = dur_el.get_text(strip=True) if dur_el else ""

            views_el = card.select_one(".v, .views")
            views = views_el.get_text(strip=True) if views_el else "—"

            if not video_url or not title:
                continue

            videos.append({
                "title": title,
                "url": video_url,
                "thumbnail": thumb,
                "duration": dur,
                "views": views,
                "site": "SpankBang",
            })
            if len(videos) >= limit:
                break

        return videos

    def _search_xhamster(self, query: str, limit: int) -> list[dict[str, Any]]:
        """XHamster video search."""
        url = f"https://xhamster.com/search/{quote_plus(query)}"
        html = self._get(url, timeout=7)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(".video-thumb, .thumb-list__item, [data-video-id]")
        videos: list[dict[str, Any]] = []

        for card in cards:
            link = card.select_one("a[href*='/videos/']")
            if not link:
                continue
            video_url = urljoin("https://xhamster.com", link["href"])
            
            title_el = card.select_one("a[data-qa='video-title'], .video-thumb-info__name, .video-thumb__name, .video-title, a[title]")
            title = ""
            if title_el:
                title = title_el.get("title") or title_el.get_text(strip=True)
            if not title:
                title = link.get("title") or link.get_text(strip=True)
            
            img = card.select_one("img[src], img[data-src], img[data-thumb]")
            thumb = img.get("data-src") or img.get("data-thumb") or img.get("src") or "" if img else ""
            if thumb.startswith("//"):
                thumb = "https:" + thumb

            dur_el = card.select_one(".thumb-image-container__duration, [data-role='video-duration'], .duration, [data-qa='video-duration']")
            dur = dur_el.get_text(strip=True) if dur_el else ""

            views_el = card.select_one(".views, [data-role='video-views'], [data-qa='video-views']")
            views = views_el.get_text(strip=True) if views_el else "—"

            if not video_url or not title or len(title) < 3:
                continue

            videos.append({
                "title": title,
                "url": video_url,
                "thumbnail": thumb,
                "duration": dur,
                "views": views,
                "site": "XHamster",
            })
            if len(videos) >= limit:
                break

        return videos

    def _search_redtube(self, query: str, limit: int) -> list[dict[str, Any]]:
        """RedTube JSON API."""
        url = f"https://api.redtube.com/?data=redtube.Videos.searchVideos&output=json&search={quote_plus(query)}"
        text = self._get(url, timeout=6)
        if not text:
            return []

        try:
            data = json.loads(text)
        except Exception:
            return []

        raw_list = data.get("videos", [])
        videos: list[dict[str, Any]] = []

        for item in raw_list:
            v = item.get("video", {})
            title = v.get("title", "")
            video_url = v.get("url", "")
            thumb = v.get("default_thumb") or v.get("thumb") or ""
            duration = v.get("duration", "")
            views = v.get("views", 0)

            if not video_url or not title:
                continue

            videos.append({
                "title": title,
                "url": video_url,
                "thumbnail": thumb,
                "duration": str(duration),
                "views": views,
                "site": "RedTube",
            })
            if len(videos) >= limit:
                break

        return videos

    def _search_youporn(self, query: str, limit: int) -> list[dict[str, Any]]:
        """YouPorn search scraper."""
        url = f"https://www.youporn.com/search/?query={quote_plus(query)}"
        html = self._get(url, timeout=6)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(".video-box, .four-col-item, [data-video-id], .video-card")
        videos: list[dict[str, Any]] = []

        for card in cards:
            link = card.select_one("a[href*='/watch/']")
            if not link:
                continue
            video_url = urljoin("https://www.youporn.com", link["href"])
            
            title_el = card.select_one(".video-title, .video-box-title, a[title]")
            title = ""
            if title_el:
                title = title_el.get("title") or title_el.get_text(strip=True)
            if not title:
                title = link.get("title") or link.get_text(strip=True)
            
            img = card.select_one("img[src], img[data-src], img[data-thumb]")
            thumb = img.get("data-src") or img.get("data-thumb") or img.get("src") or "" if img else ""
            if thumb.startswith("//"):
                thumb = "https:" + thumb

            dur_el = card.select_one(".duration, .video-duration")
            dur = dur_el.get_text(strip=True) if dur_el else ""

            views_el = card.select_one(".views, .video-views")
            views = views_el.get_text(strip=True) if views_el else "—"

            if not video_url or not title or len(title) < 3:
                continue

            videos.append({
                "title": title,
                "url": video_url,
                "thumbnail": thumb,
                "duration": dur,
                "views": views,
                "site": "YouPorn",
            })
            if len(videos) >= limit:
                break

        return videos

    def _search_ddg_videos(self, query: str, limit: int) -> list[dict[str, Any]]:
        """DuckDuckGo Multi-publisher web video aggregator."""
        videos: list[dict[str, Any]] = []
        try:
            with DDGS() as ddgs:
                for hit in ddgs.videos(query, max_results=limit, safesearch="off"):
                    title = hit.get("title", "")
                    url = hit.get("content", "") or hit.get("url", "")
                    img_dict = hit.get("images", {})
                    thumb = img_dict.get("medium") or img_dict.get("small") or img_dict.get("large") or ""
                    dur = hit.get("duration", "")
                    pub = hit.get("publisher", "Web Tube")

                    if not url or not title:
                        continue

                    videos.append({
                        "title": title,
                        "url": url,
                        "thumbnail": thumb,
                        "duration": dur,
                        "views": hit.get("statistics", {}).get("viewCount", "—"),
                        "site": pub,
                    })
                    if len(videos) >= limit:
                        break
        except Exception:
            pass

        return videos

    def _search_pimpbunny(self, query: str, limit: int) -> list[dict[str, Any]]:
        """PimpBunny video search aggregator."""
        import urllib.parse
        url = f"https://pimpbunny.com/search/{urllib.parse.quote(query)}/"
        html = self._get(url, timeout=8)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        videos: list[dict[str, Any]] = []
        seen_urls = set()

        for a in soup.select("a[href*='/videos/']"):
            href = a.get("href", "")
            if not href or href in ["https://pimpbunny.com/videos/", "/videos/"] or "?sort_by=" in href:
                continue
            if not href.startswith("http"):
                href = urljoin("https://pimpbunny.com", href)
            if href in seen_urls:
                continue

            img = a.select_one("img")
            thumb = (img.get("src") or img.get("data-src") or "") if img else ""
            title = a.get("title") or a.get_text(strip=True)
            if not title or len(title) < 3 or title.lower().startswith("this site"):
                continue

            dur_el = a.select_one(".duration, [class*='duration'], span.time")
            dur = dur_el.get_text(strip=True) if dur_el else ""

            seen_urls.add(href)
            videos.append({
                "title": title,
                "url": href,
                "thumbnail": thumb,
                "duration": dur,
                "views": "HD",
                "site": "PimpBunny",
            })
            if len(videos) >= limit:
                break

        return videos

    def _search_bunkr(self, query: str, limit: int) -> list[dict[str, Any]]:
        """Bunkr album & video search aggregator with multi-domain fallback."""
        import urllib.parse
        videos: list[dict[str, Any]] = []
        seen_urls = set()

        # Try bunkr-albums.org
        try:
            url = f"https://bunkr-albums.org/?s={urllib.parse.quote_plus(query)}"
            html = self._get(url, timeout=8)
            if html:
                soup = BeautifulSoup(html, "html.parser")
                for a in soup.select("a[href*='/a/'], article a, .card a, h2 a, h3 a"):
                    href = a.get("href", "")
                    if not href or href in seen_urls:
                        continue
                    if "/a/" not in href and "bunkr" not in href:
                        continue

                    title = a.get_text(" ", strip=True)
                    if not title or len(title) < 3 or title.lower().startswith("view album"):
                        parent = a.parent
                        title = parent.get_text(" ", strip=True) if parent else title

                    title = re.sub(r"^(?:View\s*album\s*|\s*Open\s*|\s*\?\s*)+", "", title, flags=re.IGNORECASE).strip()
                    if not title:
                        title = f"Bunkr Album - {query.title()}"

                    img = a.select_one("img") or (a.parent.select_one("img") if a.parent else None)
                    thumb = (img.get("src") or img.get("data-src") or "") if img else ""

                    file_match = re.search(r"(\d+)\s*files?", title, re.I)
                    files_str = file_match.group(0) if file_match else "Album"

                    seen_urls.add(href)
                    videos.append({
                        "title": title,
                        "url": href,
                        "thumbnail": thumb,
                        "duration": files_str,
                        "views": "Archive",
                        "site": "Bunkr",
                    })
                    if len(videos) >= limit:
                        break
        except Exception as e:
            logger.debug("Bunkr video search error: %s", e)

        # Fallback to bunkrsearch.com
        if len(videos) < limit:
            try:
                url2 = f"https://bunkrsearch.com/search?q={urllib.parse.quote_plus(query)}"
                html2 = self._get(url2, timeout=8)
                if html2:
                    soup2 = BeautifulSoup(html2, "html.parser")
                    for a in soup2.select("a[href*='bunkr'], a[href*='/a/'], a[href*='/v/'], a[href*='/i/']"):
                        href = a.get("href", "")
                        if not href or href in seen_urls or href.startswith("https://t.me/"):
                            continue
                        if not href.startswith("http"):
                            href = "https://bunkrsearch.com" + href

                        title = a.get_text(strip=True) or f"Bunkr Media - {query}"
                        seen_urls.add(href)
                        videos.append({
                            "title": title,
                            "url": href,
                            "thumbnail": "",
                            "duration": "Pack",
                            "views": "Cloud",
                            "site": "Bunkr",
                        })
                        if len(videos) >= limit:
                            break
            except Exception as e:
                logger.debug("Bunkrsearch fallback video search error: %s", e)

        return videos

    def close(self) -> None:
        if self.session:
            try:
                self.session.close()
            except Exception:
                pass
        self.client.close()

