# MaoboShot 维护说明

本文档记录项目当前的配置、资源路径和发布流程，方便后续维护时少踩路径、密钥和打包相关的问题。

## 配置文件

真实用户配置不再放在仓库根目录，而是写入：

```text
%APPDATA%\MaoboShot\config.json
```

仓库中的 `config.example.json` 是模板文件，可以复制字段结构，但不要填写真实 API Key 后提交。

配置字段：

| 字段 | 说明 |
| --- | --- |
| `DOUBAO_API_KEY` | 火山引擎 / 豆包 API Key，留空时只使用 Google 翻译 |
| `DOUBAO_MODEL_EP` | 豆包模型接入点 |
| `THEME` | `light` 或 `dark` |
| `USE_LOCAL_TTS` | 是否启用短文本本地 Piper TTS |

## 资源路径

程序默认按以下优先级查找外部工具目录：

1. 环境变量 `MAOBOSHOT_TOOL_DIR`
2. 程序或项目根目录下的 `mpv`
3. PyInstaller 资源目录中的 `mpv`

`mpv` 目录需要包含：

```text
mpv.exe
piper.exe
zh_CN-huayan-medium.onnx
en_US-lessac-medium.onnx
```

## 打包发布

普通构建：

```bash
python build_exe.py
```

输出目录：

```text
dist/ManboShot
```

构建后复制到发布目录：

```bash
python build_exe.py --deploy-dir D:\Release\ManboShot
```

只有显式传入 `--deploy-dir` 时，脚本才会清理并覆盖目标发布目录。

## 安全注意

- 不要提交 `config.json`、`.env`、日志文件或任何真实密钥。
- 如果密钥曾经进入 Git 历史，应立即在服务商控制台轮换。
- 翻译结果进入 UI 前会做 HTML 转义，后续新增富文本片段时也要保持这个规则。

## 退出清理

窗口关闭时会注销全局热键、移除剪贴板监听，并关闭翻译线程池。TTS 生成的临时 wav 文件会写入系统临时目录，播放结束后自动删除。
