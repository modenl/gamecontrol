#!/usr/bin/env python3
"""
修复 Python DLL 加载问题的脚本
用于诊断和解决 PyInstaller 打包应用程序的 DLL 加载错误
"""

import os
import sys
import shutil
import subprocess
import tempfile
import logging
from pathlib import Path

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_dll_dependencies():
    """检查 DLL 依赖"""
    logger.info("🔍 检查 DLL 依赖...")
    
    # 检查当前目录下的可执行文件
    exe_files = []
    for file in os.listdir('.'):
        if file.endswith('.exe'):
            exe_files.append(file)
    
    if not exe_files:
        logger.error("❌ 未找到可执行文件")
        return False
    
    main_exe = None
    for exe in exe_files:
        if 'GameTimeLimiter' in exe:
            main_exe = exe
            break
    
    if not main_exe:
        main_exe = exe_files[0]
    
    logger.info(f"📁 检查可执行文件: {main_exe}")
    
    # 使用 dumpbin 或 objdump 检查依赖（如果可用）
    try:
        result = subprocess.run(['dumpbin', '/dependents', main_exe], 
                              capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            logger.info("📋 DLL 依赖信息:")
            for line in result.stdout.split('\n'):
                if '.dll' in line.lower():
                    logger.info(f"   {line.strip()}")
        else:
            logger.warning("⚠️ 无法使用 dumpbin 检查依赖")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        logger.warning("⚠️ dumpbin 不可用")
    
    return True

def clean_temp_directories():
    """清理临时目录中的残留文件"""
    logger.info("🧹 清理临时目录...")
    
    temp_dirs = [
        tempfile.gettempdir(),
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Temp'),
        os.path.join(os.environ.get('TEMP', ''), ''),
    ]
    
    patterns = [
        '_MEI*',
        'gamecontrol*',
        'GameTimeLimiter*',
        'python*'
    ]
    
    cleaned_count = 0
    
    for temp_dir in temp_dirs:
        if not os.path.exists(temp_dir):
            continue
            
        logger.info(f"📂 检查目录: {temp_dir}")
        
        try:
            for item in os.listdir(temp_dir):
                item_path = os.path.join(temp_dir, item)
                
                # 检查是否匹配模式
                should_clean = False
                for pattern in patterns:
                    if pattern.replace('*', '') in item.lower():
                        should_clean = True
                        break
                
                if should_clean and os.path.isdir(item_path):
                    try:
                        shutil.rmtree(item_path)
                        logger.info(f"✅ 已清理: {item}")
                        cleaned_count += 1
                    except Exception as e:
                        logger.warning(f"⚠️ 无法清理 {item}: {e}")
                        
        except Exception as e:
            logger.warning(f"⚠️ 无法访问 {temp_dir}: {e}")
    
    logger.info(f"🎉 清理完成，共清理 {cleaned_count} 个目录")
    return cleaned_count > 0

def rebuild_application():
    """重新构建应用程序"""
    logger.info("🔨 重新构建应用程序...")
    
    # 检查是否有构建脚本
    if os.path.exists('build.py'):
        logger.info("📝 使用 build.py 重新构建...")
        try:
            # 先清理
            result = subprocess.run([sys.executable, 'cleanup_build.py'], 
                                  capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                logger.info("✅ 清理完成")
            else:
                logger.warning("⚠️ 清理过程有警告")
            
            # 重新构建
            result = subprocess.run([sys.executable, 'build.py', '--no-clean'], 
                                  capture_output=True, text=True, timeout=600)
            if result.returncode == 0:
                logger.info("✅ 重新构建成功")
                return True
            else:
                logger.error(f"❌ 构建失败: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("❌ 构建超时")
            return False
        except Exception as e:
            logger.error(f"❌ 构建过程出错: {e}")
            return False
    else:
        logger.warning("⚠️ 未找到 build.py，无法自动重新构建")
        return False

def check_python_installation():
    """检查 Python 安装"""
    logger.info("🐍 检查 Python 安装...")
    
    try:
        result = subprocess.run([sys.executable, '--version'], 
                              capture_output=True, text=True)
        logger.info(f"📋 Python 版本: {result.stdout.strip()}")
        
        # 检查关键模块
        modules = ['PyQt6', 'qasync', 'psutil', 'numpy']
        for module in modules:
            try:
                __import__(module)
                logger.info(f"✅ {module} 可用")
            except ImportError:
                logger.error(f"❌ {module} 不可用")
                
    except Exception as e:
        logger.error(f"❌ Python 检查失败: {e}")

def create_launcher_script():
    """创建启动器脚本"""
    logger.info("📝 创建启动器脚本...")
    
    launcher_content = """@echo off
echo Starting GameTimeLimiter...

REM Set working directory to script location
cd /d "%~dp0"

REM Clean up any temporary PyInstaller files
echo Cleaning temporary files...
for /d %%d in ("%TEMP%\\_MEI*") do rmdir /s /q "%%d" 2>nul
for /d %%d in ("%LOCALAPPDATA%\\Temp\\_MEI*") do rmdir /s /q "%%d" 2>nul

REM Start the application
echo Starting application...
if exist "GameTimeLimiter.exe" (
    start "" "GameTimeLimiter.exe"
) else if exist "dist\\GameTimeLimiter.exe" (
    start "" "dist\\GameTimeLimiter.exe"
) else if exist "dist\\GameTimeLimiter\\GameTimeLimiter.exe" (
    start "" "dist\\GameTimeLimiter\\GameTimeLimiter.exe"
) else (
    echo Error: GameTimeLimiter.exe not found
    pause
    exit /b 1
)

echo Application started
"""
    
    with open('start_gametimelimiter.bat', 'w', encoding='utf-8') as f:
        f.write(launcher_content)
    
    logger.info("✅ 启动器脚本已创建: start_gametimelimiter.bat")

def main():
    """主函数"""
    logger.info("🚀 开始修复 Python DLL 加载问题...")
    
    try:
        # 步骤 1: 检查 Python 安装
        check_python_installation()
        
        # 步骤 2: 检查 DLL 依赖
        check_dll_dependencies()
        
        # 步骤 3: 清理临时目录
        if clean_temp_directories():
            logger.info("✅ 临时文件清理完成")
        
        # 步骤 4: 创建启动器脚本
        create_launcher_script()
        
        # 步骤 5: 询问是否重新构建
        print("\n" + "="*60)
        print("修复建议:")
        print("1. 使用新创建的 start_gametimelimiter.bat 启动应用程序")
        print("2. 如果问题仍然存在，重新构建应用程序")
        print("3. 确保所有依赖都正确安装")
        print("="*60)
        
        choice = input("\n是否现在重新构建应用程序? (y/N): ").lower().strip()
        if choice in ['y', 'yes']:
            if rebuild_application():
                logger.info("🎉 应用程序重新构建成功！")
                print("\n✅ 修复完成！请尝试运行新构建的应用程序。")
            else:
                logger.error("❌ 重新构建失败")
                print("\n❌ 自动重新构建失败，请手动运行: python build.py")
        else:
            print("\n💡 你可以稍后手动运行: python build.py")
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("❌ 用户中断操作")
        return 1
    except Exception as e:
        logger.error(f"❌ 修复过程出错: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    input("\n按回车键退出...")
    sys.exit(exit_code) 