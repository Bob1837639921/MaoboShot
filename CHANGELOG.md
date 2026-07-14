# Changelog

本项目的重要变更记录在此文件中。

## [1.0.0] - 2026-07-14

首个公开发布版本。

### Added

- AI 与 Google 双引擎并行翻译
- OpenAI 兼容 API、模型与 Base URL 配置
- RapidOCR 截图文字识别与自动翻译
- 划词翻译、全局快捷键和系统托盘
- Edge TTS、小米 MiMo TTS 与可选 Piper/MPV 支持
- 明暗主题、结果复制和设置中心

### Improved

- 重构主窗口与设置界面，统一使用通用“AI 翻译”命名
- 增加 AI 流式输出、加载反馈、慢响应自动降级重试和手动重试
- 优化 OCR 等待与无文字反馈界面
- 改善多显示器、不同 DPI 和缩放比例下的截图坐标
- 优化长文本布局、窗口自适应和屏幕边界处理

### Fixed

- 修复 Google 先完成时 AI 卡片可能提前显示为空白的问题
- 修复 AI 空响应被误判为翻译完成的问题
- 修复 Google 翻译英文代码标识符时可能原样返回的问题
- 增强 Google 翻译网络异常与 TLS 失败时的回退处理

[1.0.0]: https://github.com/Bob1837639921/MaoboShot/releases/tag/v1.0.0
