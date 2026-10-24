import os
import sys
import logging
import json
import tempfile
import threading
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
DEFAULT_CONFIG = {
    "DOUBAO_API_KEY": os.getenv("DOUBAO_API_KEY", ""),
    "DOUBAO_MODEL_EP": os.getenv("DOUBAO_MODEL_EP", ""),
    "AI_BASE_URL": os.getenv("AI_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"),
    "THEME": "light",
    "USE_LOCAL_TTS": True,
    "AI_TTS_PROVIDER": "edge",
    "XIAOMI_TTS_API_KEY": os.getenv("XIAOMI_TTS_API_KEY", ""),
    "XIAOMI_TTS_BASE_URL": os.getenv("XIAOMI_TTS_BASE_URL", "https://token-plan-cn.xiaomimimo.com/v1"),
    "XIAOMI_TTS_MODEL": os.getenv("XIAOMI_TTS_MODEL", "mimo-v2.5-tts"),
    "XIAOMI_TTS_VOICE": os.getenv("XIAOMI_TTS_VOICE", "mimo_default"),
    "XIAOMI_TTS_STYLE": os.getenv("XIAOMI_TTS_STYLE", ""),
    "AUDIO_PLAYER": "pygame",
    "HOTKEY_SHOW": "Alt+Q",
    "HOTKEY_SNIP": "Alt+E",
    "PET_ENABLED": True,
    "PET_ID": "lihua",
    "PET_BUBBLE_ENABLED": True,
    "PET_SCALE": 100,
    "PET_POSITION": {}
}

_config_lock = threading.Lock()
_config_cache = None
_config_cache_key = None


def invalidate_config_cache():
    """清空内存中的配置缓存，下次调用 load_app_config 时重新读取磁盘。"""
    global _config_cache, _config_cache_key
    with _config_lock:
        _config_cache = None
        _config_cache_key = None


def load_app_config():
    global _config_cache, _config_cache_key
    with _config_lock:
        if CONFIG_FILE.exists():
            try:
                stat = CONFIG_FILE.stat()
                cache_key = (str(CONFIG_FILE), stat.st_mtime_ns, stat.st_size)
                if _config_cache is not None and _config_cache_key == cache_key:
                    return dict(_config_cache)
                with open(CONFIG_FILE, 'r', encoding='utf-8-sig') as f:
                    data = json.load(f)
                merged = dict(DEFAULT_CONFIG)
                merged.update(data)
                _config_cache = merged
                _config_cache_key = cache_key
                return dict(merged)
            except Exception as e:
                logger.error(f"加载配置文件失败: {e}")
        else:
            cache_key = (str(CONFIG_FILE), None, None)
            if _config_cache is not None and _config_cache_key == cache_key:
                return dict(_config_cache)
            merged = dict(DEFAULT_CONFIG)
            _config_cache = merged
            _config_cache_key = cache_key
            return dict(merged)
    # 兼容环境变量作为初始回退
    return dict(DEFAULT_CONFIG)


def save_app_config(data):
    global _config_cache, _config_cache_key
    tmp_path = None
    try:
        target_dir = CONFIG_FILE.parent
        target_dir.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=f"{CONFIG_FILE.stem}.",
            suffix=".tmp",
            dir=str(target_dir),
        )
        tmp_path = Path(tmp_name)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, CONFIG_FILE)
        with _config_lock:
            merged = dict(DEFAULT_CONFIG)
            merged.update(data)
            stat = CONFIG_FILE.stat()
            _config_cache = merged
            _config_cache_key = (str(CONFIG_FILE), stat.st_mtime_ns, stat.st_size)
    except Exception as e:
        logger.error(f"保存配置文件失败: {e}")
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass

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
