#!/usr/bin/env python3
"""
测试更新安装功能
"""

import os
import sys
import tempfile
import shutil
import logging
from pathlib import Path

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_update_script_generation():
    """测试更新脚本生成"""
    try:
        # 导入自动更新器
        from logic.auto_updater import AutoUpdater
        from version import __version__
        
        logger.info("🧪 开始测试更新脚本生成...")
        
        # 创建临时文件模拟更新文件
        with tempfile.NamedTemporaryFile(suffix='.exe', delete=False) as temp_file:
            temp_file.write(b"Fake update file content")
            update_file = temp_file.name
        
        logger.info(f"📁 创建临时更新文件: {update_file}")
        
        # 模拟当前可执行文件路径
        current_exe = os.path.abspath("GameTimeLimiter.exe")
        current_dir = os.path.dirname(current_exe)
        backup_path = os.path.join(current_dir, "backup", f"GameTimeLimiter_v{__version__}_test.exe")
        
        # 创建更新器实例
        updater = AutoUpdater()
        
        # 生成更新脚本
        script_path = updater.create_update_script(
            update_file, current_exe, current_dir, backup_path
        )
        
        logger.info(f"✅ 更新脚本已生成: {script_path}")
        
        # 读取并显示脚本内容
        with open(script_path, 'r', encoding='utf-8') as f:
            script_content = f.read()
        
        logger.info("📝 脚本内容:")
        print("=" * 60)
        print(script_content)
        print("=" * 60)
        
        # 清理临时文件
        os.unlink(update_file)
        os.unlink(script_path)
        
        logger.info("✅ 测试完成")
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}", exc_info=True)

def test_backup_creation():
    """测试备份创建功能"""
    try:
        from logic.auto_updater import AutoUpdater
        
        logger.info("🧪 开始测试备份创建...")
        
        # 创建临时文件模拟当前可执行文件
        with tempfile.NamedTemporaryFile(suffix='.exe', delete=False) as temp_file:
            temp_file.write(b"Current executable content")
            current_exe = temp_file.name
        
        logger.info(f"📁 创建临时可执行文件: {current_exe}")
        
        # 创建更新器实例
        updater = AutoUpdater()
        
        # 创建备份
        backup_path = updater.create_backup(current_exe)
        
        logger.info(f"✅ 备份已创建: {backup_path}")
        
        # 验证备份文件
        if os.path.exists(backup_path):
            logger.info("✅ 备份文件存在")
            
            # 比较文件大小
            original_size = os.path.getsize(current_exe)
            backup_size = os.path.getsize(backup_path)
            
            if original_size == backup_size:
                logger.info("✅ 备份文件大小正确")
            else:
                logger.error(f"❌ 备份文件大小不匹配: {original_size} != {backup_size}")
        else:
            logger.error("❌ 备份文件不存在")
        
        # 清理临时文件
        os.unlink(current_exe)
        if os.path.exists(backup_path):
            os.unlink(backup_path)
        
        logger.info("✅ 测试完成")
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}", exc_info=True)

def test_file_type_detection():
    """测试文件类型检测"""
    try:
        logger.info("🧪 开始测试文件类型检测...")
        
        test_files = [
            "update.exe",
            "update.zip", 
            "GameTimeLimiter.exe",
            "main.py"
        ]
        
        for filename in test_files:
            ext = os.path.splitext(filename)[1].lower()
            logger.info(f"📁 文件: {filename} -> 扩展名: {ext}")
            
            if ext == ".zip":
                logger.info("   -> 将作为ZIP文件处理")
            elif ext == ".exe":
                logger.info("   -> 将作为可执行文件处理")
            else:
                logger.info("   -> 将保持原始扩展名")
        
        logger.info("✅ 测试完成")
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}", exc_info=True)

def main():
    """主测试函数"""
    logger.info("🚀 开始更新安装功能测试")
    
    print("\n" + "="*60)
    print("测试 1: 更新脚本生成")
    print("="*60)
    test_update_script_generation()
    
    print("\n" + "="*60)
    print("测试 2: 备份创建功能")
    print("="*60)
    test_backup_creation()
    
    print("\n" + "="*60)
    print("测试 3: 文件类型检测")
    print("="*60)
    test_file_type_detection()
    
    logger.info("🎉 所有测试完成")

if __name__ == "__main__":
    main() 