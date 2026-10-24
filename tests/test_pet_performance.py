import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication

import core.config as app_config
from ui.desktop_pet import (
    PetSprite,
    SpriteArt,
    _scale_frame_animations,
    _scale_sprite_art,
)


def _ensure_qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _make_pixmap(width: int, height: int) -> QPixmap:
    image = QImage(width, height, QImage.Format_RGBA8888)
    image.fill(0xFF336699)
    return QPixmap.fromImage(image)


class ConfigCacheTests(unittest.TestCase):
    def setUp(self):
        app_config.invalidate_config_cache()

    def tearDown(self):
        app_config.invalidate_config_cache()

    def test_load_app_config_uses_memory_cache_until_file_changes(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            cfg_path = Path(tmp_dir) / "config.json"
            cfg_path.write_text(json.dumps({"THEME": "dark"}), encoding="utf-8")

            with patch.object(app_config, "CONFIG_FILE", cfg_path), \
                 patch.object(app_config, "USER_DATA_DIR", Path(tmp_dir)), \
                 patch("core.config.json.load", wraps=json.load) as mock_json_load:
                first = app_config.load_app_config()
                second = app_config.load_app_config()
                self.assertEqual(mock_json_load.call_count, 1)
                self.assertEqual(first["THEME"], "dark")
                self.assertEqual(second["THEME"], "dark")

                # Mutating the returned dict must not pollute the cached dict
                first["THEME"] = "mutated"
                self.assertEqual(app_config.load_app_config()["THEME"], "dark")
                self.assertEqual(mock_json_load.call_count, 1)

                # Saving updates the cache without requiring another disk read
                app_config.save_app_config({"THEME": "blueprint", "PET_SCALE": 120})
                updated = app_config.load_app_config()
                self.assertEqual(updated["THEME"], "blueprint")
                self.assertEqual(updated["PET_SCALE"], 120)
                self.assertEqual(mock_json_load.call_count, 1)


class PetSpritePerformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = _ensure_qapp()

    def test_scale_sprite_art_downscales_layers_and_pivots(self):
        raw_art = SpriteArt(
            base=_make_pixmap(1200, 1200),
            back_layers={"tail": _make_pixmap(1200, 1200)},
            front_layers={"paw": _make_pixmap(1200, 1200)},
            pivots={"tail": (600, 900), "paw": (300, 600)},
            blink=_make_pixmap(1200, 1200),
        )

        scaled = _scale_sprite_art(raw_art, 194)

        self.assertEqual(scaled.height, 194)
        self.assertEqual(scaled.width, 194)
        self.assertEqual(scaled.back_layers["tail"].height(), 194)
        self.assertEqual(scaled.front_layers["paw"].height(), 194)
        self.assertEqual(scaled.blink.height(), 194)
        self.assertAlmostEqual(scaled.pivots["tail"][0], 97.0, places=2)
        self.assertAlmostEqual(scaled.pivots["tail"][1], 145.5, places=2)

    def test_scale_frame_animations_rescales_frames_and_baseline(self):
        raw_animations = {
            "lick_paw": {
                "frames": [_make_pixmap(800, 1000), _make_pixmap(800, 1000)],
                "durations_ms": [90, 90],
                "loop": False,
                "reference_height": 1000,
                "baseline": 950,
                "idle_frame_indices": set(),
            }
        }

        scaled = _scale_frame_animations(raw_animations, user_scale=1.0, base_art_height=194)
        anim = scaled["lick_paw"]

        self.assertAlmostEqual(anim["reference_height"], 194.0)
        self.assertAlmostEqual(anim["baseline"], 950 * (194 / 1000), places=2)
        self.assertEqual(anim["frames"][0].height(), 194)
        self.assertEqual(anim["frames"][0].width(), round(800 * (194 / 1000)))

    def test_sprite_rebuilds_cached_art_when_user_scale_changes(self):
        sprite = PetSprite()
        raw_art = SpriteArt(
            base=_make_pixmap(1000, 1000),
            back_layers={},
            front_layers={},
            pivots={},
            blink=_make_pixmap(1000, 1000),
        )
        sprite.set_pet(raw_art, {"interval_ms": 90})
        self.assertEqual(sprite._art.height, PetSprite.BASE_ART_HEIGHT)

        sprite.set_user_scale(120)
        self.assertEqual(sprite._art.height, round(PetSprite.BASE_ART_HEIGHT * 1.2))
        self.assertEqual(sprite._source_art.height, 1000)

    def test_pause_and_hide_stop_animation_timer(self):
        sprite = PetSprite()
        self.assertTrue(sprite._timer.isActive())

        sprite.pause_animation()
        self.assertFalse(sprite._timer.isActive())

        # While paused, set_state or play_action must not restart the timer
        sprite.set_state("translating", {"interval_ms": 60})
        self.assertFalse(sprite._timer.isActive())
        sprite.play_action("jump")
        self.assertFalse(sprite._timer.isActive())

        sprite.resume_animation()
        self.assertTrue(sprite._timer.isActive())


if __name__ == "__main__":
    unittest.main()
