import edge_tts
import asyncio
import sys
import time
import os
import threading
import subprocess
import pyperclip
import re
import ctypes
from ctypes import wintypes
from openai import OpenAI
from io import BytesIO
from dotenv import load_dotenv
import certifi
import wave 
# --- PySide6 依赖 ---
# --- PySide6 依赖 (完整版) ---
from PySide6.QtWidgets import (QApplication, QLabel, QVBoxLayout, QWidget, 
                               QPushButton, QTextEdit, QFrame, 
                               QSystemTrayIcon, QMenu, QStyle)  # <--- 补齐了这三个
                               
from PySide6.QtCore import Qt, QThread, Signal, QObject, Slot, QTimer, QEvent, QRect, QBuffer, QIODevice, QByteArray

from PySide6.QtGui import (QCursor, QPainter, QColor, QPen, QGuiApplication, 
                           QAction, QIcon, QPixmap)  # <--- 补齐了 QAction 和 QIcon
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from deep_translator import GoogleTranslator, MyMemoryTranslator

if getattr(sys, 'frozen', False):
    # 打包后：sys.executable 是 dist/ManboShot/ManboShot.exe
    # os.path.dirname 拿一次是 dist/ManboShot/
    # 再拿一次就是外层的 dist/ 目录了！
    icon_path = sys._MEIPASS
    exe_dir = os.path.dirname(sys.executable)
    application_path = os.path.dirname(exe_dir)
else:
    # 开发模式 (py文件)
    application_path = os.path.dirname(os.path.abspath(__file__))

env_path = os.path.join(application_path, '.env')
load_dotenv(env_path)
# ==========================================
# 🛡️ 核心升级 1：强制获取管理员权限 (解决 Snipaste 冲突)
# ==========================================
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

if not is_admin():
    print("正在尝试获取管理员权限以解决热键冲突...")
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    sys.exit()

# ==========================================

# --- 尝试导入 OCR 库 ---
try:
    from PIL import Image
    from rapidocr_onnxruntime import RapidOCR
    HAS_OCR = True
except ImportError:
    HAS_OCR = False
    print("⚠️ 警告: OCR 库未安装，截图功能不可用。")

# --- 尝试导入音标库 ---
try:
    import eng_to_ipa as ipa
    HAS_IPA = True
except ImportError:
    HAS_IPA = False


# --- 🛡️ Windows API 常量 (商业级稳定快捷键) ---
WM_HOTKEY = 0x0312
WM_CLIPBOARDUPDATE = 0x031D
WM_POWERBROADCAST = 0x0218
PBT_APMRESUMEAUTOMATIC = 0x0012

MOD_ALT = 0x0001
VK_Q = 0x51
VK_Z = 0x5A

HOTKEY_ID_Q = 1
HOTKEY_ID_Z = 2

# ================= 🔧 超级配置中心 (请在这里填 Key) =================

# 👇👇👇 在这里填入你的豆包/火山引擎信息 👇👇👇
DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY")
DOUBAO_MODEL_EP = os.getenv("DOUBAO_MODEL_EP")

# 策略阈值: 字数少于这个值 -> 用本地 Piper; 多于 -> 用云端 Edge
HYBRID_THRESHOLD = 30 

# =================================================

# 🛠️ Windows 底层工具箱
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

os.environ['SSL_CERT_FILE'] = certifi.where()

def force_focus_window(hwnd):
    if not hwnd: return
    h_foreground = user32.GetForegroundWindow()
    u_foreground_thread = user32.GetWindowThreadProcessId(h_foreground, None)
    u_current_thread = kernel32.GetCurrentThreadId()
    if u_foreground_thread != u_current_thread:
        user32.AttachThreadInput(u_foreground_thread, u_current_thread, True)
        user32.ShowWindow(hwnd, 9) 
        user32.SetForegroundWindow(hwnd)
        user32.SetFocus(hwnd)
        user32.AttachThreadInput(u_foreground_thread, u_current_thread, False)
    else:
        user32.ShowWindow(hwnd, 9)
        user32.SetForegroundWindow(hwnd)
        user32.SetFocus(hwnd)

