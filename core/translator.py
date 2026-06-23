import re
import time
from concurrent.futures import ThreadPoolExecutor
from PySide6.QtCore import QObject, Signal, Slot
from openai import OpenAI
import requests
from bs4 import BeautifulSoup
from core.config import logger, load_app_config

try:
    import eng_to_ipa as ipa
    HAS_IPA = True
except ImportError:
    HAS_IPA = False

GOOGLE_TRANSLATE_API_URL = "https://translate.googleapis.com/translate_a/single"
GOOGLE_TRANSLATE_HTML_URLS = (
    "https://translate.google.com/m",
    "https://translate.google.com.hk/m",
)
GOOGLE_TRANSLATE_TIMEOUT = 8
GOOGLE_TRANSLATE_RETRIES = 2
GOOGLE_TRANSLATE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0 Safari/537.36"
    )
}

def phonetic_symbol(text: str):
    """提取音标"""
    if not text.strip() or len(text) > 50 or not HAS_IPA: return None
    try:
        clean_text = text.lower().strip()
        ph = ipa.convert(clean_text)
        if "*" in ph or not ph:
            return None
        return f"/{ph}/"
    except Exception as e:
        logger.error(f"音标转换错误: {e}")
        return None

def normalize_google_source_text(text: str) -> str:
    """Make code-style English identifiers readable for Google Translate."""
    source = text.strip()
    if not source or re.search(r'[\u4e00-\u9fff]', source):
        return text

    has_identifier_separator = bool(re.search(r'[_-]', source))
    has_camel_case = bool(re.search(r'[a-z][A-Z]|[A-Z]{2,}[a-z]', source))
    is_single_identifier = bool(re.fullmatch(r'[A-Za-z][A-Za-z0-9_$-]*', source))
    is_upper_identifier = bool(re.fullmatch(r'[A-Z][A-Z0-9_$-]{2,}', source))

    if not (has_identifier_separator or (is_single_identifier and (has_camel_case or is_upper_identifier))):
        return text

    normalized = source
    normalized = re.sub(r'[_-]+', ' ', normalized)
    normalized = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', normalized)
    normalized = re.sub(r'(?<=[A-Z])(?=[A-Z][a-z])', ' ', normalized)
    normalized = re.sub(r'(?<=[A-Za-z])(?=[0-9])|(?<=[0-9])(?=[A-Za-z])', ' ', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()

    return normalized.lower() if normalized else text

def google_translate_text(text: str, target: str) -> str:
    source_text = normalize_google_source_text(text) if target == 'zh-CN' else text
    last_error = None

    for _ in range(GOOGLE_TRANSLATE_RETRIES):
        try:
            response = requests.get(
                GOOGLE_TRANSLATE_API_URL,
                params={"client": "gtx", "sl": "auto", "tl": target, "dt": "t", "q": source_text},
                headers=GOOGLE_TRANSLATE_HEADERS,
                timeout=GOOGLE_TRANSLATE_TIMEOUT
            )
            response.raise_for_status()
            data = response.json()
            translated = "".join(part[0] for part in data[0] if part and part[0])
            if translated:
                return translated
            raise RuntimeError("Google 翻译结果为空")
        except requests.RequestException as e:
            last_error = e
            time.sleep(0.35)
        except Exception as e:
            last_error = e
            break

    for url in GOOGLE_TRANSLATE_HTML_URLS:
        for _ in range(GOOGLE_TRANSLATE_RETRIES):
            try:
                response = requests.get(
                    url,
                    params={"sl": "auto", "tl": target, "q": source_text},
                    headers=GOOGLE_TRANSLATE_HEADERS,
                    timeout=GOOGLE_TRANSLATE_TIMEOUT
                )
                response.raise_for_status()

                soup = BeautifulSoup(response.text, "html.parser")
                element = soup.find("div", {"class": "result-container"})
                if not element:
                    element = soup.find("div", {"class": "t0"})
                if not element:
                    raise RuntimeError("未找到 Google 翻译结果")

                translated = element.get_text(strip=True)
                if translated:
                    return translated
                raise RuntimeError("Google 翻译结果为空")
            except requests.RequestException as e:
                last_error = e
                time.sleep(0.35)
            except Exception as e:
                last_error = e
                break

    logger.error(f"Google 翻译请求失败: {last_error}")
    raise RuntimeError("Google 翻译网络连接失败，请稍后重试")

def choose_google_translation_args(text: str) -> tuple[str, str]:
    # 计算中文字符个数
    zh_count = len(re.findall(r'[\u4e00-\u9fff]', text))
    # 计算英文/外语单词个数（匹配由字母或常见西方变音字母组成的单词块）
    en_count = len(re.findall(r'[a-zA-Z\u00C0-\u017F]+', text))

    if zh_count > en_count:
        # 中文比例大，翻译为英文
        return 'auto', 'en'
    else:
        # 外文比例大或相等，或者是纯外文/无字字符，翻译为中文
        return 'auto', 'zh-CN'

def choose_translation_target(text: str) -> str:
    return choose_google_translation_args(text)[1]

def safe_google_translate(text: str, source: str, target: str) -> str:
    """安全地进行谷歌翻译，对混合文本合并同类项分块翻译，既解决长文本报错，又极大提升了翻译速度"""
    paragraphs = text.split('\n')
    
    # 1. 标记每个段落是否已经是目标语言，并计算其字数
    para_info = []
    for para in paragraphs:
        if not para.strip():
            para_info.append({"text": para, "is_target": True})
            continue
            
        zh_count = len(re.findall(r'[\u4e00-\u9fff]', para))
        en_count = len(re.findall(r'[a-zA-Z\u00C0-\u017F]+', para))
        
        is_target = False
        if target == 'zh-CN' and zh_count > en_count:
            is_target = True
        elif target == 'en' and en_count >= zh_count and en_count > 0:
            is_target = True
            
        para_info.append({"text": para, "is_target": is_target})
        
    # 2. 合并连续相同性质的段落（最大合并长度 4000 字符）
    groups = []
    current_group = []
    current_len = 0
    current_status = None
    
    for info in para_info:
        # 如果类型变了，或者当前组合计长度超过了 4000 字符，就打包当前组
        if (current_status is not None and info["is_target"] != current_status) or (current_len + len(info["text"]) + 1 > 4000):
            groups.append({"text": '\n'.join(current_group), "is_target": current_status})
            current_group = []
            current_len = 0
            
        current_status = info["is_target"]
        current_group.append(info["text"])
        current_len += len(info["text"]) + 1
        
    if current_group:
        groups.append({"text": '\n'.join(current_group), "is_target": current_status})
        
    # 3. 对各个组进行翻译
    translated_groups = []
    for g in groups:
        if g["is_target"] or not g["text"].strip():
            # 已经是目标语言或者是空行，保留原文
            translated_groups.append(g["text"])
        else:
            # 需要翻译的外语块（包含多个段落，仅进行 1 次网络请求）
            try:
                translated = google_translate_text(g["text"], target)
                translated_groups.append(translated if translated else g["text"])
            except Exception as e:
                logger.error(f"分组翻译失败: {e}")
                translated_groups.append(g["text"])
                
    return '\n'.join(translated_groups)

class TranslatorWorker(QObject):
    finished_signal = Signal(dict)
    error_signal = Signal(str)

    def __init__(self):
        super().__init__()
        self.executor = ThreadPoolExecutor(max_workers=4)
        self._current_task_id = 0
        self.reload_client()

    def reload_client(self):
        """重新加载或初始化大模型客户端"""
        config = load_app_config()
        api_key = config.get("DOUBAO_API_KEY", "").strip()
        self.model_ep = config.get("DOUBAO_MODEL_EP", "").strip()
        base_url = config.get("AI_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3").strip()
        if not base_url:
            base_url = "https://ark.cn-beijing.volces.com/api/v3"
        
        if api_key:
            self.db_client = OpenAI(
                api_key=api_key,
                base_url=base_url
            )
            logger.info("已加载 AI 大模型配置。")
        else:
            self.db_client = None
            logger.info("未配置 AI 大模型，开启纯 Google 翻译模式。")

    def stop(self):
        """停止后台翻译任务。"""
        self._current_task_id += 1
        self.executor.shutdown(wait=False, cancel_futures=True)

    @Slot(str)
    def do_work(self, text):
        self._current_task_id += 1
        task_id = self._current_task_id
        
        ai_enabled = bool(self.db_client)
        
        results = {
            "doubao": "", 
            "google": "", 
            "phonetic": phonetic_symbol(text),
            "ai_enabled": ai_enabled
        }
        google_source, google_target = choose_google_translation_args(text)

        def refresh_ui(loading_status=None):
            if self._current_task_id == task_id:
                out = dict(results)
                if loading_status:
                    out.update(loading_status)
                self.finished_signal.emit(out)

        # 🚀 任务 A: 豆包大模型
        def task_doubao():
            if not ai_enabled:
                refresh_ui({"doubao_loading": False})
                return
            
            system_prompt = "你是一个专业翻译。请将用户输入翻译为中文或英文，只输出译文本身，不要说多余的话。如果原文排版混乱、缺乏换行或全部粘连在一起（如PDF复制文本），请在翻译时根据语义进行合理的【分段和排版优化】，使其结构清晰、易读。"
            try:
                response = self.db_client.chat.completions.create(
                    model=self.model_ep,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": text}
                    ],
                    timeout=15,
                    stream=True
                )
                collected_messages = []
                last_ui_update = 0
                for chunk in response:
                    # 🛡️ 核心优化：检测当前任务是否已被废弃。如果已被新请求覆盖，立即切断网络流迭代，释放连接并优雅退出！
                    if self._current_task_id != task_id:
                        logger.info(f"Task {task_id} superseded by {self._current_task_id}. Breaking stream.")
                        break
                    
                    if chunk.choices and chunk.choices[0].delta.content:
                        collected_messages.append(chunk.choices[0].delta.content)
                        if self._current_task_id == task_id:
                            results["doubao"] = "".join(collected_messages)
                            
                            # 🛡️ 核心优化：高频流式输出节流，防止长文本导致的 Qt UI 线程卡死
                            now = time.time()
                            if now - last_ui_update > 0.1:
                                refresh_ui({"doubao_loading": False})
                                last_ui_update = now
                
                # 循环结束后，确保最后一次完整结果被更新到 UI
                if self._current_task_id == task_id:
                    refresh_ui({"doubao_loading": False})

            except Exception as e:
                logger.error(f"豆包 API 请求错误: {e}", exc_info=True)
                if self._current_task_id == task_id:
                    results["doubao"] = f"❌ 翻译出错: {e}"
                    refresh_ui({"doubao_loading": False})
            
            refresh_ui({"doubao_loading": False})

        # 🏃‍♂️ 任务 B: Google
        def task_google():
            try:
                res = safe_google_translate(text, source=google_source, target=google_target)
                if self._current_task_id == task_id:
                    results["google"] = res
            except Exception as e:
                logger.error(f"Google 翻译错误: {e}", exc_info=True)
                if self._current_task_id == task_id:
                    results["google"] = f"❌ 翻译出错: {e}"
            
            refresh_ui({"google_loading": False})

        # 触发初始加载状态
        refresh_ui({"doubao_loading": ai_enabled, "google_loading": True})

        if ai_enabled:
            self.executor.submit(task_doubao)
        self.executor.submit(task_google)
