import os
import sys
import time
import ctypes
import html as html_utils
import pyperclip
import re
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton,
                               QFrame, QSystemTrayIcon, QMenu, QStyle, QApplication, QGraphicsDropShadowEffect)
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QThread, QPropertyAnimation, QEasingCurve, QEvent
from PySide6.QtGui import QCursor, QAction, QIcon, QColor
from ui.settings_window import SettingsWindow
from ui.ui_main_window import Ui_FloatingWindow, apply_window_theme

from core.config import ICON_PATH, logger, load_app_config
from core.tts_engine import play_voice_worker, stop_tts_playback
from core.translator import TranslatorWorker
from ui.snipping_widget import SnippingWidget
from core.ocr_engine import HAS_OCR
from utils.win_api import (WM_HOTKEY, WM_CLIPBOARDUPDATE, HOTKEY_ID_SHOW, HOTKEY_ID_SNIP,
                           force_focus_window, parse_hotkey_string)

class FloatingWindow(QWidget, Ui_FloatingWindow):
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
        self.is_playing_tts = False

        self.setup_tray()
        self.tts_status_signal.connect(self.update_play_btn_status)

        if HAS_OCR:
            self.snipper = SnippingWidget()
            self.snipper.ocr_finished_signal.connect(self.handle_ocr_result)
            self.snipper.ocr_started_signal.connect(self.handle_ocr_started)

        self.setupUi(self)
        self.apply_theme()
        self._init_workers()
        self._init_hotkeys()

        # 移除之前的实时监控，改为安装事件过滤器监听 Enter 键
        self.input_edit.installEventFilter(self)
        
        from ui.selection_handler import SelectionTranslationHelper
        self.selection_helper = SelectionTranslationHelper(self)
        self.input_edit.selectionChanged.connect(self.selection_helper.handle_selection_changed)

    def eventFilter(self, obj, event):
        if obj == self.input_edit and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
                # 检查是否同时按下了 Shift (如果有 Shift 则是换行，不触发翻译)
                if not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                    self.on_translate_clicked()
                    return True # 拦截事件，防止输入换行符
        return super().eventFilter(obj, event)

    def on_translate_clicked(self):
        text = self.input_edit.toPlainText().strip()
        if text:
            # 🛡️ 核心优化：发起新查询前主动打断当前正在朗读的音频，防止旧音频重叠播放！
            stop_tts_playback()
            
            self._last_translated_text = text
            self.current_text_for_speech = text
            
            # 发起新查询前：清空旧的巨长翻译结果并收缩窗口
            self.hide_results()
            self._update_window_width(text)
            self.adjustSize()
            
            self.request_translation_signal.emit(text)

    def _update_window_width(self, text=""):
        if not text:
            text = getattr(self, 'current_text_for_speech', '') or ''
        char_count = sum(2 if '\u4e00' <= c <= '\u9fff' else 1 for c in text)
        # 动态宽度：单个字最窄 340，长句最大 800
        target_width = max(340, min(800, 340 + int(char_count * 8)))
        self.setFixedWidth(target_width)
        return target_width

    def hide_results(self):
        self.main_scroll.hide()
        self.main_scroll.setMinimumHeight(0)
        self.main_scroll.setMaximumHeight(16777215)
        self.play_btn.hide()

    def show_results(self):
        self.main_scroll.show()
        ai_enabled = getattr(self, '_last_results', {}).get("ai_enabled", True)
        self.ai_title_lbl.setVisible(ai_enabled)
        self.ai_result_lbl.setVisible(ai_enabled)
        self.google_title_lbl.show()
        self.google_result_lbl.show()

    def apply_theme(self):
        config = load_app_config()
        self.theme = config.get("THEME", "dark")
        apply_window_theme(self, self.theme)
        
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
        
        # 先注销旧热键，以支持在运行时热重载
        try:
            ctypes.windll.user32.UnregisterHotKey(self.hwnd, HOTKEY_ID_SHOW)
            ctypes.windll.user32.UnregisterHotKey(self.hwnd, HOTKEY_ID_SNIP)
        except Exception:
            pass
            
        config = load_app_config()
        show_str = config.get("HOTKEY_SHOW", "Alt+Q")
        snip_str = config.get("HOTKEY_SNIP", "Alt+E")
        
        mod_show, vk_show = parse_hotkey_string(show_str)
        mod_snip, vk_snip = parse_hotkey_string(snip_str)
        
        if vk_show:
            if not ctypes.windll.user32.RegisterHotKey(self.hwnd, HOTKEY_ID_SHOW, mod_show, vk_show):
                logger.warning(f"无法注册唤醒热键 {show_str}，可能被占用！")
        else:
            logger.warning(f"唤醒热键 {show_str} 解析失败！")
            
        if vk_snip:
            if not ctypes.windll.user32.RegisterHotKey(self.hwnd, HOTKEY_ID_SNIP, mod_snip, vk_snip):
                logger.warning(f"无法注册截图热键 {snip_str}，可能被占用！")
        else:
            logger.warning(f"截图热键 {snip_str} 解析失败！")
            
        if not getattr(self, '_clipboard_listener_registered', False):
            if ctypes.windll.user32.AddClipboardFormatListener(self.hwnd):
                self._clipboard_listener_registered = True
            else:
                logger.warning("无法注册剪贴板监听！")
                
        # 联动更新 Placeholder 提示文案
        self.input_edit.setPlaceholderText(f"在此输入 / 双击 Ctrl+C 划词 / {snip_str} 截图 / {show_str} 唤起...")

    def setup_tray(self):
        from ui.tray_icon import ManboShotTrayIcon
        self.tray_icon = ManboShotTrayIcon(self)

    def show_settings(self):
        dialog = SettingsWindow(self)
        if dialog.exec():
            # 保存并重启 worker 的客户端
            self.worker.reload_client()
            self._init_hotkeys()  # 重新初始化热键与 Placeholder
            self.tray_icon.setup_menu()  # 重新加载托盘菜单文案
            self.apply_theme()

    def handle_ocr_started(self):
        # OCR刚开始时：立即唤醒主界面，显示提取中提示
        self.input_edit.blockSignals(True)
        self.input_edit.setText("🖼️ 正在提取图片文字, 请稍候...")
        self.input_edit.blockSignals(False)
        
        placeholder = self.html_vars.get("placeholder", "#888888")
        html = f"<div style='color: {placeholder}; font-style: italic;'>⚡ 图像 OCR 识别中...</div>"
        
        self.ai_result_lbl.setText(html)
        self.ai_title_lbl.show()
        self.ai_result_lbl.show()
        self.google_title_lbl.hide()
        self.google_result_lbl.hide()
        self.main_scroll.show()
        self.play_btn.hide()
        
        # 强制缩小窗口，解决遗留的过大弹窗问题
        self._update_window_width("🖼️ 正在提取图片文字, 请稍候...")
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
            self.ai_result_lbl.setText(html)
            self.ai_title_lbl.show()
            self.ai_result_lbl.show()
            self.google_title_lbl.hide()
            self.google_result_lbl.hide()
            self.main_scroll.show()
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
            self.hide_results()
            self._update_window_width(text)
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
        self.hide_results()
        self._update_window_width(text)
        self.adjustSize()
        
        self.request_translation_signal.emit(text)
        if popup:
            self.handle_show_window(ignore_move=ignore_move)

    def handle_show_window(self, ignore_move=False, reset=False):
        self._clipboard_suppress_until = time.time() + 0.8
        
        # 动态根据当前所在屏幕可用高度，适配滚动区域的最大高度
        from PySide6.QtGui import QGuiApplication
        pos = QCursor.pos()
        screen = QGuiApplication.screenAt(pos)
        if not screen:
            screen = QGuiApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        max_scroll_height = max(300, min(800, int(screen_geometry.height() * 0.8)))
        self.main_scroll.setMaximumHeight(max_scroll_height)
        
        # 强制清空内容，恢复初始状态
        if reset:
            self.input_edit.blockSignals(True)
            self.input_edit.clear()
            self.input_edit.blockSignals(False)
            self.current_text_for_speech = ""
            self._last_translated_text = ""
            self.hide_results()
            self._update_window_width("")
            self.layout().activate()
            self.resize(1, 1)
            self.adjustSize()

        def apply_position_and_show():
            was_visible = self.isVisible()
            
            # 核心修复：如果窗口是隐藏状态，强制先以全透明模式 show() 出来，
            # 这样 Qt 的布局系统才能正确激活，后续的 adjustSize() 才能准确计算出缩小后的真实高度。
            if not was_visible:
                self.setWindowOpacity(0.0)
                self.show()

            if reset:
                self.resize(1, 1)
                self.adjustSize()

            if not ignore_move or not was_visible:
                # 修复"位置会变"问题：使用函数刚被调用瞬间获取的鼠标位置，而不是延迟后的位置
                current_pos = pos
                
                # 获取鼠标当前所在的屏幕 (解决多屏幕弹窗强制飞回主屏幕的问题)
                from PySide6.QtGui import QGuiApplication
                screen = QGuiApplication.screenAt(current_pos)
                if not screen:
                    from PySide6.QtWidgets import QApplication
                    screen = QApplication.primaryScreen()
                screen_geometry = screen.availableGeometry()
                
                # 将窗口放置在鼠标右下角
                win_x = current_pos.x() + 15
                win_y = current_pos.y() + 15
                
                # 边界防溢出保护 (根据当前所在屏幕的边界计算)
                if win_x + self.width() > screen_geometry.right():
                    win_x = screen_geometry.right() - self.width() - 15
                if win_y + self.height() > screen_geometry.bottom():
                    win_y = screen_geometry.bottom() - self.height() - 15
                    
                self.move(win_x, win_y)
                
                if not was_visible:
                    self.fade_anim.start()
            else:
                self.show()
                
            QTimer.singleShot(50, self.nuke_activate_window)

        # 移除 10ms 延迟，直接执行，防止鼠标移动导致位置偏移
        apply_position_and_show()

    def nuke_activate_window(self):
        if not self.isVisible(): 
            return 
        self._clipboard_suppress_until = time.time() + 0.5
        hwnd = int(self.winId())
        force_focus_window(hwnd)

    @Slot(dict)
    def update_translation(self, results):
        if not getattr(self, 'current_text_for_speech', ''):
            return
            
        self._last_results = results
        
        doubao_raw = results.get("doubao", "") or ""
        doubao_escaped = html_utils.escape(doubao_raw)
        doubao_escaped = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', doubao_escaped)
        doubao = doubao_escaped.replace("\n", "<br>")
        google = html_utils.escape(results.get("google", "") or "").replace("\n", "<br>")
        phonetic = html_utils.escape(results.get("phonetic", "") or "")
        
        doubao_loading = results.get("doubao_loading", False)
        google_loading = results.get("google_loading", False)
        ai_enabled = results.get("ai_enabled", True)
        
        # 智能动态音标：如果输入的是中文，没有生成音标，但翻译结果是简短的英文，提取英文的音标
        if not phonetic:
            try:
                import eng_to_ipa as ipa
                eng_result = doubao if (doubao and not doubao_loading) else google
                # 如果有结果，且结果比较短，且没有中文字符，就试着转音标
                if eng_result and len(eng_result) < 30 and not re.search(r'[\u4e00-\u9fff]', eng_result):
                    # 🛡️ 核心优化：去除首尾的常见标点符号以大幅提高 eng_to_ipa 转换成功率 (例如将 "Hello!" 转换为 "Hello" 再查音标)
                    clean_eng = re.sub(r'[.,\/#!$%\^&\*;:{}=\-_`~()?]+$', '', eng_result.strip())
                    clean_eng = re.sub(r'^[.,\/#!$%\^&\*;:{}=\-_`~()?]+', '', clean_eng)
                    ph = ipa.convert(clean_eng.lower().strip())
                    if "*" not in ph and ph:
                        phonetic = f"/{ph}/"
            except Exception:
                pass

        placeholder = self.html_vars.get('placeholder')
        
        # AI 结果分立卡片渲染
        if not ai_enabled:
            self.ai_title_lbl.hide()
            self.ai_result_lbl.hide()
            self._base_ai_html = ""
        else:
            self.ai_title_lbl.show()
            self.ai_result_lbl.show()
            
            ai_html = ""
            if phonetic:
                pb = self.html_vars.get('phonetic_bg', 'rgba(255,255,255,0.1)')
                pt = self.html_vars.get('phonetic_text', '#aaaaaa')
                ai_html += f"<div style='margin-bottom: 8px;'><span style='color:{pt}; font-size:12px; background-color: {pb}; padding: 2px 6px; border-radius: 4px;'>{phonetic}</span></div>"
            
            if doubao_loading and not doubao:
                ai_html += f"<div style='color: {placeholder}; font-style: italic;'>AI 思考中...</div>"
            else:
                ai_html += f"<div>{doubao}</div>"
            
            self.ai_result_lbl.setText(ai_html)
            self._base_ai_html = ai_html

        # Google 结果分立卡片渲染
        self.google_title_lbl.show()
        self.google_result_lbl.show()
        self.main_scroll.show()
        
        gg_html = ""
        if google_loading and not google:
            gg_html += f"<div style='color: {placeholder}; font-style: italic;'>请求中...</div>"
        else:
            gg_html += f"<div>{google}</div>"
            
        self.google_result_lbl.setText(gg_html)
        self._base_google_html = gg_html
        
        self.play_btn.show()
        
        # 动态根据当前所在屏幕可用高度，适配滚动区域的最大高度
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.screenAt(self.pos())
        if not screen:
            screen = QGuiApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        max_scroll_height = max(300, min(800, int(screen_geometry.height() * 0.8)))
        
        # 1. 设置自适应宽度
        self._update_window_width(getattr(self, 'current_text_for_speech', ''))

        # 2. 🛡️ 核心优化：强制立即激活布局并自适应调整子控件大小
        # 必须在宽度设置后，让内部 Label 按照新宽度重新折行计算高度
        self.layout().activate()
        
        # 由于合并成了一个 main_scroll，需要让 scroll_layout 也强制刷新
        vp_width = self.main_scroll.viewport().width() if self.main_scroll.isVisible() else 300
        self.ai_result_lbl.setMinimumWidth(vp_width - 20)
        self.google_result_lbl.setMinimumWidth(vp_width - 20)
        
        self.ai_result_lbl.adjustSize()
        self.google_result_lbl.adjustSize()
        
        self.scroll_layout.activate()
        self.scroll_content.adjustSize()
        
        # 预留 15px 呼吸边距防止文字裁剪，并限制在屏幕比例的最大允许高度内
        content_height = self.scroll_content.sizeHint().height() + 15
        
        self.main_scroll.setFixedHeight(min(max_scroll_height, content_height))
        
        # 自适应扩展大小 (不再强制 resize(1,1)，避免 AI 流式输出时抽搐闪烁)
        self.adjustSize()
        # 加入微小延迟的自适应，确保富文本高度计算完成后能正确撑开窗口，防止按钮遮挡底部文字
        QTimer.singleShot(10, self.adjustSize)
        QTimer.singleShot(20, self._ensure_visible_on_screen)
        QTimer.singleShot(50, self.update)

    def _ensure_visible_on_screen(self):
        """翻译结果撑开窗口后，检查是否溢出屏幕底端或右端，如果溢出则自动上移/左移"""
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.screenAt(self.pos())
        if not screen:
            screen = QGuiApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()

        current_x = self.x()
        current_y = self.y()
        win_width = self.width()
        win_height = self.height()

        new_x = current_x
        new_y = current_y

        # 防溢出：如果窗口底部超出屏幕底部，自动向上推
        if current_y + win_height > screen_geometry.bottom():
            new_y = screen_geometry.bottom() - win_height - 15
            
        # 防溢出：如果窗口右侧超出屏幕右侧，自动向左推
        if current_x + win_width > screen_geometry.right():
            new_x = screen_geometry.right() - win_width - 15
            
        # 兜底保护：不能超出屏幕左上角
        if new_x < screen_geometry.left():
            new_x = screen_geometry.left() + 15
        if new_y < screen_geometry.top():
            new_y = screen_geometry.top() + 15

        if new_x != current_x or new_y != current_y:
            self.move(new_x, new_y)

    def update_play_btn_status(self, text):
        if text == "reset":
            self.play_btn.setText("🔊 朗读原文")
            self.play_btn.setEnabled(True)
            self.is_playing_tts = False
        else:
            # 播放中按钮文本提示打断操作，并保持 Enabled=True 允许点击打断
            self.play_btn.setText(f"⏹️ 停止播放 ({text})")
            self.play_btn.setEnabled(True)
            self.is_playing_tts = True

    def play_audio(self):
        if getattr(self, "is_playing_tts", False):
            # 🛡️ 核心优化：若当前正在播放，点击按钮触发打断并停止朗读
            stop_tts_playback()
            return

        if not self.current_text_for_speech: return
        self.play_btn.setEnabled(False)
        self.is_playing_tts = True
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
                    if msg.wParam == HOTKEY_ID_SHOW:
                        self.handle_show_window(reset=True)
                    elif msg.wParam == HOTKEY_ID_SNIP:
                        self.start_snipping()
                
                elif msg.message == WM_CLIPBOARDUPDATE:
                    # 🛡️ 守卫条件：
                    # 1. 如果窗口可见，且 (处于激活状态 OR 鼠标正悬停在窗口上)，忽略！(防止内部框选触发)
                    # 2. 如果正处于强制冷却期内，忽略！
                    is_under_mouse = self.underMouse()
                    if not is_under_mouse:
                        # 兼容多屏幕 DPI 的全局坐标检测
                        pos = QCursor.pos()
                        global_top_left = self.mapToGlobal(self.rect().topLeft())
                        global_bottom_right = self.mapToGlobal(self.rect().bottomRight())
                        if global_top_left.x() <= pos.x() <= global_bottom_right.x() and global_top_left.y() <= pos.y() <= global_bottom_right.y():
                            is_under_mouse = True

                    is_active = self.isActiveWindow() or self.hasFocus() or self.input_edit.hasFocus()
                    from PySide6.QtWidgets import QApplication
                    if QApplication.activeWindow() == self:
                        is_active = True
                    
                    if (self.isVisible() and (is_active or is_under_mouse)) or time.time() < self._clipboard_suppress_until:
                        pass
                    else:
                        # 记录事件发生瞬间的 Ctrl 键物理状态 (0x11 = VK_CONTROL)
                        self._ctrl_pressed_during_copy = bool(ctypes.windll.user32.GetAsyncKeyState(0x11) & 0x8000)
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


        # ⬇️ 双击唤醒逻辑
        if time_since_last <= 0.6 and text == self.last_clipboard_text:
            # 🛡️ 终极防御：防御第三方划词软件 (如词典) 拦截鼠标双击并偷偷恢复剪贴板造成的幽灵弹窗！
            # 如果是人类真实的双击 Ctrl+C，此时 Ctrl 键必定是按下的。如果没按，说明是后台脚本作祟，当作噪音直接忽略！
            if not getattr(self, '_ctrl_pressed_during_copy', False):
                self.last_clipboard_time = current_time
                return

            # 成功触发双击复制 (间隔 0.15 ~ 0.6秒，且内容一致)
            if text != getattr(self, '_last_translated_text', ''):
                # 文本是新的，触发网络翻译请求
                self.handle_clipboard_update(text, popup=True)
            else:
                # 文本和上次一模一样，不再请求网络，只把窗口叫出来并移动到鼠标位置
                self.handle_show_window()
                
            # 重置状态，防止快速按第三下时错误触发
            self.last_clipboard_time = 0
            self.last_clipboard_text = ""
        else:
            # 记录第一次复制的特征 (用于判定下一次是否是双击)
            # 注意：不再限制 text != _last_translated_text，允许用户对着刚才的文本重新双击呼出窗口
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
            ctypes.windll.user32.UnregisterHotKey(self.hwnd, HOTKEY_ID_SHOW)
            ctypes.windll.user32.UnregisterHotKey(self.hwnd, HOTKEY_ID_SNIP)
            ctypes.windll.user32.RemoveClipboardFormatListener(self.hwnd)
        except Exception:
            pass

        if hasattr(self, 'thread'):
            if hasattr(self, 'worker'):
                self.worker.stop()
            self.thread.quit()
            self.thread.wait()
        super().closeEvent(event)


