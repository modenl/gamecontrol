from PIL import Image, ImageDraw, ImageFont
import os

def create_icon():
    """创建一个简单的应用程序图标"""
    # 创建一个 256x256 的图像，使用 RGBA 模式支持透明度
    size = 256
    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # 绘制一个圆形背景
    circle_color = (59, 130, 246)  # 蓝色
    draw.ellipse([20, 20, size-20, size-20], fill=circle_color)
    
    # 绘制时钟指针
    center = size // 2
    # 时针
    draw.line([center, center, center, center-60], fill='white', width=8)
    # 分针
    draw.line([center, center, center+80, center], fill='white', width=8)
    
    # 绘制外圈
    draw.ellipse([10, 10, size-10, size-10], outline='white', width=4)
    
    # 保存为 ICO 文件
    image.save('app.ico', format='ICO', sizes=[(256, 256)])

if __name__ == "__main__":
    create_icon() 