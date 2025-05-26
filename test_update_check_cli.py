#!/usr/bin/env python3
"""
命令行版本的自动更新测试
不需要GUI，直接测试更新检查逻辑
"""

import asyncio
import logging
import sys
from logic.auto_updater import UpdateChecker
from version import __version__, GITHUB_RELEASES_URL

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_update_check():
    """测试更新检查功能"""
    print("=" * 60)
    print("🧪 Auto-Update CLI Test")
    print("=" * 60)
    print(f"Current version: {__version__}")
    print(f"GitHub API URL: {GITHUB_RELEASES_URL}")
    print("=" * 60)
    
    # 创建更新检查器
    checker = UpdateChecker()
    
    try:
        print("📡 Checking for updates...")
        
        # 检查更新
        update_info = await checker.check_for_updates()
        
        if update_info:
            print("🎉 UPDATE AVAILABLE!")
            print(f"   New version: {update_info.version}")
            print(f"   Current version: {__version__}")
            print(f"   Download URL: {update_info.download_url}")
            print(f"   File size: {update_info.file_size:,} bytes")
            print(f"   Published: {update_info.published_at}")
            print(f"   Release notes preview:")
            print(f"   {update_info.release_notes[:200]}...")
        else:
            print("ℹ️ No updates available")
            print(f"   Current version {__version__} is the latest")
            
    except Exception as e:
        print(f"❌ Update check failed: {e}")
        logger.exception("Update check failed")
        
    finally:
        await checker.close()
        
    print("=" * 60)
    print("✅ Test completed")

def main():
    """主函数"""
    try:
        asyncio.run(test_update_check())
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 