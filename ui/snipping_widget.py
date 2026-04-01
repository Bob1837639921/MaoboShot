import numpy as np
import threading
from io import BytesIO
from PIL import Image
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, Signal, QRect, QBuffer, QIODevice, QByteArray
from PySide6.QtGui import QPainter, QColor, QPen, QGuiApplication, QPixmap, QFont

from core.ocr_engine import get_ocr_engine, HAS_OCR
from core.config import logger

class SnippingWidget(QWidget):
    ocr_started_signal = Signal()
    ocr_finished_signal = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowState(Qt.WindowFullScreen)
        self.setCursor(Qt.CrossCursor)
        self.start_pos = None
        self.end_pos = None
        self.is_drawing = False

    def start_capture(self):
        self.start_pos = None
        self.end_pos = None
        self.is_drawing = False
        screen = QGuiApplication.primaryScreen()
        if screen:
            self.original_pixmap = screen.grabWindow(0)
            self.show()
            self.activateWindow()
        
    def paintEvent(self, event):
        if not hasattr(self, 'original_pixmap'): return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 1. 绘制底层原图
        painter.drawPixmap(0, 0, self.original_pixmap)
        
        # 2. 绘制半透明黑色遮罩 (稍微调深以凸显高亮区域)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 120))
        
        if self.start_pos and self.end_pos:
            rect = QRect(self.start_pos, self.end_pos).normalized()
            
            # 3. 抠出选中的区域 (去除遮罩)
            painter.drawPixmap(rect, self.original_pixmap, rect)
            
            # 4. 绘制现代化高亮边框 (Snipaste风格的蓝色 + 内部细白线增加对比度)
            painter.setPen(QPen(QColor(26, 115, 232), 2)) # Google Blue
            painter.drawRect(rect)
            
            painter.setPen(QPen(QColor(255, 255, 255), 1))
            painter.drawRect(rect.adjusted(2, 2, -2, -2))
            
            # 5. 绘制选区尺寸信息标签
            size_text = f"{rect.width()} × {rect.height()}"
            painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
            fm = painter.fontMetrics()
            text_rect = fm.boundingRect(size_text)
            
            padding = 4
            bg_rect = QRect(
                rect.left(), 
                rect.top() - text_rect.height() - padding * 2 - 4, 
                text_rect.width() + padding * 2, 
                text_rect.height() + padding * 2
            )
            
            # 防治标签超出屏幕上边缘
            if bg_rect.top() < 0:
                bg_rect.moveTop(rect.top() + 4)
                bg_rect.moveLeft(rect.left() + 4)
                
            painter.fillRect(bg_rect, QColor(0, 0, 0, 180))
            painter.setPen(QPen(Qt.white))
            painter.drawText(bg_rect, Qt.AlignCenter, size_text)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start_pos = event.position().toPoint()
            self.end_pos = self.start_pos
            self.is_drawing = True
            self.update()
        elif event.button() == Qt.RightButton:
            # 右键随时取消截图
            self.close()

    def mouseMoveEvent(self, event):
        if self.is_drawing:
            self.end_pos = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_drawing = False
            self.end_pos = event.position().toPoint()
            self.close()
            if self.start_pos and self.end_pos:
                x1 = min(self.start_pos.x(), self.end_pos.x())
                y1 = min(self.start_pos.y(), self.end_pos.y())
                w = abs(self.end_pos.x() - self.start_pos.x())
                h = abs(self.end_pos.y() - self.start_pos.y())
                if w > 10 and h > 10:
                    self.process_image(x1, y1, w, h)

    def process_image(self, x, y, w, h):
        if not HAS_OCR: return
        self.ocr_started_signal.emit()
        cropped = self.original_pixmap.copy(x, y, w, h)
        byte_array = QByteArray()
        buffer = QBuffer(byte_array)
        buffer.open(QIODevice.WriteOnly)
        cropped.save(buffer, "PNG")
        pil_img = Image.open(BytesIO(byte_array.data()))
        
        # Start OCR in background thread
        threading.Thread(target=self._run_ocr_thread, args=(pil_img,), daemon=True).start()

    def _run_ocr_thread(self, img):
        try:
            ocr = get_ocr_engine()
            if not ocr:
                logger.error("OCR 引擎尚未就绪或初始化失败。")
                self.ocr_finished_signal.emit("")
                return
            result, _ = ocr(np.array(img))
            if result:
                text = "\n".join([line[1] for line in result])
                self.ocr_finished_signal.emit(text if text.strip() else "")
            else:
                self.ocr_finished_signal.emit("")
        except Exception as e:
            logger.error(f"OCR 处理失败: {e}", exc_info=True)
            self.ocr_finished_signal.emit("")
