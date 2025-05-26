#!/usr/bin/env python3
"""
事件日志系统集成测试

这是一个可重复执行的集成测试，测试事件日志系统的完整功能。
遵循AI开发规范：
- 可以多次运行
- 有完整的setup和teardown
- 不会留下副作用
- 测试结果一致
- 不执行真实的UI操作和GPT调用
"""

import sys
import os
import tempfile
import shutil
import unittest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from logic.event_logger import EventLogger, get_event_logger, close_event_logger
from logic.window_monitor import WindowMonitor
from logic.game_limiter import GameLimiter
from logic.math_exercises import MathExercises


class TestEventLoggingIntegration(unittest.TestCase):
    """事件日志系统集成测试类"""
    
    def setUp(self):
        """测试前的设置"""
        # 创建临时目录用于测试
        self.test_dir = tempfile.mkdtemp(prefix="gamecontrol_event_test_")
        self.test_log_file = os.path.join(self.test_dir, "test_events.log")
        
        # 创建测试用的事件日志记录器
        self.event_logger = EventLogger(self.test_log_file)
        
        # 模拟游戏限制器
        self.game_limiter = MagicMock()
        self.game_limiter.current_session_start = None
        self.game_limiter.lock_screen = MagicMock(return_value=True)
        self.game_limiter.kill_minecraft = MagicMock(return_value=True)
        
    def tearDown(self):
        """测试后的清理"""
        # 关闭事件日志记录器
        if hasattr(self, 'event_logger'):
            self.event_logger.close()
        
        # 清理临时目录
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_event_logger_initialization(self):
        """测试事件日志记录器初始化"""
        # 验证日志文件被创建
        self.assertTrue(os.path.exists(self.test_log_file))
        
        # 验证日志记录器属性
        self.assertIsNotNone(self.event_logger.logger)
        self.assertEqual(str(self.event_logger.log_file), self.test_log_file)
        
        # 验证初始化日志被写入
        with open(self.test_log_file, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn("事件日志系统已启动", content)
    
    def test_monitor_events_logging(self):
        """测试监控相关事件日志"""
        # 测试监控启动事件
        self.event_logger.log_monitor_started(15)
        
        # 测试监控停止事件
        self.event_logger.log_monitor_stopped("测试停止")
        
        # 测试受限应用检测事件
        self.event_logger.log_restricted_app_detected(
            "minecraft", 
            "process",
            details={"process_name": "java.exe", "pid": 1234}
        )
        
        # 测试进程终止事件
        self.event_logger.log_process_terminated("minecraft", 1234)
        
        # 测试屏幕锁定事件
        self.event_logger.log_screen_locked("检测到禁止应用")
        
        # 验证日志内容
        with open(self.test_log_file, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn("[MONITOR_START]", content)
            self.assertIn("[MONITOR_STOP]", content)
            self.assertIn("[RESTRICTED_APP]", content)
            self.assertIn("[PROCESS_KILL]", content)
            self.assertIn("[SCREEN_LOCK]", content)
            self.assertIn("检查间隔: 15秒", content)
            self.assertIn("minecraft", content)
            self.assertIn("java.exe", content)
    
    def test_session_events_logging(self):
        """测试会话相关事件日志"""
        # 测试会话启动事件
        self.event_logger.log_session_started(2.0, "Minecraft游戏会话")
        
        # 测试会话结束事件
        self.event_logger.log_session_ended(1.8, "正常结束")
        
        # 测试会话延长事件
        self.event_logger.log_session_extended(0.5, 2.5)
        
        # 验证日志内容
        with open(self.test_log_file, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn("[SESSION_START]", content)
            self.assertIn("[SESSION_END]", content)
            self.assertIn("[SESSION_EXTEND]", content)
            self.assertIn("2.0小时", content)
            self.assertIn("1.80小时", content)  # 修正为实际的格式
            self.assertIn("Minecraft游戏会话", content)
    
    def test_question_events_logging(self):
        """测试题目相关事件日志"""
        # 测试题目展示事件
        self.event_logger.log_question_presented(
            "数学", 
            "2 + 2 = ?", 
            difficulty="1"
        )
        
        # 测试正确答案事件
        self.event_logger.log_question_answered(
            "数学", 
            "4", 
            "4", 
            True, 
            1
        )
        
        # 测试错误答案事件
        self.event_logger.log_question_answered(
            "数学", 
            "5", 
            "4", 
            False, 
            2
        )
        
        # 测试题目超时事件
        self.event_logger.log_question_timeout("数学", 60)
        
        # 验证日志内容
        with open(self.test_log_file, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn("[QUESTION_SHOW]", content)
            self.assertIn("[QUESTION_CORRECT]", content)
            self.assertIn("[QUESTION_WRONG]", content)
            self.assertIn("[QUESTION_TIMEOUT]", content)
            self.assertIn("2 + 2 = ?", content)
            self.assertIn("难度: 1", content)
    
    def test_system_events_logging(self):
        """测试系统相关事件日志"""
        # 测试管理面板事件
        self.event_logger.log_admin_panel_opened("管理员")
        self.event_logger.log_admin_panel_closed("管理员")
        
        # 测试设置更改事件
        self.event_logger.log_settings_changed("check_interval", 15, 30)
        
        # 测试系统事件
        self.event_logger.log_system_event("测试系统事件", {"test": "data"})
        
        # 测试错误事件
        self.event_logger.log_error_event("测试错误", "TEST_ERROR", {"error_code": 500})
        
        # 测试应用生命周期事件
        self.event_logger.log_app_started()
        self.event_logger.log_app_shutdown("测试退出")
        
        # 验证日志内容
        with open(self.test_log_file, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn("[ADMIN_OPEN]", content)
            self.assertIn("[ADMIN_CLOSE]", content)
            self.assertIn("[SETTINGS_CHANGE]", content)
            self.assertIn("[SYSTEM]", content)
            self.assertIn("[ERROR]", content)
            self.assertIn("[APP_START]", content)
            self.assertIn("[APP_SHUTDOWN]", content)
            self.assertIn("check_interval", content)
            self.assertIn("测试系统事件", content)
    
    def test_window_monitor_integration(self):
        """测试窗口监控器与事件日志的集成"""
        # 创建窗口监控器（使用模拟的游戏限制器）
        window_monitor = WindowMonitor(self.game_limiter, check_interval=5)
        
        # 替换事件日志记录器为测试实例
        window_monitor.event_logger = self.event_logger
        
        # 测试启动监控
        asyncio.run(window_monitor.start_monitoring())
        
        # 验证监控启动事件被记录
        with open(self.test_log_file, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn("[MONITOR_START]", content)
            self.assertIn("检查间隔: 5秒", content)
        
        # 测试停止监控
        asyncio.run(window_monitor.stop_monitoring())
        
        # 验证监控停止事件被记录
        with open(self.test_log_file, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn("[MONITOR_STOP]", content)
            self.assertIn("手动停止", content)
    
    @patch('logic.math_exercises.openai')
    def test_math_exercises_integration(self, mock_openai):
        """测试数学练习与事件日志的集成"""
        # 模拟OpenAI API响应
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '{"is_correct": true, "explanation": "正确答案"}'
        mock_openai.chat.completions.create.return_value = mock_response
        
        # 创建数学练习实例
        math_exercises = MathExercises()
        math_exercises.event_logger = self.event_logger
        
        # 模拟一道题目
        math_exercises.questions = [{
            "question": "2 + 2 = ?",
            "answer": "4",
            "difficulty": 1,
            "reward_minutes": 1.0,
            "is_correct": None
        }]
        
        # 模拟数据库操作
        with patch.object(math_exercises, '_add_exercise_result', new_callable=AsyncMock):
            # 测试答案检查
            result = asyncio.run(math_exercises.check_answer_async(0, "4"))
            
            # 验证结果
            self.assertTrue(result[0])  # 答案正确
            
            # 验证事件日志
            with open(self.test_log_file, 'r', encoding='utf-8') as f:
                content = f.read()
                self.assertIn("[QUESTION_CORRECT]", content)
                self.assertIn("数学题目回答正确", content)
    
    def test_global_event_logger(self):
        """测试全局事件日志记录器"""
        # 测试获取全局实例
        global_logger = get_event_logger()
        self.assertIsNotNone(global_logger)
        
        # 测试单例模式
        another_logger = get_event_logger()
        self.assertIs(global_logger, another_logger)
        
        # 测试关闭全局实例
        close_event_logger()
        
        # 获取新的实例应该是不同的对象
        new_logger = get_event_logger()
        self.assertIsNot(global_logger, new_logger)
        
        # 清理
        close_event_logger()
    
    def test_event_format_and_structure(self):
        """测试事件格式和结构"""
        # 记录一个带详细信息的事件
        self.event_logger.log_restricted_app_detected(
            "test_app",
            "process",
            details={
                "process_name": "test.exe",
                "pid": 9999,
                "detection_time": "2024-01-01T12:00:00"
            }
        )
        
        # 读取日志内容
        with open(self.test_log_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 验证事件格式
        self.assertIn("[RESTRICTED_APP]", content)
        self.assertIn("test_app", content)
        self.assertIn("process", content)
        self.assertIn("test.exe", content)
        self.assertIn("9999", content)
        
        # 验证JSON格式的详细信息
        self.assertIn('"process_name": "test.exe"', content)
        self.assertIn('"pid": 9999', content)


if __name__ == '__main__':
    unittest.main() 