# ================= 🎵 播放逻辑核心 =================

def play_voice(text, status_signal=None):
    if not text: return
    CREATE_NO_WINDOW = 0x08000000
    def send_status(msg):
        if status_signal:
            status_signal.emit(msg)

    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        base_path = os.path.dirname(exe_dir)
        tool_dir = os.path.join(base_path, "mpv")
    else:
        # 开发模式 (py文件)
        tool_dir=r"D:\ManboShot\mpv"
    
    # 2. 使用 os.path.join 拼接，自动处理 Windows 的反斜杠问题
    
    
    mpv_exe = os.path.join(tool_dir, "mpv.exe")
    
    use_cloud = len(text) > HYBRID_THRESHOLD
    
    def run():
        try:
            send_status("⏳ 准备中...")
            
            if use_cloud:
                send_status("☁️ 云端连接...")
                voice_name = "zh-CN-XiaoxiaoNeural"
                
                # 1. 先把 mpv 启动起来，让它张开嘴等着 (注意最后的参数 '-')
                # stdin=subprocess.PIPE 是关键，相当于插好了管子
                player_process = subprocess.Popen(
                    [mpv_exe, "--no-terminal", "--force-window=no", "-"],
                    stdin=subprocess.PIPE,
                    creationflags=CREATE_NO_WINDOW,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )

                async def stream_edge():
                    send_status("✨ AI合成中...")
                    communicate = edge_tts.Communicate(text, voice_name)
                    
                    first_chunk = True
                    # 2. 这里的 stream() 是个生成器，会一块一块地吐出音频数据
                    async for chunk in communicate.stream():
                        if chunk["type"] == "audio":
                            if first_chunk:
                                send_status("▶️ 开始朗读...")
                                first_chunk = False
                                
                            # 3. 拿到一块数据，立刻塞进 mpv 的嘴里
                            # 只要塞了第一块，mpv 就会立刻开始出声！
                            player_process.stdin.write(chunk["data"])
                            player_process.stdin.flush() # 确保不卡在管子里
                    
                    # 4. 喂完了，把嘴合上（关闭输入流），mpv 播完剩下的就会自己退出
                    player_process.stdin.close()
                    player_process.wait()

                # 运行异步任务
                asyncio.run(stream_edge())
            else:
                send_status("⚡ 播放中...")
                piper_exe = os.path.join(tool_dir, "piper.exe")
                model_cn = os.path.join(tool_dir, "zh_CN-huayan-medium.onnx")
                model_en = os.path.join(tool_dir, "en_US-lessac-medium.onnx")
                temp_wav = os.path.join(tool_dir, "temp_speech.wav")
                silence_wav = os.path.join(tool_dir, "silence_0.5s.wav")

                if not os.path.exists(silence_wav):
                    try:
                        with wave.open(silence_wav, 'wb') as f:
                            f.setnchannels(1)
                            f.setsampwidth(2)
                            f.setframerate(22050)
                            f.writeframes(b'\x00' * int(22050 * 0.5 * 2)) 
                    except: pass

                has_chinese = bool(re.search(r'[\u4e00-\u9fff]', text))
                current_model = model_cn if has_chinese else model_en
                if not os.path.exists(current_model): current_model = model_cn

                safe_text = "，" + text 
                cmd_gen = [piper_exe, "--model", current_model, "--output_file", temp_wav]
                
                if os.path.exists(piper_exe):
                    p = subprocess.Popen(cmd_gen, stdin=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=CREATE_NO_WINDOW)
                    p.communicate(input=safe_text.encode('utf-8'))
                    if os.path.exists(temp_wav):
                        cmd_play = [mpv_exe, "--no-terminal", "--force-window=no", "--audio-buffer=0.2"]
                        if os.path.exists(silence_wav): cmd_play.append(silence_wav)
                        cmd_play.append(temp_wav)
                        subprocess.run(cmd_play, stderr=subprocess.PIPE, creationflags=CREATE_NO_WINDOW)
                else:
                    print("❌ 错误：找不到 Piper.exe")
        except Exception as e:
            print(f"❌ 播放出错: {e}")
            send_status("❌ 出错")
            time.sleep(1) 
        finally:
            send_status("reset")
    run()

