import re
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
        
        if api_key:
            self.db_client = OpenAI(
                api_key=api_key,
                base_url="https://ark.cn-beijing.volces.com/api/v3"
            )
            logger.info("已加载火山引擎豆包模型配置。")
        else:
            self.db_client = None
            logger.info("未配置豆包模型，开启纯Google翻译模式。")

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
        has_chinese = bool(re.search(r'[\u4e00-\u9fff]', text))

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
                for chunk in response:
                    # 🛡️ 核心优化：检测当前任务是否已被废弃。如果已被新请求覆盖，立即切断网络流迭代，释放连接并优雅退出！
                    if self._current_task_id != task_id:
                        logger.info(f"Task {task_id} superseded by {self._current_task_id}. Breaking stream.")
                        break
                    
                    if chunk.choices and chunk.choices[0].delta.content:
                        collected_messages.append(chunk.choices[0].delta.content)
                        if self._current_task_id == task_id:
                            results["doubao"] = "".join(collected_messages)
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
                if has_chinese:
                    res = GoogleTranslator(source='auto', target='en').translate(text)
                else:
                    res = GoogleTranslator(source='auto', target='zh-CN').translate(text)
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
