"""
修复数学题目功能的小工具
"""

import os
import sys
import sqlite3
import time
import logging
import tkinter as tk
from tkinter import messagebox
from logic.constants import DB_FILE

# 新增：自动加载.env文件
from dotenv import load_dotenv
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='fix_math.log'
)
logger = logging.getLogger('fix_math')

def ensure_db_not_locked():
    """确保数据库文件不被锁定"""
    logger.info("检查数据库是否被锁定...")
    try:
        # 尝试删除并重新创建数据库
        if os.path.exists(DB_FILE):
            try:
                # 尝试连接以确定是否被锁定
                conn = sqlite3.connect(DB_FILE, timeout=1)
                conn.close()
                logger.info("数据库未被锁定，可以继续操作")
            except sqlite3.OperationalError:
                logger.warning("数据库被锁定，尝试删除并重新创建")
                try:
                    os.remove(DB_FILE)
                    logger.info(f"成功删除数据库文件: {DB_FILE}")
                except Exception as e:
                    logger.error(f"无法删除数据库文件: {e}")
                    return False
        return True
    except Exception as e:
        logger.error(f"检查数据库锁定状态时出错: {e}")
        return False

def test_openai_api():
    """测试OpenAI API密钥"""
    logger.info("测试OpenAI API密钥...")
    api_key = os.environ.get("OPENAI_API_KEY", "")
    
    if not api_key or api_key == "your-api-key-here":
        logger.error("未设置有效的OpenAI API密钥")
        return False
        
    try:
        import openai
        openai.api_key = api_key
        # 尝试一个简单的API调用
        response = openai.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "你好"},
                {"role": "user", "content": "测试API密钥"}
            ],
            max_tokens=5
        )
        logger.info("OpenAI API密钥有效")
        return True
    except Exception as e:
        logger.error(f"OpenAI API密钥测试失败: {e}")
        return False

def generate_test_questions():
    """生成测试题目"""
    logger.info("尝试生成测试题目...")
    try:
        from logic.math_exercises import MathExercises
        math = MathExercises()
        
        # 等待数据库初始化完成
        time.sleep(2)
        
        def callback(success, error_msg):
            if success:
                logger.info("成功生成测试题目")
                print("✓ 成功生成测试题目")
            else:
                logger.error(f"生成测试题目失败: {error_msg}")
                print(f"✗ 生成测试题目失败: {error_msg}")
        
        math.generate_questions(callback)
        # 等待异步操作完成
        time.sleep(5)
        return True
    except Exception as e:
        logger.error(f"生成测试题目过程中出错: {e}")
        return False

def optimize_database():
    """优化数据库"""
    logger.info("尝试优化数据库...")
    try:
        from logic.database import Database
        db = Database()
        # 加锁调用
        result = db.optimize_database()
        if result:
            logger.info("数据库优化成功")
        else:
            logger.warning("数据库优化可能未完全成功")
        db.close()
        return result
    except Exception as e:
        logger.error(f"优化数据库过程中出错: {e}")
        return False

def main():
    """主函数"""
    print("开始修复数学题目功能...\n")
    
    # 1. 确保数据库不被锁定
    if not ensure_db_not_locked():
        print("✗ 无法解锁数据库，请关闭所有可能使用数据库的程序后重试")
        return False
    print("✓ 数据库状态正常")
    
    # 2. 检查 API 密钥
    if not test_openai_api():
        print("✗ OpenAI API密钥无效，请检查环境变量或.env文件")
        return False
    print("✓ OpenAI API密钥有效")
    
    # 3. 优化数据库
    if not optimize_database():
        print("✗ 数据库优化失败")
        return False
    print("✓ 数据库优化成功")
    
    # 4. 生成测试题目
    if not generate_test_questions():
        print("✗ 生成测试题目失败")
        return False
    
    print("\n修复完成！现在应该可以正常使用数学题目功能了。")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 