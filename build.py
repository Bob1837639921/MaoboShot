import PyInstaller.__main__
import shutil
import os

# 1. 清理旧的构建文件夹 (彻底防止缓存干扰)
print("🧹 正在清理旧的构建文件...")
if os.path.exists("dist"):
    shutil.rmtree("dist")
if os.path.exists("build"):
    shutil.rmtree("build")

# 2. 定义打包参数
params = [
    'ManboShot.py',                # 主程序文件
    '-n', 'ManboShot',             # 生成的 EXE 名字
    '--distpath', 'D:\ManboShot', # 指定输出目录
    '--onedir',                    # -F 单文件模式
    '--windowed',                  # -w 无黑框模式
    '--noconfirm',                 # 覆盖不询问
    '--clean',                     # 清理缓存
    
    # --- 📦 核心资源 ---
    '--icon=icon.ico',             # 设为你的图标
    '--add-data=icon.ico;.',       # 把图标塞进程序肚子里 (解决托盘黄点)
    
    # --- 🩹 暴力补全缺失库 ---
    '--collect-all=openai',        # 打包 openai 全家桶
    '--collect-all=jiter',         # 🔥 强制打包 jiter (解决你的报错)
    '--collect-all=edge_tts',      # 打包 edge-tts
    '--collect-all=certifi',       # 打包 SSL 证书 (解决谷歌翻译失败)
    '--collect-all=engineio',      # 打包网络引擎
    
    # --- 🕵️ 隐藏导入 (查漏补缺) ---
    '--hidden-import=engineio.async_drivers.threading',
    '--hidden-import=jiter',       # 双重保险
    '--hidden-import=jiter.jiter', # 三重保险 (针对诡异的报错路径)
]

print("📦 开始打包...")
PyInstaller.__main__.run(params)

print("\n✅ 打包完成！")
print("📂 请去 dist/ManboShot 文件夹里运行 ManboShot.exe")
print("⚠️ 别忘了把 mpv 文件夹和 .env 文件复制进去！")