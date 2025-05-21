import os
import sys
import shutil
from tkinter import messagebox
from dotenv import load_dotenv

def setup_env_file():
    """检查并创建.env文件"""
    # 获取程序运行路径
    if getattr(sys, 'frozen', False):
        # 如果是打包后的exe
        app_path = os.path.dirname(sys.executable)
    else:
        # 如果是开发环境
        app_path = os.path.dirname(os.path.abspath(__file__))
        # 如果是在logic目录中，需要回到上层目录
        if os.path.basename(app_path) == 'logic':
            app_path = os.path.dirname(app_path)
    
    env_path = os.path.join(app_path, '.env')
    env_example_path = os.path.join(app_path, '.env.example')
    
    if not os.path.exists(env_path):
        if os.path.exists(env_example_path):
            shutil.copy(env_example_path, env_path)
            messagebox.showinfo("配置", "已创建.env文件，请在其中设置你的OpenAI API密钥")
        else:
            # 创建.env文件
            with open(env_path, 'w', encoding='utf-8') as f:
                f.write("# OpenAI API Configuration\n")
                f.write("OPENAI_API_KEY=your_api_key_here\n")
            messagebox.showinfo("配置", "已创建.env文件，请在其中设置你的OpenAI API密钥")

def check_dependencies():
    """检查必要的依赖是否已安装"""
    required_modules = ["win32security"]
    missing_modules = []
    
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing_modules.append(module)
    
    if missing_modules:
        error_message = "以下模块缺失，程序可能无法正常运行：\n" + "\n".join(missing_modules)
        error_message += "\n\n请使用pip安装缺失的模块，例如：\npip install pywin32"
        messagebox.showerror("依赖缺失", error_message)
        return False
    
    return True

def initialize_app():
    """初始化应用程序环境"""
    # 检查.env文件
    setup_env_file()
    
    # 加载环境变量
    load_dotenv()
    
    # 检查依赖
    if not check_dependencies():
        return False
    
    return True 