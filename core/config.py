import os
import sys
import logging
import json
from pathlib import Path
from dotenv import load_dotenv
import certifi

# 设置证书
os.environ['SSL_CERT_FILE'] = certifi.where()

# --- 路径管理 ---
if getattr(sys, 'frozen', False):
    # 打包后环境
    APP_DIR = Path(sys.executable).parent
    RESOURCE_DIR = Path(sys._MEIPASS) if hasattr(sys, "_MEIPASS") else APP_DIR
else:
    # 开发环境
    APP_DIR = Path(__file__).parent.parent
    RESOURCE_DIR = APP_DIR

ICON_PATH = RESOURCE_DIR

ENV_PATH = APP_DIR / '.env'
load_dotenv(ENV_PATH)

def _user_data_dir():
    base_dir = os.getenv("APPDATA") or os.getenv("LOCALAPPDATA")
    if base_dir:
        return Path(base_dir) / "MaoboShot"
    return APP_DIR / "user_data"

# --- 工具路径 ---
_tool_dir_override = os.getenv("MAOBOSHOT_TOOL_DIR")
if _tool_dir_override:
    TOOL_DIR = Path(_tool_dir_override)
elif (APP_DIR / "mpv").exists():
    TOOL_DIR = APP_DIR / "mpv"
else:
    TOOL_DIR = RESOURCE_DIR / "mpv"

MPV_EXE = TOOL_DIR / "mpv.exe"
PIPER_DIR = TOOL_DIR  # 假设 piper 在同一个外部工具目录
PIPER_EXE = PIPER_DIR / "piper.exe"
PIPER_MODEL = PIPER_DIR / "zh_CN-huayan-medium.onnx"

# --- 配置管理 (支持动态设置) ---
USER_DATA_DIR = _user_data_dir()
CONFIG_FILE = USER_DATA_DIR / "config.json"
LEGACY_CONFIG_FILE = APP_DIR / "config.json"
DEFAULT_CONFIG = {
    "DOUBAO_API_KEY": os.getenv("DOUBAO_API_KEY", ""),
    "DOUBAO_MODEL_EP": os.getenv("DOUBAO_MODEL_EP", ""),
    "THEME": "light",
    "USE_LOCAL_TTS": True
}

def load_app_config():
    config_path = CONFIG_FILE if CONFIG_FILE.exists() else LEGACY_CONFIG_FILE
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)
            merged = dict(DEFAULT_CONFIG)
            merged.update(data)
            return merged
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
    # 兼容环境变量作为初始回退
    return dict(DEFAULT_CONFIG)

def save_app_config(data):
    try:
        USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"保存配置文件失败: {e}")

HYBRID_THRESHOLD = 30  # 语音合成阈值

# --- 日志配置 ---
LOG_FILE = USER_DATA_DIR / "manboshot_error.log"

def setup_logging():
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
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
