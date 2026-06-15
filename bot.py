import asyncio
import logging
import os
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import BOT_TOKEN, DOWNLOAD_DIR, PAGE_SIZE
from search import Track, search_all, format_duration, resolve_url
from downloader import download_track, cleanup_file, DownloadError, FileTooLargeError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# In-memory session: maps user_id -> list[Track]
user_sessions: dict[int, list[Track]] = {}

# Per-user current page (0-indexed)
user_pages: dict[int, int] = {}

# Per-user pending search query while waiting for source selection
pending_queries: dict[int, str] = {}

# Source keyboard
SOURCE_KB = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="🎵 YouTube",    callback_data="src:youtube"),
        InlineKeyboardButton(text="☁️ SoundCloud", callback_data="src:soundcloud"),
    ]
])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_supported_url(text: str) -> bool:
    """Return True if text looks like a SoundCloud or YouTube URL."""
    text = text.lower().strip()
    return (
        "soundcloud.com/" in text or
        "on.soundcloud.com/" in text or
        "youtu.be/" in text or
        "youtube.com/watch" in text or
        "youtube.com/shorts/" in text
    )

def build_page_keyboard(tracks: list[Track], page: int) -> InlineKeyboardMarkup:
    """Build keyboard for current page with track buttons + pagination controls."""
    builder = InlineKeyboardBuilder()
    total = len(tracks)
    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    start = page * PAGE_SIZE
    end = min(start + PAGE_SIZE, total)

    # Track buttons for current page
    for i in range(start, end):
        track = tracks[i]
        label = f"{i+1}. {track.artist} — {track.title} [{format_duration(track.duration)}]"
        builder.button(text=label[:60], callback_data=f"dl:{i}")

    builder.adjust(1)

    # Pagination row
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀ Назад", callback_data=f"page:{page-1}"))
    nav_buttons.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))
    if end < total:
        nav_buttons.append(InlineKeyboardButton(text="Вперёд ▶", callback_data=f"page:{page+1}"))

    builder.row(*nav_buttons)
    return builder.as_markup()


def build_page_text(tracks: list[Track], page: int, source_name: str) -> str:
    """Build message text listing tracks on current page."""
    total = len(tracks)
    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    start = page * PAGE_SIZE
    end = min(start + PAGE_SIZE, total)

    lines = [f"🎶 Результаты поиска по <b>{source_name}</b> (стр. {page+1}/{total_pages}):\n"]
    for i in range(start, end):
        t = tracks[i]
        lines.append(f"{i+1}. {t.artist} — {t.title} [{format_duration(t.duration)}]")
    return "\n".join(lines)


def track_info(track: Track) -> str:
    source_icon = {"youtube": "🎵", "soundcloud": "☁️"}.get(track.source, "🎵")
    return (
        f"{source_icon} <b>{track.artist}</b> — <b>{track.title}</b>\n"
        f"⏱ {format_duration(track.duration)}"
    )


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "👋 Привет! Я <b>MikaMusicSearch</b>.\n\n"
        "Просто отправь мне название трека или исполнителя, "
        "и я найду музыку для тебя.\n\n"
        "Команды:\n"
        "/help — помощь",
        parse_mode=ParseMode.HTML,
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "<b>Как пользоваться:</b>\n\n"
        "1. Напиши название песни или исполнителя\n"
        "2. Выбери источник (YouTube / SoundCloud)\n"
        "3. Листай страницы и выбери трек\n"
        "4. Получи MP3 прямо в чат 🎶\n\n"
        "Или просто отправь ссылку:\n"
        "🔗 <code>https://soundcloud.com/artist/track</code>\n"
        "🔗 <code>https://youtube.com/watch?v=...</code>\n\n"
        "<b>Источники поиска:</b>\n"
        "🎵 <b>YouTube</b> — огромная база, высокое качество\n"
        "☁️ <b>SoundCloud</b> — инди, электронная музыка, ремиксы\n\n"
        "<i>Показывается до 20 треков, по 5 на странице.\n"
        "Максимальный размер файла — 50 МБ.</i>",
        parse_mode=ParseMode.HTML,
    )


