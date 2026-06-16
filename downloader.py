import os
import asyncio
import glob
import hashlib
from typing import Optional

import yt_dlp

from config import DOWNLOAD_DIR, MAX_FILE_SIZE_MB, AUDIO_EXTENSIONS
from search import Track

os.makedirs(DOWNLOAD_DIR, exist_ok=True)


class DownloadError(Exception):
    pass


class FileTooLargeError(Exception):
    pass


# ---------------------------------------------------------------------------
# File cache: url_hash -> file_path (O(1) lookup and delete)
# ---------------------------------------------------------------------------
_cache: dict[str, str] = {}          # hash  -> path
_cache_rev: dict[str, str] = {}      # path  -> hash  (for fast cleanup)


def _url_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:16]


def _find_file(safe_title: str) -> Optional[str]:
    """Find a downloaded audio file by sanitised title (single glob pass)."""
    pattern = os.path.join(DOWNLOAD_DIR, f"{safe_title}*")
    for f in glob.glob(pattern):
        if os.path.splitext(f)[1].lower() in AUDIO_EXTENSIONS:
            return f
    return None


# yt-dlp options shared across all downloads
_YDL_OPTS_BASE = {
    "format": "bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio[ext=opus]/bestaudio",
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "writethumbnail": False,
    "max_filesize": MAX_FILE_SIZE_MB * 1024 * 1024,
    "http_chunk_size": 50 * 1024 * 1024,        # 50 MB per chunk
    "concurrent_fragment_downloads": 16,
    "buffersize": 16 * 1024,
    "retries": 3,
    "fragment_retries": 3,
    # No postprocessors — skip ffmpeg entirely for max speed
}


async def download_track(track: Track) -> str:
    """
    Download a track to DOWNLOAD_DIR and return the local file path.
    Uses an in-memory cache to avoid re-downloading the same URL.
    """
    url = track.url
    key = _url_hash(url)

    # Cache hit
    cached = _cache.get(key)
    if cached and os.path.exists(cached):
        return cached
    elif cached:
        # Stale cache entry
        _cache.pop(key, None)
        _cache_rev.pop(cached, None)

    safe_title = _sanitise(f"{track.artist} - {track.title}")
    output_template = os.path.join(DOWNLOAD_DIR, f"{safe_title}.%(ext)s")

    opts = {**_YDL_OPTS_BASE, "outtmpl": output_template}

    def _sync_download():
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

    try:
        await asyncio.get_running_loop().run_in_executor(None, _sync_download)
    except yt_dlp.utils.MaxDownloadsReached:
        raise FileTooLargeError(f"File exceeds {MAX_FILE_SIZE_MB} MB limit")
    except yt_dlp.utils.DownloadError as e:
        raise DownloadError(str(e))

    file_path = _find_file(safe_title)
    if not file_path:
        raise DownloadError("Downloaded file not found on disk")

    size_mb = os.path.getsize(file_path) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        os.remove(file_path)
        raise FileTooLargeError(f"File is {size_mb:.1f} MB — exceeds {MAX_FILE_SIZE_MB} MB limit")

    _cache[key] = file_path
    _cache_rev[file_path] = key
    return file_path


def cleanup_file(path: str) -> None:
    """Remove file from disk and cache in O(1)."""
    key = _cache_rev.pop(path, None)
    if key:
        _cache.pop(key, None)
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def _sanitise(name: str) -> str:
    keep = set(" abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_()[].,")
    return "".join(c if c in keep else "_" for c in name)[:100]
