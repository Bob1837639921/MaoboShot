import re
import threading
from PySide6.QtCore import QObject, QTimer, Signal, Slot
from core.config import logger
from core.translator import choose_google_translation_args, google_translate_text

class SelectionTranslationHelper(QObject):
    translation_ready = Signal(int, str, str)

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self._selection_generation = 0
        self._pending_selection = ""
        self._translation_cache = {}
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(180)
        self._debounce_timer.timeout.connect(self._start_pending_translation)
        self.translation_ready.connect(self._apply_translation_result)

    def handle_selection_changed(self):
        self._selection_generation += 1
        self._debounce_timer.stop()

        # 如果当前没有翻译结果，不做处理
        if not getattr(self.window, '_last_results', None):
            self._pending_selection = ""
            return
            
        selected_text = self.window.input_edit.textCursor().selectedText().strip()
        
        # 如果选中为空，恢复原始 HTML
        if not selected_text:
            self._pending_selection = ""
            self.reset_results()
            return
            
        # 限制长度，防止大段文本翻译导致延迟
        if len(selected_text) > 100:
            self._pending_selection = ""
            self.reset_results()
            return

        self._pending_selection = selected_text
        self._debounce_timer.start()

    def _start_pending_translation(self):
        selected_text = self._pending_selection
        current_selection = self.window.input_edit.textCursor().selectedText().strip()
        if not selected_text or current_selection != selected_text:
            return

        generation = self._selection_generation
        cached = self._translation_cache.get(selected_text)
        if cached:
            self._apply_translation_result(generation, selected_text, cached)
            return

        threading.Thread(
            target=self._translate_selection,
            args=(generation, selected_text),
            daemon=True
        ).start()

    def reset_results(self):
        if hasattr(self.window, '_base_ai_html') and self.window._base_ai_html:
            self.window.ai_result_lbl.setText(self.window._base_ai_html)
        if hasattr(self.window, '_base_google_html') and self.window._base_google_html:
            self.window.google_result_lbl.setText(self.window._base_google_html)

    def _translate_selection(self, generation, selected_text):
        try:
            # 检测被选中文字的语言，进行翻译
            _, target = choose_google_translation_args(selected_text)
            translated = google_translate_text(selected_text, target)
                
            if not translated:
                return
                
            self.translation_ready.emit(generation, selected_text, translated.strip())
        except Exception as e:
            logger.error(f"选择高亮翻译出错: {e}")

    @Slot(int, str, str)
    def _apply_translation_result(self, generation, source_text, target_text):
        if generation != self._selection_generation:
            return

        current_selection = self.window.input_edit.textCursor().selectedText().strip()
        if current_selection != source_text:
            return

        self._translation_cache[source_text] = target_text
        if len(self._translation_cache) > 64:
            self._translation_cache.pop(next(iter(self._translation_cache)))
            
        # 寻找匹配并高亮
        words_to_highlight = [target_text]
        if len(target_text) > 1 and not re.search(r'[\u4e00-\u9fff]', target_text):
            # 英文去除首尾标点符号，提高匹配率
            clean_word = re.sub(r'^[.,\/#!$%\^&\*;:{}=\-_`~()?]+|[.,\/#!$%\^&\*;:{}=\-_`~()?]+$', '', target_text)
            if clean_word and clean_word not in words_to_highlight:
                words_to_highlight.append(clean_word)
                
        # 分别高亮 AI 结果和谷歌结果
        for attr_base, attr_lbl in [('_base_ai_html', 'ai_result_lbl'), ('_base_google_html', 'google_result_lbl')]:
            if not hasattr(self.window, attr_base):
                continue
            html = getattr(self.window, attr_base)
            if not html:
                continue
                
            highlighted_html = html
            highlighted = False
            
            for word in words_to_highlight:
                if not word: continue
                bg_color = "rgba(255, 215, 0, 0.4)" if self.window.theme == "dark" else "rgba(26, 115, 232, 0.2)"
                text_color = "#ffffff" if self.window.theme == "dark" else "#1a73e8"
                span_style = f"background-color: {bg_color}; color: {text_color}; font-weight: bold; border-radius: 3px; padding: 1px 3px;"
                
                try:
                    escaped_word = re.escape(word)
                    # 使用正则避免匹配 HTML 标签内属性
                    if not re.search(r'[\u4e00-\u9fff]', word): # 英文使用单词边界
                        pattern = re.compile(rf'(?<!<)(?<!&)\b{escaped_word}\b(?!>)(?![^<>]*>)', re.IGNORECASE)
                        new_html, count = pattern.subn(f'<span style="{span_style}">\\g<0></span>', highlighted_html)
                    else: # 中文不使用单词边界
                        pattern_zh = re.compile(rf'(?<!<)(?<!&){escaped_word}(?!>)(?![^<>]*>)')
                        new_html, count = pattern_zh.subn(f'<span style="{span_style}">\\g<0></span>', highlighted_html)
                    
                    if count > 0:
                        highlighted_html = new_html
                        highlighted = True
                        break
                except Exception as e:
                    logger.error(f"正则高亮失败: {e}")
                    
            if highlighted:
                getattr(self.window, attr_lbl).setText(highlighted_html)
            else:
                getattr(self.window, attr_lbl).setText(html)
