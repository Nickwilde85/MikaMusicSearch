import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
DOWNLOAD_DIR: str = os.getenv("DOWNLOAD_DIR", "downloads")

# Max file size Telegram allows for bots (50 MB)
MAX_FILE_SIZE_MB: int = 50

# Total search results to fetch
MAX_SEARCH_RESULTS: int = 20

# Results shown per page
PAGE_SIZE: int = 5

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set in .env file")
