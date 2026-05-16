# ✨ ManboShot 桌面聚合翻译助手

**ManboShot** 是一款专为高效办公与开发者打造的现代化桌面翻译与语音助手。它巧妙融合了 **豆包 AI (Doubao)** 的强境语境理解能力与 **Google 翻译** 的极速响应，配备 **本地+云端混合智能语音引擎**，旨在提供极致、无痛的划词与截图翻译体验。

---

## 🌟 核心特性 (Features)

### 🏎️ 1. 双核异步翻译引擎 (Race Mode)
不再傻等 AI！软件采用“赛马机制”：
- **🌐 谷歌翻译**：毫秒级响应，瞬间给出基础翻译结果。
- **✨ 豆包 AI**：流式生成（Streaming），提供更懂代码、更符合语境的润色结果，完美应对长难句与专业术语。

### 🗣️ 2. 混合动力语音引擎 (Hybrid TTS)
根据文本长度智能路由，兼顾速度与发音质感：
- **⚡ 短句 (<30字)**：调用本地 **Piper TTS** 模型，0 延迟秒开，适合高频查单词。
- **☁️ 长文 (>30字)**：无缝切换 **微软 Edge TTS** 神经网络人声（晓晓），提供顶级听感，适合朗读长段落文章。

### 📸 3. 沉浸式截图 OCR (Screenshot & Translate)
- 深度集成 **RapidOCR** 本地推理引擎，断网也能精准提取屏幕文字。
- 按下 `Alt + Z` 即可进入媲美 Snipaste 的高级暗黑遮罩框选模式，松手即刻 OCR 并双引擎翻译。

### 🎨 4. 现代化 UI 与无感交互
- **日夜间主题切换**：支持高级毛玻璃暗色 (Dark) 与清爽浅色 (Light) 界面一键热切换。
- **智能唤醒**：选中文字后，**双击 `Ctrl + C`** 自动在光标处弹出精美卡片。
- **骨架屏过渡**：告别干等，优雅的“AI 思考中...”占位动画。
- **系统级防抖**：深度调用 Windows底层 API，完美规避连续复制与浏览器暗中操作带来的“弹窗抽搐”问题。

---

## 🚀 快速上手 (Getting Started)

### 1. 环境准备
确保已安装 Python 3.10+。

```bash
# 克隆项目
git clone https://github.com/你的用户名/ManboShot.git
cd ManboShot

# 安装依赖
pip install -r requirements.txt
```

### 2. 外部依赖配置 (关键！)
本项目音频播放与本地语音依赖外部二进制工具，请在项目根目录下创建一个名为 `mpv` 的文件夹，并放入以下必要文件：

```text
ManboShot/
├── main.py
└── mpv/  <-- 必须创建此文件夹
    ├── mpv.exe                   (核心播放器，接收音频流)
    ├── piper.exe                 (本地 TTS 推理引擎)
    ├── zh_CN-huayan-medium.onnx  (中文离线发音模型)
    └── en_US-lessac-medium.onnx  (英文离线发音模型)
```

> 💡 **获取方式**：可前往 [Piper GitHub](https://github.com/rhasspy/piper) 和 [MPV 官网](https://mpv.io/) 下载上述免安装工具。

### 3. 配置 API Key
1. 直接运行程序 `python main.py`。
2. 软件会在右下角系统托盘静默运行，右键点击 ✨ 星星图标，选择 **「⚙️ 设置」**。
3. 在设置窗口里填入火山引擎（豆包）API Key 与模型接入点 (Endpoint)，并选择你喜欢的主题。

> *如果留空不填 API Key，软件将自动降级为“纯 Google 翻译”模式，界面依然完美适配。*

设置窗口会自动把配置保存到当前用户目录下：

```text
%APPDATA%\MaoboShot\config.json
```

仓库中的 `config.example.json` 只说明字段结构。不要手动维护项目根目录的 `config.json`，也不要把真实 API Key 提交到 Git。开发或便携运行时，如果 `mpv` 工具不在项目根目录，可以通过环境变量指定：

```powershell
$env:MAOBOSHOT_TOOL_DIR="D:\Tools\maoboshot\mpv"
python main.py
```

### 4. AI 语音设置

设置窗口支持选择 AI 语音提供商：

- **Edge TTS**：默认云端语音，不需要额外 Key。
- **小米 MiMo TTS**：兼容 OpenAI 接口协议，可配置 Base URL、API Key、模型、音色和风格。

小米 MiMo 常用配置：

```text
Base URL: https://token-plan-cn.xiaomimimo.com/v1
Model: mimo-v2-tts
Voice: mimo_default / default_zh / default_en
```

真实 Key 只通过设置窗口填写，由软件保存到用户目录；不要手动写入或提交项目文件。

---

## ⌨️ 快捷键说明 (Hotkeys)

| 快捷键 | 功能 | 说明 |
| :--- | :--- | :--- |
| **连按两次 Ctrl + C** | 划词翻译 | 选中任意文本，0.15~0.6 秒内连按两次复制键，弹窗将跟随鼠标光标唤醒。 |
| **Alt + Q** | 显示/隐藏 | 随时呼出或隐藏主窗口面板。 |
| **Alt + Z** | 截图翻译 | 类似 QQ/微信 截图，框选屏幕任意区域后自动提取文字并翻译。 |
| **右键托盘图标** | 退出程序 | 彻底释放热键与后台进程。 |

---

## 📦 一键打包指南 (Build EXE)

如果你想将其打包为没有任何黑框的绿色独立软件分享给朋友，无需手动配置复杂的 PyInstaller 参数：

只需在项目根目录运行：
```bash
python build_exe.py
```

脚本将自动清理缓存、融合所有依赖项与隐式库（解决 Pydantic/SSL 等玄学报错），并在 `dist/ManboShot` 目录下生成最终可分发的绿色文件夹。

如需构建后同步复制到指定发布目录，可显式传入：

```bash
python build_exe.py --deploy-dir D:\Release\ManboShot
```

默认情况下脚本不会删除或覆盖项目外的固定目录，只会生成 `dist/ManboShot`。

**发布结构**：
将生成的 `ManboShot` 文件夹打个 `.zip` 压缩包即可发给任何人使用。
```text
dist/
└── ManboShot/
    ├── ManboShot.exe  <-- 用户双击运行这个
    └── mpv/           <-- 脚本已自动帮你把依赖复制进来了
```

---

## ⚠️ 注意事项

1. **管理员权限**：为彻底解决全局热键被占用（如被 Snipaste、微信抢占 `Alt+Z`）以及底层剪贴板监听失败的问题，程序启动时会**自动申请提权**。
2. **纯净后台**：应用完全关闭时，会自动猎杀后台所有衍生的 `mpv.exe` 和 `piper.exe` 僵尸进程，绝不泄露系统内存。

---

## 📄 License
MIT License © 2026 Manbo
