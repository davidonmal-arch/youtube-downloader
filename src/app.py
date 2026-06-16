"""Главное окно YouTube Downloader."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QComboBox, QLabel, QFileDialog, QFrame,
    QProgressBar, QSizePolicy, QScrollArea,
)

from . import downloader
from .workers import InfoWorker, DownloadWorker


# ---------- тема ----------

STYLESHEET = """
QMainWindow, QWidget#root {
    background-color: #0e0e10;
    color: #e8e8ea;
    font-family: "Segoe UI", "Inter", "Helvetica Neue", sans-serif;
    font-size: 13px;
}
QLabel#h1 {
    color: #fafafa;
    font-size: 22px;
    font-weight: 700;
    letter-spacing: -0.3px;
}
QLabel#h2 {
    color: #fafafa;
    font-size: 14px;
    font-weight: 600;
}
QLabel#muted { color: #71717a; font-size: 12px; }
QLabel#title { color: #fafafa; font-size: 15px; font-weight: 600; }
QLabel#logo { font-size: 28px; }

QLineEdit {
    background-color: #18181b;
    border: 1px solid #27272a;
    border-radius: 8px;
    padding: 11px 14px;
    color: #fafafa;
    selection-background-color: #ef4444;
    font-size: 13px;
}
QLineEdit:focus { border: 1px solid #ef4444; }
QLineEdit:disabled { color: #52525b; }

QComboBox {
    background-color: #18181b;
    border: 1px solid #27272a;
    border-radius: 8px;
    padding: 9px 30px 9px 14px;
    color: #fafafa;
    min-height: 18px;
    font-size: 13px;
}
QComboBox:hover { border-color: #3f3f46; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
    background-color: #18181b;
    border: 1px solid #27272a;
    selection-background-color: #ef4444;
    color: #fafafa;
    padding: 4px;
    outline: 0;
}

QPushButton {
    background-color: #ef4444;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 11px 20px;
    font-weight: 600;
    font-size: 13px;
}
QPushButton:hover { background-color: #dc2626; }
QPushButton:pressed { background-color: #b91c1c; }
QPushButton:disabled { background-color: #27272a; color: #52525b; }
QPushButton#secondary { background-color: #27272a; color: #fafafa; }
QPushButton#secondary:hover { background-color: #3f3f46; }
QPushButton#ghost {
    background-color: transparent;
    color: #a1a1aa;
    padding: 0;
    min-width: 28px;
    max-width: 28px;
    min-height: 28px;
    max-height: 28px;
    font-size: 14px;
    border-radius: 6px;
}
QPushButton#ghost:hover { color: #fafafa; background-color: #27272a; }

QProgressBar {
    background-color: #27272a;
    border: none;
    border-radius: 4px;
    text-align: center;
    height: 8px;
    color: transparent;
}
QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #ef4444, stop:1 #f87171);
    border-radius: 4px;
}

QFrame#card, QFrame#preview, QFrame#urlcard {
    background-color: #18181b;
    border: 1px solid #27272a;
    border-radius: 12px;
}
QFrame#queueCard {
    background-color: #18181b;
    border: 1px solid #27272a;
    border-radius: 10px;
}
QFrame#queueCard[state="done"]      { border-color: #166534; }
QFrame#queueCard[state="error"]     { border-color: #7f1d1d; }
QFrame#queueCard[state="cancelled"] { border-color: #52525b; opacity: 0.7; }

QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #3f3f46;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover { background: #52525b; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


# ---------- карточка очереди ----------

class QueueItem(QFrame):
    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("queueCard")
        self.setProperty("state", "pending")
        self._cancelled = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(10)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("title")
        self.title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.title_label.setWordWrap(True)

        self.cancel_btn = QPushButton("✕")
        self.cancel_btn.setObjectName("ghost")
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.setToolTip("Отменить")
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)

        top.addWidget(self.title_label, 1)
        top.addWidget(self.cancel_btn, 0, Qt.AlignmentFlag.AlignTop)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)

        self.status_label = QLabel("В очереди…")
        self.status_label.setObjectName("muted")

        layout.addLayout(top)
        layout.addWidget(self.progress)
        layout.addWidget(self.status_label)

    # публичный API для MainWindow
    def request_cancel(self) -> bool:
        """Помечаем как отменённый, чтобы воркер мог опросить флаг. Возвращает True, если ещё не отменяли."""
        if self._cancelled:
            return False
        self._cancelled = True
        self.cancel_btn.setEnabled(False)
        self.set_state("cancelled", "Отмена…", self.progress.value())
        return True

    def is_cancelled(self) -> bool:
        return self._cancelled

    def update_progress(self, d: dict) -> None:
        pct_str = d.get("percent", "") or ""
        try:
            pct = int(float(pct_str.replace("%", "").strip()))
        except (ValueError, AttributeError):
            pct = 0
        pct = max(0, min(100, pct))

        speed = d.get("speed", "") or ""
        eta = d.get("eta", "") or ""

        if d.get("status") == "finished":
            self.set_state("downloading", "Пост-обработка…", 100)
            return

        bits = [pct_str, speed, f"ETA {eta}" if eta else ""]
        status = "  ·  ".join(b for b in bits if b).strip(" ·")
        self.set_state("downloading", status, pct)

    def update_status(self, s: str) -> None:
        self.status_label.setText(s)

    def mark_done(self) -> None:
        self.set_state("done", "Готово ✓", 100)
        self.cancel_btn.setEnabled(False)

    def mark_error(self, msg: str) -> None:
        self.set_state("error", f"Ошибка: {msg}")
        self.cancel_btn.setEnabled(False)

    def mark_cancelled(self) -> None:
        self.set_state("cancelled", "Отменено")
        self.cancel_btn.setEnabled(False)

    def set_state(self, state: str, status: str, percent: int = -1) -> None:
        self.setProperty("state", state)
        # проси Qt пересчитать стили с новым property
        self.style().unpolish(self)
        self.style().polish(self)
        if status:
            self.status_label.setText(status)
        if 0 <= percent <= 100:
            self.progress.setValue(percent)

    def _on_cancel_clicked(self) -> None:
        self.request_cancel()


