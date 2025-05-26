#!/usr/bin/env python3
"""
基于真实日志输出的集成测试

这个测试验证应用程序的实际日志记录功能，通过检查真实的日志文件输出
来确保事件日志系统正常工作。这种方法的优势：
1. 提高性能 - 不需要模拟复杂的对象
2. 确保真实应用有日志 - 测试真实的日志输出
3. 更接近实际使用场景

遵循AI开发规范：
- 可以多次运行
- 有完整的setup和teardown
- 不会留下副作用
- 测试结果一致
"""

import sys
import os
import tempfile
import shutil
import unittest
import asyncio
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from logic.event_logger import EventLogger, get_event_logger, close_event_logger
from logic.unified_logger import get_unified_logger
from logic.game_limiter import GameLimiter
from logic.window_monitor import WindowMonitor


class TestRealLoggingIntegration(unittest.TestCase):
    """基于真实日志输出的集成测试类"""
    
    def setUp(self):
        """测试前的设置"""
        # 创建临时目录用于测试
        self.test_dir = tempfile.mkdtemp(prefix="gamecontrol_real_log_test_")
        self.test_log_file = os.path.join(self.test_dir, "real_events.log")
        
        # 创建测试用的事件日志记录器
        self.event_logger = EventLogger(self.test_log_file)
        
        # 替换全局事件日志记录器
        self.original_get_event_logger = get_event_logger
        
        def mock_get_event_logger():
            return self.event_logger
        
        # 使用patch替换全局函数
        self.event_logger_patcher = patch('logic.event_logger.get_event_logger', side_effect=mock_get_event_logger)
        self.event_logger_patcher.start()
        
        # 同时patch其他模块中的导入
        self.unified_logger_patcher = patch('logic.unified_logger.get_event_logger', side_effect=mock_get_event_logger)
        self.unified_logger_patcher.start()
        
        self.game_limiter_patcher = patch('logic.game_limiter.get_event_logger', side_effect=mock_get_event_logger)
        self.game_limiter_patcher.start()
        
        self.window_monitor_patcher = patch('logic.window_monitor.get_event_logger', side_effect=mock_get_event_logger)
        self.window_monitor_patcher.start()
        
    def tearDown(self):
        """测试后的清理"""
        # 停止所有的patch
        self.event_logger_patcher.stop()
        self.unified_logger_patcher.stop()
        self.game_limiter_patcher.stop()
        self.window_monitor_patcher.stop()
        
        # 关闭事件日志记录器
        if hasattr(self, 'event_logger'):
            self.event_logger.close()
        
        # 清理临时目录
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def read_log_file(self):
        """读取日志文件内容"""
        if os.path.exists(self.test_log_file):
            with open(self.test_log_file, 'r', encoding='utf-8') as f:
                return f.read()
        return ""
    
    def assert_log_contains(self, expected_patterns):
        """断言日志包含指定的模式"""
        log_content = self.read_log_file()
        for pattern in expected_patterns:
            self.assertIn(pattern, log_content, f"日志中未找到模式: {pattern}")
    
    def test_unified_logger_session_workflow(self):
        """测试统一日志记录器的会话工作流程"""
        # 创建统一日志记录器
        unified_logger = get_unified_logger("test_session")
        
        # 模拟会话启动
        unified_logger.log_session_start("Minecraft", 120)
        
        # 模拟会话结束
        unified_logger.log_session_end("Minecraft", 115, "正常结束")
        
        # 模拟会话错误
        unified_logger.log_session_error("开始Session", "数据库连接失败")
        
        # 验证日志内容
        self.assert_log_contains([
            "[SESSION_START]",
            "Minecraft游戏会话已启动",
            "2.0小时",
            "[SESSION_END]",
            "1.92小时",  # 115/60 = 1.916... ≈ 1.92
            "正常结束",
            "[ERROR]",
            "SESSION_开始SESSION_ERROR",
            "数据库连接失败"
        ])
    
    def test_unified_logger_monitor_workflow(self):
        """测试统一日志记录器的监控工作流程"""
        # 创建统一日志记录器
        unified_logger = get_unified_logger("test_monitor")
        
        # 模拟监控启动
        unified_logger.log_monitor_start(15)
        
        # 模拟检测到禁止应用
        unified_logger.log_restricted_app_detected(
            "minecraft", 
            "process",
            details={"process_name": "java.exe", "pid": 1234}
        )
        
        # 模拟监控停止
        unified_logger.log_monitor_stop("检测到禁止应用")
        
        # 模拟监控错误
        unified_logger.log_monitor_error("网络连接超时")
        
        # 验证日志内容
        self.assert_log_contains([
            "[MONITOR_START]",
            "检查间隔: 15秒",
            "[RESTRICTED_APP]",
            "minecraft",
            "process",
            "java.exe",
            "1234",
            "[MONITOR_STOP]",
            "检测到禁止应用",
            "[ERROR]",
            "MONITOR_ERROR",
            "网络连接超时"
        ])
    
    def test_unified_logger_admin_workflow(self):
        """测试统一日志记录器的管理面板工作流程"""
        # 创建统一日志记录器
        unified_logger = get_unified_logger("test_admin")
        
        # 模拟管理面板打开
        unified_logger.log_admin_panel_open()
        
        # 模拟管理面板关闭
        unified_logger.log_admin_panel_close()
        
        # 验证日志内容
        self.assert_log_contains([
            "[ADMIN_OPEN]",
            "管理员打开了管理面板",
            "[ADMIN_CLOSE]",
            "管理员关闭了管理面板"
        ])
    
    def test_unified_logger_question_workflow(self):
        """测试统一日志记录器的题目工作流程"""
        # 创建统一日志记录器
        unified_logger = get_unified_logger("test_question")
        
        # 模拟题目加载
        unified_logger.log_question_load(10, "GPT生成")
        
        # 模拟答案检查
        unified_logger.log_question_answer_check(0, "42", True)
        unified_logger.log_question_answer_check(1, "wrong", False)
        
        # 模拟题目错误
        unified_logger.log_question_error("生成题目", "API调用失败")
        
        # 验证日志内容
        self.assert_log_contains([
            "[SYSTEM]",
            "从GPT生成加载题目，共10道",
            "[ERROR]",
            "QUESTION_生成题目_ERROR",
            "API调用失败"
        ])
        
        # 单独验证传统日志内容（这些不会出现在事件日志中）
        log_content = self.read_log_file()
        # 注意：题目答案检查的日志是传统日志，不会出现在事件日志文件中
    
    @patch('logic.game_limiter.Database')
    def test_real_game_limiter_logging(self, mock_db_class):
        """测试真实GameLimiter的日志记录"""
        # 模拟数据库
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        
        # 创建GameLimiter实例
        game_limiter = GameLimiter()
        
        # 测试会话启动
        start_time, duration = game_limiter.start_session(60, "TestGame")
        
        # 验证会话启动日志
        self.assert_log_contains([
            "[SESSION_START]",
            "TestGame游戏会话已启动",
            "1.0小时"
        ])
        
        # 测试会话结束（需要模拟异步调用）
        async def test_end_session():
            # 使用AsyncMock来正确模拟异步方法
            from unittest.mock import AsyncMock
            mock_db.add_session = AsyncMock()
            result = await game_limiter.end_session("测试结束")
            return result
        
        # 运行异步测试
        result = asyncio.run(test_end_session())
        
        # 验证会话结束日志
        log_content = self.read_log_file()
        self.assertIn("[SESSION_END]", log_content)
        self.assertIn("测试结束", log_content)
    
    @patch('psutil.process_iter')
    def test_real_window_monitor_logging(self, mock_process_iter):
        """测试真实WindowMonitor的日志记录"""
        # 模拟进程列表
        mock_process_iter.return_value = []
        
        # 创建模拟的GameLimiter
        mock_game_limiter = MagicMock()
        mock_game_limiter.current_session_start = None
        mock_game_limiter.lock_screen = MagicMock(return_value=True)
        
        # 创建WindowMonitor实例
        window_monitor = WindowMonitor(mock_game_limiter, check_interval=5)
        
        # 测试监控启动
        async def test_monitor_start():
            await window_monitor.start_monitoring()
            # 立即停止以避免长时间运行
            await window_monitor.stop_monitoring()
        
        # 运行异步测试
        asyncio.run(test_monitor_start())
        
        # 验证监控日志
        self.assert_log_contains([
            "[MONITOR_START]",
            "检查间隔: 5秒",
            "[MONITOR_STOP]",
            "手动停止"
        ])
    
    def test_log_file_format_and_structure(self):
        """测试日志文件格式和结构"""
        # 记录各种类型的事件
        self.event_logger.log_app_started()
        self.event_logger.log_monitor_started(15)
        self.event_logger.log_session_started(2.0, "测试会话")
        self.event_logger.log_question_answered("数学", "42", "42", True, 1)
        self.event_logger.log_error_event("测试错误", "TEST_ERROR")
        self.event_logger.log_app_shutdown("测试退出")
        
        # 读取日志内容
        log_content = self.read_log_file()
        
        # 验证日志格式
        lines = log_content.strip().split('\n')
        
        # 过滤掉空行和注释行
        event_lines = [line for line in lines if line.strip() and not line.strip().startswith('#')]
        
        # 验证每行都有正确的格式
        for line in event_lines:
            # 验证时间戳格式
            self.assertRegex(line, r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}')
            # 验证包含[EVENT]标记
            self.assertIn('[EVENT]', line)
            # 验证包含日志级别
            self.assertTrue(any(level in line for level in ['INFO', 'WARNING', 'ERROR']))
            # 验证包含事件类型
            self.assertRegex(line, r'\[([A-Z_]+)\]')
        
        # 验证事件顺序和内容
        self.assertIn('[APP_START]', log_content)
        self.assertIn('[MONITOR_START]', log_content)
        self.assertIn('[SESSION_START]', log_content)
        self.assertIn('[QUESTION_CORRECT]', log_content)
        self.assertIn('[ERROR]', log_content)
        self.assertIn('[APP_SHUTDOWN]', log_content)
    
    def test_performance_and_file_handling(self):
        """测试性能和文件处理"""
        start_time = time.time()
        
        # 记录大量事件
        for i in range(100):
            self.event_logger.log_system_event(f"测试事件 {i}", {"index": i})
        
        end_time = time.time()
        duration = end_time - start_time
        
        # 验证性能（100个事件应该在1秒内完成）
        self.assertLess(duration, 1.0, "日志记录性能不达标")
        
        # 验证文件大小合理
        file_size = os.path.getsize(self.test_log_file)
        self.assertGreater(file_size, 0, "日志文件为空")
        self.assertLess(file_size, 100000, "日志文件过大")  # 100KB限制
        
        # 验证文件内容完整性
        log_content = self.read_log_file()
        event_count = log_content.count('[SYSTEM]')
        # 注意：可能包含系统启动事件，所以应该是100或101
        self.assertGreaterEqual(event_count, 100, "日志事件数量不足")
        self.assertLessEqual(event_count, 102, "日志事件数量过多")


if __name__ == '__main__':
    unittest.main() 