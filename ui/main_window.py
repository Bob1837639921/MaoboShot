import os
import sys
import time
import ctypes
import pyperclip
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton,
                               QFrame, QSystemTrayIcon, QMenu, QStyle, QApplication, QGraphicsDropShadowEffect)
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QThread, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QCursor, QAction, QIcon, QColor
from ui.settings_window import SettingsWindow

from core.config import ICON_PATH, logger, load_app_config
from core.tts_engine import play_voice_worker
from core.translator import TranslatorWorker
from ui.snipping_widget import SnippingWidget
from core.ocr_engine import HAS_OCR
from utils.win_api import (WM_HOTKEY, WM_CLIPBOARDUPDATE, HOTKEY_ID_Q, HOTKEY_ID_Z,
                           force_focus_window, MOD_ALT, VK_Q, VK_Z)

class FloatingWindow(QWidget):
    request_translation_signal = Signal(str)
    show_window_signal = Signal()
    trigger_snipping_signal = Signal()
    tts_status_signal = Signal(str)

    def __init__(self):
        super().__init__()
        # 移除边框，保持置顶，工具窗口(不在任务栏显示)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.StrongFocus) 
        
        self.current_text_for_speech = ""
        self.drag_pos = None
        
        self._clipboard_suppress_until = 0
        self.last_clipboard_time = 0
        self.last_clipboard_text = ""

        self.setup_tray()
        self.tts_status_signal.connect(self.update_play_btn_status)

        if HAS_OCR:
            self.snipper = SnippingWidget()
            self.snipper.ocr_finished_signal.connect(self.handle_ocr_result)
            self.snipper.ocr_started_signal.connect(self.handle_ocr_started)

        self._init_ui()
        self._init_workers()
        self._init_hotkeys()

        self.input_edit.textChanged.connect(self.on_input_changed)

    def _init_ui(self):
        self.main_layout = QVBoxLayout()
        # 预留外边距给阴影效果
        self.main_layout.setContentsMargins(15, 15, 15, 15)
        
        self.container = QFrame()
        self.container.setObjectName("container")
        
        # 增加硬件级窗口阴影
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 160))
        self.container.setGraphicsEffect(shadow)
        
        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(15, 15, 15, 15)
        self.content_layout.setSpacing(10)

        # === 顶部拖拽把手与控制栏 ===
        self.header_layout = QHBoxLayout()
        self.header_layout.setContentsMargins(0, 0, 0, 0)
        
        self.title_label = QLabel("✨ ManboShot")
        
        self.close_btn = QPushButton("×")
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.clicked.connect(self.hide)
        
        self.header_layout.addWidget(self.title_label)
        self.header_layout.addStretch()
        self.header_layout.addWidget(self.close_btn)

        # === 输入框 ===
        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText("手动输入 / 划词复制 / Alt+Z 截图...")
        self.input_edit.setMaximumHeight(80)

        # === 结果展示 ===
        self.result_label = QLabel()
        self.result_label.setWordWrap(True)
        self.result_label.setTextFormat(Qt.RichText)
        self.result_label.setOpenExternalLinks(True)
        self.result_label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)

        # === 朗读按钮 ===
        self.play_btn = QPushButton("🔊 朗读原文")
        self.play_btn.setCursor(Qt.PointingHandCursor)
        self.play_btn.clicked.connect(self.play_audio)

        self.content_layout.addLayout(self.header_layout)
        self.content_layout.addWidget(self.input_edit)
        self.content_layout.addWidget(self.result_label)
        self.content_layout.addWidget(self.play_btn)
        
        self.container.setLayout(self.content_layout)
        self.main_layout.addWidget(self.container)
        self.setLayout(self.main_layout)

        self.result_label.hide()
        self.play_btn.hide()
        self.resize(380, 100)
        
        # === 弹窗淡入动画 ===
        self.fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self.fade_anim.setDuration(150)
        self.fade_anim.setStartValue(0.0)
        self.fade_anim.setEndValue(1.0)
        self.fade_anim.setEasingCurve(QEasingCurve.OutQuad)
        
        # 应用初始主题
        self.apply_theme()

    def apply_theme(self):
        config = load_app_config()
        self.theme = config.get("THEME", "dark")
        
        if self.theme == "light":
            bg_color = "rgba(245, 245, 245, 245)"
            border_color = "rgba(200, 200, 200, 150)"
            title_color = "#666666"
            close_btn_color = "#888888"
            input_bg = "rgba(255, 255, 255, 200)"
            input_text = "#333333"
            input_border = "rgba(200, 200, 200, 180)"
            result_text = "#333333"
            play_btn_bg = "#1a73e8"
            play_btn_hover = "#2b84f3"
            
            self.html_vars = {
                "card_bg": "rgba(0,0,0,0.05)",
                "phonetic_bg": "rgba(0,0,0,0.08)",
                "phonetic_text": "#666666",
                "divider": "rgba(0,0,0,0.08)",
                "ai_title": "#0067C0",
                "google_title": "#d97b00",
                "placeholder": "#888888"
            }
        else:
            bg_color = "rgba(30, 30, 30, 245)"
            border_color = "rgba(80, 80, 80, 150)"
            title_color = "#999999"
            close_btn_color = "#888888"
            input_bg = "rgba(15, 15, 15, 150)"
            input_text = "#ffffff"
            input_border = "rgba(80, 80, 80, 150)"
            result_text = "#e0e0e0"
            play_btn_bg = "#1a73e8"
            play_btn_hover = "#2b84f3"
            
            self.html_vars = {
                "card_bg": "rgba(0,0,0,0.15)",
                "phonetic_bg": "rgba(255,255,255,0.1)",
                "phonetic_text": "#aaaaaa",
                "divider": "rgba(255,255,255,0.1)",
                "ai_title": "#5bc0de",
                "google_title": "#f0ad4e",
                "placeholder": "#888888"
            }

        self.container.setStyleSheet(f"""
            QFrame#container {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 12px;
            }}
        """)
        
        self.title_label.setStyleSheet(f"color: {title_color}; font-family: 'Segoe UI', 'Microsoft YaHei'; font-size: 12px; font-weight: bold;")
        
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {close_btn_color};
                font-size: 16px;
                font-weight: bold;
                border: none;
                border-radius: 12px;
            }}
            QPushButton:hover {{ background-color: #ff4d4f; color: white; }}
        """)
        
        self.input_edit.setStyleSheet(f"""
            QTextEdit {{ 
                background-color: {input_bg}; 
                color: {input_text}; 
                border: 1px solid {input_border}; 
                border-radius: 8px; 
                font-family: 'Segoe UI', 'Microsoft YaHei'; 
                font-size: 14px; 
                padding: 8px; 
            }}
            QTextEdit:focus {{
                border: 1px solid #1a73e8;
            }}
        """)
        
        self.result_label.setStyleSheet(f"QLabel {{ color: {result_text}; font-family: 'Segoe UI', 'Microsoft YaHei'; font-size: 14px; line-height: 1.4; }}")
        
        self.play_btn.setStyleSheet(f"""
            QPushButton {{ 
                background-color: {play_btn_bg}; 
                color: white; 
                border: none; 
                border-radius: 8px; 
                padding: 8px 16px; 
                font-family: 'Segoe UI', 'Microsoft YaHei'; 
                font-size: 13px;
                font-weight: bold; 
            }} 
            QPushButton:hover {{ background-color: {play_btn_hover}; }}
            QPushButton:pressed {{ background-color: #1257b5; }}
            QPushButton:disabled {{ background-color: #555555; color: #aaaaaa; }}
        """)
        
        if hasattr(self, '_last_results') and self._last_results:
            self.update_translation(self._last_results)

    def _init_workers(self):
        self.thread = QThread()
        self.worker = TranslatorWorker()
        self.worker.moveToThread(self.thread)
        self.request_translation_signal.connect(self.worker.do_work)
        self.worker.finished_signal.connect(self.update_translation)
        self.thread.start()

    def _init_hotkeys(self):
        self.hwnd = int(self.winId())
        if not ctypes.windll.user32.RegisterHotKey(self.hwnd, HOTKEY_ID_Q, MOD_ALT, VK_Q):
            logger.warning("无法注册 Alt+Q，可能被占用！")
        if not ctypes.windll.user32.RegisterHotKey(self.hwnd, HOTKEY_ID_Z, MOD_ALT, VK_Z):
            logger.warning("无法注册 Alt+Z，可能被占用！")
        if not ctypes.windll.user32.AddClipboardFormatListener(self.hwnd):
            logger.warning("无法注册剪贴板监听！")

    def setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setToolTip("✨ ManboShot")
        
        icon_file = ICON_PATH / "icon.ico"
        if icon_file.exists():
            self.tray_icon.setIcon(QIcon(str(icon_file)))
        else:
            self.tray_icon.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        
        self.tray_menu = QMenu()
        show_action = QAction("显示主界面 (Alt+Q)", self)
        show_action.triggered.connect(self.handle_show_window)
        snip_action = QAction("截图翻译 (Alt+Z)", self)
        snip_action.triggered.connect(self.start_snipping)
        settings_action = QAction("⚙️ 设置", self)
        settings_action.triggered.connect(self.show_settings)
        
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(QApplication.instance().quit)

        self.tray_menu.addAction(show_action)
        self.tray_menu.addAction(snip_action)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(settings_action)
        self.tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.show()

    def show_settings(self):
        dialog = SettingsWindow(self)
        if dialog.exec():
            # 保存并重启 worker 的客户端
            self.worker.reload_client()
            self.apply_theme()

    def handle_ocr_started(self):
        # OCR刚开始时：立即唤醒主界面，显示提取中提示
        self.input_edit.blockSignals(True)
        self.input_edit.setText("🖼️ 正在提取图片文字, 请稍候...")
        self.input_edit.blockSignals(False)
        
        card_bg = self.html_vars.get("card_bg", "rgba(0,0,0,0.15)")
        placeholder = self.html_vars.get("placeholder", "#888888")
        html = f"<div style='background-color: {card_bg}; padding: 10px; border-radius: 8px;'><div style='color: {placeholder}; font-style: italic;'>⚡ 图像 OCR 识别中...</div></div>"
        
        self.result_label.setText(html)
        self.result_label.show()
        self.play_btn.hide()
        
        # 强制缩小窗口，解决遗留的过大弹窗问题
        self.resize(1, 1)
        self.adjustSize()
        self.handle_show_window()

    def handle_ocr_result(self, text):
        logger.info("OCR完成，触发翻译")
        if not text or not text.strip():
            self.input_edit.blockSignals(True)
            self.input_edit.setText("⚠️ 未在截图区域识别到任何文字。")
            self.input_edit.blockSignals(False)
            
            card_bg = self.html_vars.get("card_bg", "rgba(0,0,0,0.15)")
            placeholder = self.html_vars.get("placeholder", "#888888")
            html = f"<div style='background-color: {card_bg}; padding: 10px; border-radius: 8px;'><div style='color: {placeholder}; font-style: italic;'>请重新截图尝试。</div></div>"
            self.result_label.setText(html)
            self.adjustSize()
            return
            
        self.handle_clipboard_update(text, popup=True, ignore_move=True)

    def start_snipping(self):
        if not HAS_OCR: return
        self.hide()
        QTimer.singleShot(200, self.snipper.start_capture)

    def on_input_changed(self):
        text = self.input_edit.toPlainText().strip()
        if text and text != getattr(self, '_last_translated_text', ''):
            self._last_translated_text = text
            self.current_text_for_speech = text
            
            # 发起新查询前：清空旧的巨长翻译结果并收缩窗口
            self.result_label.hide()
            self.play_btn.hide()
            self.resize(1, 1)
            self.adjustSize()
            
            self.request_translation_signal.emit(text)

    def handle_clipboard_update(self, text, popup=True, ignore_move=False):
        if not text: return
        
        self.input_edit.blockSignals(True)
        self.input_edit.setText(text)
        self.input_edit.blockSignals(False)
        self.current_text_for_speech = text
        self._last_translated_text = text
        
        # 发起新查询前：清空旧的巨长翻译结果并收缩窗口
        self.result_label.hide()
        self.play_btn.hide()
        self.resize(1, 1)
        self.adjustSize()
        
        self.request_translation_signal.emit(text)
        if popup:
            self.handle_show_window(ignore_move=ignore_move)

    def handle_show_window(self, ignore_move=False):
        self._clipboard_suppress_until = time.time() + 0.8
        
        if not ignore_move or not self.isVisible():
            pos = QCursor.pos()
            
            # 获取鼠标当前所在的屏幕 (解决多屏幕弹窗强制飞回主屏幕的问题)
            from PySide6.QtGui import QGuiApplication
            screen = QGuiApplication.screenAt(pos)
            if not screen:
                screen = QApplication.primaryScreen()
            screen_geometry = screen.availableGeometry()
            
            # 将窗口放置在鼠标右下角
            win_x = pos.x() + 15
            win_y = pos.y() + 15
            
            # 边界防溢出保护 (根据当前所在屏幕的边界计算)
            if win_x + self.width() > screen_geometry.right():
                win_x = screen_geometry.right() - self.width() - 15
            if win_y + self.height() > screen_geometry.bottom():
                win_y = screen_geometry.bottom() - self.height() - 15
                
            if not self.isVisible():
                self.setWindowOpacity(0.0)
                self.move(win_x, win_y)
                self.show()
                self.fade_anim.start()
            else:
                # 如果窗口已经可见，直接移动，不播放淡入动画 (防止闪烁)
                self.move(win_x, win_y)
                self.show()
        else:
            self.show()
            
        QTimer.singleShot(50, self.nuke_activate_window)

    def nuke_activate_window(self):
        if not self.isVisible(): 
            return 
        self._clipboard_suppress_until = time.time() + 0.5
        hwnd = int(self.winId())
        force_focus_window(hwnd)

    @Slot(dict)
    def update_translation(self, results):
        self._last_results = results
        
        doubao = results.get("doubao", "")
        google = results.get("google", "")
        phonetic = results.get("phonetic", "")
        
        doubao_loading = results.get("doubao_loading", False)
        google_loading = results.get("google_loading", False)
        ai_enabled = results.get("ai_enabled", True)
        
        # 结果面板渲染为内嵌风格卡片
        card_bg = self.html_vars.get("card_bg")
        placeholder = self.html_vars.get('placeholder')
        html = f"<div style='background-color: {card_bg}; padding: 10px; border-radius: 8px;'>"
        
        # --- 豆包模块 (始终显示) ---
        if phonetic:
            pb = self.html_vars.get('phonetic_bg')
            pt = self.html_vars.get('phonetic_text')
            html += f"<div style='margin-bottom: 8px;'><span style='color:{pt}; font-size:12px; background-color: {pb}; padding: 2px 6px; border-radius: 4px;'>{phonetic}</span></div>"
        
        ai_title_color = self.html_vars.get('ai_title')
        html += f"<div style='color:{ai_title_color}; font-weight:bold; font-size:12px; margin-bottom: 6px;'>✨ 豆包 AI</div>"
        
        if not ai_enabled:
            html += f"<div style='margin-bottom: 12px; color: {placeholder}; font-style: italic;'>暂未配置 API Key</div>"
        elif doubao_loading and not doubao:
            html += f"<div style='margin-bottom: 12px; color: {placeholder}; font-style: italic;'>AI 思考中...</div>"
        else:
            html += f"<div style='margin-bottom: 12px;'>{doubao}</div>"
            
        # --- 谷歌模块 (始终显示) ---
        divider = self.html_vars.get('divider')
        border_top = f"border-top: 1px solid {divider}; padding-top: 10px;"
        html += f"<div style='{border_top}'>"
        
        gg_title_color = self.html_vars.get('google_title')
        html += f"<div style='color:{gg_title_color}; font-weight:bold; font-size:12px; margin-bottom: 6px;'>🌐 谷歌翻译</div>"
        
        if google_loading and not google:
            html += f"<div style='color: {placeholder}; font-style: italic;'>请求中...</div></div>"
        else:
            html += f"<div>{google}</div></div>"
            
        html += "</div>"

        self.result_label.setText(html)
        self.result_label.show()
        self.play_btn.show()
        
        # 自适应扩展大小 (不再强制 resize(1,1)，避免 AI 流式输出时抽搐闪烁)
        self.adjustSize()

    def update_play_btn_status(self, text):
        if text == "reset":
            self.play_btn.setText("🔊 朗读原文")
            self.play_btn.setEnabled(True)
        else:
            self.play_btn.setText(text)

    def play_audio(self):
        if not self.current_text_for_speech: return
        self.play_btn.setEnabled(False)
        import threading
        threading.Thread(target=play_voice_worker, args=(self.current_text_for_speech, self.tts_status_signal), daemon=True).start()

    def _safe_get_clipboard(self):
        try:
            return pyperclip.paste()
        except Exception:
            return ""

    def nativeEvent(self, eventType, message):
        try:
            if eventType == b"windows_generic_MSG":
                msg = ctypes.wintypes.MSG.from_address(int(message))
                
                if msg.message == WM_HOTKEY:
                    if msg.wParam == HOTKEY_ID_Q:
                        self.handle_show_window()
                    elif msg.wParam == HOTKEY_ID_Z:
                        self.start_snipping()
                
                elif msg.message == WM_CLIPBOARDUPDATE:
                    # 🛡️ 守卫条件：
                    # 1. 如果窗口可见，且 (处于激活状态 OR 鼠标正悬停在窗口上)，忽略！(防止内部框选触发)
                    # 2. 如果正处于强制冷却期内，忽略！
                    is_under_mouse = self.frameGeometry().contains(QCursor.pos())
                    is_active = self.isActiveWindow() or self.hasFocus()
                    
                    if (self.isVisible() and (is_active or is_under_mouse)) or time.time() < self._clipboard_suppress_until:
                        pass
                    else:
                        QTimer.singleShot(50, self._process_clipboard)

        except Exception as e:
            logger.error(f"nativeEvent Error: {e}")
        return super().nativeEvent(eventType, message)

    def _process_clipboard(self):
        text = self._safe_get_clipboard()
        if not text:
            return

        current_time = time.time()
        time_since_last = current_time - self.last_clipboard_time

        if time_since_last <= 0.15:
            # 防抖：忽略单一复制动作产生的多次连续系统事件 (如浏览器复制通常会发两次)
            return
        elif time_since_last <= 0.6 and text == self.last_clipboard_text:
            # 成功触发双击复制 (间隔 0.15 ~ 0.6秒，且内容一致)
            if not self.isVisible():
                # 只有在文本真正发生变化时才触发新的网络请求
                if text != getattr(self, '_last_translated_text', ''):
                    self.handle_clipboard_update(text, popup=True)
                else:
                    self.handle_show_window()
            else:
                # 如果已经可见，只刷新内容并移动到新鼠标位置
                if text != getattr(self, '_last_translated_text', ''):
                    self.handle_clipboard_update(text, popup=True)
                else:
                    self.handle_show_window()
                
            # 重置状态，防止快速按第三下时错误触发
            self.last_clipboard_time = 0
            self.last_clipboard_text = ""
        else:
            # 记录第一次复制的特征 (或者新的不同文本)
            # 只有当新文本与刚才翻译完保留在输入框的文本不一样时，才算作一次全新的双击计时
            if text != getattr(self, '_last_translated_text', ''):
                self.last_clipboard_time = current_time
                self.last_clipboard_text = text

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # 允许按住任意空白处拖拽
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.drag_pos:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.drag_pos = None

    def closeEvent(self, event):
        try:
            ctypes.windll.user32.UnregisterHotKey(self.hwnd, HOTKEY_ID_Q)
            ctypes.windll.user32.UnregisterHotKey(self.hwnd, HOTKEY_ID_Z)
            ctypes.windll.user32.RemoveClipboardFormatListener(self.hwnd)
        except Exception:
            pass

        if hasattr(self, 'thread'):
            self.thread.quit()
            self.thread.wait()
        super().closeEvent(event)