# ---------- главное окно ----------

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("YouTube Downloader")
        self.setMinimumSize(720, 720)
        self.resize(820, 820)

        self._info_gen = 0
        self._info_worker: Optional[InfoWorker] = None
        self._download_workers: list[DownloadWorker] = []
        self._current_info: Optional[downloader.VideoInfo] = None
        self._output_dir = str(Path.home() / "Downloads" / "YouTube")
        Path(self._output_dir).mkdir(parents=True, exist_ok=True)

        self._fetch_timer = QTimer(self)
        self._fetch_timer.setSingleShot(True)
        self._fetch_timer.setInterval(450)
        self._fetch_timer.timeout.connect(self._fetch_info)

        self._build_ui()
        self._refresh_download_button()

    # ---------- UI ----------

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(28, 22, 28, 22)
        outer.setSpacing(16)

        # --- header ---
        header = QHBoxLayout()
        header.setSpacing(10)
        logo = QLabel("🎬")
        logo.setObjectName("logo")
        title = QLabel("YouTube Downloader")
        title.setObjectName("h1")
        header.addWidget(logo)
        header.addWidget(title, 1)
        subtitle = QLabel("без cookies · на yt-dlp")
        subtitle.setObjectName("muted")
        header.addWidget(subtitle, 0, Qt.AlignmentFlag.AlignBottom)
        outer.addLayout(header)

        # --- URL ---
        url_card = QFrame()
        url_card.setObjectName("urlcard")
        url_layout = QVBoxLayout(url_card)
        url_layout.setContentsMargins(16, 16, 16, 16)
        url_layout.setSpacing(10)

        url_caption = QLabel("Ссылка на видео")
        url_caption.setObjectName("h2")
        url_layout.addWidget(url_caption)

        url_row = QHBoxLayout()
        url_row.setSpacing(10)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText(
            "https://www.youtube.com/watch?v=…   или просто перетащи ссылку сюда"
        )
        self.url_input.setClearButtonEnabled(True)
        self.url_input.textChanged.connect(self._on_url_changed)

        self.paste_btn = QPushButton("Вставить")
        self.paste_btn.setObjectName("secondary")
        self.paste_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.paste_btn.clicked.connect(self._on_paste_clicked)

        url_row.addWidget(self.url_input, 1)
        url_row.addWidget(self.paste_btn)
        url_layout.addLayout(url_row)
        outer.addWidget(url_card)

        # --- preview ---
        self.preview_card = QFrame()
        self.preview_card.setObjectName("preview")
        self.preview_card.setVisible(False)
        pv = QHBoxLayout(self.preview_card)
        pv.setContentsMargins(14, 14, 14, 14)
        pv.setSpacing(14)

        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(160, 90)
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_label.setStyleSheet(
            "background-color: #27272a; border-radius: 6px; color: #52525b;"
            "font-size: 11px;"
        )
        self.thumb_label.setText("превью")

        pv_text = QVBoxLayout()
        pv_text.setSpacing(4)
        self.preview_title = QLabel()
        self.preview_title.setObjectName("title")
        self.preview_title.setWordWrap(True)

        self.preview_meta = QLabel()
        self.preview_meta.setObjectName("muted")

        self.preview_status = QLabel()
        self.preview_status.setObjectName("muted")
        self.preview_status.setWordWrap(True)

        pv_text.addWidget(self.preview_title)
        pv_text.addWidget(self.preview_meta)
        pv_text.addWidget(self.preview_status)
        pv_text.addStretch(1)

        pv.addWidget(self.thumb_label, 0, Qt.AlignmentFlag.AlignTop)
        pv.addLayout(pv_text, 1)
        outer.addWidget(self.preview_card)

        # --- settings ---
        settings_card = QFrame()
        settings_card.setObjectName("card")
        s = QVBoxLayout(settings_card)
        s.setContentsMargins(16, 16, 16, 16)
        s.setSpacing(12)

        s.addWidget(self._h2("Настройки"))

        quality_row = QHBoxLayout()
        quality_row.setSpacing(10)
        quality_caption = self._muted("Качество")
        quality_caption.setFixedWidth(120)
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(list(downloader.QUALITY_PRESETS.keys()))
        self.quality_combo.setCurrentText("1080p")
        self.quality_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        quality_row.addWidget(quality_caption)
        quality_row.addWidget(self.quality_combo, 1)
        s.addLayout(quality_row)

        output_row = QHBoxLayout()
        output_row.setSpacing(10)
        output_caption = self._muted("Папка")
        output_caption.setFixedWidth(120)
        self.output_edit = QLineEdit(self._output_dir)
        self.output_edit.setReadOnly(True)
        browse_btn = QPushButton("Обзор…")
        browse_btn.setObjectName("secondary")
        browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        browse_btn.clicked.connect(self._on_browse)
        output_row.addWidget(output_caption)
        output_row.addWidget(self.output_edit, 1)
        output_row.addWidget(browse_btn)
        s.addLayout(output_row)

        outer.addWidget(settings_card)

        # --- download button ---
        self.download_btn = QPushButton("⬇   Скачать")
        self.download_btn.setMinimumHeight(50)
        f = self.download_btn.font()
        f.setPointSize(14)
        f.setBold(True)
        self.download_btn.setFont(f)
        self.download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.download_btn.clicked.connect(self._on_download)
        outer.addWidget(self.download_btn)

        # --- queue ---
        qhead = QHBoxLayout()
        qhead.setSpacing(8)
        qhead.addWidget(self._h2("Очередь"))
        self.queue_count = self._muted("0")
        qhead.addWidget(self.queue_count)
        qhead.addStretch(1)
        outer.addLayout(qhead)

        self.queue_scroll = QScrollArea()
        self.queue_scroll.setWidgetResizable(True)
        self.queue_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.queue_inner = QWidget()
        self.queue_inner.setObjectName("root")
        self.queue_layout = QVBoxLayout(self.queue_inner)
        self.queue_layout.setContentsMargins(0, 0, 0, 0)
        self.queue_layout.setSpacing(10)
        self.queue_layout.addStretch(1)
        self.queue_scroll.setWidget(self.queue_inner)
        outer.addWidget(self.queue_scroll, 1)

        self.setAcceptDrops(True)

    def _h2(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setObjectName("h2")
        return l

    def _muted(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setObjectName("muted")
        return l

    # ---------- URL & info ----------

    def _on_url_changed(self, _text: str) -> None:
        self._refresh_download_button()
        if not downloader.is_valid_url(self.url_input.text()):
            self._clear_preview()
            self._fetch_timer.stop()
            return
        self._fetch_timer.start()

    def _on_paste_clicked(self) -> None:
        cb = QApplication.clipboard()
        text = (cb.text() or "").strip()
        if text:
            self.url_input.setText(text)

    def _refresh_download_button(self) -> None:
        valid = (
            downloader.is_valid_url(self.url_input.text())
            and self._current_info is not None
        )
        self.download_btn.setEnabled(valid)

    def _clear_preview(self) -> None:
        self._current_info = None
        self.preview_card.setVisible(False)
        self.thumb_label.setText("превью")
        self.thumb_label.setPixmap(QPixmap())

    def _fetch_info(self) -> None:
        url = self.url_input.text().strip()
        if not downloader.is_valid_url(url):
            return

        self._info_gen += 1
        gen = self._info_gen

        self._clear_preview()
        self.preview_card.setVisible(True)
        self.preview_title.setText("Загружаю…")
        self.preview_meta.setText("")
        self.preview_status.setText("Тяну инфо о видео")
        self.thumb_label.setText("⏳")
        self._refresh_download_button()

        worker = InfoWorker(url)
        worker.ok.connect(lambda info, g=gen: self._on_info_loaded(info, g))
        worker.fail.connect(lambda msg, g=gen: self._on_info_failed(msg, g))
        worker.finished.connect(worker.deleteLater)
        self._info_worker = worker
        worker.start()

    def _on_info_loaded(self, info: downloader.VideoInfo, gen: int) -> None:
        if gen != self._info_gen:
            return
        self._current_info = info
        self.preview_card.setVisible(True)
        self.preview_title.setText(info.title)
        self.preview_meta.setText(f"{info.uploader}  ·  {info.duration_str}")
        self.preview_status.setText("")

        if info.thumbnail_bytes:
            pix = QPixmap()
            if pix.loadFromData(info.thumbnail_bytes):
                scaled = pix.scaled(
                    160, 90,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.thumb_label.setText("")
                self.thumb_label.setPixmap(scaled)
            else:
                self.thumb_label.setText("превью")
        else:
            self.thumb_label.setText("превью")

        self._refresh_download_button()

    def _on_info_failed(self, msg: str, gen: int) -> None:
        if gen != self._info_gen:
            return
        self.preview_card.setVisible(True)
        self.preview_title.setText("Не получилось загрузить")
        self.preview_meta.setText(self.url_input.text().strip())
        self.preview_status.setText(msg or "Неизвестная ошибка")
        self.thumb_label.setText("⚠")
        self.thumb_label.setPixmap(QPixmap())
        self._current_info = None
        self._refresh_download_button()

    # ---------- папка ----------

    def _on_browse(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Куда скачивать", self._output_dir)
        if d:
            self._output_dir = d
            self.output_edit.setText(d)

    # ---------- очередь ----------

    def _on_download(self) -> None:
        if not self._current_info:
            return
        self._enqueue(
            url=self._current_info.url,
            title=self._current_info.title,
            quality=self.quality_combo.currentText(),
            output_dir=self._output_dir,
        )

    def _enqueue(self, url: str, title: str, quality: str, output_dir: str) -> None:
        item = QueueItem(title)

        # вставляем перед финальным stretch
        stretch_idx = self.queue_layout.count() - 1
        self.queue_layout.insertWidget(stretch_idx, item)

        worker = DownloadWorker(url, quality, output_dir)
        worker.progress.connect(item.update_progress)
        worker.status.connect(item.update_status)
        worker.finished.connect(lambda ok, msg, w=worker, it=item: self._on_dl_finished(it, w, ok, msg))
        worker.finished.connect(worker.deleteLater)

        item.cancel_btn.clicked.connect(worker.cancel)

        self._download_workers.append(worker)
        worker.start()
        self._update_queue_count()

    def _on_dl_finished(self, item: QueueItem, worker: DownloadWorker, ok: bool, msg: str) -> None:
        if worker in self._download_workers:
            self._download_workers.remove(worker)
        self._update_queue_count()

        if item.is_cancelled():
            item.mark_cancelled()
        elif ok:
            item.mark_done()
        else:
            item.mark_error(msg or "неизвестная ошибка")

    def _update_queue_count(self) -> None:
        active = len(self._download_workers)
        if active:
            self.queue_count.setText(f"{active} активных")
        else:
            self.queue_count.setText("0")

    # ---------- drag & drop ----------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        md = event.mimeData()
        if md.hasUrls() or md.hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        md = event.mimeData()
        url = ""
        if md.hasUrls() and md.urls():
            url = md.urls()[0].toString()
        elif md.hasText():
            url = md.text()
        url = url.strip()
        if url:
            self.url_input.setText(url)
            event.acceptProposedAction()

    # ---------- закрытие ----------

    def closeEvent(self, event) -> None:
        # отменяем всё, что качается
        for w in list(self._download_workers):
            w.cancel()
        super().closeEvent(event)
