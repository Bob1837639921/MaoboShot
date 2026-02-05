# 🐱 MaoboShot Desktop Translator (MaoboShot)

**Maobo Desktop Translator** 是一款专为开发者打造的高性能桌面翻译工具。它集成了 **豆包 AI (Doubao)** 的智能理解能力与 **Google 翻译** 的速度，并配备了 **本地+云端混合语音引擎**，旨在提供极致的“无感”翻译体验。

---

## ✨ 核心特性 (Features)

### 🧠 1. 异步双引擎翻译 (Race Mode)

不再傻等 AI！软件采用“赛马机制”：

* **Google 翻译**：毫秒级响应，瞬间给出基础翻译结果。
* **豆包 AI (Doubao)**：随后到达，提供更懂代码、更自然的润色结果（会自动保留 `camelCase` 或 `snake_case` 变量名）。

### 🗣️ 2. 混合动力语音引擎 (Hybrid TTS)

根据文本长度智能切换，兼顾速度与音质：

* **⚡ 短句 (<30字)**：使用本地 **Piper TTS**，0 延迟秒开，适合查单词。
* **☁️ 长文 (>30字)**：无缝切换 **Microsoft Edge TTS**，享受顶级神经网络人声（晓晓），适合听长段落。

### 📸 3. 截图 OCR (Screenshot & Translate)

* 集成 **RapidOCR** 引擎。
* 按下 `Alt + Z` 即可截取屏幕区域，自动识别文字并翻译。

### 🛠️ 4. 开发者友好的交互

* **智能唤醒**：选中文字后双击 `Ctrl + C` 自动呼出。
* **静默运行**：无任务栏图标，后台静默驻留，按 `Alt + Q` 随时呼出。
* **防吞字优化**：底层音频流预处理，解决蓝牙耳机/声卡唤醒慢导致的“吞字”问题。

---

## 🚀 快速开始 (Getting Started)

### 1. 环境准备

确保已安装 Python 3.10+。

```bash
# 克隆项目
git clone https://github.com/你的用户名/Maobo-Desktop-Translator.git
cd Maobo-Desktop-Translator

# 安装依赖
pip install -r requirements.txt

```

### 2. 外部依赖配置 (关键！)

本项目依赖外部二进制工具，请在项目根目录下创建一个名为 `mpv` 的文件夹，并放入以下文件：

```text
Maobo-Desktop-Translator/
├── desktop_trans.py
└── mpv/  <-- 必须创建此文件夹
    ├── mpv.exe                   (播放器核心)
    ├── piper.exe                 (本地TTS核心)
    ├── piper_phonemize.exe       (Piper依赖)
    ├── zh_CN-huayan-medium.onnx  (中文模型)
    ├── en_US-lessac-medium.onnx  (英文模型)
    └── silence_0.5s.wav          (程序会自动生成，无需手动下载)

```

> 💡 **提示**：你可以从 [Piper GitHub](https://www.google.com/search?q=https://github.com/rhasspy/piper) 和 [MPV 官网](https://www.google.com/search?q=https://mpv.io/) 下载上述工具。

### 3. 配置 API Key

打开 `desktop_trans.py`，找到配置区域填入你的火山引擎（豆包）Key：

```python
# ================= 🔧 超级配置中心 =================
DOUBAO_API_KEY = "sk-xxxxxxxxxxxx"       # 你的 API Key
DOUBAO_MODEL_EP = "ep-202xxxxxxxx"       # 你的接入点 ID

```

*如果留空，软件将自动降级为仅使用 Google 翻译。*

### 4. 运行

```bash
python desktop_trans.py

```

---

## ⌨️ 快捷键说明 (Hotkeys)

| 快捷键 | 功能 | 说明 |
| --- | --- | --- |
| **Ctrl + C** | 划词翻译 | 选中任意文本，0.5秒内**连按两次**复制即可触发。 |
| **Alt + Q** | 显示/隐藏 | 快速呼出或隐藏主窗口。 |
| **Alt + Z** | 截图翻译 | 类似 QQ 截图，框选区域后自动 OCR 并翻译。 |
| **Alt + Esc** | 强制退出 | 彻底关闭程序进程。 |

---

## 📦 打包指南 (Build EXE)

如果你想将其打包为独立的 `.exe` 文件分享给朋友：

1. 安装打包工具：
```bash
pip install pyinstaller

```


2. 运行打包命令：
```bash
# 注意：这里使用了智能路径判定，打包后必须把 mpv 文件夹放在 exe 旁边
pyinstaller -F -w -i .\icon.ico -n "MaoboShot" MaoboShot.py

```


3. **发布结构**：
将生成的 `MaoboShot.exe` 和 `mpv` 文件夹放在一起即可分发：
```text
发布文件夹/
├── MaoboShot.exe
└── mpv/ (包含所有依赖)

```



---

## ⚠️ 注意事项

1. **管理员权限**：程序启动时会请求管理员权限，这是为了避免与 Snipaste 等截图软件发生热键冲突，请允许通过。
2. **API 安全**：提交代码到 GitHub 前，**请务必删除代码中的 API Key**！

---

## 📄 License

MIT License © 2026 Maobo