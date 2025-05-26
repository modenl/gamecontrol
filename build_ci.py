#!/usr/bin/env python3
"""
Simplified build script for CI environments
Avoids complex file operations that might fail in GitHub Actions
"""

import os
import sys
import subprocess
import shutil
import argparse
import traceback

def check_file_exists(filepath, description):
    """Check if a file exists and log the result"""
    if os.path.exists(filepath):
        size = os.path.getsize(filepath)
        print(f"[CI BUILD] ✓ {description}: {filepath} ({size} bytes)")
        return True
    else:
        print(f"[CI BUILD] ✗ {description}: {filepath} NOT FOUND")
        return False

def main():
    parser = argparse.ArgumentParser(description='Build GameTimeLimiter for CI')
    parser.add_argument('--optimize', type=int, default=1, choices=[0, 1, 2],
                       help='Optimization level (0=none, 1=basic, 2=advanced)')
    args = parser.parse_args()
    
    print(f"[CI BUILD] Starting build with optimization level {args.optimize}")
    print(f"[CI BUILD] Python version: {sys.version}")
    print(f"[CI BUILD] Working directory: {os.getcwd()}")
    print(f"[CI BUILD] Python executable: {sys.executable}")
    
    # Check required files exist
    required_files = ['main.py', 'app.ico', 'requirements.txt']
    for file in required_files:
        if not check_file_exists(file, f"Required file"):
            print(f"[CI BUILD] ERROR: Missing required file: {file}")
            return 1
    
    # Check directories
    required_dirs = ['ui', 'logic']
    for dir in required_dirs:
        if os.path.exists(dir):
            files = os.listdir(dir)
            print(f"[CI BUILD] ✓ Directory {dir}: {len(files)} files")
        else:
            print(f"[CI BUILD] ✗ Directory {dir}: NOT FOUND")
            return 1
    
    # Clean dist directory if it exists
    if os.path.exists('dist'):
        print("[CI BUILD] Removing existing dist directory...")
        try:
            shutil.rmtree('dist')
            print("[CI BUILD] ✓ Dist directory removed")
        except Exception as e:
            print(f"[CI BUILD] Warning: Could not remove dist directory: {e}")
    
    # Clean build directory if it exists
    if os.path.exists('build'):
        print("[CI BUILD] Removing existing build directory...")
        try:
            shutil.rmtree('build')
            print("[CI BUILD] ✓ Build directory removed")
        except Exception as e:
            print(f"[CI BUILD] Warning: Could not remove build directory: {e}")
    
    # Verify critical imports with detailed error reporting
    print("[CI BUILD] Verifying critical imports...")
    try:
        import PyQt6
        print(f"[CI BUILD] ✓ PyQt6 version: {PyQt6.QtCore.PYQT_VERSION_STR}")
        print(f"[CI BUILD] ✓ Qt version: {PyQt6.QtCore.QT_VERSION_STR}")
    except ImportError as e:
        print(f"[CI BUILD] ✗ PyQt6 import failed: {e}")
        print(f"[CI BUILD] Traceback: {traceback.format_exc()}")
        return 1
    
    try:
        import psutil
        print(f"[CI BUILD] ✓ psutil version: {psutil.__version__}")
    except ImportError as e:
        print(f"[CI BUILD] ✗ psutil import failed: {e}")
        print(f"[CI BUILD] Traceback: {traceback.format_exc()}")
        return 1
    
    try:
        import qasync
        print(f"[CI BUILD] ✓ qasync imported successfully")
    except ImportError as e:
        print(f"[CI BUILD] ✗ qasync import failed: {e}")
        print(f"[CI BUILD] Traceback: {traceback.format_exc()}")
        return 1
    
    try:
        import openai
        print(f"[CI BUILD] ✓ openai version: {openai.__version__}")
    except ImportError as e:
        print(f"[CI BUILD] ✗ openai import failed: {e}")
        print(f"[CI BUILD] Traceback: {traceback.format_exc()}")
        return 1
    
    # Build command
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--name=GameTimeLimiter',
        '--onefile',
        '--windowed',
        '--icon=app.ico',
        '--add-data=ui;ui',
        '--add-data=logic;logic',
        '--add-data=.env.example;.',
        '--hidden-import=PyQt6.QtCore',
        '--hidden-import=PyQt6.QtGui',
        '--hidden-import=PyQt6.QtWidgets',
        '--hidden-import=qasync',
        '--hidden-import=openai',
        '--hidden-import=psutil',
        '--hidden-import=pygetwindow',
        '--collect-all=PyQt6',
        '--noconfirm',
        '--log-level=DEBUG',  # Add debug logging
        'main.py'
    ]
    
    # Add optimization flags
    if args.optimize >= 1:
        cmd.extend(['--optimize', '1'])
    if args.optimize >= 2:
        cmd.extend(['--strip'])
    
    print(f"[CI BUILD] Running PyInstaller command:")
    print(f"[CI BUILD] {' '.join(cmd)}")
    print("[CI BUILD] " + "="*50)
    
    try:
        # Run with real-time output
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Print output in real-time
        for line in process.stdout:
            print(f"[PYINSTALLER] {line.rstrip()}")
        
        process.wait()
        
        if process.returncode == 0:
            print("[CI BUILD] ✓ PyInstaller completed successfully")
        else:
            print(f"[CI BUILD] ✗ PyInstaller failed with return code {process.returncode}")
            return 1
            
    except Exception as e:
        print(f"[CI BUILD] ✗ PyInstaller execution failed: {e}")
        print(f"[CI BUILD] Traceback: {traceback.format_exc()}")
        return 1
    
    # Verify the build
    exe_path = os.path.join('dist', 'GameTimeLimiter.exe')
    if os.path.exists(exe_path):
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
        print(f"[CI BUILD] ✓ SUCCESS: Built {exe_path} ({size_mb:.1f} MB)")
        
        # List all files in dist
        print("[CI BUILD] Dist directory contents:")
        for root, dirs, files in os.walk('dist'):
            for file in files:
                filepath = os.path.join(root, file)
                size = os.path.getsize(filepath)
                print(f"[CI BUILD]   {filepath}: {size} bytes")
        
        return 0
    else:
        print(f"[CI BUILD] ✗ ERROR: Expected executable not found at {exe_path}")
        
        # Debug: check what was actually created
        if os.path.exists('dist'):
            print("[CI BUILD] Dist directory exists but exe not found. Contents:")
            for root, dirs, files in os.walk('dist'):
                for file in files:
                    filepath = os.path.join(root, file)
                    size = os.path.getsize(filepath)
                    print(f"[CI BUILD]   {filepath}: {size} bytes")
        else:
            print("[CI BUILD] Dist directory does not exist")
        
        return 1

if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as e:
        print(f"[CI BUILD] FATAL ERROR: {e}")
        print(f"[CI BUILD] Traceback: {traceback.format_exc()}")
        sys.exit(1) 