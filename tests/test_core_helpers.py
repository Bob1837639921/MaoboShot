import unittest
from types import SimpleNamespace

from core.translator import (
    choose_google_translation_args,
    normalize_google_source_text,
)
from ui.main_window import FloatingWindow
from ui.selection_handler import (
    build_highlight_candidates,
    highlight_html_with_candidates,
)
from ui.snipping_widget import SnippingWidget
from utils.win_api import parse_hotkey_string


class NormalizeGoogleSourceTextTests(unittest.TestCase):
    def test_splits_camel_case_and_pascal_case_identifiers(self):
        self.assertEqual(normalize_google_source_text("setStyleSheet"), "set style sheet")
        self.assertEqual(normalize_google_source_text("HTTPResponseCode"), "http response code")

    def test_splits_snake_case_kebab_case_and_digits(self):
        self.assertEqual(normalize_google_source_text("MAX_RETRY_COUNT_2"), "max retry count 2")
        self.assertEqual(normalize_google_source_text("user-profile-v2"), "user profile v 2")

    def test_preserves_normal_sentences_and_chinese_text(self):
        sentence = "Hello, world! This is a normal sentence."
        self.assertEqual(normalize_google_source_text(sentence), sentence)
        zh_text = "包含中文的 setStyleSheet 标识符"
        self.assertEqual(normalize_google_source_text(zh_text), zh_text)

    def test_choose_google_translation_args_detects_dominant_language(self):
        self.assertEqual(choose_google_translation_args("你好世界 hello"), ("auto", "en"))
        self.assertEqual(choose_google_translation_args("Hello world 你好"), ("auto", "zh-CN"))


class OcrRestoreLayoutTests(unittest.TestCase):
    @staticmethod
    def _box(x_min, y_min, x_max, y_max):
        return [
            [x_min, y_min],
            [x_max, y_min],
            [x_max, y_max],
            [x_min, y_max],
        ]

    def test_merges_segments_on_same_line_with_ascii_spacing(self):
        dummy = SimpleNamespace()
        ocr_result = [
            (self._box(90, 12, 160, 32), ("World", 0.98)),
            (self._box(10, 10, 80, 30), ("Hello", 0.99)),
        ]
        restored = SnippingWidget._restore_layout(dummy, ocr_result)
        self.assertEqual(restored, "Hello World")

    def test_joins_cjk_segments_without_extra_space_and_sorts_lines_top_to_bottom(self):
        dummy = SimpleNamespace()
        ocr_result = [
            (self._box(10, 60, 80, 82), "第二行"),
            (self._box(65, 10, 120, 30), "世界"),
            (self._box(10, 11, 60, 31), "你好"),
        ]
        restored = SnippingWidget._restore_layout(dummy, ocr_result)
        self.assertEqual(restored, "你好世界\n第二行")

    def test_handles_empty_or_malformed_ocr_items(self):
        dummy = SimpleNamespace()
        self.assertEqual(SnippingWidget._restore_layout(dummy, None), "")
        self.assertEqual(SnippingWidget._restore_layout(dummy, []), "")
        self.assertEqual(SnippingWidget._restore_layout(dummy, [None, (), ([], "")]), "")


class ParseHotkeyStringTests(unittest.TestCase):
    def test_parses_single_and_combined_modifiers_case_insensitively(self):
        # Alt (0x0001) + Q (0x51)
        self.assertEqual(parse_hotkey_string("Alt+Q"), (0x0001, 0x51))
        # Ctrl (0x0002) | Shift (0x0004) + F5 (0x74)
        self.assertEqual(parse_hotkey_string("ctrl + shift + f5"), (0x0006, 0x74))
        # Control alias (0x0002) | Win (0x0008) + 1 (0x31)
        self.assertEqual(parse_hotkey_string("Control+Win+1"), (0x000A, 0x31))

    def test_returns_zero_tuple_for_empty_string(self):
        self.assertEqual(parse_hotkey_string(""), (0, 0))
        self.assertEqual(parse_hotkey_string(None), (0, 0))


