import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv
import certifi

# 设置证书
os.environ['SSL_CERT_FILE'] = certifi.where()

# --- 路径管理 ---
if getattr(sys, 'frozen', False):
    # 打包后环境
    APP_DIR = Path(sys.executable).parent.parent
    ICON_PATH = Path(sys._MEIPASS) if hasattr(sys, "_MEIPASS") else APP_DIR
else:
    # 开发环境
    APP_DIR = Path(__file__).parent.parent
    ICON_PATH = APP_DIR

ENV_PATH = APP_DIR / '.env'
load_dotenv(ENV_PATH)

# --- 工具路径 ---
if getattr(sys, 'frozen', False):
    # PyInstaller 解压后的临时目录(_MEIPASS)或单文件夹模式下的根目录
    TOOL_DIR = APP_DIR / "mpv"
else:
    # 兼容原逻辑，开发模式下的硬编码可以改写为相对路径或根据配置
    TOOL_DIR = Path(r"D:\ManboShot\mpv")

MPV_EXE = TOOL_DIR / "mpv.exe"
PIPER_DIR = TOOL_DIR  # 假设 piper 在同一个外部工具目录
PIPER_EXE = PIPER_DIR / "piper.exe"
PIPER_MODEL = PIPER_DIR / "zh_CN-huayan-medium.onnx"

import json

# --- 配置管理 (支持动态设置) ---
CONFIG_FILE = APP_DIR / "config.json"

def load_app_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
    # 兼容环境变量作为初始回退
    return {
        "DOUBAO_API_KEY": os.getenv("DOUBAO_API_KEY", ""),
        "DOUBAO_MODEL_EP": os.getenv("DOUBAO_MODEL_EP", "")
    }

def save_app_config(data):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"保存配置文件失败: {e}")

HYBRID_THRESHOLD = 30  # 语音合成阈值

# --- 日志配置 ---
LOG_FILE = APP_DIR / "manboshot_error.log"

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

setup_logging()
logger = logging.getLogger("ManboShot")
