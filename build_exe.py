import argparse
import shutil
from pathlib import Path
import PyInstaller.__main__

EXCLUDED_MODULES = (
    # 未使用的第三方与标准库模块
    "deep_translator",
    "keyboard",
    "pyttsx3",
    "piper",
    "comtypes",
    "sympy",
    "mpmath",
    "tkinter",
    "unittest",
    "pytest",
    "pydoc",
    "doctest",
    # 未使用的 PySide6 模块（仅使用 QtCore / QtGui / QtWidgets / QtNetwork）
    "PySide6.QtQml",
    "PySide6.QtQmlMeta",
    "PySide6.QtQmlModels",
    "PySide6.QtQmlWorkerScript",
    "PySide6.QtQuick",
    "PySide6.QtQuickControls2",
    "PySide6.QtQuickWidgets",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "PySide6.QtSvg",
    "PySide6.QtSvgWidgets",
    "PySide6.QtVirtualKeyboard",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DRender",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtXml",
)

# 打包完成后可安全剔除的冗余动态库、资源与目录（相对于 _internal）
PRUNABLE_INTERNAL_PATHS = (
    "PySide6/opengl32sw.dll",
    "PySide6/Qt6Quick.dll",
    "PySide6/Qt6Qml.dll",
    "PySide6/Qt6QmlMeta.dll",
    "PySide6/Qt6QmlModels.dll",
    "PySide6/Qt6QmlWorkerScript.dll",
    "PySide6/Qt6Pdf.dll",
    "PySide6/Qt6OpenGL.dll",
    "PySide6/Qt6VirtualKeyboard.dll",
    "PySide6/translations",
    "PySide6/plugins/platforminputcontexts",
    "eng_to_ipa/resources/CMU_dict.json",
    "eng_to_ipa/resources/CMU_source_files",
)


def build_pyinstaller_args(project_root: Path, dist_dir: Path, build_dir: Path, spec_dir: Path) -> list[str]:
    icon_path = project_root / "icon.ico"
    assets_path = project_root / "assets"
    mpv_path = project_root / "mpv"

    args = [
        str(project_root / 'main.py'),
        '--name=ManboShot',
        '--noconsole',              # 隐藏控制台黑框
        '--windowed',               # 窗口模式
        '--noconfirm',              # 覆盖不询问
        '--clean',                  # 清理 PyInstaller 缓存
        f'--distpath={dist_dir}',
        f'--workpath={build_dir}',
        f'--specpath={spec_dir}',

        # --- 📦 核心资源 ---
        f'--icon={icon_path}',      # 设置应用图标
        f'--add-data={icon_path};.',
    ]

    if assets_path.exists():
        args.append(f'--add-data={assets_path};assets')

    # 可选：如果项目里存在 mpv 文件夹，才进行打包
    if mpv_path.exists():
        args.append(f'--add-data={mpv_path};mpv')
    else:
        print(f"Warning: mpv folder not found at {mpv_path}! Skipping its package.")
        print("Tip: Default Edge TTS + pygame still works without mpv.")

    # --- 🩹 补全动态加载依赖 ---
    args.extend([
        '--collect-all=openai',               # 打包 openai
        '--collect-all=jiter',                # 打包 jiter (Pydantic/OpenAI 底层依赖)
        '--collect-all=edge_tts',             # 打包 edge-tts
        '--collect-all=certifi',              # 打包 SSL 证书
        '--collect-all=rapidocr_onnxruntime', # 打包 OCR 的 ONNX 推理模型和配置
        '--collect-all=onnxruntime',          # 打包 onnxruntime 动态库

        # --- 🕵️ 隐藏导入 ---
        '--hidden-import=jiter',
        '--hidden-import=jiter.jiter',
        '--hidden-import=rapidocr_onnxruntime',
        '--hidden-import=eng_to_ipa',
        '--hidden-import=PIL',
        '--hidden-import=PIL.Image',
        '--hidden-import=PIL.ImageDraw',
        '--hidden-import=PySide6.QtNetwork',
    ])

    for mod in EXCLUDED_MODULES:
        args.append(f'--exclude-module={mod}')

    return args


def prune_bundle(bundle_dir: Path) -> int:
    """清理 PyInstaller 产物中未被 ManboShot 使用的庞大二进制与资源，返回释放字节数。"""
    internal_dir = bundle_dir / "_internal"
    if not internal_dir.exists():
        return 0

    removed_bytes = 0

    def _remove_path(target: Path):
        nonlocal removed_bytes
        if not target.exists():
            return
        if target.is_dir():
            for child in target.rglob("*"):
                if child.is_file():
                    removed_bytes += child.stat().st_size
            shutil.rmtree(target, ignore_errors=True)
        else:
            removed_bytes += target.stat().st_size
            target.unlink(missing_ok=True)

    for rel in PRUNABLE_INTERNAL_PATHS:
        _remove_path(internal_dir / rel)

    # OpenCV 仅用于图像矩阵处理，不需要 28MB 的 FFmpeg 视频编解码动态库
    cv2_dir = internal_dir / "cv2"
    if cv2_dir.exists():
        for ffmpeg_dll in cv2_dir.glob("opencv_videoio_ffmpeg*.dll"):
            _remove_path(ffmpeg_dll)

    return removed_bytes


def build(deploy_dir=None, output_root=None):
    project_root = Path(__file__).parent.absolute()
    output_root = Path(output_root).expanduser().resolve() if output_root else project_root
    output_root.mkdir(parents=True, exist_ok=True)

    # 清理历史构建
    dist_dir = output_root / 'dist'
    build_dir = output_root / 'build'
    spec_dir = output_root / 'spec'
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    if build_dir.exists():
        shutil.rmtree(build_dir)
    if spec_dir.exists():
        shutil.rmtree(spec_dir)
    spec_dir.mkdir(parents=True, exist_ok=True)

    args = build_pyinstaller_args(project_root, dist_dir, build_dir, spec_dir)

    print("Starting build...")
    print("Args:", " ".join(args))
    PyInstaller.__main__.run(args)

    source_dir = dist_dir / 'ManboShot'
    if source_dir.exists():
        freed_mb = prune_bundle(source_dir) / (1024 * 1024)
        print(f"Pruned unused bundle files: {freed_mb:.1f} MB freed.")
    print("\nBuild complete! Check dist/ManboShot folder.")

    # --- 🚀 可选部署到指定目录 ---
    target_dir = Path(deploy_dir).expanduser().resolve() if deploy_dir else None

    if source_dir.exists() and target_dir:
        print(f"\nMoving packaged files to {target_dir}...")
        try:
            if target_dir.exists():
                shutil.rmtree(target_dir)

            shutil.copytree(source_dir, target_dir)
            print(f"✅ Automatically deployed to: {target_dir}")
        except Exception as e:
            print(f"❌ Failed to move to {target_dir}: {e}")
    elif source_dir.exists():
        print(f"Packaged files are ready at: {source_dir}")
    else:
        print("❌ Build output not found. Something went wrong.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Build MaoboShot with PyInstaller.")
    parser.add_argument(
        "--deploy-dir",
        help="Optional directory to receive a clean copy of dist/ManboShot after build."
    )
    parser.add_argument(
        "--output-root",
        help="Optional isolated root for build, spec, and dist outputs."
    )
    args = parser.parse_args()
    build(args.deploy_dir, args.output_root)
