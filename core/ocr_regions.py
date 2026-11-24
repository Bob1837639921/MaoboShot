from dataclasses import dataclass
from math import ceil, floor


OCR_PADDING = 20


@dataclass(frozen=True)
class OcrRegion:
    text: str
    bounds: tuple[int, int, int, int]


def screenshot_regions(result, width, height):
    regions = []
    for item in result:
        if not item or len(item) < 2:
            continue
        box, text = item[:2]
        if isinstance(text, (tuple, list)):
            text = text[0] if text else ""
        if not isinstance(text, str) or not text.strip():
            continue
        try:
            xs, ys = zip(*box)
            left = max(0, floor(min(xs)) - OCR_PADDING)
            top = max(0, floor(min(ys)) - OCR_PADDING)
            right = min(width, ceil(max(xs)) - OCR_PADDING)
            bottom = min(height, ceil(max(ys)) - OCR_PADDING)
        except (TypeError, ValueError, OverflowError):
            continue
        if left < right and top < bottom:
            regions.append(OcrRegion(text.strip(), (left, top, right - left, bottom - top)))
    return tuple(sorted(regions, key=lambda region: (region.bounds[1], region.bounds[0])))
