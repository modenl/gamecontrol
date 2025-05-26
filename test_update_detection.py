#!/usr/bin/env python3
"""
测试更新检测功能
"""

import asyncio
import logging
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_update_check():
    """测试更新检查功能"""
    try:
        from logic.auto_updater import UpdateChecker
        from version import __version__
        
        logger.info("🧪 开始测试更新检测...")
        logger.info(f"📋 当前版本: {__version__}")
        
        # 创建更新检查器
        checker = UpdateChecker()
        
        # 检查更新
        logger.info("🔍 检查GitHub上的最新版本...")
        update_info = await checker.check_for_updates()
        
        if update_info:
            logger.info("🎉 发现新版本!")
            logger.info(f"   版本: {update_info.version}")
            logger.info(f"   文件: {update_info.asset_name}")
            logger.info(f"   大小: {update_info.asset_size:,} 字节")
            logger.info(f"   下载地址: {update_info.download_url}")
            logger.info(f"   发布时间: {update_info.published_at}")
            
            if update_info.release_notes:
                logger.info(f"   更新说明: {update_info.release_notes[:200]}...")
        else:
            logger.info("ℹ️ 当前已是最新版本")
        
        # 关闭检查器
        await checker.close()
        
        logger.info("✅ 测试完成")
        return update_info
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}", exc_info=True)
        return None

def main():
    """主函数"""
    logger.info("🚀 开始更新检测测试")
    
    # 创建Qt应用程序（某些功能需要）
    app = QApplication(sys.argv)
    
    # 运行异步测试
    async def run_test():
        result = await test_update_check()
        app.quit()
        return result
    
    # 使用QTimer来运行异步函数
    def start_test():
        import qasync
        loop = qasync.QEventLoop(app)
        asyncio.set_event_loop(loop)
        
        with loop:
            loop.run_until_complete(run_test())
    
    QTimer.singleShot(100, start_test)
    
    # 运行应用程序
    app.exec()
    
    logger.info("🎉 测试完成")

if __name__ == "__main__":
    main() 