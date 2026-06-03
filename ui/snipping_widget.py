import numpy as np
import threading
from io import BytesIO
from PIL import Image
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, Signal, QRect, QBuffer, QIODevice, QByteArray
from PySide6.QtGui import QPainter, QColor, QPen, QGuiApplication, QPixmap, QFont, QCursor

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
        
        # 获取当前鼠标所在的屏幕
        cursor_pos = QCursor.pos()
        screen = QGuiApplication.screenAt(cursor_pos)
        if not screen:
            screen = QGuiApplication.primaryScreen()
            
        if screen:
            self.original_pixmap = screen.grabWindow(0)
            # 解决多显示器跳转问题：先解除全屏 -> 移动到目标屏幕坐标系 -> 再全屏
            self.setWindowState(Qt.WindowNoState)
            self.setGeometry(screen.geometry())
            self.setWindowState(Qt.WindowFullScreen)
            
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

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

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

    def _restore_layout(self, ocr_result):
        if not ocr_result:
            return ""
        
        parsed_items = []
        for item in ocr_result:
            if not item or len(item) < 2:
                continue
            box = item[0]
            if isinstance(item[1], (tuple, list)):
                text = item[1][0]
            else:
                text = item[1]
                
            if not text:
                continue
                
            xs = [pt[0] for pt in box]
            ys = [pt[1] for pt in box]
            x_min, x_max = min(xs), max(xs)
            y_min, y_max = min(ys), max(ys)
            y_center = (y_min + y_max) / 2.0
            height = y_max - y_min
            
            parsed_items.append({
                'x_min': x_min,
                'x_max': x_max,
                'y_min': y_min,
                'y_max': y_max,
                'y_center': y_center,
                'height': height,
                'text': text
            })
            
        if not parsed_items:
            return ""
            
        # 按 y_center 排序进行分行
        parsed_items.sort(key=lambda item: item['y_center'])
        
        lines = []
        for item in parsed_items:
            placed = False
            for line in lines:
                avg_y_center = sum(member['y_center'] for member in line) / len(line)
                avg_height = sum(member['height'] for member in line) / len(line)
                
                # 如果 Y 轴中心点差值在平均高度的 60% 以内，视作同一行
                if abs(item['y_center'] - avg_y_center) < (avg_height * 0.6):
                    line.append(item)
                    placed = True
                    break
                    
            if not placed:
                lines.append([item])
                
        # 按照平均 y_center 对行进行自上而下排序
        lines.sort(key=lambda line: sum(member['y_center'] for member in line) / len(line))
        
        formatted_lines = []
        for line in lines:
            # 同一行内自左向右排序
            line.sort(key=lambda member: member['x_min'])
            
            line_text = line[0]['text']
            for i in range(1, len(line)):
                prev_text = line_text
                curr_text = line[i]['text']
                
                prev_char = prev_text[-1] if prev_text else ''
                curr_char = curr_text[0] if curr_text else ''
                
                need_space = False
                if prev_char and curr_char:
                    # 如果前一个段落以西文字符结尾且当前段落以西文字符开头，增加空格
                    if ord(prev_char) < 128 and ord(curr_char) < 128:
                        if prev_char != ' ' and curr_char != ' ':
                            need_space = True
                
                if need_space:
                    line_text += " " + curr_text
                else:
                    line_text += curr_text
                    
            formatted_lines.append(line_text)
            
        return "\n".join(formatted_lines)

    def _run_ocr_thread(self, img):
        try:
            ocr = get_ocr_engine()
            if not ocr:
                logger.error("OCR 引擎尚未就绪或初始化失败。")
                self.ocr_finished_signal.emit("")
                return
            
            # 将 PIL Image 转换为 numpy 数组
            img_arr = np.array(img)
            
            # 单个单词或贴边截图容易导致检测失败。增加边缘 padding
            if img_arr.ndim == 3:
                # PIL Image 转换为 numpy 后为 RGB / RGBA，而 RapidOCR 默认期望 BGR
                if img_arr.shape[2] == 3:
                    img_arr = img_arr[:, :, ::-1]  # RGB to BGR
                elif img_arr.shape[2] == 4:
                    img_arr = img_arr[:, :, [2, 1, 0, 3]]  # RGBA to BGRA
                # 使用边缘像素填充 20 像素，避免引入人造边界
                img_arr = np.pad(img_arr, ((20, 20), (20, 20), (0, 0)), mode='edge')
            elif img_arr.ndim == 2:
                img_arr = np.pad(img_arr, ((20, 20), (20, 20)), mode='edge')

            result, _ = ocr(img_arr)
            if result:
                text = self._restore_layout(result)
                self.ocr_finished_signal.emit(text if text.strip() else "")
            else:
                self.ocr_finished_signal.emit("")
        except Exception as e:
            logger.error(f"OCR 处理失败: {e}", exc_info=True)
            self.ocr_finished_signal.emit("")
