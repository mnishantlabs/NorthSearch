"""Direct ad-free video stream extractor and high-speed 8-part parallel PC download manager."""

from __future__ import annotations

import logging
import os
import re
import threading
import time
import urllib.parse
import uuid
from pathlib import Path
from typing import Any, Callable

import yt_dlp

logger = logging.getLogger(__name__)

# Default user downloads directory on PC
DEFAULT_DOWNLOADS_DIR = Path.home() / "Downloads"
DEFAULT_DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)


class StreamExtractor:
    """Extracts direct playable stream URLs (MP4 & HLS) and available qualities for video networks."""

    def __init__(self) -> None:
        self.ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "format": "best",
            "noplaylist": True,
            "extract_flat": False,
            "retries": 5,
        }

    def _normalize_url(self, url: str) -> list[str]:
        """Generates primary and fallback stream extraction URLs for maximum compatibility."""
        clean = url.strip()
        urls = [clean]

        # Pornhub: embed fallback
        ph_match = re.search(r"viewkey=([a-zA-Z0-9]+)", clean)
        if ph_match:
            ph_embed = f"https://www.pornhub.com/embed/{ph_match.group(1)}"
            if ph_embed not in urls:
                urls.append(ph_embed)

        # RedTube: embed fallback
        rt_match = re.search(r"redtube\.com/(\d+)", clean)
        if rt_match:
            rt_embed = f"https://embed.redtube.com/?id={rt_match.group(1)}"
            if rt_embed not in urls:
                urls.append(rt_embed)

        return urls

    def _extract_hdthot(self, url: str) -> dict[str, Any] | None:
        """Extracts direct m3u8 stream and metadata from HDThot."""
        import base64
        import httpx
        from bs4 import BeautifulSoup

        try:
            client = httpx.Client(
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"},
                follow_redirects=True,
                timeout=10.0,
            )
            resp = client.get(url)
            if resp.status_code != 200:
                return None

            soup = BeautifulSoup(resp.text, "html.parser")
            pw = soup.select_one("#player-wrap, .player-wrap, [data-source]")
            if not pw or not pw.get("data-source"):
                return None

            ds = pw.get("data-source", "")
            rev = ds[::-1]
            idx = rev.find("aHR0")
            if idx == -1:
                return None

            chunk = rev[idx:]
            m = re.match(r"([A-Za-z0-9+/=]+)", chunk)
            if not m:
                return None

            b64_str = m.group(1)
            stream_url = ""
            for cut in range(len(b64_str), max(0, len(b64_str) - 40), -1):
                test_str = b64_str[:cut]
                padded = test_str + "=" * ((4 - len(test_str) % 4) % 4)
                try:
                    raw = base64.b64decode(padded)
                    dec = raw.decode("utf-8", errors="ignore")
                    found = re.search(r"https?://[a-zA-Z0-9\.\-_/:]+\.m3u8(?:\?[a-zA-Z0-9=&_\-\.%]+)?", dec)
                    if found:
                        stream_url = found.group(0)
                        break
                except Exception:
                    continue

            if not stream_url:
                return None

            # Title & Metadata
            title = ""
            h1 = soup.select_one("h1, .video-title, .post-title, meta[property='og:title']")
            if h1:
                title = h1.get("content") or h1.get_text(strip=True)
            if not title:
                title = "HDThot Video Scene"

            thumb = ""
            og_img = soup.select_one("meta[property='og:image'], img.thumb, #player-wrap img")
            if og_img:
                thumb = og_img.get("content") or og_img.get("src") or ""

            dur = ""
            dur_el = soup.select_one(".duration, .video-duration")
            if dur_el:
                dur = dur_el.get_text(strip=True)

            return {
                "success": True,
                "title": title,
                "duration": 0,
                "duration_formatted": dur,
                "thumbnail": thumb,
                "webpage_url": url,
                "site": "HDThot",
                "stream_url": stream_url,
                "is_hls": True,
                "qualities": [
                    {
                        "format_id": "hls-1080p",
                        "height": 1080,
                        "label": "1080p Full HD (HLS)",
                        "ext": "mp4",
                        "url": stream_url,
                        "is_hls": True,
                        "filesize": None,
                        "filesize_mb": None,
                        "protocol": "m3u8",
                    },
                    {
                        "format_id": "hls-720p",
                        "height": 720,
                        "label": "720p HD (HLS)",
                        "ext": "mp4",
                        "url": stream_url,
                        "is_hls": True,
                        "filesize": None,
                        "filesize_mb": None,
                        "protocol": "m3u8",
                    },
                ],
                "embed_url": url,
            }
        except Exception as e:
            logger.debug("HDThot extraction error: %s", e)
            return None

    def _extract_pimpbunny(self, url: str) -> dict[str, Any] | None:
        """Extracts direct MP4 progressive video streams and resolutions from PimpBunny."""
        import httpx
        from bs4 import BeautifulSoup
        import re

        try:
            client = httpx.Client(
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    "Cookie": "kt_tcookie=1; kt_is_visited=1; age_verified=1;",
                },
                follow_redirects=True,
                timeout=12.0,
            )
            resp = client.get(url)
            if resp.status_code != 200:
                return None

            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Title
            title = ""
            title_tag = soup.select_one("h1, .video-title, .title, meta[property='og:title']")
            if title_tag:
                title = title_tag.get("content") or title_tag.get_text(strip=True)
            if not title or title.lower().startswith("this site") or title.lower() == "videos | pimpbunny":
                if soup.title and soup.title.string:
                    title = soup.title.string.replace("| PimpBunny", "").strip()
            if not title:
                title = "PimpBunny Video Scene"

            # Thumbnail
            thumb = ""
            og_img = soup.select_one("meta[property='og:image'], video[poster], img.thumb")
            if og_img:
                thumb = og_img.get("content") or og_img.get("poster") or og_img.get("src") or ""

            # Extract all progressive MP4 URLs in page — PimpBunny CDN may use different domains
            # Try 1: get_file pattern on any domain
            all_mp4s = list(set(re.findall(r"https?://[^\s\"'<>]+/get_file/[^\s\"'<>]+\.mp4[^\s\"'<>]*", resp.text)))
            # Try 2: any MP4 on known CDN patterns
            if not all_mp4s:
                all_mp4s = list(set(re.findall(r"https?://[^\s\"'<>]*(?:cdn|media|video|stream)[^\s\"'<>]*\.mp4[^\s\"'<>]*", resp.text, re.I)))
            # Try 3: any .mp4 URL
            if not all_mp4s:
                all_mp4s = list(set(re.findall(r"https?://[^\s\"'<>\?]+\.mp4", resp.text)))
            # Try 4: JSON/JS source objects  
            if not all_mp4s:
                all_mp4s = list(set(re.findall(r'(?:file|src|source|url)\s*[=:]\s*["\']([^"\']+\.mp4[^"\']*)["\']', resp.text, re.I)))
            # Filter out obvious non-video fragments
            all_mp4s = [u for u in all_mp4s if "pb_preview" not in u or len(all_mp4s) == 1]

            if not all_mp4s:
                return None

            qualities: list[dict[str, Any]] = []
            
            mp4_1080 = next((u for u in all_mp4s if "1080p" in u and "preview" not in u), None)
            mp4_720 = next((u for u in all_mp4s if "720p" in u and "preview" not in u), None)
            mp4_480 = next((u for u in all_mp4s if "480p" in u and "preview" not in u), None)
            mp4_360 = next((u for u in all_mp4s if "360p" in u and "preview" not in u), None)
            mp4_default = next((u for u in all_mp4s if not any(k in u for k in ["1080p", "720p", "480p", "360p", "preview", "pb_preview"])), None)
            mp4_preview = next((u for u in all_mp4s if "preview" in u), None)

            if mp4_1080:
                qualities.append({
                    "format_id": "pb-1080p",
                    "height": 1080,
                    "label": "1080p Full HD (Direct MP4)",
                    "ext": "mp4",
                    "url": mp4_1080,
                    "is_hls": False,
                    "filesize": None,
                    "filesize_mb": None,
                    "protocol": "https",
                })
            if mp4_720:
                qualities.append({
                    "format_id": "pb-720p",
                    "height": 720,
                    "label": "720p HD (Direct MP4)",
                    "ext": "mp4",
                    "url": mp4_720,
                    "is_hls": False,
                    "filesize": None,
                    "filesize_mb": None,
                    "protocol": "https",
                })
            if mp4_480:
                qualities.append({
                    "format_id": "pb-480p",
                    "height": 480,
                    "label": "480p SD (Direct MP4)",
                    "ext": "mp4",
                    "url": mp4_480,
                    "is_hls": False,
                    "filesize": None,
                    "filesize_mb": None,
                    "protocol": "https",
                })
            if mp4_360:
                qualities.append({
                    "format_id": "pb-360p",
                    "height": 360,
                    "label": "360p SD (Direct MP4)",
                    "ext": "mp4",
                    "url": mp4_360,
                    "is_hls": False,
                    "filesize": None,
                    "filesize_mb": None,
                    "protocol": "https",
                })
            if mp4_default and not qualities:
                qualities.append({
                    "format_id": "pb-direct",
                    "height": 720,
                    "label": "Direct MP4 Stream",
                    "ext": "mp4",
                    "url": mp4_default,
                    "is_hls": False,
                    "filesize": None,
                    "filesize_mb": None,
                    "protocol": "https",
                })
            if not qualities and mp4_preview:
                qualities.append({
                    "format_id": "pb-preview",
                    "height": 480,
                    "label": "Direct MP4 Stream",
                    "ext": "mp4",
                    "url": mp4_preview,
                    "is_hls": False,
                    "filesize": None,
                    "filesize_mb": None,
                    "protocol": "https",
                })

            if not qualities:
                return None

            best_stream = qualities[0]["url"]

            return {
                "success": True,
                "title": title,
                "duration": 0,
                "duration_formatted": "HD",
                "thumbnail": thumb,
                "webpage_url": url,
                "site": "PimpBunny",
                "stream_url": best_stream,
                "is_hls": False,
                "qualities": qualities,
                "embed_url": url,
            }
        except Exception as e:
            logger.debug("PimpBunny extraction error: %s", e)
            return None

    def _extract_bunkr(self, url: str) -> dict[str, Any] | None:
        """Extracts direct download/media streams from Bunkr albums or individual file pages."""
        import httpx
        from bs4 import BeautifulSoup
        import re

        try:
            client = httpx.Client(
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                },
                follow_redirects=True,
                timeout=12.0,
            )
            resp = client.get(url)
            if resp.status_code != 200:
                return None

            soup = BeautifulSoup(resp.text, "html.parser")
            title = ""
            if soup.title and soup.title.string:
                title = soup.title.string.replace("| Bunkr", "").strip()
            if not title:
                h1 = soup.select_one("h1, .entry-title")
                title = h1.get_text(strip=True) if h1 else "Bunkr Media"

            # Check if this is an album page (/a/...)
            if "/a/" in url:
                files = []
                for a in soup.select("a[href*='/f/'], a[href*='/v/'], a[href*='/i/'], a[href*='/d/']"):
                    f_href = a.get("href", "")
                    if f_href:
                        if not f_href.startswith("http"):
                            f_href = urllib.parse.urljoin(url, f_href)
                        files.append(f_href)
                
                if files:
                    first_file_url = files[0]
                    f_resp = client.get(first_file_url)
                    if f_resp.status_code == 200:
                        f_soup = BeautifulSoup(f_resp.text, "html.parser")
                        if f_soup.title and f_soup.title.string:
                            f_title = f_soup.title.string.replace("| Bunkr", "").strip()
                            if f_title:
                                title = f"{title} - {f_title}"
                        dl_tag = f_soup.select_one("a[href*='dl.'], a[href*='/file/'], a[download], video source, video")
                        direct_url = dl_tag.get("href") or dl_tag.get("src") if dl_tag else None
                        if not direct_url:
                            mp4_match = re.findall(r"https?://[^\s\"\'<>]+\.(?:mp4|m4v|mov|webm)", f_resp.text, re.I)
                            if mp4_match:
                                direct_url = mp4_match[0]
                        if direct_url:
                            return {
                                "success": True,
                                "title": title,
                                "duration": 0,
                                "duration_formatted": f"{len(files)} files",
                                "thumbnail": "",
                                "webpage_url": url,
                                "site": "Bunkr",
                                "stream_url": direct_url,
                                "is_hls": False,
                                "qualities": [
                                    {
                                        "format_id": "bunkr-orig",
                                        "height": 1080,
                                        "label": f"Original Media ({len(files)} items in album)",
                                        "ext": "mp4",
                                        "url": direct_url,
                                        "is_hls": False,
                                        "filesize": None,
                                        "filesize_mb": None,
                                        "protocol": "https",
                                    }
                                ],
                                "embed_url": url,
                            }

            # Individual file page (/f/..., /v/..., /i/..., /d/...)
            dl_tag = soup.select_one("a[href*='dl.'], a[href*='/file/'], a[download], video source, video")
            direct_url = dl_tag.get("href") or dl_tag.get("src") if dl_tag else None
            if not direct_url:
                mp4_match = re.findall(r"https?://[^\s\"\'<>]+\.(?:mp4|m4v|mov|webm)", resp.text, re.I)
                if mp4_match:
                    direct_url = mp4_match[0]

            if not direct_url:
                return None

            return {
                "success": True,
                "title": title,
                "duration": 0,
                "duration_formatted": "HD",
                "thumbnail": "",
                "webpage_url": url,
                "site": "Bunkr",
                "stream_url": direct_url,
                "is_hls": False,
                "qualities": [
                    {
                        "format_id": "bunkr-orig",
                        "height": 1080,
                        "label": "Original Quality (Direct Bunkr Stream)",
                        "ext": "mp4",
                        "url": direct_url,
                        "is_hls": False,
                        "filesize": None,
                        "filesize_mb": None,
                        "protocol": "https",
                    }
                ],
                "embed_url": url,
            }
        except Exception as e:
            logger.debug("Bunkr extraction error: %s", e)
            return None

    def extract_info(self, url: str) -> dict[str, Any]:
        """Extracts direct video stream URL, available formats/qualities, and metadata."""
        clean_url = url.strip()

        # Dedicated handler for HDThot
        if "hdthot.com" in clean_url:
            hdthot_info = self._extract_hdthot(clean_url)
            if hdthot_info:
                return hdthot_info

        # Dedicated handler for PimpBunny
        if "pimpbunny.com" in clean_url:
            pb_info = self._extract_pimpbunny(clean_url)
            if pb_info:
                return pb_info

        # Dedicated handler for Bunkr
        if any(d in clean_url for d in ["bunkr", "bunkrr"]):
            bunkr_info = self._extract_bunkr(clean_url)
            if bunkr_info:
                return bunkr_info

        target_urls = self._normalize_url(clean_url)
        last_error = ""

        for candidate_url in target_urls:
            try:
                with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                    info = ydl.extract_info(candidate_url, download=False)
                    if not info:
                        continue

                    title = info.get("title") or "Video Stream"
                    duration = info.get("duration") or 0
                    thumbnail = info.get("thumbnail") or ""
                    webpage_url = info.get("webpage_url") or clean_url
                    extractor = info.get("extractor") or "Web Video"

                    # Parse available formats/qualities
                    formats_raw = info.get("formats", [])
                    qualities: list[dict[str, Any]] = []
                    direct_stream_url = ""
                    best_hls_url = ""

                    # Sort formats by height and bitrate descending
                    sorted_formats = sorted(
                        formats_raw,
                        key=lambda f: (f.get("height") or 0, f.get("tbr") or 0),
                        reverse=True,
                    )

                    seen_heights: set[int] = set()
                    for f in sorted_formats:
                        f_url = f.get("url")
                        if not f_url:
                            continue

                        # Check if format has video
                        vcodec = f.get("vcodec") or ""
                        if vcodec == "none":
                            continue

                        height = f.get("height") or 0
                        format_id = str(f.get("format_id", ""))
                        format_note = f.get("format_note") or ""
                        ext = f.get("ext") or "mp4"
                        protocol = f.get("protocol") or ""
                        filesize = f.get("filesize") or f.get("filesize_approx") or 0
                        tbr = f.get("tbr") or 0

                        # Calculate approximate size if missing
                        if not filesize and tbr and duration:
                            filesize = int((tbr * 1000 / 8) * duration)

                        is_hls = "m3u8" in protocol or ".m3u8" in f_url or "hls" in format_id.lower()

                        if is_hls and not best_hls_url:
                            best_hls_url = f_url

                        label = f"{height}p" if height > 0 else (format_note or format_id or "Auto")
                        if height >= 1080:
                            label = f"{height}p Full HD"
                        elif height >= 720:
                            label = f"{height}p HD"
                        elif height >= 480:
                            label = f"{height}p SD"
                        elif height > 0:
                            label = f"{height}p"

                        if height not in seen_heights and height > 0:
                            seen_heights.add(height)
                            qualities.append({
                                "format_id": format_id,
                                "height": height,
                                "label": label,
                                "ext": ext,
                                "url": f_url,
                                "is_hls": is_hls,
                                "filesize": filesize,
                                "filesize_mb": round(filesize / (1024 * 1024), 1) if filesize > 0 else None,
                                "protocol": protocol,
                            })

                        # Prefer direct progressive MP4 stream for fastest playback
                        if not direct_stream_url and not is_hls and ("http" in protocol or ext == "mp4"):
                            direct_stream_url = f_url

                    # Fallback stream selection
                    if not direct_stream_url:
                        direct_stream_url = best_hls_url or info.get("url") or ""

                    if not qualities and direct_stream_url:
                        qualities.append({
                            "format_id": "best",
                            "height": 720,
                            "label": "Auto / Best Quality",
                            "ext": "mp4",
                            "url": direct_stream_url,
                            "is_hls": ".m3u8" in direct_stream_url,
                            "filesize": None,
                            "filesize_mb": None,
                            "protocol": "http",
                        })

                    return {
                        "success": True,
                        "title": title,
                        "duration": duration,
                        "duration_formatted": f"{int(duration)//60}:{int(duration)%60:02d}" if duration else "",
                        "thumbnail": thumbnail,
                        "webpage_url": webpage_url,
                        "site": extractor,
                        "stream_url": direct_stream_url,
                        "is_hls": ".m3u8" in direct_stream_url if direct_stream_url else False,
                        "qualities": qualities,
                    }

            except Exception as e:
                last_error = str(e)
                logger.debug("Candidate extraction failed for %s: %s", candidate_url, e)
                continue

        logger.error("All stream extractions failed for %s: %s", url, last_error)
        return {
            "success": False,
            "error": last_error or "Failed to extract direct stream",
            "title": "Video Stream",
            "webpage_url": clean_url,
            "stream_url": None,
            "is_hls": False,
            "qualities": [],
        }


