import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from core.config import _merge_config
from core.tts_engine import _play_custom_tts


class CustomTtsTests(unittest.TestCase):
    @patch("core.tts_engine._play_audio_file")
    @patch("core.tts_engine.requests.post")
    def test_speech_endpoint_sends_model_and_voice_and_plays_audio(self, post, play):
        audio = b"RIFF-test-audio"
        post.return_value = Mock(status_code=200, headers={"content-type": "audio/wav"}, content=audio)
        config = _merge_config({
            "TTS_BASE_URL": "https://example.com/v1/",
            "TTS_API_KEY": "",
            "TTS_MODEL": "speech-model",
            "TTS_VOICE": "custom-voice",
            "TTS_STYLE": "Read slowly.",
        })
        play.side_effect = lambda path, _: self.assertEqual(Path(path).read_bytes(), audio)

        _play_custom_tts("Tailscale", config, Mock())

        self.assertEqual(post.call_args.args[0], "https://example.com/v1/audio/speech")
        self.assertEqual(post.call_args.kwargs["json"], {
            "model": "speech-model",
            "input": "Tailscale",
            "voice": "custom-voice",
            "response_format": "wav",
            "instructions": "Read slowly.",
        })
        play.assert_called_once()
        self.assertFalse(Path(play.call_args.args[0]).exists())

    def test_selected_legacy_provider_keeps_chat_protocol(self):
        config = _merge_config({
            "AI_TTS_PROVIDER": "xiaomi",
            "XIAOMI_TTS_MODEL": "mimo-v2-tts",
            "XIAOMI_TTS_VOICE": "legacy-voice",
        })
        self.assertEqual(config["AI_TTS_PROVIDER"], "custom")
        self.assertEqual(config["TTS_API_FORMAT"], "chat")
        self.assertEqual(config["TTS_MODEL"], "mimo-v2.5-tts")
        self.assertEqual(config["TTS_VOICE"], "legacy-voice")
