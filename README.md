# ManboShot

> Windows 桌面截图、划词与 AI/Google 双引擎翻译工具。

[![Latest release](https://img.shields.io/github/v/release/Bob1837639921/MaoboShot?display_name=tag&style=flat-square)](https://github.com/Bob1837639921/MaoboShot/releases/latest)
[![Platform](https://img.shields.io/badge/platform-Windows-2563EB?style=flat-square)](https://github.com/Bob1837639921/MaoboShot/releases/latest)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/UI-PySide6-41CD52?style=flat-square)](https://doc.qt.io/qtforpython-6/)

ManboShot 是一款常驻系统托盘的 Windows 翻译助手。它可以从剪贴板、手动输入或屏幕截图中获取文字，并行提供 AI 语境翻译与 Google 快速翻译；同时支持 OCR、原文朗读、明暗主题和自定义快捷键。

## 下载

前往 [Releases](https://github.com/Bob1837639921/MaoboShot/releases/latest) 下载最新的 Windows 压缩包。

1. 下载 `ManboShot-windows-x64-*.zip`。
2. 完整解压压缩包，不要只复制其中的 `ManboShot.exe`。
3. 双击 `ManboShot.exe`，程序会在系统托盘中运行。
4. 首次启动可能出现 Windows 权限确认，这是全局快捷键和剪贴板监听所需。

## 功能

| 功能 | 说明 |
| --- | --- |
| AI + Google 双引擎 | Google 优先返回快速结果，AI 通过流式输出提供更自然的语境翻译。两路请求互不阻塞。 |
| OpenAI 兼容接口 | 可自定义 API Key、Base URL 和模型名称，适配常见 OpenAI 兼容服务。未配置 AI 时自动使用纯 Google 模式。 |
| 截图 OCR | 框选屏幕区域后使用 RapidOCR 在本地提取文字，并自动进入翻译流程。支持多显示器与不同缩放比例。 |
| 划词翻译 | 复制选中的文本后自动在光标附近显示翻译窗口。 |
| 可靠的请求反馈 | AI 流式输出、慢响应自动重试、空响应检测和可读的错误提示，Google 结果不会被 AI 超时阻塞。 |
| 语音朗读 | 默认使用 Edge TTS 和 Pygame；也可配置小米 MiMo TTS，或安装可选的 Piper/MPV 本地组件。 |
| 桌面体验 | 系统托盘、明暗主题、可配置全局快捷键、结果复制和紧凑的 OCR 等待状态。 |

## 使用

### 常用操作

| 操作 | 默认方式 |
| --- | --- |
| 显示或隐藏窗口 | `Alt + Q` |
| 截图翻译 | `Alt + E` |
| 划词翻译 | 选中文字后快速复制两次 |
| 手动翻译 | 输入文字后按 `Enter`，`Shift + Enter` 用于换行 |
| 打开设置或退出 | 右键系统托盘图标 |

快捷键可以在“通用设置”中修改。若本机已有软件占用默认组合键，请更换后重试。

### 配置 AI 翻译

打开“设置 → AI 翻译”，填写：

- `API Key`
- `Base URL`
- `Model`

这些配置保存在本机 `%APPDATA%\MaoboShot\config.json`，不会写入项目目录。留空 API Key 时，AI 翻译卡片会自动隐藏，Google 翻译仍可正常使用。

## 从源码运行

需要 Windows 和 Python 3.10 或更高版本。

```powershell
git clone https://github.com/Bob1837639921/MaoboShot.git
cd MaoboShot
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

## 可选语音组件

默认的 Edge TTS + Pygame 无需额外下载。若需要本地 Piper TTS 或 MPV 播放，可在项目根目录创建 `mpv` 文件夹：

```text
mpv/
├── mpv.exe
├── piper.exe
├── zh_CN-huayan-medium.onnx
└── en_US-lessac-medium.onnx
```

程序也支持通过环境变量 `MAOBOSHOT_TOOL_DIR` 指定该目录。可选组件不会包含在默认 Release 中。

## 构建 Windows 版本

```powershell
python build_exe.py
```

输出位于 `dist/ManboShot`。发布时必须压缩并分发整个 `ManboShot` 文件夹，因为 `_internal` 中包含运行依赖。

```text
dist/
└── ManboShot/
    ├── ManboShot.exe
    └── _internal/
```

## 隐私与安全

- OCR 在本机执行；翻译和云端语音内容会发送给对应的服务提供商。
- API Key 仅保存在当前 Windows 用户的配置目录中。
- 请勿提交 `.env`、`config.json`、日志文件或任何真实密钥。
- Release 不包含开发者的本地配置和 API Key。

## 文档

- [版本记录](CHANGELOG.md)
- [维护与发布说明](docs/maintenance.md)

## License

MIT License © 2026 Manbo
