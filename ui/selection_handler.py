import re
import threading
from PySide6.QtCore import QObject, QTimer, Signal, Slot
from core.config import logger
from core.translator import (
    choose_google_translation_args,
    google_translate_candidates,
    google_translate_text,
)


def build_highlight_candidates(source_text: str, translated_candidates: list[str] | tuple[str, ...]) -> list[str]:
    """构建选词高亮的候选词列表，按完整度与长度从高到低排列。"""
    tiers: list[list[str]] = [[], [], []]
    seen: set[str] = set()

    def _add(tier_idx: int, item: str):
        if not item:
            return
        w = item.strip()
        if not w or w in seen:
            return
        # 过滤单个常见虚词/单字噪声，避免误高亮整句中的“的/是/在/a/I”
        if len(w) == 1 and w in {"的", "地", "得", "了", "着", "过", "是", "在", "和", "与", "或", "a", "A", "I"}:
            return
        seen.add(w)
        tiers[tier_idx].append(w)

    # Tier 0: 完整主译文、备选译文与词典同义词
    for raw in translated_candidates:
        if not raw:
            continue
        _add(0, raw)
        if len(raw) > 1 and not re.search(r"[一-鿿]", raw):
            clean_en = re.sub(
                r'^[.,\/#!$%\^&\*;:{}=\-_`~()?]+|[.,\/#!$%\^&\*;:{}=\-_`~()?]+$',
                "",
                raw.strip(),
            )
            _add(0, clean_en)

    # Tier 1: 原文词本身（应对 Pillow、pygame、API、JSON 等在译文中保留不翻译的专有名词）
    if source_text:
        clean_src = re.sub(
            r'^[.,\/#!$%\^&\*;:{}=\-_`~()?]+|[.,\/#!$%\^&\*;:{}=\-_`~()?]+$',
            "",
            source_text.strip(),
        )
        if len(clean_src) >= 2:
            _add(1, clean_src)
        for token in re.findall(r"[A-Za-z][A-Za-z0-9_+-]{1,}", source_text):
            _add(1, token)

    # Tier 2: 当长短语在 AI 与 Google 中措辞略有差异（如“源精灵工件” vs “源精灵图产物”）时，
    # 提取主译文中 2~6 字的连续中文前缀/核心子串作为降级高亮候选
    if translated_candidates:
        primary = (translated_candidates[0] or "").strip()
        for zh_chunk in re.findall(r"[一-鿿]{3,}", primary):
            # 优先尝试较长的前缀与后缀（例如“源精灵工件” -> “源精灵”、“精灵工件”）
            max_sub = min(len(zh_chunk) - 1, 5)
            for sub_len in range(max_sub, 1, -1):
                _add(2, zh_chunk[:sub_len])
                _add(2, zh_chunk[len(zh_chunk) - sub_len:])

    return tiers[0] + tiers[1] + tiers[2]


def highlight_html_with_candidates(html: str, candidates: list[str], span_style: str) -> tuple[str, bool]:
    """在 HTML 文本中查找首个能匹配的候选词并包裹高亮样式（不破坏 HTML 标签与属性）。"""
    if not html or not candidates:
        return html, False

    for word in candidates:
        if not word:
            continue
        try:
            escaped_word = re.escape(word)
            if not re.search(r"[一-鿿]", word):
                pattern = re.compile(rf"(?<!<)(?<!&)\b{escaped_word}\b(?!>)(?![^<>]*>)", re.IGNORECASE)
            else:
                pattern = re.compile(rf"(?<!<)(?<!&){escaped_word}(?!>)(?![^<>]*>)")

            new_html, count = pattern.subn(f'<span style="{span_style}">\\g<0></span>', html)
            if count > 0:
                return new_html, True
        except Exception as e:
            logger.error(f"正则高亮失败: {e}")

    return html, False


class SelectionTranslationHelper(QObject):
    translation_ready = Signal(int, str, object)

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

        # 先立即尝试用原文词本身做一次零延迟本地匹配（例如选中 Pillow / pygame 立即可高亮）
        self._apply_candidates_to_labels(selected_text, ())

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
            daemon=True,
        ).start()

    def reset_results(self):
        if hasattr(self.window, '_base_ai_html') and self.window._base_ai_html:
            self.window.ai_result_lbl.setText(self.window._base_ai_html)
        if hasattr(self.window, '_base_google_html') and self.window._base_google_html:
            self.window.google_result_lbl.setText(self.window._base_google_html)

    def _translate_selection(self, generation, selected_text):
        try:
            _, target = choose_google_translation_args(selected_text)
            candidates = list(google_translate_candidates(selected_text, target))

            # 多词英文短语：并发补充每个实词的译文候选，解决 AI 与 Google 对复合短语后半部分译法不同的问题
            en_tokens = [
                tok for tok in re.findall(r"[A-Za-z]{3,}", selected_text)
                if tok.lower() not in {"the", "and", "for", "with", "from", "into", "that", "this"}
            ]
            if 2 <= len(en_tokens) <= 4 and target == "zh-CN":
                for tok in en_tokens:
                    for sub_cand in google_translate_candidates(tok, target)[:3]:
                        if sub_cand not in candidates:
                            candidates.append(sub_cand)

            if not candidates:
                translated = google_translate_text(selected_text, target)
                if translated:
                    candidates.append(translated.strip())

            if not candidates:
                return

            self.translation_ready.emit(generation, selected_text, tuple(candidates))
        except Exception as e:
            logger.error(f"选择高亮翻译出错: {e}")

    def _span_style(self) -> str:
        bg_color = "rgba(255, 215, 0, 0.4)" if self.window.theme == "dark" else "rgba(26, 115, 232, 0.2)"
        text_color = "#ffffff" if self.window.theme == "dark" else "#1a73e8"
        return (
            f"background-color: {bg_color}; color: {text_color}; "
            "font-weight: bold; border-radius: 3px; padding: 1px 3px;"
        )

    def _apply_candidates_to_labels(self, source_text: str, translated_candidates: tuple[str, ...]):
        words_to_highlight = build_highlight_candidates(source_text, translated_candidates)
        span_style = self._span_style()

        for attr_base, attr_lbl in [('_base_ai_html', 'ai_result_lbl'), ('_base_google_html', 'google_result_lbl')]:
            if not hasattr(self.window, attr_base):
                continue
            html = getattr(self.window, attr_base)
            if not html:
                continue

            highlighted_html, highlighted = highlight_html_with_candidates(
                html, words_to_highlight, span_style
            )
            getattr(self.window, attr_lbl).setText(highlighted_html if highlighted else html)

    @Slot(int, str, object)
    def _apply_translation_result(self, generation, source_text, target_candidates):
        if generation != self._selection_generation:
            return

        current_selection = self.window.input_edit.textCursor().selectedText().strip()
        if current_selection != source_text:
            return

        if isinstance(target_candidates, str):
            candidates_tuple = (target_candidates,)
        else:
            candidates_tuple = tuple(target_candidates or ())

        self._translation_cache[source_text] = candidates_tuple
        if len(self._translation_cache) > 64:
            self._translation_cache.pop(next(iter(self._translation_cache)))

        self._apply_candidates_to_labels(source_text, candidates_tuple)
