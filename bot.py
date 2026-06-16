import asyncio
import logging
import os
from dataclasses import dataclass
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

from config import BOT_TOKEN, DOWNLOAD_DIR, PAGE_SIZE, SOURCE_NAMES, AUDIO_EXTENSIONS
from search import Track, search_all, format_duration, resolve_url
from downloader import download_track, cleanup_file, DownloadError, FileTooLargeError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ---------------------------------------------------------------------------
# Session state — one dataclass per user instead of 3 separate dicts
# ---------------------------------------------------------------------------

@dataclass
class UserSession:
    tracks: list[Track]
    page: int = 0


_sessions: dict[int, UserSession] = {}     # user_id -> session
_pending: dict[int, str] = {}              # user_id -> pending search query


# ---------------------------------------------------------------------------
# Source keyboard (built once, reused everywhere)
# ---------------------------------------------------------------------------

SOURCE_KB = InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(text="🎵 YouTube",    callback_data="src:youtube"),
    InlineKeyboardButton(text="☁️ SoundCloud", callback_data="src:soundcloud"),
]])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_supported_url(text: str) -> bool:
    t = text.lower().strip()
    return any(domain in t for domain in (
        "soundcloud.com/", "on.soundcloud.com/",
        "youtu.be/", "youtube.com/watch", "youtube.com/shorts/",
    ))


def track_info(track: Track) -> str:
    icon = {"youtube": "🎵", "soundcloud": "☁️"}.get(track.source, "🎵")
    return f"{icon} <b>{track.artist}</b> — <b>{track.title}</b>\n⏱ {format_duration(track.duration)}"


def build_page_keyboard(tracks: list[Track], page: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    total = len(tracks)
    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    start = page * PAGE_SIZE
    end = min(start + PAGE_SIZE, total)

    for i in range(start, end):
        t = tracks[i]
        label = f"{i+1}. {t.artist} — {t.title} [{format_duration(t.duration)}]"
        builder.button(text=label[:60], callback_data=f"dl:{i}")
    builder.adjust(1)

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀ Назад", callback_data=f"page:{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))
    if end < total:
        nav.append(InlineKeyboardButton(text="Вперёд ▶", callback_data=f"page:{page+1}"))
    builder.row(*nav)
    return builder.as_markup()


def build_page_text(tracks: list[Track], page: int, source_name: str) -> str:
    total = len(tracks)
    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    start = page * PAGE_SIZE
    end = min(start + PAGE_SIZE, total)
    lines = [f"🎶 Результаты поиска по <b>{source_name}</b> (стр. {page+1}/{total_pages}):\n"]
    for i in range(start, end):
        t = tracks[i]
        lines.append(f"{i+1}. {t.artist} — {t.title} [{format_duration(t.duration)}]")
    return "\n".join(lines)


async def _keep_uploading(chat_id: int, action: str, stop: asyncio.Event):
    """Ping upload indicator every 4s so Telegram keeps showing it."""
    while not stop.is_set():
        try:
            await bot.send_chat_action(chat_id=chat_id, action=action)
        except Exception:
            pass
        await asyncio.sleep(4)


async def send_audio_fast(chat_id: int, file_path: str, track: Track) -> None:
    """Send audio file with a live upload indicator."""
    ext = os.path.splitext(file_path)[1].lower()
    is_audio = ext in (".mp3", ".m4a", ".flac")
    action = "upload_voice" if is_audio else "upload_document"
    audio = FSInputFile(file_path, filename=os.path.basename(file_path))

    stop = asyncio.Event()
    indicator = asyncio.create_task(_keep_uploading(chat_id, action, stop))
    try:
        if is_audio:
            await bot.send_audio(
                chat_id=chat_id, audio=audio,
                title=track.title, performer=track.artist,
                duration=track.duration,
                caption=f"🎵 {track.artist} — {track.title}",
            )
        else:
            await bot.send_document(
                chat_id=chat_id, document=audio,
                caption=f"🎵 {track.artist} — {track.title}",
            )
    finally:
        stop.set()
        indicator.cancel()


async def _do_download(chat_id: int, status_msg: Message, track: Track) -> None:
    """Shared download+send logic used by both URL and search handlers."""
    file_path: Optional[str] = None
    try:
        file_path = await download_track(track)
        await send_audio_fast(chat_id, file_path, track)
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


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "👋 Привет! Я <b>MikaMusicSearch</b>.\n\n"
        "Отправь название трека или исполнителя — найду и скачаю.\n\n"
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
        "4. Получи аудио прямо в чат 🎶\n\n"
        "Или отправь прямую ссылку:\n"
        "🔗 <code>https://soundcloud.com/artist/track</code>\n"
        "🔗 <code>https://youtube.com/watch?v=...</code>\n\n"
        "<i>До 20 треков, по 5 на странице. Лимит файла — 50 МБ.</i>",
        parse_mode=ParseMode.HTML,
    )


@dp.message(F.text & ~F.text.startswith("/"))
async def handle_text(message: Message):
    query = message.text.strip()
    if not query:
        return

    if is_supported_url(query):
        status_msg = await message.answer("🔎 Получаю информацию о треке...")
        try:
            track = await resolve_url(query)
        except Exception as e:
            await status_msg.edit_text(f"❌ Не удалось получить трек по ссылке: {e}")
            return

        await status_msg.edit_text(
            f"⏬ Скачиваю: {track_info(track)}\nПожалуйста, подожди...",
            parse_mode=ParseMode.HTML,
        )
        await _do_download(message.chat.id, status_msg, track)
        return

    _pending[message.from_user.id] = query
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
    query = _pending.get(user_id)

    if not query:
        await callback.answer("Сначала введи запрос.", show_alert=True)
        return

    source_name = SOURCE_NAMES.get(source, source)
    await callback.message.edit_text(
        f"🔎 Ищу <b>{query}</b> на <b>{source_name}</b>...",
        parse_mode=ParseMode.HTML,
    )

    try:
        tracks = await search_all(query, source=source)
    except Exception as e:
        logger.exception("Search error")
        await callback.message.edit_text(f"❌ Ошибка поиска: {e}")
        return

    if not tracks:
        await callback.message.edit_text("😔 Ничего не найдено. Попробуй другой запрос.")
        return

    _sessions[user_id] = UserSession(tracks=tracks, page=0)
    await callback.message.edit_text(
        build_page_text(tracks, 0, source_name),
        reply_markup=build_page_keyboard(tracks, 0),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("page:"))
async def on_page_change(callback: CallbackQuery):
    user_id = callback.from_user.id
    session = _sessions.get(user_id)

    if not session:
        await callback.answer("Сессия устарела, выполни поиск заново.", show_alert=True)
        return

    page = int(callback.data.split(":", 1)[1])
    session.page = page
    source_name = SOURCE_NAMES.get(session.tracks[0].source, "Unknown")

    await callback.message.edit_text(
        build_page_text(session.tracks, page, source_name),
        reply_markup=build_page_keyboard(session.tracks, page),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("dl:"))
async def on_download(callback: CallbackQuery):
    user_id = callback.from_user.id
    index = int(callback.data.split(":", 1)[1])
    session = _sessions.get(user_id)

    if not session or index >= len(session.tracks):
        await callback.answer("Сессия устарела, выполни поиск заново.", show_alert=True)
        return

    track = session.tracks[index]
    await callback.answer()
    status_msg = await callback.message.answer(
        f"⏬ Скачиваю: {track_info(track)}\nПожалуйста, подожди...",
        parse_mode=ParseMode.HTML,
    )
    await _do_download(callback.message.chat.id, status_msg, track)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main():
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    logger.info("Bot starting...")
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
