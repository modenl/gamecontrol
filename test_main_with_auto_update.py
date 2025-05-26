#!/usr/bin/env python3
"""
测试主程序的自动更新功能
观察详细的日志输出
"""

import sys
import os
import logging
import time
from datetime import datetime

# 设置详细日志
log_filename = f"main_auto_update_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("AutoUpdateTest")

def main():
    """主测试函数"""
    logger.info("=" * 70)
    logger.info("🧪 主程序自动更新测试")
    logger.info("=" * 70)
    logger.info(f"📝 日志文件: {log_filename}")
    logger.info(f"🕐 开始时间: {datetime.now()}")
    
    try:
        # 导入并运行主程序
        logger.info("📦 导入主程序模块...")
        import main
        
        logger.info("🚀 启动主程序...")
        logger.info("⚠️ 注意观察自动更新相关的日志输出")
        logger.info("📋 特别关注以下标识:")
        logger.info("   🚀 - 启动相关")
        logger.info("   🔍 - 检查更新")
        logger.info("   📋 - 状态信息")
        logger.info("   🎉 - 发现更新")
        logger.info("   ❌ - 错误信息")
        logger.info("   ⚠️ - 警告信息")
        logger.info("   💬 - 用户交互")
        
        # 运行主程序
        exit_code = main.main()
        
        logger.info(f"✅ 主程序退出，退出码: {exit_code}")
        return exit_code
        
    except KeyboardInterrupt:
        logger.info("⚠️ 用户中断程序")
        return 0
    except Exception as e:
        logger.error(f"❌ 测试过程中出错: {e}", exc_info=True)
        return 1
    finally:
        logger.info("=" * 70)
        logger.info(f"🕐 结束时间: {datetime.now()}")
        logger.info(f"📝 完整日志已保存到: {log_filename}")
        logger.info("=" * 70)

if __name__ == "__main__":
    print("🧪 主程序自动更新测试")
    print("=" * 50)
    print("这个测试将启动主程序并观察自动更新功能的详细日志")
    print("请注意观察控制台输出和日志文件中的自动更新相关信息")
    print("=" * 50)
    
    try:
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        sys.exit(1) 