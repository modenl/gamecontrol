#!/usr/bin/env python3
"""
会话流程集成测试

这是一个可重复执行的集成测试，测试完整的游戏会话流程。
遵循AI开发规范：
- 可以多次运行
- 有完整的setup和teardown
- 不会留下副作用
- 测试结果一致
"""

import sys
import os
import asyncio
import unittest
from unittest.mock import patch, MagicMock

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from logic.game_limiter import GameLimiter


class TestSessionFlowIntegration(unittest.TestCase):
    """会话流程集成测试类"""
    
    def setUp(self):
        """测试前的设置"""
        # 创建测试用的游戏限制器
        self.game_limiter = GameLimiter()
        
        # 模拟锁屏功能（避免实际锁屏）
        self.game_limiter.lock_screen = MagicMock()
        
        # 模拟数据库优化（避免异步问题）
        self.game_limiter._check_auto_optimize = MagicMock()
        
    def tearDown(self):
        """测试后的清理"""
        try:
            # 关闭游戏限制器
            if hasattr(self.game_limiter, 'close'):
                self.game_limiter.close()
        except Exception as e:
            print(f"清理测试环境时出错: {e}")
    
    def test_complete_session_workflow(self):
        """测试完整的会话工作流程"""
        # 1. 检查初始状态
        initial_status = asyncio.run(self.game_limiter.get_weekly_status())
        self.assertIsInstance(initial_status, dict)
        self.assertIn('remaining_minutes', initial_status)
        
        # 2. 开始会话
        duration = 1.0  # 1分钟（较短的测试时间）
        start_time, session_duration = self.game_limiter.start_session(duration)
        
        # 验证会话已开始
        self.assertIsNotNone(start_time)
        self.assertEqual(session_duration, duration)
        self.assertIsNotNone(self.game_limiter.current_session_start)
        
        # 3. 检查会话期间状态
        session_status = asyncio.run(self.game_limiter.get_weekly_status())
        self.assertIsInstance(session_status, dict)
        
        # 4. 结束会话
        result = asyncio.run(self.game_limiter.end_session())
        
        # 5. 验证会话已结束
        self.assertIsNotNone(result)
        self.assertIsNone(self.game_limiter.current_session_start)
        
        final_status = asyncio.run(self.game_limiter.get_weekly_status())
        self.assertIsInstance(final_status, dict)
        
        # 6. 检查会话记录
        sessions = asyncio.run(self.game_limiter.get_sessions())
        self.assertIsInstance(sessions, list)
    
    def test_session_basic_functionality(self):
        """测试会话基本功能"""
        # 测试开始会话
        duration = 0.5  # 30秒
        start_time, session_duration = self.game_limiter.start_session(duration, "TestGame")
        
        # 验证会话参数
        self.assertIsNotNone(start_time)
        self.assertEqual(session_duration, duration)
        self.assertEqual(self.game_limiter.current_game_name, "TestGame")
        
        # 测试结束会话
        result = asyncio.run(self.game_limiter.end_session("测试结束"))
        self.assertIsNotNone(result)
    
    def test_weekly_status_structure(self):
        """测试每周状态数据结构"""
        status = asyncio.run(self.game_limiter.get_weekly_status())
        
        # 验证必需的字段
        required_fields = ['week_start', 'used_minutes', 'extra_minutes', 
                          'weekly_limit', 'remaining_minutes']
        
        for field in required_fields:
            self.assertIn(field, status, f"缺少必需字段: {field}")
            
        # 验证数据类型
        self.assertIsInstance(status['used_minutes'], (int, float))
        self.assertIsInstance(status['extra_minutes'], (int, float))
        self.assertIsInstance(status['weekly_limit'], (int, float))
        self.assertIsInstance(status['remaining_minutes'], (int, float))
    
    def test_session_without_end(self):
        """测试未结束的会话处理"""
        # 开始会话但不结束
        self.game_limiter.start_session(1.0)
        
        # 验证会话状态
        self.assertIsNotNone(self.game_limiter.current_session_start)
        
        # 尝试开始另一个会话（应该覆盖前一个）
        new_start, new_duration = self.game_limiter.start_session(2.0)
        self.assertIsNotNone(new_start)
        self.assertEqual(new_duration, 2.0)
        
        # 清理：结束会话
        asyncio.run(self.game_limiter.end_session())


def run_integration_tests():
    """运行集成测试的主函数"""
    print("=" * 60)
    print("🧪 GameTimeLimiter 会话流程集成测试")
    print("=" * 60)
    
    # 创建测试套件
    suite = unittest.TestLoader().loadTestsFromTestCase(TestSessionFlowIntegration)
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 返回测试结果
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_integration_tests()
    
    if success:
        print("\n✅ 所有集成测试通过！")
        sys.exit(0)
    else:
        print("\n❌ 部分集成测试失败！")
        sys.exit(1) 