#!/usr/bin/env python3
"""
测试自动更新核心逻辑
直接测试 UpdateChecker 和下载功能
"""

import asyncio
import logging
import sys
import os

# 设置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_update_checker():
    """测试更新检查器"""
    print("=" * 60)
    print("🧪 测试 UpdateChecker")
    print("=" * 60)
    
    try:
        from logic.auto_updater import UpdateChecker
        from version import __version__
        
        print(f"📋 当前版本: {__version__}")
        
        # 创建更新检查器
        checker = UpdateChecker()
        
        print("🔍 开始检查更新...")
        update_info = await checker.check_for_updates()
        
        if update_info:
            print("🎉 发现更新!")
            print(f"   新版本: {update_info.version}")
            print(f"   文件名: {update_info.asset_name}")
            print(f"   文件大小: {update_info.asset_size:,} 字节")
            print(f"   下载地址: {update_info.download_url}")
            print(f"   发布时间: {update_info.published_at}")
            print(f"   更新说明: {update_info.release_notes[:100]}...")
            
            return update_info
        else:
            print("ℹ️ 没有可用更新")
            return None
            
    except Exception as e:
        print(f"❌ 更新检查失败: {e}")
        logger.exception("更新检查失败")
        return None
    finally:
        if 'checker' in locals():
            await checker.close()

async def test_download(update_info):
    """测试下载功能"""
    print("\n" + "=" * 60)
    print("🧪 测试下载功能")
    print("=" * 60)
    
    if not update_info:
        print("⚠️ 没有更新信息，跳过下载测试")
        return None
    
    try:
        from logic.auto_updater import UpdateDownloader
        
        # 创建下载器
        downloader = UpdateDownloader()
        
        print(f"📥 开始下载: {update_info.asset_name}")
        print(f"   大小: {update_info.asset_size:,} 字节")
        print(f"   URL: {update_info.download_url}")
        
        # 设置进度回调
        def on_progress(downloaded, total):
            if total > 0:
                percentage = (downloaded / total) * 100
                print(f"   进度: {percentage:.1f}% ({downloaded:,}/{total:,} 字节)")
        
        # 连接进度信号（简化版本）
        downloader._emit_progress = on_progress
        
        # 开始下载
        download_path = await downloader.download_update(update_info)
        
        print(f"✅ 下载完成: {download_path}")
        
        # 验证文件
        if os.path.exists(download_path):
            file_size = os.path.getsize(download_path)
            print(f"   文件大小: {file_size:,} 字节")
            
            if file_size == update_info.asset_size:
                print("✅ 文件大小验证通过")
            else:
                print(f"⚠️ 文件大小不匹配: 期望 {update_info.asset_size:,}，实际 {file_size:,}")
        else:
            print("❌ 下载的文件不存在")
            return None
        
        return download_path
        
    except Exception as e:
        print(f"❌ 下载失败: {e}")
        logger.exception("下载失败")
        return None
    finally:
        if 'downloader' in locals():
            await downloader.close()

async def test_install_simulation(download_path):
    """模拟安装过程"""
    print("\n" + "=" * 60)
    print("🧪 模拟安装过程")
    print("=" * 60)
    
    if not download_path or not os.path.exists(download_path):
        print("⚠️ 没有有效的下载文件，跳过安装测试")
        return
    
    try:
        import tempfile
        import shutil
        from version import __version__, UPDATE_BACKUP_ENABLED
        
        print(f"📦 下载文件: {download_path}")
        
        # 模拟获取当前可执行文件路径
        if hasattr(sys, 'frozen'):
            current_exe = sys.executable
        else:
            current_exe = os.path.abspath(sys.argv[0])
        
        current_dir = os.path.dirname(current_exe)
        print(f"📁 当前目录: {current_dir}")
        print(f"📄 当前可执行文件: {current_exe}")
        
        # 模拟备份过程
        if UPDATE_BACKUP_ENABLED:
            backup_dir = os.path.join(current_dir, "backup")
            print(f"📂 备份目录: {backup_dir}")
            
            if not os.path.exists(backup_dir):
                print("   创建备份目录...")
                # os.makedirs(backup_dir, exist_ok=True)  # 注释掉实际操作
            
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"GameTimeLimiter_v{__version__}_{timestamp}.exe"
            backup_path = os.path.join(backup_dir, backup_name)
            print(f"   备份文件: {backup_path}")
            
            # 模拟备份
            print("   📋 模拟备份当前版本...")
            # shutil.copy2(current_exe, backup_path)  # 注释掉实际操作
        
        # 模拟创建更新脚本
        script_path = os.path.join(tempfile.gettempdir(), "gamecontrol_update.bat")
        print(f"📝 更新脚本: {script_path}")
        
        script_content = f"""@echo off
echo Starting GameTimeLimiter update process...

REM Wait for main process to exit
timeout /t 3 /nobreak >nul

echo Installing update executable...
copy /y "{download_path}" "{current_exe}"
if errorlevel 1 (
    echo Failed to copy update file
    pause
    exit /b 1
)

REM Clean up temporary files
del /q "{download_path}" 2>nul

echo Update completed successfully!
echo Restarting application...

REM Start the updated application
start "" "{current_exe}"

REM Clean up this script
del /q "%~f0" 2>nul
"""
        
        print("📋 更新脚本内容:")
        print(script_content)
        
        # 模拟写入脚本
        print("✅ 更新脚本创建成功（模拟）")
        
        print("\n🚀 在实际情况下，程序会:")
        print("   1. 执行更新脚本")
        print("   2. 退出当前程序")
        print("   3. 脚本等待3秒")
        print("   4. 复制新文件覆盖旧文件")
        print("   5. 重启程序")
        print("   6. 清理临时文件")
        
        # 清理下载文件（测试用）
        print(f"\n🧹 清理测试下载文件: {download_path}")
        try:
            os.remove(download_path)
            print("✅ 清理完成")
        except:
            print("⚠️ 清理失败")
        
    except Exception as e:
        print(f"❌ 安装模拟失败: {e}")
        logger.exception("安装模拟失败")

async def main():
    """主测试函数"""
    print("🚀 开始自动更新核心逻辑测试")
    print("=" * 70)
    
    try:
        # 步骤1: 测试更新检查
        update_info = await test_update_checker()
        
        if update_info:
            # 步骤2: 测试下载
            download_path = await test_download(update_info)
            
            if download_path:
                # 步骤3: 模拟安装
                await test_install_simulation(download_path)
            else:
                print("\n❌ 下载失败，无法进行安装测试")
        else:
            print("\n❌ 没有可用更新，无法进行下载和安装测试")
    
    except Exception as e:
        print(f"\n❌ 测试过程中出错: {e}")
        logger.exception("测试失败")
    
    print("\n" + "=" * 70)
    print("✅ 测试完成")
    print("=" * 70)

if __name__ == "__main__":
    # 运行测试
    asyncio.run(main()) 