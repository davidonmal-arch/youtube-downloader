"""Thin wrapper around yt-dlp. No cookies, no surprises."""
from __future__ import annotations

import re
import shutil
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional

import yt_dlp


# ---------- ffmpeg discovery ----------

def find_ffmpeg() -> Optional[str]:
    """Prefer the imageio-ffmpeg bundle (modern, static); fall back to PATH."""
    try:
        import imageio_ffmpeg
        path = imageio_ffmpeg.get_ffmpeg_exe()
        if path:
            return path
    except Exception:
        pass
    found = shutil.which("ffmpeg")
    return found if found else None


# ---------- quality presets ----------

@dataclass(frozen=True)
class QualityPreset:
    label: str
    format: str
    is_audio: bool = False


# m4a is preferred so the merge is a no-op remux when possible (≤1080p on
# YouTube). If m4a isn't available (common at 4K/1440p) we fall back to opus
# and the postprocessor below transcodes audio to AAC.
QUALITY_PRESETS: list[QualityPreset] = [
    QualityPreset(
        "Best (auto)",
        "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio[ext=m4a]/best[ext=mp4]/best",
    ),
    QualityPreset(
        "4K · 2160p",
        "bestvideo[height<=2160]+bestaudio[ext=m4a]/bestvideo[height<=2160]+bestaudio/best[height<=2160]/best",
    ),
    QualityPreset(
        "1440p",
        "bestvideo[height<=1440]+bestaudio[ext=m4a]/bestvideo[height<=1440]+bestaudio/best[height<=1440]/best",
    ),
    QualityPreset(
        "1080p",
        "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio[ext=m4a]/best[height<=1080]/best",
    ),
    QualityPreset(
        "720p",
        "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio[ext=m4a]/best[height<=720]/best",
    ),
    QualityPreset(
        "480p",
        "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio[ext=m4a]/best[height<=480]/best",
    ),
    QualityPreset(
        "360p",
        "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=360]+bestaudio[ext=m4a]/best[height<=360]/best",
    ),
    QualityPreset("Audio only (MP3)", "bestaudio/best", is_audio=True),
]


def quality_labels() -> list[str]:
    return [p.label for p in QUALITY_PRESETS]


def get_preset(label: str) -> QualityPreset:
    for p in QUALITY_PRESETS:
        if p.label == label:
            return p
    raise KeyError(label)


# ---------- models ----------

@dataclass(frozen=True)
class VideoInfo:
    title: str
    uploader: str
    duration: int
    thumbnail: str
    thumbnail_bytes: bytes
    url: str

    @property
    def duration_str(self) -> str:
        s = self.duration or 0
        h, rem = divmod(s, 3600)
        m, s = divmod(rem, 60)
        if h:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"


# ---------- validation ----------

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


# ---------- video info ----------

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
    opts = {
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "cookiefile": None,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    thumb_url = info.get("thumbnail") or ""
    return VideoInfo(
        title=info.get("title") or "Untitled",
        uploader=info.get("uploader") or info.get("channel") or "Unknown",
        duration=int(info.get("duration") or 0),
        thumbnail=thumb_url,
        thumbnail_bytes=_fetch_thumbnail_bytes(thumb_url),
        url=url,
    )


# ---------- download ----------

class FFmpegNotFoundError(RuntimeError):
    """Neither imageio-ffmpeg nor ffmpeg in PATH."""


def _ensure_ffmpeg() -> str:
    path = find_ffmpeg()
    if not path:
        raise FFmpegNotFoundError(
            "ffmpeg not found. Install imageio-ffmpeg (recommended):\n"
            "    pip install imageio-ffmpeg\n"
            "Or add ffmpeg to PATH: https://www.gyan.dev/ffmpeg/builds/"
        )
    return path


def _build_opts(
    quality: str,
    output_dir: str,
    progress_hook: Callable[[dict], None],
) -> dict:
    preset = get_preset(quality)

    opts: dict = {
        "format": preset.format,
        "outtmpl": f"{output_dir}/%(title).150B [%(id)s].%(ext)s",
        "progress_hooks": [progress_hook],
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "cookiefile": None,
        "restrictfilenames": False,
        "windowsfilenames": True,
    }

    if preset.is_audio:
        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]
        opts["postprocessor_args"] = ["-id3v2_version", "4"]
    else:
        # Always end up with mp4 + AAC so legacy players (Windows Media Player,
        # QuickTime, etc.) can play the result. Video stream is copied as-is to
        # avoid a re-encode; audio is transcoded to AAC when the source is opus.
        opts["postprocessors"] = [{
            "key": "FFmpegVideoConvertor",
            "preferedformat": "mp4",
        }]
        opts["postprocessor_args"] = [
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
        ]

    ff = find_ffmpeg()
    if ff:
        opts["ffmpeg_location"] = ff
    return opts


def download(
    url: str,
    quality: str,
    output_dir: str,
    progress_hook: Callable[[dict], None],
    should_cancel: Optional[Callable[[], bool]] = None,
) -> None:
    _ensure_ffmpeg()
    opts = _build_opts(quality, output_dir, progress_hook)

    def wrapped(d: dict) -> None:
        if should_cancel and should_cancel():
            raise _CancelledError()
        progress_hook(d)

    opts["progress_hooks"] = [wrapped]

    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])


class _CancelledError(Exception):
    pass
