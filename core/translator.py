import re
import time
from concurrent.futures import ThreadPoolExecutor
from PySide6.QtCore import QObject, Signal, Slot
from openai import OpenAI
from deep_translator import GoogleTranslator
from core.config import logger, load_app_config

try:
    import eng_to_ipa as ipa
    HAS_IPA = True
except ImportError:
    HAS_IPA = False

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
    translator = GoogleTranslator(source=source, target=target)
    for g in groups:
        if g["is_target"] or not g["text"].strip():
            # 已经是目标语言或者是空行，保留原文
            translated_groups.append(g["text"])
        else:
            # 需要翻译的外语块（包含多个段落，仅进行 1 次网络请求）
            try:
                translated = translator.translate(g["text"])
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
