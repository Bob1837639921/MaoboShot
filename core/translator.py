import re
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from PySide6.QtCore import QObject, Signal, Slot
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI
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

AI_STREAM_TIMEOUT = 20
AI_FALLBACK_TIMEOUT = 30


class EmptyAIResponseError(RuntimeError):
    pass


def should_retry_ai_error(error: Exception) -> bool:
    if isinstance(error, (EmptyAIResponseError, APITimeoutError, APIConnectionError)):
        return True
    if isinstance(error, APIStatusError):
        status_code = getattr(error, "status_code", 0)
        return status_code in (408, 409, 429) or status_code >= 500
    return False


def friendly_ai_error(error: Exception) -> str:
    if isinstance(error, APITimeoutError):
        return "AI 响应超时，请重试"
    if isinstance(error, APIConnectionError):
        return "AI 服务连接失败，请检查网络后重试"
    if isinstance(error, EmptyAIResponseError):
        return "AI 未返回内容，请重试"
    if isinstance(error, APIStatusError):
        status_code = getattr(error, "status_code", 0)
        if status_code in (401, 403):
            return "AI 配置无效，请检查 API Key"
        if status_code == 404:
            return "未找到 AI 模型或接口，请检查配置"
        if status_code == 429:
            return "AI 请求过于频繁，请稍后重试"
        if status_code >= 500:
            return "AI 服务暂时不可用，请稍后重试"
    return "AI 翻译失败，请重试"


def extract_ai_message_content(response) -> str:
    if not getattr(response, "choices", None):
        return ""
    content = getattr(response.choices[0].message, "content", "") or ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text", "")))
            else:
                parts.append(str(getattr(item, "text", "")))
        return "".join(parts).strip()
    return str(content).strip()

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

@lru_cache(maxsize=128)
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
                base_url=base_url,
                max_retries=0
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
            "doubao_error": "",
            "google": "", 
            "phonetic": phonetic_symbol(text),
            "ai_enabled": ai_enabled
        }
        loading_state = {
            "doubao_loading": ai_enabled,
            "doubao_retrying": False,
            "google_loading": True
        }
        google_source, google_target = choose_google_translation_args(text)

        def refresh_ui(loading_status=None):
            if self._current_task_id == task_id:
                if loading_status:
                    loading_state.update(loading_status)
                out = dict(results)
                out.update(loading_state)
                self.finished_signal.emit(out)

        # AI 翻译先尝试流式输出；超时、连接失败或空响应时自动降级为普通请求。
        def task_doubao():
            if not ai_enabled:
                refresh_ui({"doubao_loading": False})
                return
            
            system_prompt = "你是一个专业翻译。请将用户输入翻译为中文或英文，只输出译文本身，不要说多余的话。如果原文排版混乱、缺乏换行或全部粘连在一起（如PDF复制文本），请在翻译时根据语义进行合理的【分段和排版优化】，使其结构清晰、易读。"
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ]

            for attempt in range(2):
                if self._current_task_id != task_id:
                    return

                use_stream = attempt == 0
                results["doubao"] = ""
                results["doubao_error"] = ""
                if attempt:
                    refresh_ui({"doubao_loading": True, "doubao_retrying": True})

                try:
                    response = self.db_client.chat.completions.create(
                        model=self.model_ep,
                        messages=messages,
                        timeout=AI_STREAM_TIMEOUT if use_stream else AI_FALLBACK_TIMEOUT,
                        stream=use_stream
                    )

                    if use_stream:
                        collected_messages = []
                        last_ui_update = 0
                        for chunk in response:
                            if self._current_task_id != task_id:
                                logger.info(
                                    f"Task {task_id} superseded by {self._current_task_id}. Breaking stream."
                                )
                                return

                            if chunk.choices and chunk.choices[0].delta.content:
                                collected_messages.append(chunk.choices[0].delta.content)
                                results["doubao"] = "".join(collected_messages)

                                now = time.time()
                                if now - last_ui_update > 0.1:
                                    refresh_ui({"doubao_loading": True})
                                    last_ui_update = now
                        translated = "".join(collected_messages).strip()
                    else:
                        translated = extract_ai_message_content(response)

                    if not translated:
                        raise EmptyAIResponseError("AI returned an empty response")

                    if self._current_task_id == task_id:
                        results["doubao"] = translated
                        results["doubao_error"] = ""
                        refresh_ui({"doubao_loading": False, "doubao_retrying": False})
                    return

                except Exception as e:
                    if self._current_task_id != task_id:
                        return
                    if attempt == 0 and should_retry_ai_error(e):
                        logger.warning(f"AI 首次请求失败，正在自动重试: {e}")
                        continue

                    logger.error(f"AI API 请求错误: {e}", exc_info=True)
                    results["doubao"] = ""
                    results["doubao_error"] = friendly_ai_error(e)
                    refresh_ui({"doubao_loading": False, "doubao_retrying": False})
                    return

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
