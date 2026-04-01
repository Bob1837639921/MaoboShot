import PyInstaller.__main__
import os
import shutil
from pathlib import Path

def build():
    # 获取项目根目录
    project_root = Path(__file__).parent.absolute()
    
    # 清理历史构建
    dist_dir = project_root / 'dist'
    build_dir = project_root / 'build'
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    if build_dir.exists():
        shutil.rmtree(build_dir)
        
    icon_path = project_root / "icon.ico"
    mpv_path = project_root / "mpv"

    # 定义打包参数
    args = [
        str(project_root / 'main.py'),
        '--name=ManboShot',
        '--noconsole',              # 隐藏控制台黑框
        '--windowed',               # 窗口模式
        '--noconfirm',              # 覆盖不询问
        '--clean',                  # 清理 PyInstaller 缓存
        
        # --- 📦 核心资源 ---
        f'--icon={icon_path}',      # 设置应用图标
        f'--add-data={icon_path};.', # 把图标塞进程序肚子里 (解决托盘黄点)
        f'--add-data={mpv_path};mpv',# 暴力把外部依赖播放器一并打包进去
        
        # --- 🩹 暴力补全缺失库 (吸收旧 build.py 经验) ---
        '--collect-all=openai',     # 打包 openai 全家桶
        '--collect-all=jiter',      # 强制打包 jiter (解决 Pydantic/OpenAI 的底层依赖报错)
        '--collect-all=edge_tts',   # 强制打包 edge-tts 资源
        '--collect-all=certifi',    # 打包 SSL 证书 (解决局域网/梯子下的 SSL 报错)
        
        # --- 🕵️ 隐藏导入 (查漏补缺) ---
        '--hidden-import=jiter',
        '--hidden-import=jiter.jiter',
        '--hidden-import=rapidocr_onnxruntime',
        '--hidden-import=eng_to_ipa',
        '--hidden-import=deep_translator',
        '--hidden-import=PIL',
        '--hidden-import=PySide6.QtNetwork', # Qt 的网络库，部分环境下如果缺失会崩溃
    ]

    print("🚀 开始清理与准备打包...")
    print("📦 打包参数:", " ".join(args))
    PyInstaller.__main__.run(args)
    print("\n✅ 打包完成！请查看 dist/ManboShot 文件夹，运行里面的 ManboShot.exe 即可。")

if __name__ == '__main__':
    build()
