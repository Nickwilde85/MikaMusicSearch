import asyncio
from dataclasses import dataclass
from typing import Optional
import yt_dlp

from config import MAX_SEARCH_RESULTS


@dataclass
class Track:
    title: str
    artist: str
    duration: int          # seconds
    url: str               # source URL for download
    source: str            # "youtube" | "soundcloud"
    thumbnail: Optional[str] = None


# ---------------------------------------------------------------------------
# YouTube search
# ---------------------------------------------------------------------------

async def search_youtube(query: str) -> list[Track]:
    """Search YouTube and return tracks."""

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "default_search": "ytsearch",
        "noplaylist": True,
    }

    def _sync_search():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_query = f"ytsearch{MAX_SEARCH_RESULTS}:{query}"
            info = ydl.extract_info(search_query, download=False)
            tracks = []
            for entry in info.get("entries", []):
                if not entry:
                    continue
                duration = entry.get("duration") or 0
                tracks.append(Track(
                    title=entry.get("title", "Unknown"),
                    artist=entry.get("uploader", "Unknown"),
                    duration=int(duration),
                    url=f"https://www.youtube.com/watch?v={entry['id']}",
                    source="youtube",
                    thumbnail=entry.get("thumbnail"),
                ))
            return tracks

    return await asyncio.get_event_loop().run_in_executor(None, _sync_search)


# ---------------------------------------------------------------------------
# SoundCloud search
# ---------------------------------------------------------------------------

async def search_soundcloud(query: str) -> list[Track]:
    """Search SoundCloud and return tracks."""

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "default_search": "scsearch",
        "noplaylist": True,
    }

    def _sync_search():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_query = f"scsearch{MAX_SEARCH_RESULTS}:{query}"
            info = ydl.extract_info(search_query, download=False)
            tracks = []
            for entry in info.get("entries", []):
                if not entry:
                    continue
                duration = entry.get("duration") or 0
                tracks.append(Track(
                    title=entry.get("title", "Unknown"),
                    artist=entry.get("uploader", "Unknown"),
                    duration=int(duration),
                    url=entry.get("url") or entry.get("webpage_url", ""),
                    source="soundcloud",
                    thumbnail=entry.get("thumbnail"),
                ))
            return tracks

    return await asyncio.get_event_loop().run_in_executor(None, _sync_search)


# ---------------------------------------------------------------------------
# Unified search
# ---------------------------------------------------------------------------

async def search_all(query: str, source: str = "youtube") -> list[Track]:
    """Search across a specific source."""
    if source == "soundcloud":
        return await search_soundcloud(query)
    else:
        return await search_youtube(query)


def format_duration(seconds: int) -> str:
    minutes, secs = divmod(seconds, 60)
    return f"{minutes}:{secs:02d}"


# ---------------------------------------------------------------------------
# Resolve direct URL
# ---------------------------------------------------------------------------

async def resolve_url(url: str) -> Track:
    """Fetch track metadata from a direct SoundCloud or YouTube URL."""

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }

    def _sync_resolve():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                raise ValueError("Could not extract info from URL")

            # Determine source
            webpage = info.get("webpage_url", url).lower()
            if "soundcloud.com" in webpage or "soundcloud.com" in url.lower():
                source = "soundcloud"
            else:
                source = "youtube"

            title = info.get("title", "Unknown")
            artist = info.get("uploader") or info.get("artist") or "Unknown"
            duration = int(info.get("duration") or 0)
            thumbnail = info.get("thumbnail")

            return Track(
                title=title,
                artist=artist,
                duration=duration,
                url=url,
                source=source,
                thumbnail=thumbnail,
            )

    return await asyncio.get_event_loop().run_in_executor(None, _sync_resolve)
