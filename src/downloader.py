"""Обёртка над yt-dlp. Без cookies, без сюрпризов."""
from __future__ import annotations

import re
import shutil
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional

import yt_dlp


# ---------- где искать ffmpeg ----------

def find_ffmpeg() -> Optional[str]:
    """Ищем нормальный ffmpeg. Сначала бандл от imageio-ffmpeg, потом PATH."""
    try:
        import imageio_ffmpeg
        path = imageio_ffmpeg.get_ffmpeg_exe()
        if path:
            return path
    except Exception:
        pass
    found = shutil.which("ffmpeg")
    return found if found else None


# ---------- пресеты качества ----------

# Приоритет: m4a (AAC) → любой лучший аудио-поток. Так когда доступен m4a
# (YouTube даёт его для ≤1080p), merge пройдёт без перекодирования; для 4K/1440p
# (где m4a обычно нет) упадём на opus/webm, и тогда перекодирует постпроцессор ниже.
QUALITY_PRESETS: dict[str, str] = {
    "Лучшее (авто)":          "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio[ext=m4a]/best[ext=mp4]/best",
    "4K · 2160p":             "bestvideo[height<=2160]+bestaudio[ext=m4a]/bestvideo[height<=2160]+bestaudio/best[height<=2160]/best",
    "1440p":                  "bestvideo[height<=1440]+bestaudio[ext=m4a]/bestvideo[height<=1440]+bestaudio/best[height<=1440]/best",
    "1080p":                  "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio[ext=m4a]/best[height<=1080]/best",
    "720p":                   "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio[ext=m4a]/best[height<=720]/best",
    "480p":                   "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio[ext=m4a]/best[height<=480]/best",
    "360p":                   "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=360]+bestaudio[ext=m4a]/best[height<=360]/best",
    "Только аудио (MP3)":     "bestaudio/best",
}

# ---------- модели ----------

@dataclass(frozen=True)
class VideoInfo:
    title: str
    uploader: str
    duration: int          # секунды
    thumbnail: str
    thumbnail_bytes: bytes # пусто, если не удалось скачать
    url: str

    @property
    def duration_str(self) -> str:
        s = self.duration or 0
        h, rem = divmod(s, 3600)
        m, s = divmod(rem, 60)
        if h:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"


# ---------- валидация ----------

_YT_RE = re.compile(
    r"^(https?://)?(www\.|m\.|music\.)?"
    r"(youtube\.com/(watch\?v=|shorts/|live/)|youtu\.be/)[\w\-]{6,}",
    re.IGNORECASE,
)


def is_valid_url(url: str) -> bool:
    url = url.strip()
    if not url:
        return False
    return bool(_YT_RE.match(url))


# ---------- инфо о видео ----------

def _fetch_thumbnail_bytes(url: str) -> bytes:
    if not url:
        return b""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.read()
    except Exception:
        return b""


def fetch_info(url: str) -> VideoInfo:
    """Тянем метаданные без скачивания + превью-картинку."""
    opts = {
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "cookiefile": None,        # жёстко без cookies
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    thumb_url = info.get("thumbnail") or ""
    return VideoInfo(
        title=info.get("title") or "Без названия",
        uploader=info.get("uploader") or info.get("channel") or "Неизвестно",
        duration=int(info.get("duration") or 0),
        thumbnail=thumb_url,
        thumbnail_bytes=_fetch_thumbnail_bytes(thumb_url),
        url=url,
    )


# ---------- скачивание ----------

def _build_opts(
    quality: str,
    output_dir: str,
    progress_hook: Callable[[dict], None],
) -> dict:
    is_audio = "аудио" in quality.lower()

    opts: dict = {
        "format": QUALITY_PRESETS[quality],
        # yt-dlp сам разруливает слэши и на Windows
        "outtmpl": f"{output_dir}/%(title).150B [%(id)s].%(ext)s",
        "progress_hooks": [progress_hook],
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "cookiefile": None,        # ← без cookies
        "restrictfilenames": False,
        "windowsfilenames": True,
    }

    if is_audio:
        # аудио → mp3, теги id3v2
        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]
        opts["postprocessor_args"] = ["-id3v2_version", "4"]
    else:
        # видео → mp4 с AAC-аудио, чтоб WMP и прочие старые плееры не падали
        # видео копируем без перекода (быстро), аудио opus→aac если попалось
        opts["postprocessors"] = [{
            "key": "FFmpegVideoConvertor",
            "preferedformat": "mp4",
        }]
        opts["postprocessor_args"] = ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]

    # ffmpeg: явно указываем где брать, чтоб не упёрся в PATH-раритет
    ff = find_ffmpeg()
    if ff:
        opts["ffmpeg_location"] = ff
    return opts


class FFmpegNotFoundError(RuntimeError):
    """Ни imageio-ffmpeg, ни ffmpeg в PATH не нашлись."""


def _ensure_ffmpeg() -> str:
    path = find_ffmpeg()
    if not path:
        raise FFmpegNotFoundError(
            "ffmpeg не найден. Поставь imageio-ffmpeg (рекомендую):\n"
            "    pip install imageio-ffmpeg\n"
            "Или ffmpeg в PATH: https://www.gyan.dev/ffmpeg/builds/"
        )
    return path


def download(
    url: str,
    quality: str,
    output_dir: str,
    progress_hook: Callable[[dict], None],
    should_cancel: Optional[Callable[[], bool]] = None,
) -> None:
    """Скачивает видео/аудио. Кидает исключение, если should_cancel() вернул True."""
    _ensure_ffmpeg()           # упадёт с понятной ошибкой, если нет ffmpeg
    opts = _build_opts(quality, output_dir, progress_hook)

    # обёртка: если юзер нажал отмену — кидаем сигнал
    def wrapped(d: dict) -> None:
        if should_cancel and should_cancel():
            raise _CancelledError()
        progress_hook(d)

    opts["progress_hooks"] = [wrapped]

    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])


class _CancelledError(Exception):
    """Внутренний флаг отмены скачивания."""
