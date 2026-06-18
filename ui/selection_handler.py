import re
import threading
from PySide6.QtCore import QObject, Qt, Slot, QMetaObject, Q_ARG
from deep_translator import GoogleTranslator
from core.config import logger
from core.translator import choose_google_translation_args

class SelectionTranslationHelper(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window

    def handle_selection_changed(self):
        # 如果当前没有翻译结果，不做处理
        if not getattr(self.window, '_last_results', None):
            return
            
        selected_text = self.window.input_edit.textCursor().selectedText().strip()
        
        # 如果选中为空，恢复原始 HTML
        if not selected_text:
            self.reset_results()
            return
            
        # 限制长度，防止大段文本翻译导致延迟
        if len(selected_text) > 100:
            return
            
        # 启动后台线程翻译选中的词/短语
        threading.Thread(target=self._translate_and_highlight_selection, args=(selected_text,), daemon=True).start()

    def reset_results(self):
        if hasattr(self.window, '_base_ai_html') and self.window._base_ai_html:
            self.window.ai_result_lbl.setText(self.window._base_ai_html)
        if hasattr(self.window, '_base_google_html') and self.window._base_google_html:
            self.window.google_result_lbl.setText(self.window._base_google_html)

    def _translate_and_highlight_selection(self, selected_text):
        try:
            # 检测被选中文字的语言，进行翻译
            source, target = choose_google_translation_args(selected_text)
            translated = GoogleTranslator(source=source, target=target).translate(selected_text)
                
            if not translated:
                return
                
            # 回到主线程更新 UI 高亮
            QMetaObject.invokeMethod(self, "_highlight_translated_text", 
                                   Qt.QueuedConnection, 
                                   Q_ARG(str, translated.strip()))
        except Exception as e:
            logger.error(f"选择高亮翻译出错: {e}")

    @Slot(str)
    def _highlight_translated_text(self, target_text):
        # 获取当前正在选中的文本，如果用户已经取消选择，则不进行高亮
        current_selection = self.window.input_edit.textCursor().selectedText().strip()
        if not current_selection:
            self.reset_results()
            return
            
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