# ==========================================

# 📸 截图工具类 (保持不变)
class SnippingWidget(QWidget):
    ocr_finished_signal = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowState(Qt.WindowFullScreen)
        self.setCursor(Qt.CrossCursor)
        self.start_pos = None
        self.end_pos = None
        self.is_drawing = False
        self.ocr_engine = None

    def start_capture(self):
        self.start_pos = None
        self.end_pos = None
        self.is_drawing = False
        screen = QGuiApplication.primaryScreen()
        if screen:
            self.original_pixmap = screen.grabWindow(0)
            self.show()
            self.activateWindow()
        
    def paintEvent(self, event):
        if not hasattr(self, 'original_pixmap'): return
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.original_pixmap)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        if self.start_pos and self.end_pos:
            rect = QRect(self.start_pos, self.end_pos).normalized()
            painter.drawPixmap(rect, self.original_pixmap, rect)
            painter.setPen(QPen(QColor(255, 0, 0), 2))
            painter.drawRect(rect)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start_pos = event.position().toPoint()
            self.end_pos = self.start_pos
            self.is_drawing = True
            self.update()

    def mouseMoveEvent(self, event):
        if self.is_drawing:
            self.end_pos = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_drawing = False
            self.end_pos = event.position().toPoint()
            self.close()
            if self.start_pos and self.end_pos:
                x1 = min(self.start_pos.x(), self.end_pos.x())
                y1 = min(self.start_pos.y(), self.end_pos.y())
                w = abs(self.end_pos.x() - self.start_pos.x())
                h = abs(self.end_pos.y() - self.start_pos.y())
                if w > 10 and h > 10:
                    self.process_image(x1, y1, w, h)

    def process_image(self, x, y, w, h):
        if not HAS_OCR: return
        cropped = self.original_pixmap.copy(x, y, w, h)
        byte_array = QByteArray()
        buffer = QBuffer(byte_array)
        buffer.open(QIODevice.WriteOnly)
        cropped.save(buffer, "PNG")
        pil_img = Image.open(BytesIO(byte_array.data()))
        threading.Thread(target=self._run_ocr_thread, args=(pil_img,)).start()

    def _run_ocr_thread(self, img):
        if self.ocr_engine is None:
            self.ocr_engine = RapidOCR()
        result, _ = self.ocr_engine(np.array(img))
        if result:
            text = "\n".join([line[1] for line in result])
            if text.strip():
                self.ocr_finished_signal.emit(text)

