import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
DOWNLOAD_DIR: str = os.getenv("DOWNLOAD_DIR", "downloads")

MAX_FILE_SIZE_MB: int = 50
MAX_SEARCH_RESULTS: int = 20
PAGE_SIZE: int = 5

# Supported audio extensions
AUDIO_EXTENSIONS: tuple = (".m4a", ".mp3", ".opus", ".ogg", ".webm", ".flac", ".wav")

# Sources display names
SOURCE_NAMES: dict[str, str] = {
    "youtube": "YouTube",
    "soundcloud": "SoundCloud",
}

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set in .env file")