class DownloadManager:
    """Manages high-speed 8-part parallel downloads into PC Downloads folder with live telemetry."""

    def __init__(self, downloads_dir: Path | None = None) -> None:
        self.downloads_dir = downloads_dir or DEFAULT_DOWNLOADS_DIR
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        self._tasks: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._pause_events: dict[str, threading.Event] = {}  # task_id -> Event (set = running, clear = paused)

    def get_status(self, task_id: str) -> dict[str, Any] | None:
        with self._lock:
            task = self._tasks.get(task_id)
            return task.copy() if task else None

    def get_all_tasks(self) -> list[dict[str, Any]]:
        """Return all active and completed download tasks ordered by most recent."""
        with self._lock:
            tasks = list(self._tasks.values())
            tasks.sort(key=lambda t: t.get("started_at", 0), reverse=True)
            return [t.copy() for t in tasks]

    def clear_completed(self) -> int:
        """Clear all finished or errored downloads from history."""
        with self._lock:
            to_del = [tid for tid, t in self._tasks.items() if t.get("state") in ("finished", "completed", "error", "cancelled")]
            for tid in to_del:
                del self._tasks[tid]
                self._pause_events.pop(tid, None)
            return len(to_del)

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a running download task."""
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id]["state"] = "cancelled"
                self._tasks[task_id]["error"] = "Download cancelled by user."
                # Also unblock any paused thread so it can see cancellation
                ev = self._pause_events.get(task_id)
                if ev:
                    ev.set()
                return True
        return False

    def pause_task(self, task_id: str) -> bool:
        """Pause a running download task (HTTP fallback path only)."""
        with self._lock:
            task = self._tasks.get(task_id)
            if task and task.get("state") == "downloading":
                ev = self._pause_events.get(task_id)
                if ev:
                    ev.clear()  # Clearing the event pauses the worker's wait() call
                task["state"] = "paused"
                return True
        return False

    def resume_task(self, task_id: str) -> bool:
        """Resume a paused download task."""
        with self._lock:
            task = self._tasks.get(task_id)
            if task and task.get("state") == "paused":
                ev = self._pause_events.get(task_id)
                if ev:
                    ev.set()  # Unblocks the worker's pause_event.wait()
                task["state"] = "downloading"
                return True
        return False

    def start_download(
        self,
        url: str,
        format_id: str | None = None,
        title: str | None = None,
        custom_title: str | None = None,
    ) -> dict[str, Any]:
        """Start downloading a video in the background with 8-part parallel acceleration."""
        task_id = str(uuid.uuid4())[:8]
        display_title = title or custom_title or "Downloading video..."

        # Parse requested resolution label
        quality_label = "Auto Best"
        if format_id and format_id != "best":
            h_match = re.search(r"(\d+)", str(format_id))
            if h_match:
                quality_label = f"{h_match.group(1)}p HD"
            else:
                quality_label = str(format_id)

        with self._lock:
            self._tasks[task_id] = {
                "task_id": task_id,
                "url": url,
                "state": "downloading",
                "percent": 0.0,
                "downloaded_bytes": 0,
                "total_bytes": 0,
                "speed_str": "0 KB/s",
                "eta_str": "--:--",
                "filename": "",
                "filepath": "",
                "quality_label": quality_label,
                "parallel_parts": 8,
                "error": None,
                "title": display_title,
                "started_at": time.time(),
            }
            # Create a pause event (set = running; clear = paused)
            pause_event = threading.Event()
            pause_event.set()  # Start in running state
            self._pause_events[task_id] = pause_event

        def _progress_hook(d: dict[str, Any]) -> None:
            # Check for cancellation
            with self._lock:
                task = self._tasks.get(task_id)
                if task and task.get("state") == "cancelled":
                    raise Exception("Download cancelled by user")

            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes") or 0
                speed = d.get("speed") or 0
                eta = d.get("eta") or 0

                percent = round((downloaded / total * 100), 1) if total > 0 else 0.0
                speed_str = f"{speed / (1024 * 1024):.1f} MB/s" if speed >= 1024 * 1024 else f"{speed / 1024:.0f} KB/s"
                eta_str = f"{int(eta)//60}:{int(eta)%60:02d}" if eta else "--:--"

                with self._lock:
                    if task_id in self._tasks:
                        self._tasks[task_id].update({
                            "state": "downloading",
                            "percent": percent,
                            "downloaded_bytes": downloaded,
                            "total_bytes": total,
                            "speed_str": speed_str,
                            "eta_str": eta_str,
                            "filename": Path(d.get("filename", "")).name,
                        })

            elif d.get("status") == "finished":
                filename = Path(d.get("filename", "")).name
                filepath = str(self.downloads_dir / filename)
                with self._lock:
                    if task_id in self._tasks:
                        self._tasks[task_id].update({
                            "state": "finished",
                            "percent": 100.0,
                            "speed_str": "Done",
                            "eta_str": "00:00",
                            "filename": filename,
                            "filepath": filepath,
                            "finished_at": time.time(),
                        })

        def _worker() -> None:
            out_template = str(self.downloads_dir / "%(title)s [%(resolution)s].%(ext)s")

            # Smart resilient format selection
            if not format_id or format_id == "best":
                fmt = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best"
            else:
                h_match = re.search(r"(\d+)", str(format_id))
                if h_match:
                    h = int(h_match.group(1))
                    fmt = f"{format_id}/bestvideo[height<={h}]+bestaudio/best[height<={h}]/best"
                else:
                    fmt = f"{format_id}/best"

            # Enable 8-part parallel concurrent fragment downloads
            ydl_opts = {
                "format": fmt,
                "outtmpl": out_template,
                "progress_hooks": [_progress_hook],
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
                "retries": 10,
                "fragment_retries": 10,
                "concurrent_fragment_downloads": 8,  # 8 Parallel chunks for maximum speed
                "http_chunk_size": 10485760,         # 10 MB chunks
            }

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    video_title = info.get("title", "Video")
                    with self._lock:
                        if task_id in self._tasks:
                            self._tasks[task_id]["title"] = video_title
            except Exception as e:
                err_msg = str(e)
                if "cancelled" in err_msg.lower():
                    logger.info("Task %s cancelled.", task_id)
                    return
                
                # Resilient fallback: direct HTTP multi-part stream download for PimpBunny, Bunkr, or direct media links
                try:
                    logger.info("yt-dlp failed for %s, trying direct HTTP stream download...", url)
                    direct_url = url
                    # If it's a webpage, try extract_info first
                    if not direct_url.endswith(".mp4") and "get_file" not in direct_url and "dl." not in direct_url:
                        info = _extractor.extract_info(url)
                        if info.get("stream_url"):
                            direct_url = info["stream_url"]
                            if info.get("title") and display_title == "Downloading video...":
                                display_title = info["title"]
                    
                    import httpx
                    safe_title = re.sub(r'[\\/*?:"<>|]', "", display_title).strip()[:60] or f"video_{task_id}"
                    out_file = self.downloads_dir / f"{safe_title}.mp4"
                    
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                        "Cookie": "kt_tcookie=1; kt_is_visited=1; age_verified=1;",
                    }
                    
                    with httpx.Client(headers=headers, follow_redirects=True, timeout=30.0) as client:
                        with client.stream("GET", direct_url) as resp:
                            if resp.status_code not in (200, 206):
                                raise Exception(f"HTTP stream error {resp.status_code}")
                            
                            total = int(resp.headers.get("content-length", 0))
                            downloaded = 0
                            start_t = time.time()
                            
                            with out_file.open("wb") as f:
                                for chunk in resp.iter_bytes(chunk_size=1048576): # 1MB chunks
                                    # Block here when paused (event is cleared)
                                    pause_event.wait()
                                    with self._lock:
                                        if self._tasks.get(task_id, {}).get("state") == "cancelled":
                                            raise Exception("Download cancelled by user")
                                    if chunk:
                                        f.write(chunk)
                                        downloaded += len(chunk)
                                        elapsed = max(0.1, time.time() - start_t)
                                        speed = downloaded / elapsed
                                        percent = round((downloaded / total * 100), 1) if total > 0 else 50.0
                                        speed_str = f"{speed / (1024 * 1024):.1f} MB/s" if speed >= 1024 * 1024 else f"{speed / 1024:.0f} KB/s"
                                        eta = int((total - downloaded) / speed) if total > downloaded and speed > 0 else 0
                                        eta_str = f"{eta//60}:{eta%60:02d}" if eta else "--:--"
                                        
                                        with self._lock:
                                            if task_id in self._tasks:
                                                self._tasks[task_id].update({
                                                    "state": "downloading",
                                                    "percent": percent,
                                                    "downloaded_bytes": downloaded,
                                                    "total_bytes": total,
                                                    "speed_str": speed_str,
                                                    "eta_str": eta_str,
                                                    "filename": out_file.name,
                                                })

                    
                    # Finished direct HTTP download
                    with self._lock:
                        if task_id in self._tasks:
                            self._tasks[task_id].update({
                                "state": "finished",
                                "percent": 100.0,
                                "speed_str": "Done",
                                "eta_str": "00:00",
                                "filename": out_file.name,
                                "filepath": str(out_file),
                                "finished_at": time.time(),
                            })
                    return
                except Exception as fallback_e:
                    logger.error("Direct HTTP fallback also failed: %s", fallback_e)
                    with self._lock:
                        if task_id in self._tasks:
                            self._tasks[task_id].update({
                                "state": "error",
                                "error": f"{err_msg} | Fallback: {fallback_e}",
                            })

        threading.Thread(target=_worker, daemon=True, name=f"video-dl-{task_id}").start()

        return {
            "task_id": task_id,
            "state": "downloading",
            "quality_label": quality_label,
            "parallel_parts": 8,
            "message": "8-part parallel download started in background.",
            "downloads_dir": str(self.downloads_dir),
        }


# Global Singletons
_extractor = StreamExtractor()
_download_manager = DownloadManager()


def get_stream_extractor() -> StreamExtractor:
    return _extractor


def get_download_manager() -> DownloadManager:
    return _download_manager