@dp.message(F.text & ~F.text.startswith("/"))
async def handle_search_query(message: Message):
    query = message.text.strip()
    if not query:
        return

    # Check if the message is a direct SoundCloud or YouTube URL
    if is_supported_url(query):
        status_msg = await message.answer(
            "🔎 Получаю информацию о треке...",
            parse_mode=ParseMode.HTML,
        )
        try:
            track = await resolve_url(query)
        except Exception as e:
            await status_msg.edit_text(f"❌ Не удалось получить трек по ссылке: {e}")
            return

        await status_msg.edit_text(
            f"⏬ Скачиваю: {track_info(track)}\nПожалуйста, подожди...",
            parse_mode=ParseMode.HTML,
        )

        file_path: Optional[str] = None
        try:
            file_path = await download_track(track)
            audio = FSInputFile(file_path, filename=os.path.basename(file_path))
            await bot.send_audio(
                chat_id=message.chat.id,
                audio=audio,
                title=track.title,
                performer=track.artist,
                duration=track.duration,
                caption=f"🎵 {track.artist} — {track.title}",
            )
            await status_msg.delete()
        except FileTooLargeError as e:
            await status_msg.edit_text(f"⚠️ {e}")
        except DownloadError as e:
            logger.error("Download error: %s", e)
            await status_msg.edit_text(
                f"❌ Не удалось скачать трек.\n<code>{e}</code>",
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            logger.exception("Unexpected download error")
            await status_msg.edit_text(f"❌ Неожиданная ошибка: {e}")
        finally:
            if file_path:
                cleanup_file(file_path)
        return

    # Regular text search — ask for source
    pending_queries[message.from_user.id] = query
    await message.answer(
        f"🔍 Ищем: <b>{query}</b>\n\nВыбери источник:",
        reply_markup=SOURCE_KB,
        parse_mode=ParseMode.HTML,
    )


@dp.callback_query(F.data == "noop")
async def on_noop(callback: CallbackQuery):
    await callback.answer()


@dp.callback_query(F.data.startswith("src:"))
async def on_source_selected(callback: CallbackQuery):
    source = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id
    query = pending_queries.get(user_id)

    if not query:
        await callback.answer("Сначала введи запрос.", show_alert=True)
        return

    source_names = {"youtube": "YouTube", "soundcloud": "SoundCloud"}
    await callback.message.edit_text(
        f"🔎 Ищу <b>{query}</b> на <b>{source_names[source]}</b>...",
        parse_mode=ParseMode.HTML,
    )

    try:
        tracks = await search_all(query, source=source)
    except Exception as e:
        logger.exception("Search error")
        await callback.message.edit_text(f"❌ Ошибка поиска: {e}")
        return

    if not tracks:
        await callback.message.edit_text(
            "😔 Ничего не найдено. Попробуй другой запрос или источник."
        )
        return

    user_sessions[user_id] = tracks
    user_pages[user_id] = 0

    source_name = source_names[source]
    await callback.message.edit_text(
        build_page_text(tracks, 0, source_name),
        reply_markup=build_page_keyboard(tracks, 0),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("page:"))
async def on_page_change(callback: CallbackQuery):
    user_id = callback.from_user.id
    page = int(callback.data.split(":", 1)[1])
    tracks = user_sessions.get(user_id)

    if not tracks:
        await callback.answer("Сессия устарела, выполни поиск заново.", show_alert=True)
        return

    user_pages[user_id] = page

    # Determine source name from first track
    source_names = {"youtube": "YouTube", "soundcloud": "SoundCloud"}
    source_name = source_names.get(tracks[0].source, "Unknown")

    await callback.message.edit_text(
        build_page_text(tracks, page, source_name),
        reply_markup=build_page_keyboard(tracks, page),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("dl:"))
async def on_download(callback: CallbackQuery):
    user_id = callback.from_user.id
    index = int(callback.data.split(":", 1)[1])
    tracks = user_sessions.get(user_id)

    if not tracks or index >= len(tracks):
        await callback.answer("Сессия устарела, выполни поиск заново.", show_alert=True)
        return

    track = tracks[index]
    await callback.answer()
    status_msg = await callback.message.answer(
        f"⏬ Скачиваю: {track_info(track)}\nПожалуйста, подожди...",
        parse_mode=ParseMode.HTML,
    )

    file_path: Optional[str] = None
    try:
        file_path = await download_track(track)

        audio = FSInputFile(file_path, filename=os.path.basename(file_path))
        await bot.send_audio(
            chat_id=callback.message.chat.id,
            audio=audio,
            title=track.title,
            performer=track.artist,
            duration=track.duration,
            caption=f"🎵 {track.artist} — {track.title}",
        )
        await status_msg.delete()

    except FileTooLargeError as e:
        await status_msg.edit_text(f"⚠️ {e}")
    except DownloadError as e:
        logger.error("Download error: %s", e)
        await status_msg.edit_text(
            f"❌ Не удалось скачать трек.\n<code>{e}</code>",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logger.exception("Unexpected error during download")
        await status_msg.edit_text(f"❌ Неожиданная ошибка: {e}")
    finally:
        if file_path:
            cleanup_file(file_path)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main():
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    logger.info("Bot is starting...")
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
