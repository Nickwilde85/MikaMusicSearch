import asyncio
from dataclasses import dataclass
from typing import Optional

import yt_dlp

from config import MAX_SEARCH_RESULTS


@dataclass
class Track:
    title: str
    artist: str
    duration: int        # seconds
    url: str             # source URL for download
    source: str          # "youtube" | "soundcloud"
    thumbnail: Optional[str] = None


# ---------------------------------------------------------------------------
# Shared yt-dlp options for flat search (no download, just metadata)
# ---------------------------------------------------------------------------

_SEARCH_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "extract_flat": True,
    "noplaylist": True,
    "skip_download": True,
}


def _entry_to_track(entry: dict, source: str) -> Optional[Track]:
    """Convert a yt-dlp flat entry dict to a Track. Returns None if invalid."""
    if not entry:
        return None
    video_id = entry.get("id")
    if source == "youtube" and not video_id:
        return None

    url = (
        f"https://www.youtube.com/watch?v={video_id}"
        if source == "youtube"
        else (entry.get("url") or entry.get("webpage_url", ""))
    )
    if not url:
        return None

    return Track(
        title=entry.get("title") or "Unknown",
        artist=entry.get("uploader") or "Unknown",
        duration=int(entry.get("duration") or 0),
        url=url,
        source=source,
        thumbnail=entry.get("thumbnail"),
    )


# ---------------------------------------------------------------------------
# Generic search — reused for both YouTube and SoundCloud
# ---------------------------------------------------------------------------

async def _search(query: str, source: str) -> list[Track]:
    prefix = "ytsearch" if source == "youtube" else "scsearch"
    search_query = f"{prefix}{MAX_SEARCH_RESULTS}:{query}"

    def _sync():
        with yt_dlp.YoutubeDL(_SEARCH_OPTS) as ydl:
            info = ydl.extract_info(search_query, download=False)
            return [
                t for entry in (info.get("entries") or [])
                if (t := _entry_to_track(entry, source)) is not None
            ]

    return await asyncio.get_running_loop().run_in_executor(None, _sync)


async def search_all(query: str, source: str = "youtube") -> list[Track]:
    return await _search(query, source)


# ---------------------------------------------------------------------------
# Resolve a direct URL to a Track (metadata only, no download)
# ---------------------------------------------------------------------------

async def resolve_url(url: str) -> Track:
    """Fetch track metadata from a direct SoundCloud or YouTube URL."""

    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        # extract_flat speeds up metadata fetch — no format resolution needed
        "extract_flat": "in_playlist",
        "skip_download": True,
    }

    def _sync():
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                raise ValueError("Could not extract info from URL")

            webpage = info.get("webpage_url", url).lower()
            source = "soundcloud" if "soundcloud.com" in webpage or "soundcloud.com" in url.lower() else "youtube"

            return Track(
                title=info.get("title") or "Unknown",
                artist=info.get("uploader") or info.get("artist") or "Unknown",
                duration=int(info.get("duration") or 0),
                url=url,
                source=source,
                thumbnail=info.get("thumbnail"),
            )

    return await asyncio.get_running_loop().run_in_executor(None, _sync)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def format_duration(seconds: int) -> str:
    minutes, secs = divmod(seconds, 60)
    return f"{minutes}:{secs:02d}"
