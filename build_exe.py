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
        # 将静态资源打包进去 (源目录;目标目录)
        f'--add-data={icon_path};.',
    ]

    # 可选：如果项目里存在 mpv 文件夹，才进行打包
    if mpv_path.exists():
        args.append(f'--add-data={mpv_path};mpv')
    else:
        print(f"Warning: mpv folder not found at {mpv_path}! Skipping its package.")
        print("Tip: This may cause speech to fail. Make sure the mpv folder and its .exe exist.")
        
    # --- 🩹 暴力补全缺失库 (吸收旧 build.py 经验) ---
    args.extend([
        '--collect-all=openai',     # 打包 openai 全家桶
        '--collect-all=jiter',      # 强制打包 jiter (解决 Pydantic/OpenAI 的底层依赖报错)
        '--collect-all=edge_tts',   # 强制打包 edge-tts 资源
        '--collect-all=certifi',    # 打包 SSL 证书 (解决局域网/梯子下的 SSL 报错)
        '--collect-all=rapidocr_onnxruntime', # 强制打包 OCR 的 ONNX 推理模型文件和动态库
        '--collect-all=onnxruntime', # 强制打包 onnxruntime
        
        # --- 🕵️ 隐藏导入 (查漏补缺) ---
        '--hidden-import=jiter',
        '--hidden-import=jiter.jiter',
        '--hidden-import=rapidocr_onnxruntime',
        '--hidden-import=eng_to_ipa',
        '--hidden-import=deep_translator',
        '--hidden-import=PIL',
        '--hidden-import=PySide6.QtNetwork', # Qt 的网络库，部分环境下如果缺失会崩溃
    ])

    print("Starting build...")
    print("Args:", " ".join(args))
    PyInstaller.__main__.run(args)
    print("\nBuild complete! Check dist/ManboShot folder.")

    # --- 🚀 自动部署到指定目录 ---
    source_dir = dist_dir / 'ManboShot'
    target_dir = Path(r"D:\ManboShot\ManboShot")
    
    if source_dir.exists():
        print(f"\nMoving packaged files to {target_dir}...")
        try:
            # 如果目标文件夹已存在，先删除，确保干净覆盖
            if target_dir.exists():
                shutil.rmtree(target_dir)
            
            # 将 dist/ManboShot 复制到 D:\ManboShot\ManboShot
            shutil.copytree(source_dir, target_dir)
            print(f"✅ Automatically deployed to: {target_dir}")
        except Exception as e:
            print(f"❌ Failed to move to {target_dir}: {e}")
    else:
        print("❌ Build output not found. Something went wrong.")

if __name__ == '__main__':
    build()
