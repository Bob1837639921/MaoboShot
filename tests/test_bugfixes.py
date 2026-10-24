import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import core.config as app_config
import core.tts_engine as tts_engine
import utils.win_api as win_api
from core.translator import safe_google_translate


class PygameStopPlaybackTests(unittest.TestCase):
    def test_stop_tts_playback_interrupts_active_pygame_loop(self):
        fake_music = MagicMock()
        busy_calls = 0

        def get_busy():
            nonlocal busy_calls
            busy_calls += 1
            if busy_calls == 2:
                tts_engine.stop_tts_playback()
            return busy_calls <= 5

        fake_music.get_busy.side_effect = get_busy
        fake_pygame = SimpleNamespace(
            mixer=SimpleNamespace(
                init=Mock(),
                quit=Mock(),
                music=fake_music,
            )
        )

        generation = tts_engine._begin_playback()
        with patch.dict("sys.modules", {"pygame": fake_pygame}):
            with patch("core.tts_engine.time.sleep"):
                tts_engine._play_audio_file("sample.mp3", generation=generation)

        fake_music.stop.assert_called_once_with()
        fake_music.unload.assert_called_once_with()
        fake_pygame.mixer.quit.assert_called_once_with()

    def test_stale_generation_skips_pygame_playback_before_init(self):
        fake_pygame = SimpleNamespace(
            mixer=SimpleNamespace(
                init=Mock(),
                quit=Mock(),
                music=MagicMock(),
            )
        )
        generation = tts_engine._begin_playback()
        tts_engine.stop_tts_playback()

        with patch.dict("sys.modules", {"pygame": fake_pygame}):
            tts_engine._play_audio_file("sample.mp3", generation=generation)

        fake_pygame.mixer.init.assert_not_called()

    def test_status_sender_emits_reset_for_interrupted_latest_worker_only(self):
        first_signal = Mock()
        second_signal = Mock()

        first_gen = tts_engine._begin_playback()
        first_send = tts_engine._make_status_sender(first_signal, first_gen)
        tts_engine.stop_tts_playback()

        first_send("▶️ 开始朗读...")
        first_signal.emit.assert_not_called()

        first_send("reset")
        first_signal.emit.assert_called_once_with("reset")

        first_signal.reset_mock()
        second_gen = tts_engine._begin_playback()
        second_send = tts_engine._make_status_sender(second_signal, second_gen)

        first_send("reset")
        first_signal.emit.assert_not_called()

        second_send("reset")
        second_signal.emit.assert_called_once_with("reset")


class GoogleTranslateErrorPropagationTests(unittest.TestCase):
    @patch(
        "core.translator.google_translate_text",
        side_effect=RuntimeError("Google 翻译网络连接失败，请稍后重试"),
    )
    def test_safe_google_translate_raises_when_all_translatable_groups_fail(self, _mock_translate):
        with self.assertRaises(RuntimeError) as ctx:
            safe_google_translate("Hello world", source="auto", target="zh-CN")

        self.assertIn("网络连接失败", str(ctx.exception))

    @patch("core.translator.google_translate_text")
    def test_safe_google_translate_keeps_partial_result_when_some_groups_succeed(
        self, mock_translate
    ):
        mock_translate.side_effect = [
            "你好",
            RuntimeError("temporary failure"),
        ]
        source = "Hello\n已有中文段落\nWorld"
        result = safe_google_translate(source, source="auto", target="zh-CN")

        self.assertEqual(result, "你好\n已有中文段落\nWorld")


class SingleInstanceMutexTests(unittest.TestCase):
    def setUp(self):
        win_api._instance_mutex_handle = None

    def tearDown(self):
        win_api._instance_mutex_handle = None

    def test_acquire_returns_false_and_closes_handle_when_already_running(self):
        with patch.object(win_api.kernel32, "CreateMutexW", return_value=42) as create_mutex, \
             patch.object(win_api.kernel32, "GetLastError", return_value=win_api.ERROR_ALREADY_EXISTS), \
             patch.object(win_api.kernel32, "CloseHandle") as close_handle:
            acquired = win_api.acquire_single_instance_mutex("Local\\TestMutex")

        self.assertFalse(acquired)
        create_mutex.assert_called_once_with(None, False, "Local\\TestMutex")
        close_handle.assert_called_once_with(42)
        self.assertIsNone(win_api._instance_mutex_handle)

    def test_acquire_and_release_manage_mutex_handle(self):
        with patch.object(win_api.kernel32, "CreateMutexW", return_value=99), \
             patch.object(win_api.kernel32, "GetLastError", return_value=0), \
             patch.object(win_api.kernel32, "CloseHandle") as close_handle:
            self.assertTrue(win_api.acquire_single_instance_mutex("Local\\TestMutex"))
            self.assertEqual(win_api._instance_mutex_handle, 99)

            win_api.release_single_instance_mutex()
            close_handle.assert_called_once_with(99)
            self.assertIsNone(win_api._instance_mutex_handle)


class AtomicConfigSaveTests(unittest.TestCase):
    def test_save_app_config_writes_atomically_and_leaves_no_temp_files(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            cfg_path = Path(tmp_dir) / "config.json"
            with patch.object(app_config, "CONFIG_FILE", cfg_path), \
                 patch.object(app_config, "USER_DATA_DIR", Path(tmp_dir)):
                app_config.save_app_config({"DOUBAO_API_KEY": "sk-test", "PET_SCALE": 110})

                saved = json.loads(cfg_path.read_text(encoding="utf-8"))
                self.assertEqual(saved["DOUBAO_API_KEY"], "sk-test")
                self.assertEqual(saved["PET_SCALE"], 110)
                self.assertEqual(list(Path(tmp_dir).glob("*.tmp")), [])

    def test_save_app_config_preserves_existing_file_when_dump_fails(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            cfg_path = Path(tmp_dir) / "config.json"
            original = {"DOUBAO_API_KEY": "keep-me", "THEME": "dark"}
            cfg_path.write_text(json.dumps(original), encoding="utf-8")

            with patch.object(app_config, "CONFIG_FILE", cfg_path), \
                 patch.object(app_config, "USER_DATA_DIR", Path(tmp_dir)), \
                 patch("core.config.json.dump", side_effect=OSError("disk full")):
                app_config.save_app_config({"DOUBAO_API_KEY": "lost"})

            preserved = json.loads(cfg_path.read_text(encoding="utf-8"))
            self.assertEqual(preserved, original)
            self.assertEqual(list(Path(tmp_dir).glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