# ==========================================
# 🧠 翻译引擎 (豆包 + 谷歌)
# ==========================================
# ==========================================
# 🧠 翻译引擎 (异步并发版：谷歌秒出，豆包随后)
# ==========================================
class TranslatorWorker(QObject):
    start_translation = Signal(str)
    translation_finished = Signal(str)

    def __init__(self):
        super().__init__()
        self.start_translation.connect(self.do_work)
        # 线程池：允许同时跑多个任务
        self.executor = ThreadPoolExecutor(max_workers=8)
        
        self.db_client = None
        if DOUBAO_API_KEY and DOUBAO_MODEL_EP:
            try:
                self.db_client = OpenAI(
                    api_key=DOUBAO_API_KEY,
                    base_url="https://ark.cn-beijing.volces.com/api/v3",
                )
                print("✅ 豆包 AI 翻译服务已就绪！")
            except Exception as e:
                print(f"⚠️ 豆包初始化失败: {e}")

    def do_work(self, text):
        try: print(f"DEBUG: 收到任务: {text[:15]}...", flush=True)
        except: pass
        
        has_chinese = bool(re.search(r'[\u4e00-\u9fff]', text))
        
        # 1. 准备原文头部 (含音标)
        phonetic_symbol = ""
        if HAS_IPA and not has_chinese:
            try:
                words = text.split()
                if 0 < len(words) <= 5:
                    clean = re.sub(r'[^\w\s]', '', text)
                    sym = ipa.convert(clean)
                    if sym and sym != "*" and sym != clean: 
                        phonetic_symbol = f"  [{sym}]"
            except: pass
            
        original_text = f"【原文】{text}{phonetic_symbol}"

        # 结果容器 (闭包变量，线程安全)
        # None 代表“正在加载”，字符串代表“结果出来了”
        results = {
            "doubao": None, 
            "google": None
        }
        
        # 🔥 核心魔法：实时刷新 UI 的函数
        def refresh_ui():
            parts = [original_text]
            
            # --- 豆包部分 ---
            if self.db_client:
                if results["doubao"] is not None:
                    # 跑完了，显示结果
                    parts.append(f"【豆包 AI 译】\n{results['doubao']}")
                else:
                    # 还没跑完，显示占位符
                    parts.append(f"【豆包 AI 】\n(⏳ AI 正在思考...)")

            # --- Google 部分 ---
            if results["google"] is not None:
                parts.append(f"【谷歌汉译】\n{results['google']}")
            else:
                # Google 通常很快，甚至不需要占位符，但为了整齐也可以加
                parts.append(f"【谷歌汉译】\n(⏳ 机翻中...)")
            
            # 发送信号给主界面 (主界面收到后会立马更新文字)
            self.translation_finished.emit("\n\n".join(parts))

        # 🏃‍♂️ 任务 A: 豆包 (可能慢)
        def task_doubao():
            if not self.db_client: return
            try:
                prompt_lang = "英语" if has_chinese else "中文"
                system_prompt = (
                    f"你是一个专业的翻译助手。请将用户输入的文本翻译成{prompt_lang}。\n"
                    "要求：\n"
                    "1. 保持专业术语准确无误。\n"
                    "2. 保留代码变量名。\n"
                    "3. 仅返回译文。\n"
                )
                response = self.db_client.chat.completions.create(
                    model=DOUBAO_MODEL_EP,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": text}
                    ],
                    timeout=15
                )
                results["doubao"] = response.choices[0].message.content.strip()
            except Exception as e:
                results["doubao"] = f"(连接超时或错误: {e})"
            
            refresh_ui() # 跑完喊一声

        # 🏃‍♂️ 任务 B: Google (通常快)
        def task_google():
            try:
                if has_chinese:
                    res = GoogleTranslator(source='auto', target='en').translate(text)
                else:
                    res = GoogleTranslator(source='auto', target='zh-CN').translate(text)
                results["google"] = res
            except Exception as e:
                results["google"] = "(翻译失败)"
            
            refresh_ui() # 跑完喊一声

        # 1. 先显示一个初始状态 (两个都在加载)
        refresh_ui()

        # 2. 同时发射两个任务！
        if self.db_client:
            self.executor.submit(task_doubao)
        
        self.executor.submit(task_google)

