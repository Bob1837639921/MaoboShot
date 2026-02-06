from PIL import Image

# 1. 确保安装了 Pillow 库
# pip install Pillow

# 2. 读取你的 PNG 图片
# 记得把文件名改成你实际的文件名
img_path = 'icon.png' 
img = Image.open(img_path)

# 3. 重新采样并保存为包含多个尺寸的 ICO
# 这一步非常关键，它会生成一个文件包，Windows 会根据场景自动选用清晰度最高的那个
img.save('icon.ico', format='ICO', sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])

print("成功！app.ico 已经生成，背景是透明的，且包含所有标准尺寸。")