import os
import sys
import shutil
import subprocess
import argparse
import platform

def check_dependencies():
    """Check and install necessary dependencies"""
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
            print(f"[OK] {package} already installed")
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"Installing missing packages: {', '.join(missing_packages)}")
        for package in missing_packages:
            print(f"Installing {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    else:
        print("[OK] All dependencies are installed")

def create_env_example():
    """Create .env.example file"""
    if not os.path.exists('.env.example'):
        with open('.env.example', 'w', encoding='utf-8') as f:
            f.write("# OpenAI API Configuration\n")
            f.write("OPENAI_API_KEY=your_api_key_here\n")
        print("[OK] Created .env.example file")
    else:
        print("[OK] .env.example already exists")

def install_upx():
    """Check if UPX is installed, prompt for installation if not found"""
    try:
        # Check if UPX is in PATH
        subprocess.run(['upx', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        return True
    except FileNotFoundError:
        print("UPX compression tool not found, will not use UPX compression.")
        print("To reduce executable size, install UPX: https://upx.github.io/")
        return False

def build(clean=True, optimize=0):
    """Build application
    
    Args:
        clean (bool): Whether to clean old build files
        optimize (int): Optimization level (0=no optimization, 1=light optimization, 2=high optimization)
    """
    print("Starting application build...")
    
    # Check dependencies
    check_dependencies()
    
    # Create .env.example
    create_env_example()
    
    # Clean old build files
    if clean:
        print("Cleaning old build files...")
        if os.path.exists('build'):
            shutil.rmtree('build')
        if os.path.exists('dist'):
            shutil.rmtree('dist')
    else:
        print("Keeping old build files...")
    
    # Basic build command
    cmd = [
        'pyinstaller',
        '--name=GameTimeLimiter',
        '--windowed',
        '--icon=app.ico',
        '--add-data=.env.example;.',
    ]
    
    # Necessary hidden imports
    cmd.extend([
        '--hidden-import=win32security',
        '--hidden-import=psutil',
    ])
    
    # Add extra options based on optimization level
    if optimize >= 1:
        print("Applying light optimization...")
        # Use more precise packaging to reduce file size
        cmd.append('--noupx')  # Don't use UPX for now, will apply manually later
        
        # Exclude some unnecessary modules
        excludes = [
            'matplotlib.tests', 'numpy.testing', 'scipy', 'pandas', 
            'tk', 'tkinter', 'PyQt5', 'PySide2', 'pytest', 'pyviz', 
            'bokeh', 'seaborn', 'jupyter', 'IPython', 'sphinx'
        ]
        
        for exclude in excludes:
            cmd.append(f'--exclude-module={exclude}')
        
        # Single file or directory
        if optimize == 1:
            cmd.append('--onefile')  # Light optimization uses single file mode
        else:
            cmd.append('--onedir')   # High optimization uses directory mode for faster startup
    
    if optimize >= 2:
        print("Applying high optimization...")
        # Add advanced optimization options
        cmd.extend([
            '--noconfirm',
            '--clean',
            '--strip',             # Reduce file size
            '--log-level=WARN',    # Reduce logging
        ])
        
        # More precise module exclusions
        precise_excludes = [
            'matplotlib.backends.backend_tkagg', 'matplotlib.backends.backend_wxagg',
            'PIL.ImageDraw', 'PIL.ImageFilter', 'numpy.distutils', 'numpy.f2py',
            'PyQt6.QtWebEngineCore', 'PyQt6.QtWebEngineWidgets', 'PyQt6.QtMultimedia'
        ]
        
        for exclude in precise_excludes:
            cmd.append(f'--exclude-module={exclude}')
    
    # Finally add entry point
    cmd.append('main.py')
    
    # Execute build
    subprocess.check_call(cmd)
    
    # If high optimization is enabled and UPX is found, compress executable
    if optimize >= 2 and install_upx():
        try:
            print("Compressing executable with UPX...")
            if os.path.exists('dist/GameTimeLimiter.exe'):
                upx_cmd = ['upx', '--best', '--lzma', 'dist/GameTimeLimiter.exe']
                subprocess.check_call(upx_cmd)
            elif os.path.exists('dist/GameTimeLimiter/GameTimeLimiter.exe'):
                upx_cmd = ['upx', '--best', '--lzma', 'dist/GameTimeLimiter/GameTimeLimiter.exe']
                subprocess.check_call(upx_cmd)
        except Exception as e:
            print(f"UPX compression failed, skipping: {e}")
    
    print("\nBuild completed!")
    
    # Output final executable path
    if optimize == 2:
        print("Executable located at: dist/GameTimeLimiter/GameTimeLimiter.exe")
        print("Note: Directory mode used for faster startup, keep folder integrity.")
    else:
        print("Executable located at: dist/GameTimeLimiter.exe")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Build GameTimeLimiter application')
    parser.add_argument('--no-clean', action='store_true', help='Do not clean old build files')
    parser.add_argument('--optimize', type=int, choices=[0, 1, 2], default=0, 
                        help='Optimization level: 0=no optimization, 1=light optimization, 2=high optimization (faster startup but uses directory structure)')
    args = parser.parse_args()
    
    build(clean=not args.no_clean, optimize=args.optimize) 