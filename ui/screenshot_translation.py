import threading
from html import escape
from queue import Empty, Queue
from statistics import median

from PySide6.QtCore import QEvent, QRect, QRectF, Qt, Signal, Slot
from PySide6.QtGui import QColor, QCursor, QFont, QFontMetrics, QGuiApplication, QPainter
from PySide6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel, QPushButton, QToolTip, QVBoxLayout, QWidget,
)

from core.config import load_app_config, logger
from core.translator import choose_translation_target, google_translate_text
from ui.theme import theme_palette


def draw_translation(image, original, bounds, text):
    rect = QRect(*bounds)
    margin = max(1, rect.height() // 8)
    outside = rect.adjusted(-margin, -margin, margin, margin).intersected(original.rect())
    xs = (outside.left(), outside.center().x(), outside.right())
    ys = (outside.top(), outside.center().y(), outside.bottom())
    samples = [
        original.pixelColor(x, y)
        for x in xs for y in ys
        if not rect.contains(x, y)
    ]
    background = QColor(245, 245, 245)
    if samples:
        background = QColor(*(round(median(c.getRgb()[i] for c in samples)) for i in range(3)))
    brightness = (299 * background.red() + 587 * background.green() + 114 * background.blue()) / 1000
    foreground = QColor("#161A20") if brightness >= 145 else QColor("#FFFFFF")
    painter = QPainter(image)
    try:
        painter.fillRect(rect, background)
        painter.setClipRect(rect)
        painter.setPen(foreground)
        painter.setRenderHint(QPainter.TextAntialiasing)
        text_rect = QRectF(rect.adjusted(1, 0, -1, 0))
        font = QFont("Microsoft YaHei")
        flags = int(Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWrapAnywhere)
        largest = max(6, min(96, round(rect.height() * 0.8)))
        smallest = max(6, round(largest * 0.62))
        for size in range(largest, smallest - 1, -1):
            font.setPixelSize(size)
            painter.setFont(font)
            if painter.boundingRect(text_rect, flags, text).height() <= rect.height():
                painter.drawText(text_rect, flags, text)
                break
        else:
            label = QFontMetrics(font).elidedText(text, Qt.ElideRight, max(0, int(text_rect.width())))
            painter.drawText(text_rect, int(Qt.AlignLeft | Qt.AlignVCenter), label)
    finally:
        painter.end()


class ScreenshotCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.original = None
        self.translated = None
        self.regions = ()
        self.results = {}
        self.show_original = False
        self.setMinimumHeight(160)

    def _image_rect(self):
        scale = min(self.width() / self.original.width(), self.height() / self.original.height(), 2)
        width, height = self.original.width() * scale, self.original.height() * scale
        return QRectF((self.width() - width) / 2, (self.height() - height) / 2, width, height)

    def paintEvent(self, event):
        if self.original is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        image = self.original if self.show_original else self.translated
        painter.drawImage(self._image_rect(), image, QRectF(image.rect()))
        painter.end()

    def event(self, event):
        if event.type() == QEvent.Type.ToolTip and self.original is not None:
            display = self._image_rect()
            if not self.show_original and display.contains(event.pos()):
                x = (event.pos().x() - display.x()) * self.original.width() / display.width()
                y = (event.pos().y() - display.y()) * self.original.height() / display.height()
                for index, result in self.results.items():
                    if QRectF(QRect(*self.regions[index].bounds)).contains(x, y):
                        QToolTip.showText(event.globalPos(), f"<qt>{escape(result)}</qt>", self)
                        return True
            QToolTip.hideText()
            event.ignore()
            return True
        return super().event(event)


class ScreenshotTranslationDialog(QDialog):
    full_translation_requested = Signal(str)
    _region_ready = Signal(int, int, str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("截图原位翻译 · ManboShot")
        self.setFont(QFont("Microsoft YaHei UI"))
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.setMinimumSize(350, 240)
        self._job = 0
        self._cancel = threading.Event()
        self._region_ready.connect(self._apply_result)
        self.finished.connect(self._cancel_job)

        self.canvas = ScreenshotCanvas(self)
        self.status = QLabel()
        self.original_button = QPushButton("原图")
        self.original_button.setCheckable(True)
        self.original_button.toggled.connect(self._toggle_original)
        self.copy_button = QPushButton("复制图片")
        self.copy_button.clicked.connect(self._copy_image)
        full_button = QPushButton("打开完整翻译")
        full_button.clicked.connect(self._open_full)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        toolbar.addWidget(self.status, 1)
        toolbar.addWidget(self.original_button)
        toolbar.addWidget(self.copy_button)
        toolbar.addWidget(full_button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        layout.addLayout(toolbar)
        layout.addWidget(self.canvas, 1)

    def show_capture(self, image, regions, source_text):
        self._cancel_job()
        self._cancel = threading.Event()
        self._source_text = source_text
        self.canvas.original = image
        self.canvas.translated = image.copy()
        self.canvas.regions = regions
        self.canvas.results = {}
        self.original_button.setChecked(False)
        self.copy_button.setEnabled(False)
        self._finished_count = 0
        self._failed_count = 0
        self.status.setText(f"翻译中 0/{len(regions)}")
        palette = theme_palette(load_app_config().get("THEME", "light"))
        self.setStyleSheet(f"""
            QDialog {{ background: {palette['surface_subtle']}; }}
            QLabel {{ color: {palette['text']}; }}
            QPushButton {{ color: {palette['text']}; background: {palette['surface']};
                border: 1px solid {palette['border']}; border-radius: 6px; padding: 6px 10px; }}
            QPushButton:hover, QPushButton:checked {{ border-color: {palette['primary']}; }}
            QPushButton:disabled {{ color: {palette['muted']}; }}
        """)
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        if screen:
            available = screen.availableGeometry()
            width = min(max(485, image.width() + 24), round(available.width() * 0.9))
            height = min(max(300, image.height() + 68), round(available.height() * 0.85))
            self.resize(width, height)
            self.move(available.center() - self.rect().center())
        self.canvas.update()
        self.show()
        self.raise_()
        self.activateWindow()

        target = choose_translation_target(source_text)
        pending = Queue()
        for index, region in enumerate(regions):
            pending.put((index, region.text))
        for _ in range(min(3, len(regions))):
            threading.Thread(
                target=self._translate_regions, args=(pending, target, self._job, self._cancel),
                daemon=True,
            ).start()

    def _translate_regions(self, pending, target, job, cancel):
        while not cancel.is_set():
            try:
                index, source = pending.get_nowait()
            except Empty:
                return
            try:
                text = google_translate_text(source, target).strip()
            except Exception as error:
                logger.warning("截图原位翻译失败: %s", type(error).__name__)
                text = ""
            if not cancel.is_set():
                self._region_ready.emit(job, index, text)

    @Slot(int, int, str)
    def _apply_result(self, job, index, text):
        if job != self._job:
            return
        self._finished_count += 1
        region = self.canvas.regions[index]
        if not text:
            self._failed_count += 1
        elif text != region.text:
            draw_translation(self.canvas.translated, self.canvas.original, region.bounds, text)
            self.canvas.results[index] = text
            self.canvas.update()
        total = len(self.canvas.regions)
        if self._finished_count < total:
            self.status.setText(f"翻译中 {self._finished_count}/{total}")
        elif self._failed_count == total:
            self.status.setText("原位翻译失败")
        elif self._failed_count:
            self.status.setText(f"{self._failed_count} 处未译")
        else:
            self.status.setText("翻译完成")
        self.copy_button.setEnabled(self.canvas.show_original or bool(self.canvas.results))

    def _toggle_original(self, original):
        self.canvas.show_original = original
        self.copy_button.setEnabled(original or bool(self.canvas.results))
        self.canvas.update()

    def _copy_image(self):
        image = self.canvas.original if self.canvas.show_original else self.canvas.translated
        QApplication.clipboard().setImage(image)

    def _open_full(self):
        source_text = self._source_text
        self.close()
        self.full_translation_requested.emit(source_text)

    def _cancel_job(self):
        self._cancel.set()
        self._job += 1