# 2️⃣ 主窗口
class FloatingWindow(QWidget):
    request_translation_signal = Signal(str)
    show_window_signal = Signal()
    trigger_snipping_signal = Signal()
    tts_finished_signal = Signal()
    tts_status_signal = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.StrongFocus) 
        self.current_text_for_speech = ""
        self.setup_tray()
        self.tts_finished_signal.connect(self.reset_play_btn)
        self.tts_status_signal.connect(self.update_play_btn_status)

        if HAS_OCR:
            self.snipper = SnippingWidget()
            self.snipper.ocr_finished_signal.connect(self.handle_ocr_result)

        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.container = QFrame()
        self.container.setObjectName("container")
        self.container.setStyleSheet("""
            QFrame#container {
                background-color: #2b2b2b;
                border: 1px solid #444;
                border-radius: 10px;
            }
        """)
        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(15, 15, 15, 15)
        self.content_layout.setSpacing(10)

        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText("手动输入 / 划词复制 / Alt+Z 截图...")
        self.input_edit.setStyleSheet("QTextEdit { background-color: #3a3a3a; color: #ffffff; border: 1px solid #555; border-radius: 5px; font-family: 'Microsoft YaHei'; font-size: 14px; padding: 5px; }")
        self.input_edit.setFixedHeight(80) 
        self.content_layout.addWidget(self.input_edit)

        self.trans_btn = QPushButton("🚀 立即翻译")
        self.trans_btn.setCursor(Qt.PointingHandCursor)
        self.trans_btn.clicked.connect(self.manual_translate)
        self.trans_btn.setStyleSheet("QPushButton { background-color: #ff9800; color: white; border: none; padding: 6px; border-radius: 4px; font-weight: bold; } QPushButton:hover { background-color: #f57c00; }")
        self.content_layout.addWidget(self.trans_btn)

        self.result_label = QLabel("")
        self.result_label.setWordWrap(True)
        self.result_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.result_label.setStyleSheet("""
            QLabel {
                color: #dddddd; 
                font-family: 'Microsoft YaHei'; 
                font-size: 14px; 
                padding: 5px; 
                background-color: transparent;
                selection-background-color: #0078D4;
                selection-color: white;
            }
        """)
        self.content_layout.addWidget(self.result_label)
        self.result_label.hide()

        self.play_btn = QPushButton("🔊 朗读原文")
        self.play_btn.setCursor(Qt.PointingHandCursor)
        self.play_btn.clicked.connect(self.play_audio)
        self.play_btn.setStyleSheet("QPushButton { background-color: #0078D4; color: white; border: none; padding: 6px; border-radius: 4px; font-weight: bold; } QPushButton:hover { background-color: #106EBE; }")
        self.content_layout.addWidget(self.play_btn)
        self.play_btn.hide()

        self.container.setLayout(self.content_layout)
        self.main_layout.addWidget(self.container)
        self.setLayout(self.main_layout)
        
        self.request_translation_signal.connect(self.handle_hotkey_request)
        self.show_window_signal.connect(self.handle_show_window)
        self.trigger_snipping_signal.connect(self.start_snipping)
        self.input_edit.installEventFilter(self)
        # --- 🕒 双击 Ctrl+C 的时间记录 ---
        self.last_clipboard_time = 0
        self.last_clipboard_text = ""  # 新增：记住上次复制的内容
        # --- 🛡️ 注册商业级系统热键 ---
        self.hwnd = int(self.winId()) # 获取当前窗口的系统句柄
        
        # 注册 Alt + Q (显示面板)
        ctypes.windll.user32.RegisterHotKey(self.hwnd, HOTKEY_ID_Q, MOD_ALT, VK_Q)
        # 注册 Alt + Z (截图)
        ctypes.windll.user32.RegisterHotKey(self.hwnd, HOTKEY_ID_Z, MOD_ALT, VK_Z)
        
        # --- 📋 注册剪贴板变动监听 (完美替代 Ctrl+C 键盘钩子) ---
        ctypes.windll.user32.AddClipboardFormatListener(self.hwnd)
    # --- 🖱️ 新增：窗口拖动逻辑 ---
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # 记录鼠标按下时的相对位置
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.drag_pos:
            # 移动窗口到新位置
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.drag_pos = None
    # ---------------------------
    def restart_app(self):
        """💥 彻底重启软件 (专治挂机假死)"""
        print("正在执行重启...")
        try:
            # 1. 先把托盘图标藏起来，防止重启后右下角残留一个无效图标
            self.tray_icon.hide()
            
            # 2. 准备重启命令
            # getattr(sys, 'frozen', False) 用来判断是 EXE 还是 脚本
            if getattr(sys, 'frozen', False):
                # --- EXE 模式 ---
                # 重新启动当前的 exe 文件
                subprocess.Popen([sys.executable] + sys.argv[1:])
            else:
                # --- 脚本模式 ---
                # 使用当前的 python 解释器重新运行脚本
                subprocess.Popen([sys.executable] + sys.argv)
            
            # 3. 杀掉当前进程 (光荣下岗)
            sys.exit(0)
            
        except Exception as e:
            print(f"重启失败: {e}")
            self.show_window_signal.emit()
            self.tray_icon.showMessage("错误", f"重启失败: {e}", QSystemTrayIcon.Warning)
            self.tray_icon.show()
    def setup_tray(self):
        """设置系统托盘图标 (双重搜索版)"""
        self.tray_icon = QSystemTrayIcon(self)
        
        # --- 🕵️‍♂️ 核心修改：双重搜索逻辑 ---
        # 1. 先定义两个可能的路径
        # 路径A: PyInstaller 的内部临时目录 (如果用了 --add-data)
        path_internal = os.path.join(icon_path, "icon.ico")
        
        # 路径B: EXE 文件所在的实际目录 (如果你手动复制了文件)
        # 注意: sys.executable 是 EXE 的路径，dirname 是它所在的文件夹
        exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else application_path
        path_external = os.path.join(exe_dir, "icon.ico")

        final_icon_path = None
        
        # 2. 依次检查
        if os.path.exists(path_internal):
            final_icon_path = path_internal
            # print(f"DEBUG: 在内部目录找到了图标: {path_internal}")
        elif os.path.exists(path_external):
            final_icon_path = path_external
            # print(f"DEBUG: 在外部目录找到了图标: {path_external}")
            
        # 3. 设置图标
        if final_icon_path:
            self.tray_icon.setIcon(QIcon(final_icon_path))
        else:
            # ⚠️ 实在找不到，画黄点
            pixmap = QPixmap(16, 16)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setBrush(QColor("#ff9800"))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(2, 2, 12, 12)
            painter.end()
            self.tray_icon.setIcon(QIcon(pixmap))

        # 创建右键菜单
        tray_menu = QMenu()
        
        # 动作1: 显示面板
        action_show = QAction("显示面板", self)
        action_show.triggered.connect(self.show_window_signal.emit)
        tray_menu.addAction(action_show)

        # 动作2: 🚑 重置监听 (这里就是你的救命稻草)
        action_reset = QAction("重置键盘监听", self)
        action_reset.triggered.connect(self.reset_listener)
        tray_menu.addAction(action_reset)

        tray_menu.addSeparator()
        action_restart = QAction("🔄 重启软件", self)
        action_restart.triggered.connect(self.restart_app) # 绑定刚才写的函数
        tray_menu.addAction(action_restart)
        # 动作3: 退出
        action_quit = QAction("退出软件", self)
        action_quit.triggered.connect(QApplication.instance().quit)
        tray_menu.addAction(action_quit)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
        
        self.tray_icon.activated.connect(
            lambda reason: self.show_window_signal.emit() if reason == QSystemTrayIcon.DoubleClick else None
        )
        

    def reset_listener(self):
        """手动重启键盘钩子"""
        try:
            print("正在重置键盘监听...")
            
            # 弹个气泡提示告诉用户成功了
            self.tray_icon.showMessage(
                "ManboShot", 
                "键盘监听已成功重置！👂", 
                QSystemTrayIcon.Information, 
                2000
            )
        except Exception as e:
            self.tray_icon.showMessage(
                "ManboShot", 
                f"重置失败: {e}", 
                QSystemTrayIcon.Warning, 
                2000
            )
    def eventFilter(self, obj, event):
        if obj == self.input_edit and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Return and (event.modifiers() & Qt.ControlModifier):
                self.manual_translate()
                return True
        return super().eventFilter(obj, event)

    def changeEvent(self, event):
        if event.type() == QEvent.ActivationChange:
            if not self.isActiveWindow():
                self.hide()
        super().changeEvent(event)

    def setup_worker(self):
        self.thread = QThread()
        self.worker = TranslatorWorker()
        self.worker.moveToThread(self.thread)
        self.worker.translation_finished.connect(self.update_result)
        self.thread.start()

    def manual_translate(self):
        text = self.input_edit.toPlainText().strip()
        if text:
            cleaned_text = re.sub(r'[_\n\r]+', ' ', text)
            self.current_text_for_speech = cleaned_text
            self.result_label.setText("⏳ 正在翻译...")
            self.result_label.show()
            self.play_btn.hide()
            self.adjustSize()
            self.worker.start_translation.emit(cleaned_text)

    # 🛠️ 关键修复：确保窗口如果被隐藏了，就不会再强制夺取焦点
    def nuke_activate_window(self):
        # 如果窗口已经被用户关了(不可见)，那就不要再去骚扰用户了！
        if not self.isVisible(): 
            return 
        
        hwnd = int(self.winId())
        force_focus_window(hwnd)
        self.input_edit.setFocus()
    # ==========================================
    # 🧠 新增：智能防遮挡移动逻辑
    # ==========================================
    def move_smart(self):
        """支持多屏幕的智能移动逻辑"""
        self.adjustSize()  # 确保拿到最新大小
        
        # 1. 获取鼠标当前位置
        cursor_pos = QCursor.pos()
        
        # 2. 【关键修改】获取鼠标当前所在的屏幕（而不是主屏幕）
        screen = QGuiApplication.screenAt(cursor_pos)
        
        # 防御性代码：万一鼠标位置很偏，找不到屏幕，就回退到主屏幕
        if not screen:
            screen = QGuiApplication.primaryScreen()
            
        screen_rect = screen.availableGeometry() # 获取该屏幕的矩形区域 (x, y, w, h)
        
        # 3. 预设目标位置（默认在鼠标右下方 +15像素）
        target_x = cursor_pos.x() + 15
        target_y = cursor_pos.y() + 15
        
        # 4. 获取窗口尺寸
        win_w = self.width()
        win_h = self.height()
        
        # 5. 【底部防遮挡】
        # screen_rect.bottom() 会自动处理多屏坐标（比如副屏可能是 2160）
        if target_y + win_h > screen_rect.bottom():
            # 策略：改为显示在鼠标【上方】
            target_y = cursor_pos.y() - win_h - 15
            
        # 6. 【右侧防遮挡】
        # screen_rect.right() 也会自动处理多屏坐标（比如副屏右边缘是 3840）
        if target_x + win_w > screen_rect.right():
            # 策略：贴着该屏幕的右边缘
            target_x = screen_rect.right() - win_w - 5

        # 7. 【顶部防遮挡】
        if target_y < screen_rect.top():
            target_y = cursor_pos.y() + 15
            
        # 8. 【左侧防遮挡】(通常不太需要，但为了保险加上)
        if target_x < screen_rect.left():
            target_x = cursor_pos.x() + 15

        self.move(target_x, target_y)
    @Slot()
    def start_snipping(self):
        if HAS_OCR:
            self.hide() 
            time.sleep(0.2)
            self.snipper.start_capture()
        else:
            print("OCR 库未安装，无法截图。")

    @Slot(str)
    def handle_ocr_result(self, text):
        self.input_edit.setPlainText(text)
        self.manual_translate()
        self.move_smart()
        self.show()
        QTimer.singleShot(50, self.nuke_activate_window)

    @Slot(str)
    def handle_hotkey_request(self, text):
        self.input_edit.setPlainText(text)
        self.manual_translate() 
        self.move_smart()
        self.show()
        QTimer.singleShot(50, self.nuke_activate_window)

    @Slot()
    def handle_show_window(self):
        self.move_smart()
        self.input_edit.clear() 
        self.result_label.hide()
        self.play_btn.hide()
        self.show()
        QTimer.singleShot(50, self.nuke_activate_window)

    # 🔥 核心修复：防止“诈尸”逻辑
    def update_result(self, result_text):
        # 1. 无论如何，先把文本更新好
        self.result_label.setText(result_text)
        self.result_label.show()
        self.play_btn.show()
        self.adjustSize()
        QTimer.singleShot(10, self.adjustSize)
        # 2. 关键判断：
        # 如果当前窗口是开着的，那我们才去刷新焦点。
        # 如果用户刚才点旁边把它关了 (isVisible == False)，那就什么都不要做！
        # 这样它就会默默地在后台把结果填好，但不会跳出来吓人。
        if self.isVisible():
            QTimer.singleShot(50, self.nuke_activate_window)
        else:
            print("DEBUG: 用户已关闭窗口，静默更新结果，不弹窗。")

    @Slot()
    def reset_play_btn(self):
        self.play_btn.setText("🔊 朗读原文")
        self.play_btn.setEnabled(True)

    def update_play_btn_status(self, text):
        if text == "reset":
            self.play_btn.setText("朗读") 
            self.play_btn.setEnabled(True)
        else:
            self.play_btn.setText(text) 

    def play_audio(self):
        if not self.current_text_for_speech: return
        threading.Thread(target=play_voice, args=(self.current_text_for_speech, self.tts_status_signal)).start()

    def closeEvent(self, event):
        # --- 🧹 退出时归还系统资源 ---
        try:
            ctypes.windll.user32.UnregisterHotKey(self.hwnd, HOTKEY_ID_Q)
            ctypes.windll.user32.UnregisterHotKey(self.hwnd, HOTKEY_ID_Z)
            ctypes.windll.user32.RemoveClipboardFormatListener(self.hwnd)
        except:
            pass

        if hasattr(self, 'thread'):
            self.thread.quit()
            self.thread.wait()
        super().closeEvent(event)
    # === 👇 这是新加的系统消息中枢 👇 ===
    def nativeEvent(self, eventType, message):
        """👂 商业级系统消息中枢：处理永不丢失的热键、剪贴板和唤醒"""
        try:
            if eventType == b"windows_generic_MSG":
                msg = ctypes.wintypes.MSG.from_address(int(message))
                
                # 1. ⌨️ 处理系统级热键 (Alt+Q, Alt+Z)
                if msg.message == WM_HOTKEY:
                    if msg.wParam == HOTKEY_ID_Q:
                        self.handle_show_window()
                    elif msg.wParam == HOTKEY_ID_Z:
                        self.start_snipping()
                        
                # 2. 📋 处理剪贴板变动 (智能防抖 + 内容校验版)
                elif msg.message == WM_CLIPBOARDUPDATE:
                    current_time = time.time()
                    time_diff = current_time - self.last_clipboard_time
                    
                    try:
                        # 场景 A: 距离上次复制超过 0.6 秒，认为是全新的第一次复制
                        if time_diff > 0.6:
                            self.last_clipboard_time = current_time
                            time.sleep(0.05) # 给系统一点时间把数据写完
                            self.last_clipboard_text = pyperclip.paste()
                            
                        # 场景 B: 间隔在 0.15 ~ 0.6 秒之间，说明是人类的“双击 Ctrl+C”
                        elif 0.15 < time_diff <= 0.6:
                            time.sleep(0.05)
                            current_text = pyperclip.paste()
                            
                            # 【核心防御】只有当两次复制的文字一模一样，且不为空时，才触发翻译！
                            # 这完美防住了点击输入框产生的无效剪贴板刷新
                            if current_text and current_text == self.last_clipboard_text:
                                if not self.isVisible():
                                    # 触发翻译信号
                                    self.request_translation_signal.emit(current_text)
                                # 触发成功后，重置状态
                                self.last_clipboard_time = 0
                                self.last_clipboard_text = ""
                        
                        # 场景 C: 间隔小于 0.15 秒 (time_diff <= 0.15)
                        # 这是 Windows 的系统级“连发”，直接无视，什么都不做
                        
                    except Exception as e:
                        print(f"读取剪贴板异常: {e}")

                # 3. ⚡ 处理系统睡眠唤醒
                elif msg.message == WM_POWERBROADCAST and msg.wParam == PBT_APMRESUMEAUTOMATIC:
                    print("⚡ 系统唤醒，快捷键依然稳如泰山！")
                    
        except Exception as e:
            pass
            
        return super().nativeEvent(eventType, message)
    # === 👆 新加结束 👆 ===

# 全局变量
window = None
last_copy_time = 0

def check_hotkey():
    global last_copy_time
    current_time = time.time()
    
    if current_time - last_copy_time < 0.5:
        try:
            if window.isVisible():
                print("DEBUG: 窗口已存在，忽略新的翻译请求")
                last_copy_time = 0 
                return

            time.sleep(0.1) 
            text = pyperclip.paste()
            if text and text.strip():
                window.request_translation_signal.emit(text)
        except: pass
        last_copy_time = 0 
    else:
        last_copy_time = current_time

def safe_show_window():
    if window.isVisible():
        return
    window.show_window_signal.emit()

def safe_trigger_snipping():
    window.trigger_snipping_signal.emit()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    window = FloatingWindow()
    window.setup_worker()
    
    
    print("🚀 尊享版 (豆包AI+Piper+Edge-TTS) 已启动！")
    sys.exit(app.exec())