#!/usr/bin/env python3
"""
监控恢复集成测试

这是一个可重复执行的集成测试，测试admin面板退出后monitor自动重启的功能。
遵循AI开发规范：
- 可以多次运行
- 有完整的setup和teardown
- 不会留下副作用
- 测试结果一致
- 不执行真实的UI操作和GPT调用
"""

import sys
import os
import asyncio
import unittest
from unittest.mock import patch, MagicMock, AsyncMock

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from logic.game_limiter import GameLimiter
from logic.window_monitor import WindowMonitor
from logic.task_manager import get_task_manager


class TestMonitorRecoveryIntegration(unittest.TestCase):
    """监控恢复集成测试类"""
    
    def setUp(self):
        """测试前的设置"""
        # 创建测试用的游戏限制器
        self.game_limiter = GameLimiter()
        
        # 模拟锁屏功能（避免实际锁屏）
        self.game_limiter.lock_screen = MagicMock(return_value=True)
        
        # 模拟数据库优化（避免异步问题）
        self.game_limiter._check_auto_optimize = MagicMock()
        
        # 创建窗口监控器
        self.window_monitor = WindowMonitor(self.game_limiter, check_interval=1)  # 短间隔用于测试
        
        # 模拟任务管理器
        self.task_manager = get_task_manager()
        
        # 模拟主窗口（不创建真实UI）
        self.mock_main_window = MagicMock()
        self.mock_main_window.session_active = False
        self.mock_main_window.window_monitor = self.window_monitor
        self.mock_main_window.game_limiter = self.game_limiter
        
        # 模拟admin面板（不创建真实UI）
        self.mock_admin_panel = MagicMock()
        
    def tearDown(self):
        """测试后的清理"""
        try:
            # 停止监控
            if self.window_monitor.is_running:
                asyncio.run(self.window_monitor.stop_monitoring())
            
            # 关闭游戏限制器
            if hasattr(self.game_limiter, 'close'):
                self.game_limiter.close()
                
            # 清理任务管理器
            self.task_manager.cancel_all_tasks_sync()
        except Exception as e:
            print(f"清理测试环境时出错: {e}")
    
    def test_monitor_basic_functionality(self):
        """测试监控器基本功能"""
        # 1. 验证初始状态
        self.assertFalse(self.window_monitor.is_running)
        self.assertIsNone(self.window_monitor._monitor_task_id)
        
        # 2. 启动监控
        asyncio.run(self.window_monitor.start_monitoring())
        
        # 3. 验证监控已启动
        self.assertTrue(self.window_monitor.is_running)
        self.assertIsNotNone(self.window_monitor._monitor_task_id)
        
        # 4. 停止监控
        asyncio.run(self.window_monitor.stop_monitoring())
        
        # 5. 验证监控已停止
        self.assertFalse(self.window_monitor.is_running)
    
    def test_admin_panel_monitor_lifecycle(self):
        """测试admin面板生命周期中的监控状态"""
        # 1. 初始状态：启动监控
        asyncio.run(self.window_monitor.start_monitoring())
        self.assertTrue(self.window_monitor.is_running)
        
        # 2. 模拟打开admin面板：停止监控
        asyncio.run(self.window_monitor.stop_monitoring())
        self.assertFalse(self.window_monitor.is_running)
        
        # 3. 模拟admin面板关闭：恢复监控
        asyncio.run(self.window_monitor.start_monitoring())
        self.assertTrue(self.window_monitor.is_running)
        
        # 4. 清理
        asyncio.run(self.window_monitor.stop_monitoring())
    
    def test_session_state_affects_monitoring(self):
        """测试会话状态对监控的影响"""
        # 1. 启动监控
        asyncio.run(self.window_monitor.start_monitoring())
        self.assertTrue(self.window_monitor.is_running)
        
        # 2. 模拟开始会话
        self.game_limiter.start_session(1.0)
        self.assertIsNotNone(self.game_limiter.current_session_start)
        
        # 3. 在会话期间，监控应该跳过检查（通过检查_check_restricted_apps的行为）
        # 这里我们验证监控仍在运行，但不会触发锁屏
        with patch.object(self.window_monitor, '_check_restricted_processes', return_value=[{'name': 'minecraft', 'type': 'process'}]):
            # 运行一次检查循环
            asyncio.run(self.window_monitor._check_restricted_apps())
            # 由于有活动会话，不应该调用锁屏
            self.game_limiter.lock_screen.assert_not_called()
        
        # 4. 结束会话
        asyncio.run(self.game_limiter.end_session())
        self.assertIsNone(self.game_limiter.current_session_start)
        
        # 5. 清理
        asyncio.run(self.window_monitor.stop_monitoring())
    
    def test_monitor_recovery_after_admin_close(self):
        """测试admin面板关闭后监控恢复的完整流程"""
        # 模拟主窗口的监控恢复方法
        async def mock_resume_monitoring():
            """模拟主窗口的resume_monitoring方法"""
            try:
                # 检查是否有活动会话
                if self.mock_main_window.session_active:
                    return
                    
                # 如果监控未运行，则启动
                if not self.window_monitor.is_running:
                    await self.window_monitor.start_monitoring()
            except Exception as e:
                print(f"恢复监控时出错: {e}")
        
        # 1. 初始状态：监控运行中
        asyncio.run(self.window_monitor.start_monitoring())
        self.assertTrue(self.window_monitor.is_running)
        
        # 2. 模拟打开admin面板：停止监控
        asyncio.run(self.window_monitor.stop_monitoring())
        self.assertFalse(self.window_monitor.is_running)
        
        # 3. 模拟admin面板关闭：触发监控恢复
        asyncio.run(mock_resume_monitoring())
        
        # 4. 验证监控已恢复
        self.assertTrue(self.window_monitor.is_running)
        
        # 5. 清理
        asyncio.run(self.window_monitor.stop_monitoring())
    
    def test_monitor_recovery_with_active_session(self):
        """测试有活动会话时admin面板关闭后不应启动监控"""
        # 模拟主窗口的监控恢复方法
        async def mock_resume_monitoring():
            """模拟主窗口的resume_monitoring方法"""
            try:
                # 检查是否有活动会话
                if self.mock_main_window.session_active:
                    return  # 有活动会话时不启动监控
                    
                # 如果监控未运行，则启动
                if not self.window_monitor.is_running:
                    await self.window_monitor.start_monitoring()
            except Exception as e:
                print(f"恢复监控时出错: {e}")
        
        # 1. 设置活动会话状态
        self.mock_main_window.session_active = True
        self.game_limiter.start_session(1.0)
        
        # 2. 初始状态：监控未运行（因为有活动会话）
        self.assertFalse(self.window_monitor.is_running)
        
        # 3. 模拟admin面板关闭：尝试恢复监控
        asyncio.run(mock_resume_monitoring())
        
        # 4. 验证监控仍未启动（因为有活动会话）
        self.assertFalse(self.window_monitor.is_running)
        
        # 5. 结束会话
        self.mock_main_window.session_active = False
        asyncio.run(self.game_limiter.end_session())
        
        # 6. 再次尝试恢复监控
        asyncio.run(mock_resume_monitoring())
        
        # 7. 验证监控现在已启动
        self.assertTrue(self.window_monitor.is_running)
        
        # 8. 清理
        asyncio.run(self.window_monitor.stop_monitoring())
    
    @patch('logic.window_monitor.gw.getAllWindows')
    @patch('logic.window_monitor.psutil.process_iter')
    def test_monitor_detection_without_real_apps(self, mock_process_iter, mock_get_windows):
        """测试监控检测功能（不使用真实应用）"""
        # 模拟没有受限进程
        mock_process_iter.return_value = []
        
        # 模拟没有Chrome窗口
        mock_get_windows.return_value = []
        
        # 启动监控
        asyncio.run(self.window_monitor.start_monitoring())
        
        # 运行一次检查
        asyncio.run(self.window_monitor._check_restricted_apps())
        
        # 验证没有触发锁屏（因为没有检测到受限应用）
        self.game_limiter.lock_screen.assert_not_called()
        
        # 清理
        asyncio.run(self.window_monitor.stop_monitoring())
    
    @patch('logic.window_monitor.gw.getAllWindows')
    @patch('logic.window_monitor.psutil.process_iter')
    def test_monitor_detection_with_mock_apps(self, mock_process_iter, mock_get_windows):
        """测试监控检测功能（使用模拟应用）"""
        # 模拟检测到Minecraft进程
        mock_process = MagicMock()
        mock_process.info = {'pid': 1234, 'name': 'minecraft.exe'}
        mock_process_iter.return_value = [mock_process]
        
        # 模拟检测到bloxd.io Chrome窗口
        mock_window = MagicMock()
        mock_window.title = "bloxd.io - Chrome"
        mock_get_windows.return_value = [mock_window]
        
        # 启动监控
        asyncio.run(self.window_monitor.start_monitoring())
        
        # 运行一次检查
        asyncio.run(self.window_monitor._check_restricted_apps())
        
        # 验证触发了锁屏（因为检测到受限应用）
        self.game_limiter.lock_screen.assert_called_once()
        
        # 清理
        asyncio.run(self.window_monitor.stop_monitoring())
    
    def test_task_manager_integration(self):
        """测试与任务管理器的集成"""
        # 1. 启动监控
        asyncio.run(self.window_monitor.start_monitoring())
        
        # 2. 验证任务ID已设置（即使任务管理器已关闭，ID仍会被设置）
        self.assertIsNotNone(self.window_monitor._monitor_task_id)
        
        # 3. 验证监控状态
        self.assertTrue(self.window_monitor.is_running)
        
        # 4. 停止监控
        asyncio.run(self.window_monitor.stop_monitoring())
        
        # 5. 验证任务已从任务管理器中移除
        self.assertIsNone(self.window_monitor._monitor_task_id)
        self.assertFalse(self.window_monitor.is_running)


def run_integration_tests():
    """运行集成测试的主函数"""
    print("=" * 60)
    print("🧪 GameTimeLimiter 监控恢复集成测试")
    print("=" * 60)
    
    # 创建测试套件
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMonitorRecoveryIntegration)
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 返回测试结果
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_integration_tests()
    
    if success:
        print("\n✅ 所有监控恢复集成测试通过！")
        sys.exit(0)
    else:
        print("\n❌ 部分监控恢复集成测试失败！")
        sys.exit(1) 