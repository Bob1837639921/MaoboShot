import sys
import os
from PySide6.QtWidgets import QApplication
from core.config import logger
from utils.win_api import elevate_privileges
from core.tts_engine import cleanup_tts_processes
from core.ocr_engine import warmup_ocr_background
from ui.main_window import FloatingWindow

def main():
    # 如果是开发环境 (非打包状态) 且没有指定 --admin 参数，或者指定了 --no-admin，则不强制提权，方便开发调试与终端日志输出
    if "--no-admin" not in sys.argv:
        if getattr(sys, 'frozen', False) or "--admin" in sys.argv:
            elevate_privileges()

    # 初始化应用
    app = QApplication(sys.argv)
    
    # 提前在后台静默预加载OCR引擎 (提升截图秒开体验)
    warmup_ocr_background()

    # 注册退出时的子进程清理回调 (防止孤儿进程/僵尸进程泄露)
    app.aboutToQuit.connect(cleanup_tts_processes)

    # 实例化并显示主窗口
    try:
        window = FloatingWindow()
        # window 默认是隐藏的，由热键触发或托盘点击触发
        logger.info("ManboShot 助手已启动，隐藏在系统托盘。使用 Alt+Q 唤醒。")
        sys.exit(app.exec())
    except Exception as e:
        logger.error(f"应用崩溃: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
