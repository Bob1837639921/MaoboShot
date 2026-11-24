import unittest

from core.ocr_regions import OcrRegion, screenshot_regions


class ScreenshotRegionTests(unittest.TestCase):
    def test_removes_padding_clips_to_image_and_keeps_text_with_coordinates(self):
        rows = [
            ([[48, 54], [82, 54], [82, 64], [48, 64]], "second", 0.99),
            ([[16, 18], [42, 18], [42, 39], [16, 39]], (" first ", 0.99)),
            ([[0, 0], [12, 0], [12, 8], [0, 8]], "outside", 0.99),
            ([], "invalid", 0.99),
        ]
        self.assertEqual(screenshot_regions(rows, 58, 40), (
            OcrRegion("first", (0, 0, 22, 19)),
            OcrRegion("second", (28, 34, 30, 6)),
        ))