class SpeechTargetResolutionTests(unittest.TestCase):
    @staticmethod
    def _make_window(full_text: str, selected_text: str = ""):
        from unittest.mock import Mock

        cursor = SimpleNamespace(selectedText=lambda: selected_text)
        input_edit = SimpleNamespace(
            textCursor=lambda: cursor,
            toPlainText=lambda: full_text,
        )
        win = SimpleNamespace(
            input_edit=input_edit,
            play_btn=Mock(),
            current_text_for_speech="stale sentence",
            is_playing_tts=False,
        )
        win._resolve_speech_text = lambda: FloatingWindow._resolve_speech_text(win)
        win._idle_play_btn_label = lambda: FloatingWindow._idle_play_btn_label(win)
        return win

    def test_prefers_selected_word_over_full_input_and_updates_button_label(self):
        win = self._make_window("This is an extraordinary example.", "extraordinary")
        text, is_selection = FloatingWindow._resolve_speech_text(win)
        self.assertEqual((text, is_selection), ("extraordinary", True))

        FloatingWindow._sync_speech_controls(win)
        self.assertEqual(win.current_text_for_speech, "extraordinary")
        win.play_btn.setText.assert_called_once_with("朗读选中 · extraordinary")
        win.play_btn.setEnabled.assert_called_once_with(True)

    def test_uses_edited_input_text_immediately_without_retranslating(self):
        win = self._make_window("extraordinary", "")
        text, is_selection = FloatingWindow._resolve_speech_text(win)
        self.assertEqual((text, is_selection), ("extraordinary", False))

        FloatingWindow._sync_speech_controls(win)
        self.assertEqual(win.current_text_for_speech, "extraordinary")
        win.play_btn.setText.assert_called_once_with("朗读原文")
        win.play_btn.setEnabled.assert_called_once_with(True)


class SelectionHighlightMatchingTests(unittest.TestCase):
    def test_highlights_untranslated_proper_noun_like_pillow_in_both_cards(self):
        candidates = build_highlight_candidates("Pillow", ("枕头",))
        ai_html = "<div>清理未使用的 Pillow、pygame 和源精灵图产物</div>"
        gg_html = "<div>修剪未使用的 Pillow、pygame 和源精灵工件</div>"

        ai_out, ai_hit = highlight_html_with_candidates(ai_html, candidates, "hl")
        gg_out, gg_hit = highlight_html_with_candidates(gg_html, candidates, "hl")

        self.assertTrue(ai_hit)
        self.assertTrue(gg_hit)
        self.assertIn('<span style="hl">Pillow</span>', ai_out)
        self.assertIn('<span style="hl">Pillow</span>', gg_out)

    def test_highlights_dictionary_synonym_when_ai_and_google_wording_differ(self):
        # Google primary is "修剪", dictionary synonym includes "清理"
        candidates = build_highlight_candidates("prune", ("修剪", "清理", "精简"))
        ai_html = "<div>清理未使用的 Pillow、pygame 和源精灵图产物</div>"
        gg_html = "<div>修剪未使用的 Pillow、pygame 和源精灵工件</div>"

        ai_out, ai_hit = highlight_html_with_candidates(ai_html, candidates, "hl")
        gg_out, gg_hit = highlight_html_with_candidates(gg_html, candidates, "hl")

        self.assertTrue(ai_hit)
        self.assertTrue(gg_hit)
        self.assertIn('<span style="hl">清理</span>', ai_out)
        self.assertIn('<span style="hl">修剪</span>', gg_out)

    def test_highlights_phrase_prefix_when_compound_noun_differs_in_ai_translation(self):
        # Google translates "source sprite artifacts" -> "源精灵工件",
        # while AI translates it as "源精灵图产物".
        candidates = build_highlight_candidates(
            "source sprite artifacts",
            ("源精灵工件", "源精灵伪影"),
        )
        ai_html = "<div>清理未使用的 Pillow、pygame 和源精灵图产物</div>"
        gg_html = "<div>修剪未使用的 Pillow、pygame 和源精灵工件</div>"

        ai_out, ai_hit = highlight_html_with_candidates(ai_html, candidates, "hl")
        gg_out, gg_hit = highlight_html_with_candidates(gg_html, candidates, "hl")

        self.assertTrue(ai_hit)
        self.assertTrue(gg_hit)
        self.assertIn('<span style="hl">源精灵</span>图产物', ai_out)
        self.assertIn('<span style="hl">源精灵工件</span>', gg_out)


if __name__ == "__main__":
    unittest.main()
