import re
import threading
from PySide6.QtCore import QObject, QTimer, Signal, Slot
from core.config import logger
from core.translator import (
    choose_google_translation_args,
    google_translate_candidates,
    google_translate_text,
)

# 仅在提取“长句降级单字”时过滤高频结构虚字；若主译文本身就是单字（如 and -> “和”），则允许正常匹配
_NOISE_SINGLE_CHARS = {"的", "地", "得", "了", "着", "过", "a", "A", "I"}


def build_highlight_candidates(
    source_text: str,
    translated_candidates: list[str] | tuple[str, ...],
) -> list[str]:
    """构建选词高亮的候选词列表，按完整度与长度从高到低排列。"""
    tiers: list[list[str]] = [[], [], []]
    seen: set[str] = set()

    src_words = re.findall(r"[A-Za-z0-9_+-]+", source_text or "")
    is_single_word_selection = len(src_words) <= 1 and len((source_text or "").strip()) <= 24

    def _add(tier_idx: int, item: str, allow_single_zh: bool = False):
        if not item:
            return
        w = item.strip()
        if not w or w in seen:
            return
        if len(w) == 1:
            if w in _NOISE_SINGLE_CHARS:
                return
            if not allow_single_zh and w in {"是", "在", "和", "与", "或", "有", "把", "被"}:
                return
        seen.add(w)
        tiers[tier_idx].append(w)

    # Tier 0: 完整主译文、备选译文与词典同义词
    for idx, raw in enumerate(translated_candidates):
        if not raw:
            continue
        _add(0, raw, allow_single_zh=(idx == 0 or is_single_word_selection))
        if len(raw) > 1 and not re.search(r"[一-鿿]", raw):
            clean_en = re.sub(
                r'^[.,\/#!$%\^&\*;:{}=\-_`~()?]+|[.,\/#!$%\^&\*;:{}=\-_`~()?]+$',
                "",
                raw.strip(),
            )
            _add(0, clean_en, allow_single_zh=False)

    # Tier 1: 原文词本身
    if source_text:
        clean_src = re.sub(
            r'^[.,\/#!$%\^&\*;:{}=\-_`~()?]+|[.,\/#!$%\^&\*;:{}=\-_`~()?]+$',
            "",
            source_text.strip(),
        )
        if len(clean_src) >= 2:
            _add(1, clean_src)

    # Tier 2: 提取主译文中 2~6 字的连续中文前缀/核心子串作为降级高亮候选
    if translated_candidates:
        primary = (translated_candidates[0] or "").strip()
        for zh_chunk in re.findall(r"[一-鿿]{3,}", primary):
            max_sub = min(len(zh_chunk) - 1, 6)
            for sub_len in range(max_sub, 1, -1):
                _add(2, zh_chunk[:sub_len])
                _add(2, zh_chunk[len(zh_chunk) - sub_len:])

    return tiers[0] + tiers[1] + tiers[2]


def _common_prefix_len(a: str, b: str) -> int:
    limit = min(len(a), len(b))
    i = 0
    while i < limit and a[i] == b[i]:
        i += 1
    return i


def _common_suffix_len(a: str, b: str) -> int:
    limit = min(len(a), len(b))
    i = 0
    while i < limit and a[len(a) - 1 - i] == b[len(b) - 1 - i]:
        i += 1
    return i


