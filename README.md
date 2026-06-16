# YouTube Downloader

Простой и симпатичный скачиватель видео с YouTube на `yt-dlp` + `PyQt6`.
Без cookies, без рекламы, без мусора.

## Установка

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # Linux/Mac

pip install -r requirements.txt
```

## Запуск

```bash
python main.py
```

## Фичи

- Drag-and-drop ссылки прямо в окно
- Превью видео перед скачиванием (название, автор, длительность)
- Пресеты качества: 4K, 1440p, 1080p, 720p, 480p, 360p, Audio-only (MP3)
- Параллельная очередь с прогресс-барами, скоростью и ETA
- Тёмная тема, нормальный шрифт, без виндовых 90-х

## Заметки

- `yt-dlp` тянет ffmpeg автоматически на Windows; на Linux поставь `ffmpeg` пакетом.
- Скачивание идёт **без cookies** — если попадётся возрастное ограничение, скажи, добавим опциональный вход.
