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

---

## Автозапуск при старте системы

### 🐧 Linux (systemd)

1. **Создай файл сервиса:**
   ```bash
   sudo nano /etc/systemd/system/mikamusicbot.service
   ```

2. **Вставь содержимое** (замени пути и имя пользователя):
   ```ini
   [Unit]
   Description=MikaMusicSearch Telegram Bot
   After=network.target

   [Service]
   Type=simple
   User=твой_пользователь
   WorkingDirectory=/путь/до/music_bot
   ExecStart=/usr/bin/python3 /путь/до/music_bot/bot.py
   Restart=always
   RestartSec=10
   StandardOutput=journal
   StandardError=journal

   [Install]
   WantedBy=multi-user.target
   ```

   Пример с реальными путями:
   ```ini
   User=ubuntu
   WorkingDirectory=/home/ubuntu/MikaMusicSearch
   ExecStart=/usr/bin/python3 /home/ubuntu/MikaMusicSearch/bot.py
   ```

   > Если используешь виртуальное окружение, замени ExecStart на:
   > `ExecStart=/home/ubuntu/MikaMusicSearch/venv/bin/python bot.py`

3. **Активируй и запусти:**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable mikamusicbot
   sudo systemctl start mikamusicbot
   ```

4. **Проверь статус:**
   ```bash
   sudo systemctl status mikamusicbot
   ```

5. **Смотреть логи:**
   ```bash
   journalctl -u mikamusicbot -f
   ```

6. **Остановить / перезапустить:**
   ```bash
   sudo systemctl stop mikamusicbot
   sudo systemctl restart mikamusicbot
   ```

---

### 🪟 Windows (Task Scheduler)

1. **Создай файл `start_bot.bat`** в папке `music_bot`:
   ```bat
   @echo off
   cd /d C:\Projects\Misuk\music_bot
   python bot.py
   ```

2. **Открой Планировщик задач:**
   - Нажми `Win + R`, введи `taskschd.msc`, нажми Enter

3. **Создай задачу:**
   - Справа нажми **«Создать задачу»**
   - Вкладка **Общие**:
     - Имя: `MikaMusicSearch`
     - Поставь галочку **«Выполнять для всех пользователей»**
     - Поставь галочку **«Выполнять с наивысшими правами»**
   - Вкладка **Триггеры** → **Создать**:
     - Начать задачу: **«При запуске»**
     - Нажми OK
   - Вкладка **Действия** → **Создать**:
     - Действие: **«Запуск программы»**
     - Программа: укажи путь до `start_bot.bat`
     - Например: `C:\Projects\Misuk\music_bot\start_bot.bat`
   - Вкладка **Условия**:
     - Снять галочку **«Запускать только при питании от сети»**
   - Нажми **OK**

4. **Проверь** — перезагрузи ПК, бот должен запуститься автоматически.

> **Альтернатива через NSSM** (удобнее, работает как настоящий сервис):
> ```bash
> # Скачай nssm с https://nssm.cc/download
> nssm install MikaMusicSearch
> # В открывшемся окне укажи путь до python.exe и bot.py
> nssm start MikaMusicSearch
> ```
