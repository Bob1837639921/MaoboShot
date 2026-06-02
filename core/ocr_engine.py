import threading
import logging
from core.config import logger

HAS_OCR = False
_ocr_instance = None
_ocr_lock = threading.Lock()

try:
    from PIL import Image
    from rapidocr_onnxruntime import RapidOCR
    HAS_OCR = True
except ImportError:
    logger.warning("OCR 库未安装，截图功能不可用。")

def init_ocr_engine():
    """预加载/预热 OCR 引擎 (避免首次截图时卡顿)"""
    global _ocr_instance
    if not HAS_OCR:
        return None

    with _ocr_lock:
        if _ocr_instance is None:
            logger.info("Initializing OCR Engine (Warm-up)...")
            try:
                _ocr_instance = RapidOCR(
                    det_limit_side_len=2048,
                    det_box_thresh=0.3,
                    det_unclip_ratio=1.6
                )
                logger.info("OCR Engine initialized successfully with optimized parameters.")
            except Exception as e:
                logger.error(f"Failed to initialize OCR: {e}", exc_info=True)
                _ocr_instance = None
    return _ocr_instance

def get_ocr_engine():
    """获取单例 OCR 引擎"""
    global _ocr_instance
    if _ocr_instance is None:
        init_ocr_engine()
    return _ocr_instance

def warmup_ocr_background():
    """在后台线程静默预热OCR模型"""
    if HAS_OCR:
        t = threading.Thread(target=init_ocr_engine, daemon=True)
        t.start()
