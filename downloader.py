import os
import asyncio
import glob
from pathlib import Path

import yt_dlp

from config import DOWNLOAD_DIR, MAX_FILE_SIZE_MB
from search import Track


os.makedirs(DOWNLOAD_DIR, exist_ok=True)


class DownloadError(Exception):
    pass


class FileTooLargeError(Exception):
    pass


async def download_track(track: Track) -> str:
    """
    Download a track to DOWNLOAD_DIR and return the local file path.
    Raises DownloadError or FileTooLargeError on failure.
    """

    # For Spotify tracks, the url is a yt-dlp ytsearch query
    url = track.url

    # Sanitise filename
    safe_title = _sanitise(f"{track.artist} - {track.title}")
    output_template = os.path.join(DOWNLOAD_DIR, f"{safe_title}.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            },
            {
                "key": "FFmpegMetadata",
                "add_metadata": True,
            },
            {
                "key": "EmbedThumbnail",
            },
        ],
        "writethumbnail": True,
        # Abort if file exceeds MAX_FILE_SIZE_MB
        "max_filesize": MAX_FILE_SIZE_MB * 1024 * 1024,
    }

    def _sync_download():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

    try:
        await asyncio.get_event_loop().run_in_executor(None, _sync_download)
    except yt_dlp.utils.MaxDownloadsReached:
        raise FileTooLargeError(f"File exceeds {MAX_FILE_SIZE_MB} MB limit")
    except yt_dlp.utils.DownloadError as e:
        raise DownloadError(str(e))

    # Find the downloaded mp3
    pattern = os.path.join(DOWNLOAD_DIR, f"{safe_title}.mp3")
    matches = glob.glob(pattern)
    if not matches:
        # Fallback: grab any mp3 with the safe title prefix
        matches = glob.glob(os.path.join(DOWNLOAD_DIR, f"{safe_title}*.mp3"))
    if not matches:
        raise DownloadError("Downloaded file not found on disk")

    file_path = matches[0]

    # Double-check size
    size_mb = os.path.getsize(file_path) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        os.remove(file_path)
        raise FileTooLargeError(f"File is {size_mb:.1f} MB — exceeds {MAX_FILE_SIZE_MB} MB Telegram limit")

    return file_path


def cleanup_file(path: str) -> None:
    """Remove a downloaded file after sending."""
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def _sanitise(name: str) -> str:
    """Remove characters that are unsafe in filenames."""
    keep = set(" abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_()[].,")
    return "".join(c if c in keep else "_" for c in name)[:100]
