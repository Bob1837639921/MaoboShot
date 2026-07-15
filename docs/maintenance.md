# ManboShot 维护与发布说明

本文档面向项目维护者，记录配置边界、翻译状态、资源路径和 Release 流程。

## 配置边界

真实用户配置只保存在：

```text
%APPDATA%\MaoboShot\config.json
```

仓库中的 `config.example.json` 只用于描述字段结构。程序不会读取项目根目录下的 `config.json`，也不应把真实密钥写入源码或构建目录。

| 字段 | 说明 |
| --- | --- |
| `DOUBAO_API_KEY` | AI 翻译 API Key；字段名为历史兼容保留，界面统一称为“AI 翻译” |
| `DOUBAO_MODEL_EP` | OpenAI 兼容接口使用的模型名称或接入点 |
| `AI_BASE_URL` | OpenAI 兼容接口地址 |
| `THEME` | `light` 或 `dark` |
| `USE_LOCAL_TTS` | 是否优先使用本地 Piper TTS |
| `AI_TTS_PROVIDER` | `edge` 或 `xiaomi` |
| `XIAOMI_TTS_API_KEY` | 小米 MiMo TTS 或兼容网关 Key |
| `XIAOMI_TTS_BASE_URL` | 小米 MiMo OpenAI 兼容接口地址 |
| `XIAOMI_TTS_MODEL` | 小米 TTS 模型名称 |
| `XIAOMI_TTS_VOICE` | 小米 TTS 音色 |
| `XIAOMI_TTS_STYLE` | 可选语音风格 |
| `AUDIO_PLAYER` | `pygame` 或 `mpv` |
| `HOTKEY_SHOW` | 显示/隐藏窗口快捷键 |
| `HOTKEY_SNIP` | 截图翻译快捷键 |

## 翻译任务模型

AI 与 Google 翻译由线程池并行执行。修改相关逻辑时需要保持以下约束：

- 两路 loading 状态必须合并保存，不能让先完成的请求覆盖另一条仍在执行的状态。
- AI 流式响应为空、连接失败或超时时，自动降级为一次非流式请求。
- API 错误通过独立的 `doubao_error` 字段传给 UI，不要把错误文本混入翻译结果。
- UI 必须对“结束但结果为空”做防御性处理，并提供手动重试入口。
- 新请求通过 task id 废弃旧请求，避免过期结果覆盖当前文本。
- 所有进入富文本标签的外部内容都必须先进行 HTML 转义。

## 外部资源

程序按以下顺序查找 `mpv`/Piper 工具目录：

1. 环境变量 `MAOBOSHOT_TOOL_DIR`
2. 程序或项目根目录下的 `mpv`
3. PyInstaller 资源目录中的 `mpv`

可选目录结构：

```text
mpv/
├── mpv.exe
├── piper.exe
├── zh_CN-huayan-medium.onnx
└── en_US-lessac-medium.onnx
```

没有该目录时，Edge TTS 与 Pygame 仍可使用；默认 Release 不包含这些可选二进制和模型。

## 本地验证

提交或发布前至少运行：

```powershell
.\.venv\Scripts\python.exe -m compileall -q core ui utils main.py build_exe.py
git diff --check
```

涉及界面状态时，还应验证：

- AI/Google 加载、成功、部分失败与重试状态
- OCR 识别中、无文字和识别成功状态
- 五套可切换主题（经典深色、经典浅色、暗夜地形、冰霜蓝图、信号甲板）
- 不同窗口宽度和多显示器缩放
- 全局快捷键与托盘退出

## 构建

```powershell
.\.venv\Scripts\python.exe .\build_exe.py
```

输出目录：

```text
dist/ManboShot/
```

`ManboShot.exe` 依赖同目录下的 `_internal`，发布时必须压缩整个文件夹。只有显式传入 `--deploy-dir` 时，构建脚本才会覆盖项目外的目标目录。

## Release 检查清单

1. 确认工作区干净，目标提交已推送到 `main`。
2. 完成编译检查与核心交互验证。
3. 重新构建 `dist/ManboShot`，不要复用旧成品。
4. 检查构建目录中不存在 `.env`、`config.json`、日志或真实密钥。
5. 将完整目录压缩为 `ManboShot-windows-x64-vX.Y.Z.zip`。
6. 计算 SHA256，并在 Release 说明中提供校验值。
7. 创建 `vX.Y.Z` 标签，上传压缩包并发布非草稿 Release。
8. 下载 Release 资产进行一次解压启动验证。

## 安全注意

- 不要提交 `.env`、`config.json`、日志文件或任何真实密钥。
- 密钥若曾进入 Git 历史，应立即在服务商控制台轮换。
- TTS 临时音频写入系统临时目录，播放结束后应清理。
- 窗口退出时应注销全局热键、移除剪贴板监听并关闭翻译线程池。
