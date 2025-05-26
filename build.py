import os
import sys
import shutil
import subprocess
import argparse
import platform
import time
import psutil

def check_dependencies():
    """Check and install necessary dependencies"""
    # 检查 Python 版本
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    print(f"[INFO] Using Python {python_version}")
    
    if sys.version_info < (3, 10):
        print("[WARNING] Python 3.10+ recommended for best compatibility")
    elif sys.version_info >= (3, 14):
        print("[WARNING] Python version may be too new, consider using 3.13")
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

def kill_processes_using_directory(directory):
    """Kill processes that might be using files in the directory"""
    if not os.path.exists(directory):
        return
    
    print(f"Checking for processes using files in {directory}...")
    killed_processes = []
    
    try:
        for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline']):
            try:
                # Check if process executable is in the directory
                if proc.info['exe'] and directory.lower() in proc.info['exe'].lower():
                    print(f"Found process using directory: {proc.info['name']} (PID: {proc.info['pid']})")
                    proc.terminate()
                    killed_processes.append(proc.info['name'])
                    continue
                
                # Check command line arguments
                if proc.info['cmdline']:
                    cmdline = ' '.join(proc.info['cmdline'])
                    if directory.lower() in cmdline.lower():
                        print(f"Found process with directory in cmdline: {proc.info['name']} (PID: {proc.info['pid']})")
                        proc.terminate()
                        killed_processes.append(proc.info['name'])
                        
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    except Exception as e:
        print(f"Warning: Could not check all processes: {e}")
    
    if killed_processes:
        print(f"Terminated processes: {', '.join(set(killed_processes))}")
        time.sleep(2)  # Give processes time to terminate
    
    return len(killed_processes) > 0

def safe_rmtree(path, max_retries=5):
    """Safely remove directory tree with retries for Windows file locking issues"""
    if not os.path.exists(path):
        return True
    
    print(f"Removing directory: {path}")
    
    for attempt in range(max_retries):
        try:
            # First attempt: normal removal
            shutil.rmtree(path)
            print(f"Successfully removed {path}")
            return True
            
        except PermissionError as e:
            print(f"Attempt {attempt + 1}/{max_retries}: Permission denied - {e}")
            
            if attempt == 0:
                # First retry: try to kill processes using the directory
                if kill_processes_using_directory(os.path.abspath(path)):
                    print("Killed processes, retrying...")
                    time.sleep(1)
                    continue
            
            # Try PowerShell Remove-Item as fallback (Windows-specific)
            if platform.system() == "Windows" and attempt == 1:
                try:
                    print("Trying PowerShell Remove-Item...")
                    import subprocess
                    result = subprocess.run([
                        'powershell', '-Command', 
                        f'Remove-Item -Path "{path}" -Recurse -Force -ErrorAction SilentlyContinue'
                    ], capture_output=True, text=True, timeout=30)
                    
                    if result.returncode == 0 and not os.path.exists(path):
                        print(f"Successfully removed {path} using PowerShell")
                        return True
                    else:
                        print("PowerShell removal failed or incomplete")
                except Exception as ps_e:
                    print(f"PowerShell removal failed: {ps_e}")
            
            if attempt < max_retries - 1:
                # Try to change permissions and retry
                try:
                    print("Attempting to change file permissions...")
                    for root, dirs, files in os.walk(path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            try:
                                os.chmod(file_path, 0o777)
                            except:
                                pass
                        for dir in dirs:
                            dir_path = os.path.join(root, dir)
                            try:
                                os.chmod(dir_path, 0o777)
                            except:
                                pass
                except:
                    pass
                
                print(f"Waiting {2 * (attempt + 1)} seconds before retry...")
                time.sleep(2 * (attempt + 1))
            else:
                print(f"Failed to remove {path} after {max_retries} attempts")
                print("You may need to:")
                print("1. Close any file explorers or editors that might have files open")
                print("2. Run the build script as administrator")
                print("3. Manually delete the directory and try again")
                print("4. Try: Remove-Item -Path \"" + path + "\" -Recurse -Force")
                return False
                
        except Exception as e:
            print(f"Attempt {attempt + 1}/{max_retries}: Unexpected error - {e}")
            if attempt < max_retries - 1:
                time.sleep(1)
            else:
                print(f"Failed to remove {path}: {e}")
                return False
    
    return False

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
        
        # Use safe removal for build directory
        if os.path.exists('build'):
            if not safe_rmtree('build'):
                print("Warning: Could not completely remove build directory")
        
        # Use safe removal for dist directory
        if os.path.exists('dist'):
            if not safe_rmtree('dist'):
                print("Error: Could not remove dist directory. Build cannot continue.")
                print("\nTroubleshooting steps:")
                print("1. Close any file explorers showing the dist folder")
                print("2. Close any running GameTimeLimiter processes")
                print("3. Run: python cleanup_processes.py --auto")
                print("4. Try building again")
                return False
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
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as e:
        print(f"Build failed with error: {e}")
        return False
    
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
    
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Build GameTimeLimiter application')
    parser.add_argument('--no-clean', action='store_true', help='Do not clean old build files')
    parser.add_argument('--optimize', type=int, choices=[0, 1, 2], default=0, 
                        help='Optimization level: 0=no optimization, 1=light optimization, 2=high optimization (faster startup but uses directory structure)')
    args = parser.parse_args()
    
    success = build(clean=not args.no_clean, optimize=args.optimize)
    if not success:
        sys.exit(1) 