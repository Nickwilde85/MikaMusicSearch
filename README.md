# 🎵 MikaMusicSearch

Telegram бот для поиска и скачивания музыки с YouTube и SoundCloud.

## Возможности

- 🔍 Поиск музыки по названию или исполнителю
- 🎵 Поиск на YouTube и ☁️ SoundCloud
- 📄 Пагинация — до 20 результатов, по 5 на странице
- 🔗 Скачивание по прямой ссылке (soundcloud.com, on.soundcloud.com, youtube.com, youtu.be)
- 📤 Отправка MP3 прямо в Telegram чат

## Требования

- Python 3.10+
- [ffmpeg](https://ffmpeg.org/download.html) (должен быть в PATH)

## Установка

1. **Клонируй репозиторий:**
   ```bash
   git clone https://github.com/your-username/music-bot.git
   cd music-bot
   ```

2. **Установи зависимости:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Создай файл `.env` из примера:**
   ```bash
   cp .env.example .env
   ```

4. **Заполни `.env`:**
   ```env
   BOT_TOKEN=your_telegram_bot_token_here
   ```
   Токен получи у [@BotFather](https://t.me/BotFather).

5. **Установи ffmpeg:**
   - Windows: скачай с [gyan.dev](https://www.gyan.dev/ffmpeg/builds/), распакуй и добавь папку `bin` в PATH
   - Linux: `sudo apt install ffmpeg`
   - macOS: `brew install ffmpeg`

6. **Запусти бота:**
   ```bash
   python bot.py
   ```

## Использование

| Действие | Как |
|---|---|
| Поиск по названию | Просто напиши название трека |
| Скачать по ссылке | Отправь ссылку SoundCloud или YouTube |
| Помощь | `/help` |

## Структура проекта

```
├── bot.py          — основная логика бота
├── search.py       — поиск треков и резолв URL
├── downloader.py   — скачивание через yt-dlp
├── config.py       — конфигурация
├── requirements.txt
├── .env.example    — пример конфига
└── .gitignore
```
