import tempfile
import unittest
from pathlib import Path

from build_exe import (
    EXCLUDED_MODULES,
    build_pyinstaller_args,
    prune_bundle,
)


class BuildConfigTests(unittest.TestCase):
    def test_build_args_exclude_unused_heavy_modules_and_drop_dead_hidden_imports(self):
        project_root = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = build_pyinstaller_args(
                project_root,
                root / "dist",
                root / "build",
                root / "spec",
            )

        self.assertNotIn("--hidden-import=deep_translator", args)
        for mod in (
            "sympy",
            "PySide6.QtQuick",
            "PySide6.QtQml",
            "PySide6.QtPdf",
            "PySide6.QtWebEngineCore",
        ):
            self.assertIn(f"--exclude-module={mod}", args)
            self.assertIn(mod, EXCLUDED_MODULES)

    def test_prune_bundle_removes_unused_qt_cv2_and_dict_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "ManboShot"
            internal = bundle / "_internal"

            qt_dir = internal / "PySide6"
            (qt_dir / "translations").mkdir(parents=True)
            (qt_dir / "translations" / "qt_zh_CN.qm").write_bytes(b"x" * 128)
            (qt_dir / "opengl32sw.dll").write_bytes(b"x" * 256)
            (qt_dir / "Qt6Quick.dll").write_bytes(b"x" * 256)
            (qt_dir / "Qt6Core.dll").write_bytes(b"k" * 64)

            cv2_dir = internal / "cv2"
            cv2_dir.mkdir(parents=True)
            (cv2_dir / "opencv_videoio_ffmpeg4130_64.dll").write_bytes(b"f" * 512)
            (cv2_dir / "cv2.pyd").write_bytes(b"c" * 64)

            ipa_res = internal / "eng_to_ipa" / "resources"
            ipa_res.mkdir(parents=True)
            (ipa_res / "CMU_dict.json").write_bytes(b"j" * 256)
            (ipa_res / "CMU_dict.db").write_bytes(b"d" * 64)

            freed = prune_bundle(bundle)

            self.assertEqual(freed, 128 + 256 + 256 + 512 + 256)
            self.assertFalse((qt_dir / "opengl32sw.dll").exists())
            self.assertFalse((qt_dir / "Qt6Quick.dll").exists())
            self.assertFalse((qt_dir / "translations").exists())
            self.assertFalse((cv2_dir / "opencv_videoio_ffmpeg4130_64.dll").exists())
            self.assertFalse((ipa_res / "CMU_dict.json").exists())

            # Required runtime files remain intact
            self.assertTrue((qt_dir / "Qt6Core.dll").exists())
            self.assertTrue((cv2_dir / "cv2.pyd").exists())
            self.assertTrue((ipa_res / "CMU_dict.db").exists())

    def test_requirements_separate_runtime_and_dev_dependencies(self):
        project_root = Path(__file__).resolve().parent.parent
        runtime_reqs = (project_root / "requirements.txt").read_text(encoding="utf-8")
        dev_reqs = (project_root / "requirements-dev.txt").read_text(encoding="utf-8")

        for unused in (
            "keyboard==",
            "pyttsx3==",
            "deep-translator==",
            "piper-tts==",
            "comtypes==",
            "pyinstaller==",
            "opencv-python==",
        ):
            self.assertNotIn(unused, runtime_reqs)

        self.assertIn("opencv-python-headless==", runtime_reqs)
        self.assertIn("-r requirements.txt", dev_reqs)
        self.assertIn("pyinstaller==", dev_reqs)


if __name__ == "__main__":
    unittest.main()
