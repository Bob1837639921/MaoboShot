import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.pet_pack import _load_pack


class PetPackTests(unittest.TestCase):
    def test_loads_valid_pack(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "sprite.png").write_bytes(b"placeholder")
            manifest = {
                "schema_version": 1,
                "id": "sample-pet",
                "name": "Sample Pet",
                "sprite": "sprite.png",
            }
            manifest_path = root / "pet.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            pack = _load_pack(manifest_path)

            self.assertIsNotNone(pack)
            self.assertEqual(pack.pet_id, "sample-pet")
            self.assertEqual(pack.name, "Sample Pet")

    def test_rejects_sprite_outside_pack(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            outside = root.parent / "outside.png"
            outside.write_bytes(b"placeholder")
            manifest_path = root / "pet.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "id": "unsafe",
                        "name": "Unsafe",
                        "sprite": "../outside.png",
                    }
                ),
                encoding="utf-8",
            )

            with patch("core.pet_pack.logger"):
                self.assertIsNone(_load_pack(manifest_path))
            outside.unlink(missing_ok=True)

    def test_resolves_animation_frames_inside_pack(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "sprite.png").write_bytes(b"placeholder")
            frames = root / "frames"
            frames.mkdir()
            (frames / "00.png").write_bytes(b"frame-0")
            (frames / "01.png").write_bytes(b"frame-1")
            manifest_path = root / "pet.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "id": "animated",
                        "name": "Animated",
                        "sprite": "sprite.png",
                        "animations": {
                            "lick_paw": {
                                "frames": ["frames/00.png", "frames/01.png"],
                                "durations_ms": [120, 180],
                                "reference_height": 198,
                                "baseline": 203,
                                "idle_frame_indices": [0, 1],
                                "loop": True,
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            animation = _load_pack(manifest_path).animation_for("lick_paw")

            self.assertEqual(animation["frames"], [frames / "00.png", frames / "01.png"])
            self.assertEqual(animation["durations_ms"], [120, 180])
            self.assertEqual(animation["reference_height"], 198)
            self.assertEqual(animation["baseline"], 203)
            self.assertEqual(animation["idle_frame_indices"], {0, 1})
            self.assertTrue(animation["loop"])

    def test_rejects_animation_frame_outside_pack(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "sprite.png").write_bytes(b"placeholder")
            outside = root.parent / "outside-frame.png"
            outside.write_bytes(b"placeholder")
            manifest_path = root / "pet.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "id": "animated",
                        "name": "Animated",
                        "sprite": "sprite.png",
                        "animations": {
                            "lick_paw": {
                                "frames": ["../outside-frame.png"],
                                "durations_ms": [120],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            self.assertIsNone(_load_pack(manifest_path).animation_for("lick_paw"))
            outside.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