def infer_aligned_target_span(
    selected_phrase: str,
    primary_candidates: list[str] | tuple[str, ...],
    google_text: str,
    target_text: str,
) -> str | None:
    """利用 Google 译文中的命中区间作为上下文锚点，反推 AI 译文中对应位置的完整词组。

    例如：
    - Google: "修剪未使用的 Pillow、pygame 和源精灵工件"
    - AI:     "清理未使用的 Pillow、pygame 和源精灵素材文件"
    - 当选中 "prune"（Google 命中 "修剪"），紧邻后缀锚点是 "未使用的"，从而在 AI 中精准定位出 "清理"；
    - 当选中 "source sprite artifacts"（Google 命中 "源精灵工件"），紧邻前缀锚点是 "和"，从而在 AI 中精准定位出 "源精灵素材文件"。
    """
    if not google_text or not target_text:
        return None

    gg_line = google_text.strip()
    tg_line = target_text.strip()
    if not gg_line or not tg_line or gg_line == tg_line:
        return None

    # 1. 在 Google 整句译文中找到当前选区对应的区间 [g_start, g_end)
    search_terms = list(primary_candidates or [])
    if selected_phrase and selected_phrase.strip() not in search_terms:
        search_terms.append(selected_phrase.strip())

    g_start = -1
    g_end = -1
    for term in search_terms:
        if not term:
            continue
        idx = gg_line.find(term)
        if idx != -1:
            g_start = idx
            g_end = idx + len(term)
            break

    if g_start == -1:
        return None

    g_prefix = gg_line[:g_start]
    g_suffix = gg_line[g_end:]

    # 2. 在 target_text 中对齐左边界 t_start
    if not g_prefix:
        t_start = 0
    else:
        t_start = -1
        # 从紧邻 g_start 左侧取最长公共后缀（最多 10 个字符，至少 1 个字符）在 target_text 中定位
        for anchor_len in range(min(len(g_prefix), 10), 0, -1):
            anchor = g_prefix[-anchor_len:]
            pos = tg_line.find(anchor)
            if pos != -1:
                t_start = pos + len(anchor)
                break
        if t_start == -1:
            return None

    # 3. 在 target_text 中对齐右边界 t_end
    if not g_suffix:
        t_end = len(tg_line)
    else:
        t_end = -1
        for anchor_len in range(min(len(g_suffix), 10), 0, -1):
            anchor = g_suffix[:anchor_len]
            pos = tg_line.find(anchor, t_start)
            if pos != -1:
                t_end = pos
                break
        if t_end == -1:
            return None

    if t_end <= t_start:
        return None

    span = tg_line[t_start:t_end].strip()
    # 防止锚点过短导致误框选整句
    max_reasonable_len = max(len(gg_line[g_start:g_end]) * 3, 12)
    if not span or len(span) > max_reasonable_len:
        return None

    return span


def _highlight_single_term(html: str, word: str, span_style: str) -> tuple[str, int]:
    escaped_word = re.escape(word)
    if not re.search(r"[一-鿿]", word):
        pattern = re.compile(rf"(?<!<)(?<!&)\b{escaped_word}\b(?!>)(?![^<>]*>)", re.IGNORECASE)
    else:
        pattern = re.compile(rf"(?<!<)(?<!&){escaped_word}(?!>)(?![^<>]*>)")
    return pattern.subn(f'<span style="{span_style}">\\g<0></span>', html)


