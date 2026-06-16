# YouTube Downloader

A clean, no-nonsense YouTube downloader with a dark PyQt6 interface, built on
[yt-dlp](https://github.com/yt-dlp/yt-dlp). No cookies, no browser data, no ads.

## Features

- Drag-and-drop URLs straight into the window
- Live preview: title, uploader, duration, thumbnail
- Eight quality presets: 4K · 1440p · 1080p · 720p · 480p · 360p · Best (auto) · Audio-only (MP3)
- Parallel queue with progress bars, speed and ETA per item
- Output is always **mp4 + AAC** for maximum player compatibility (Windows Media Player, QuickTime, etc.)
- Bundled ffmpeg via `imageio-ffmpeg` — no separate ffmpeg install required
- Dark theme, modern typography, zero telemetry

## Install

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # Linux / macOS

pip install -r requirements.txt
```

## Run

```bash
python main.py
```

## How it works

`yt-dlp` resolves the requested quality, downloads video and audio as separate
streams, and `ffmpeg` merges them into a single file. The app prefers the
`m4a` (AAC) audio track when available so the merge is a fast remux; when only
`opus` is offered (common at 4K / 1440p) the post-processor transcodes the
audio stream to AAC while copying the video stream untouched.

No cookies are sent to YouTube. The downloader explicitly disables cookie
loading on every call.

## License

[MIT](LICENSE)
