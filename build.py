import os
import sys
import shutil
import subprocess
import argparse
import platform

def check_dependencies():
    """检查并安装必要的依赖"""
    required_packages = [
        'pyinstaller',
        'PyQt6',
        'qasync',
        'openai',
        'python-dotenv',
        'pillow',
        'numpy',
        'markdown==3.4.3',
        'python-markdown-math',
        'psutil==5.9.5',
        'pygetwindow',
        'pywin32'
    ]
    
    missing_packages = []
    for package in required_packages:
        package_name = package.split('==')[0].replace('-', '_').replace('python_', '')
        if package_name == 'pygetwindow':
            package_name = 'pygetwindow'
        elif package_name == 'pillow':
            package_name = 'PIL'
        elif package_name == 'PyQt6':
            package_name = 'PyQt6'
            
        try:
            __import__(package_name)
            print(f"✓ {package} already installed")
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"Installing missing packages: {', '.join(missing_packages)}")
        for package in missing_packages:
            print(f"Installing {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    else:
        print("✓ All dependencies are installed")

def create_env_example():
    """创建.env.example文件"""
    if not os.path.exists('.env.example'):
        with open('.env.example', 'w', encoding='utf-8') as f:
            f.write("# OpenAI API Configuration\n")
            f.write("OPENAI_API_KEY=your_api_key_here\n")
        print("✓ Created .env.example file")
    else:
        print("✓ .env.example already exists")

def install_upx():
    """检查UPX是否已安装，如果没有则提示安装"""
    try:
        # 检查UPX是否在PATH中
        subprocess.run(['upx', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        return True
    except FileNotFoundError:
        print("未找到UPX压缩工具，将不使用UPX进行压缩。")
        print("要减小可执行文件大小，请安装UPX: https://upx.github.io/")
        return False

def build(clean=True, optimize=0):
    """构建应用程序
    
    Args:
        clean (bool): 是否清理旧的构建文件
        optimize (int): 优化级别（0=无优化, 1=轻度优化, 2=高度优化）
    """
    print("开始构建应用程序...")
    
    # 检查依赖
    check_dependencies()
    
    # 创建.env.example
    create_env_example()
    
    # 清理旧的构建文件
    if clean:
        print("清理旧的构建文件...")
        if os.path.exists('build'):
            shutil.rmtree('build')
        if os.path.exists('dist'):
            shutil.rmtree('dist')
    else:
        print("保留旧的构建文件...")
    
    # 基本构建命令
    cmd = [
        'pyinstaller',
        '--name=GameTimeLimiter',
        '--windowed',
        '--icon=app.ico',
        '--add-data=.env.example;.',
    ]
    
    # 必要的隐藏导入
    cmd.extend([
        '--hidden-import=win32security',
        '--hidden-import=psutil',
    ])
    
    # 根据优化级别添加额外选项
    if optimize >= 1:
        print("应用轻度优化...")
        # 使用更精确的打包方式减小文件大小
        cmd.append('--noupx')  # 暂时不用UPX，后面会手动应用
        
        # 排除一些不必要的模块
        excludes = [
            'matplotlib.tests', 'numpy.testing', 'scipy', 'pandas', 
            'tk', 'tkinter', 'PyQt5', 'PySide2', 'pytest', 'pyviz', 
            'bokeh', 'seaborn', 'jupyter', 'IPython', 'sphinx'
        ]
        
        for exclude in excludes:
            cmd.append(f'--exclude-module={exclude}')
        
        # 是单文件还是目录
        if optimize == 1:
            cmd.append('--onefile')  # 轻度优化使用单文件模式
        else:
            cmd.append('--onedir')   # 高度优化使用目录模式，提高启动速度
    
    if optimize >= 2:
        print("应用高度优化...")
        # 添加高级优化选项
        cmd.extend([
            '--noconfirm',
            '--clean',
            '--strip',             # 减小文件大小
            '--log-level=WARN',    # 减少日志
        ])
        
        # 更精确的排除模块
        precise_excludes = [
            'matplotlib.backends.backend_tkagg', 'matplotlib.backends.backend_wxagg',
            'PIL.ImageDraw', 'PIL.ImageFilter', 'numpy.distutils', 'numpy.f2py',
            'PyQt6.QtWebEngineCore', 'PyQt6.QtWebEngineWidgets', 'PyQt6.QtMultimedia'
        ]
        
        for exclude in precise_excludes:
            cmd.append(f'--exclude-module={exclude}')
    
    # 最后添加入口点
    cmd.append('main.py')
    
    # 执行构建
    subprocess.check_call(cmd)
    
    # 如果启用高度优化，并且找到了UPX，则压缩可执行文件
    if optimize >= 2 and install_upx():
        try:
            print("使用UPX压缩可执行文件...")
            if os.path.exists('dist/GameTimeLimiter.exe'):
                upx_cmd = ['upx', '--best', '--lzma', 'dist/GameTimeLimiter.exe']
                subprocess.check_call(upx_cmd)
            elif os.path.exists('dist/GameTimeLimiter/GameTimeLimiter.exe'):
                upx_cmd = ['upx', '--best', '--lzma', 'dist/GameTimeLimiter/GameTimeLimiter.exe']
                subprocess.check_call(upx_cmd)
        except Exception as e:
            print(f"UPX压缩失败，跳过: {e}")
    
    print("\n构建完成！")
    
    # 输出最终的可执行文件路径
    if optimize == 2:
        print("可执行文件位于: dist/GameTimeLimiter/GameTimeLimiter.exe")
        print("注意: 使用了目录模式以提高启动速度，请保持文件夹完整性。")
    else:
        print("可执行文件位于: dist/GameTimeLimiter.exe")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='构建游戏时间管理器应用程序')
    parser.add_argument('--no-clean', action='store_true', help='不清除旧的构建文件')
    parser.add_argument('--optimize', type=int, choices=[0, 1, 2], default=0, 
                        help='优化级别: 0=无优化, 1=轻度优化, 2=高度优化(更快启动但使用目录结构)')
    args = parser.parse_args()
    
    build(clean=not args.no_clean, optimize=args.optimize) 