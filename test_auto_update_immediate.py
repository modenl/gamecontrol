#!/usr/bin/env python3
"""
直接测试自动更新功能
绕过TaskManager，直接调用UpdateChecker
"""

import sys
import asyncio
import logging
from datetime import datetime

# 设置详细日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("DirectUpdateTest")

async def test_update_checker():
    """直接测试UpdateChecker"""
    logger.info("=" * 60)
    logger.info("🧪 直接测试 UpdateChecker")
    logger.info("=" * 60)
    
    try:
        from logic.auto_updater import UpdateChecker
        from version import __version__
        
        logger.info(f"📋 当前版本: {__version__}")
        
        # 创建更新检查器
        checker = UpdateChecker()
        
        logger.info("🔍 开始检查更新...")
        update_info = await checker.check_for_updates()
        
        if update_info:
            logger.info("🎉 发现更新!")
            logger.info(f"   新版本: {update_info.version}")
            logger.info(f"   文件名: {update_info.asset_name}")
            logger.info(f"   文件大小: {update_info.asset_size:,} 字节")
            logger.info(f"   下载地址: {update_info.download_url}")
            logger.info(f"   发布时间: {update_info.published_at}")
            logger.info(f"   更新说明: {update_info.release_notes[:200]}...")
        else:
            logger.info("ℹ️ 当前已是最新版本")
        
        # 关闭HTTP客户端
        await checker.close()
        
        return update_info
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}", exc_info=True)
        return None

async def test_auto_updater():
    """测试AutoUpdater"""
    logger.info("=" * 60)
    logger.info("🧪 测试 AutoUpdater")
    logger.info("=" * 60)
    
    try:
        from logic.auto_updater import AutoUpdater
        
        # 创建自动更新器（不需要父窗口）
        updater = AutoUpdater(parent=None)
        
        logger.info("🔍 开始异步检查更新...")
        await updater._async_check_for_updates()
        
        logger.info("✅ 异步检查完成")
        
        # 关闭更新器
        await updater.close()
        
    except Exception as e:
        logger.error(f"❌ AutoUpdater测试失败: {e}", exc_info=True)

def main():
    """主函数"""
    logger.info("🚀 开始直接测试自动更新功能")
    logger.info(f"🕐 开始时间: {datetime.now()}")
    
    try:
        # 测试UpdateChecker
        logger.info("📋 第一步：测试UpdateChecker")
        update_info = asyncio.run(test_update_checker())
        
        logger.info("")
        logger.info("📋 第二步：测试AutoUpdater")
        asyncio.run(test_auto_updater())
        
        logger.info("")
        logger.info("✅ 所有测试完成")
        
        if update_info:
            logger.info("🎉 测试结果：发现新版本可用")
            return 0
        else:
            logger.info("ℹ️ 测试结果：当前已是最新版本")
            return 0
            
    except Exception as e:
        logger.error(f"❌ 测试过程中出错: {e}", exc_info=True)
        return 1
    finally:
        logger.info(f"🕐 结束时间: {datetime.now()}")

if __name__ == "__main__":
    print("🧪 直接测试自动更新功能")
    print("=" * 50)
    print("这个测试将直接调用UpdateChecker和AutoUpdater")
    print("绕过TaskManager，查看是否有网络或其他问题")
    print("=" * 50)
    
    try:
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        sys.exit(1) 