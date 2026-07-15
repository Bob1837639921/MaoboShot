import unittest

from core.pet_state import resolve_translation_state


class PetTranslationStateTests(unittest.TestCase):
    def test_streaming_ai_is_translating(self):
        state = resolve_translation_state(
            {
                "doubao": "Partial result",
                "google": "",
                "doubao_loading": True,
                "google_loading": True,
                "ai_enabled": True,
            }
        )
        self.assertEqual(state.state, "translating")
        self.assertEqual(state.engine_label, "AI 流式输出")

    def test_both_engines_success(self):
        state = resolve_translation_state(
            {
                "doubao": "AI result",
                "google": "Google result",
                "doubao_loading": False,
                "google_loading": False,
                "ai_enabled": True,
            }
        )
        self.assertEqual(state.state, "success")
        self.assertEqual(state.result_text, "AI result")

    def test_google_fallback_is_partial_success(self):
        state = resolve_translation_state(
            {
                "doubao": "",
                "doubao_error": "Request timed out",
                "google": "Google result",
                "doubao_loading": False,
                "google_loading": False,
                "ai_enabled": True,
            }
        )
        self.assertEqual(state.state, "partial_error")
        self.assertEqual(state.result_text, "Google result")

    def test_all_engines_failed(self):
        state = resolve_translation_state(
            {
                "doubao": "",
                "doubao_error": "Request timed out",
                "google": "❌ 翻译出错",
                "doubao_loading": False,
                "google_loading": False,
                "ai_enabled": True,
            }
        )
        self.assertEqual(state.state, "error")


if __name__ == "__main__":
    unittest.main()
