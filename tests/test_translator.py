import unittest
from unittest.mock import Mock, patch

import requests

from core.translator import google_translate_text, safe_google_translate


class GoogleTranslatorTests(unittest.TestCase):
    def setUp(self):
        google_translate_text.cache_clear()

    def tearDown(self):
        google_translate_text.cache_clear()

    @staticmethod
    def _response(status_code, payload=None):
        response = Mock()
        response.status_code = status_code
        response.json.return_value = payload
        if status_code >= 400:
            response.raise_for_status.side_effect = requests.HTTPError(response=response)
        return response

    @patch("core.translator.requests.get")
    def test_rate_limited_endpoint_falls_back_to_next_google_client(self, get):
        get.side_effect = [
            self._response(429),
            self._response(200, [[["Imagegen 所见的 Astra", "Astra, as seen by Imagegen"]]]),
        ]

        translated = google_translate_text("Astra, as seen by Imagegen", "zh-CN")

        self.assertEqual(translated, "Imagegen 所见的 Astra")
        self.assertEqual(get.call_count, 2)
        self.assertEqual(get.call_args_list[0].kwargs["params"]["client"], "dict-chrome-ex")
        self.assertEqual(get.call_args_list[1].kwargs["params"]["client"], "at")

    @patch("core.translator.google_translate_text")
    def test_group_failure_is_not_reported_as_unchanged_translation(self, translate):
        translate.side_effect = RuntimeError("Google 翻译网络连接失败，请稍后重试")

        with self.assertRaisesRegex(RuntimeError, "网络连接失败"):
            safe_google_translate("Astra, as seen by Imagegen", "auto", "zh-CN")


if __name__ == "__main__":
    unittest.main()
