"""QThread-воркеры: качают в фоне, шлют сигналы в UI."""
from __future__ import annotations

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from . import downloader


class InfoWorker(QThread):
    """Тянет инфо о видео в фоне, чтобы UI не фризился."""

    ok = pyqtSignal(object)        # VideoInfo
    fail = pyqtSignal(str)         # error message

    def __init__(self, url: str) -> None:
        super().__init__()
        self.url = url

    def run(self) -> None:
        try:
            info = downloader.fetch_info(self.url)
            self.ok.emit(info)
        except Exception as e:  # noqa: BLE001
            self.fail.emit(str(e))


class DownloadWorker(QThread):
    """Качает одно видео/аудио. Сигналы:"""

    progress = pyqtSignal(dict)    # {percent, speed, eta, downloaded_bytes, total_bytes, status}
    status = pyqtSignal(str)       # короткий статус ("Скачивание...", "Пост-обработка...")
    finished = pyqtSignal(bool, str)  # (ok, message)

    def __init__(self, url: str, quality: str, output_dir: str) -> None:
        super().__init__()
        self.url = url
        self.quality = quality
        self.output_dir = output_dir
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def _should_cancel(self) -> bool:
        return self._cancel

    def _hook(self, d: dict) -> None:
        status = d.get("status")
        if status == "downloading":
            self.progress.emit({
                "status": "downloading",
                "percent": d.get("_percent_str", "").strip(),
                "speed": d.get("_speed_str", "").strip(),
                "eta": d.get("_eta_str", "").strip(),
                "downloaded_bytes": d.get("downloaded_bytes") or 0,
                "total_bytes": d.get("total_bytes") or d.get("total_bytes_estimate") or 0,
            })
        elif status == "finished":
            self.progress.emit({
                "status": "finished",
                "percent": "100%",
                "speed": "",
                "eta": "",
                "downloaded_bytes": d.get("downloaded_bytes") or 0,
                "total_bytes": d.get("total_bytes") or 0,
            })

    def run(self) -> None:
        try:
            self.status.emit("Подключение…")
            downloader.download(
                self.url,
                self.quality,
                self.output_dir,
                progress_hook=self._hook,
                should_cancel=self._should_cancel,
            )
            if self._cancel:
                self.finished.emit(False, "Отменено")
            else:
                self.status.emit("Готово")
                self.finished.emit(True, "Готово")
        except downloader._CancelledError:
            self.finished.emit(False, "Отменено")
        except Exception as e:  # noqa: BLE001
            self.finished.emit(False, str(e))
