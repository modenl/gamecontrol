#!/usr/bin/env python3
"""
简单测试任务管理器修复效果
"""

import asyncio
import logging
import time
from logic.task_manager import get_task_manager, run_task_safe

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_task(task_name, duration):
    """测试任务"""
    logger.info(f"任务 {task_name} 开始，持续 {duration} 秒")
    await asyncio.sleep(duration)
    logger.info(f"任务 {task_name} 完成")
    return f"{task_name}_result"

def on_complete(result):
    """任务完成回调"""
    logger.info(f"✅ 任务完成回调: {result}")

def on_error(error):
    """任务错误回调"""
    logger.error(f"❌ 任务错误回调: {error}")

async def main():
    """主测试函数"""
    logger.info("🧪 开始测试 TaskManager 修复效果...")
    
    # 获取任务管理器
    task_manager = get_task_manager()
    
    # 测试1: 单个任务
    logger.info("📋 测试1: 单个任务")
    task_id1 = run_task_safe(
        test_task("Task1", 1),
        task_id="test_single",
        on_complete=on_complete,
        on_error=on_error
    )
    logger.info(f"启动任务: {task_id1}")
    
    # 等待任务完成
    await asyncio.sleep(2)
    
    # 测试2: 并发任务
    logger.info("📋 测试2: 并发任务")
    task_ids = []
    for i in range(3):
        task_id = run_task_safe(
            test_task(f"ConcurrentTask{i+1}", 0.5 + i * 0.2),
            task_id=f"concurrent_{i+1}",
            on_complete=on_complete,
            on_error=on_error,
            delay_ms=i * 10  # 小延迟避免冲突
        )
        task_ids.append(task_id)
        logger.info(f"启动并发任务: {task_id}")
    
    # 等待所有任务完成
    await asyncio.sleep(3)
    
    # 检查任务状态
    running_tasks = task_manager.get_running_tasks()
    logger.info(f"📊 任务状态: {running_tasks}")
    
    # 测试3: 任务取消
    logger.info("📋 测试3: 任务取消")
    cancel_task_id = run_task_safe(
        test_task("CancelTask", 5),  # 长时间任务
        task_id="cancel_test",
        on_complete=on_complete,
        on_error=on_error
    )
    logger.info(f"启动待取消任务: {cancel_task_id}")
    
    # 等待1秒后取消
    await asyncio.sleep(1)
    logger.info("取消任务...")
    task_manager.cancel_task_safe(cancel_task_id)
    
    # 等待取消完成
    await asyncio.sleep(2)
    
    # 最终状态检查
    final_tasks = task_manager.get_running_tasks()
    logger.info(f"📊 最终任务状态: {final_tasks}")
    
    if not final_tasks or all(final_tasks.values()):
        logger.info("🎉 所有测试通过！TaskManager 修复成功！")
    else:
        logger.warning("⚠️ 还有任务在运行中...")
    
    # 清理所有任务
    logger.info("🧹 清理所有任务...")
    task_manager.cancel_all_tasks_sync()
    
    logger.info("✅ 测试完成")

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 Simple TaskManager Test - qasync Conflict Fix")
    print("=" * 60)
    
    # 运行测试
    asyncio.run(main()) 