def highlight_html_with_candidates(
    html: str,
    candidates: list[str],
    span_style: str,
    allow_multi_match: bool = False,
) -> tuple[str, bool]:
    """在 HTML 文本中查找候选词并包裹高亮样式（不破坏 HTML 标签与属性）。"""
    if not html or not candidates:
        return html, False

    if not allow_multi_match:
        for word in candidates:
            if not word:
                continue
            try:
                new_html, count = _highlight_single_term(html, word, span_style)
                if count > 0:
                    return new_html, True
            except Exception as e:
                logger.error(f"正则高亮失败: {e}")
        return html, False

    working_html = html
    any_hit = False
    matched_substrings: list[str] = []

    for idx, word in enumerate(candidates):
        if not word:
            continue
        if any(word in prev or prev in word for prev in matched_substrings):
            continue
        try:
            new_html, count = _highlight_single_term(working_html, word, span_style)
            if count > 0:
                working_html = new_html
                any_hit = True
                matched_substrings.append(word)
                if idx == 0:
                    return working_html, True
        except Exception as e:
            logger.error(f"正则高亮失败: {e}")

    return (working_html if any_hit else html), any_hit


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

    def _is_full_input_selected(self, selected_text: str) -> bool:
        full_text = self.window.input_edit.toPlainText().strip()
        if not full_text or not selected_text:
            return False
        norm_sel = " ".join(selected_text.split())
        norm_full = " ".join(full_text.split())
        return norm_sel == norm_full

    def handle_selection_changed(self):
        self._selection_generation += 1
        self._debounce_timer.stop()

        if not getattr(self.window, '_last_results', None):
            self._pending_selection = ""
            return

        selected_text = self.window.input_edit.textCursor().selectedText().replace(" ", "\n").strip()

        if not selected_text:
            self._pending_selection = ""
            self.reset_results()
            return

        if self._is_full_input_selected(selected_text):
            self._pending_selection = ""
            self._highlight_entire_results()
            return

        if len(selected_text) > 100:
            self._pending_selection = ""
            self.reset_results()
            return

        if len(re.findall(r"[A-Za-z0-9_+-]+", selected_text)) == 1:
            self._apply_candidates_to_labels(selected_text, ())

        self._pending_selection = selected_text
        self._debounce_timer.start()

    def _highlight_entire_results(self):
        span_style = self._span_style()
        results = getattr(self.window, "_last_results", {}) or {}
        for key, attr_base, attr_lbl in [
            ("doubao", "_base_ai_html", "ai_result_lbl"),
            ("google", "_base_google_html", "google_result_lbl"),
        ]:
            raw = (results.get(key, "") or "").strip()
            html = getattr(self.window, attr_base, "")
            if not raw or not html or raw.startswith("❌"):
                continue
            first_line = raw.splitlines()[0].strip()
            highlighted_html, hit = highlight_html_with_candidates(html, [first_line], span_style)
            getattr(self.window, attr_lbl).setText(highlighted_html if hit else html)

    def _start_pending_translation(self):
        selected_text = self._pending_selection
        current_selection = self.window.input_edit.textCursor().selectedText().replace(" ", "\n").strip()
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

            en_tokens = [
                tok for tok in re.findall(r"[A-Za-z]{3,}", selected_text)
                if tok.lower() not in {"the", "and", "for", "with", "from", "into", "that", "this"}
            ]
            if 2 <= len(en_tokens) <= 5 and target == "zh-CN":
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
        base_candidates = build_highlight_candidates(source_text, translated_candidates)
        span_style = self._span_style()
        is_multi_word = len(re.findall(r"[A-Za-z0-9_+-]+", source_text or "")) >= 2

        results = getattr(self.window, "_last_results", {}) or {}
        google_raw = (results.get("google", "") or "").strip()
        ai_raw = (results.get("doubao", "") or "").strip()

        # 利用 Google 译文中的命中位置作为锚点，推断 AI 译文中对应位置的完整词组（如 "清理"、"源精灵素材文件"）
        aligned_ai_span = infer_aligned_target_span(
            source_text,
            base_candidates,
            google_raw,
            ai_raw,
        )

        for attr_base, attr_lbl, is_ai in [
            ('_base_ai_html', 'ai_result_lbl', True),
            ('_base_google_html', 'google_result_lbl', False),
        ]:
            if not hasattr(self.window, attr_base):
                continue
            html = getattr(self.window, attr_base)
            if not html:
                continue

            card_candidates = list(base_candidates)
            if is_ai and aligned_ai_span and aligned_ai_span not in card_candidates:
                card_candidates.insert(0, aligned_ai_span)

            highlighted_html, highlighted = highlight_html_with_candidates(
                html,
                card_candidates,
                span_style,
                allow_multi_match=is_multi_word,
            )
            getattr(self.window, attr_lbl).setText(highlighted_html if highlighted else html)

    @Slot(int, str, object)
    def _apply_translation_result(self, generation, source_text, target_candidates):
        if generation != self._selection_generation:
            return

        current_selection = self.window.input_edit.textCursor().selectedText().replace(" ", "\n").strip()
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
