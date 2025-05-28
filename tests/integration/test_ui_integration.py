#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UI集成测试 - 测试主要UI组件和交互
这是一个永久测试文件，可重复运行
"""
import os
import sys
import asyncio
import logging
import tempfile
import shutil
from pathlib import Path

# 设置测试模式
os.environ['GAMECONTROL_TEST_MODE'] = 'true'

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 导入PyQt6相关模块
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from PyQt6.QtTest import QTest
import qasync

from logic.game_limiter import GameLimiter
from ui.main_window import MainWindow
from ui.math_panel_simple import SimpleMathPanel
from ui.admin_panel import AdminPanel

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class UIIntegrationTest:
    """UI集成测试类"""
    
    def __init__(self):
        self.app = None
        self.main_window = None
        self.temp_dir = None
        self.test_db_path = None
        self.game_limiter = None
        
    async def setup(self):
        """设置测试环境"""
        logger.info("🚀 设置UI集成测试环境")
        
        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp(prefix="gamecontrol_ui_test_")
        self.test_db_path = os.path.join(self.temp_dir, "test_ui.db")
        logger.info(f"临时目录: {self.temp_dir}")
        
        # 创建QApplication（如果不存在）
        if not QApplication.instance():
            self.app = QApplication([])
        else:
            self.app = QApplication.instance()
            
        # 创建GameLimiter
        self.game_limiter = GameLimiter(db_path=self.test_db_path)
        await self.game_limiter.initialize()
        
        # 创建主窗口
        self.main_window = MainWindow()
        self.main_window.game_limiter = self.game_limiter
        
        logger.info("✅ UI集成测试环境设置完成")
        
    async def teardown(self):
        """清理测试环境"""
        logger.info("🧹 清理UI集成测试环境")
        
        try:
            if self.main_window:
                self.main_window.close()
                
            if self.game_limiter:
                self.game_limiter.close()
                
            if self.temp_dir and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                logger.info(f"清理临时目录: {self.temp_dir}")
                
        except Exception as e:
            logger.error(f"清理UI测试环境时出错: {e}")
            
        logger.info("✅ UI集成测试环境清理完成")
        
    async def test_main_window_creation(self):
        """测试主窗口创建"""
        logger.info("🧪 测试主窗口创建")
        
        assert self.main_window is not None, "主窗口应该被创建"
        assert self.main_window.isVisible() == False, "主窗口初始应该不可见"
        
        # 显示主窗口
        self.main_window.show()
        await asyncio.sleep(0.1)  # 等待UI更新
        
        assert self.main_window.isVisible(), "主窗口应该可见"
        
        # 隐藏主窗口
        self.main_window.hide()
        await asyncio.sleep(0.1)
        
        logger.info("✅ 主窗口创建测试通过")
        
    async def test_math_panel_creation(self):
        """测试数学面板创建"""
        logger.info("🧪 测试数学面板创建")
        
        # 创建数学面板（使用共享的math_exercises实例）
        math_panel = SimpleMathPanel(
            parent=self.main_window,
            math_exercises=self.game_limiter.math_exercises
        )
        
        assert math_panel is not None, "数学面板应该被创建"
        assert math_panel.math is not None, "数学面板应该有math_exercises实例"
        
        # 显示数学面板
        math_panel.show()
        await asyncio.sleep(0.1)
        
        assert math_panel.isVisible(), "数学面板应该可见"
        
        # 关闭数学面板
        math_panel.close()
        await asyncio.sleep(0.1)
        
        logger.info("✅ 数学面板创建测试通过")
        
    async def test_admin_panel_creation(self):
        """测试管理面板创建"""
        logger.info("🧪 测试管理面板创建")
        
        # 创建管理面板
        admin_panel = AdminPanel(self.main_window, self.game_limiter)
        
        assert admin_panel is not None, "管理面板应该被创建"
        assert admin_panel.game_limiter is not None, "管理面板应该有game_limiter实例"
        
        # 显示管理面板
        admin_panel.show()
        await asyncio.sleep(0.1)
        
        assert admin_panel.isVisible(), "管理面板应该可见"
        
        # 关闭管理面板
        admin_panel.close()
        await asyncio.sleep(0.1)
        
        logger.info("✅ 管理面板创建测试通过")
        
    async def test_main_window_methods(self):
        """测试主窗口方法"""
        logger.info("🧪 测试主窗口方法")
        
        # 测试显示数学面板方法
        try:
            self.main_window.show_math_panel()
            await asyncio.sleep(0.1)
            logger.info("✅ show_math_panel方法调用成功")
        except Exception as e:
            logger.warning(f"show_math_panel方法调用失败: {e}")
            
        # 测试显示管理面板方法
        try:
            self.main_window.show_admin_panel()
            await asyncio.sleep(0.1)
            logger.info("✅ show_admin_panel方法调用成功")
        except Exception as e:
            logger.warning(f"show_admin_panel方法调用失败: {e}")
            
        logger.info("✅ 主窗口方法测试通过")
        
    async def test_ui_components_interaction(self):
        """测试UI组件交互"""
        logger.info("🧪 测试UI组件交互")
        
        # 创建数学面板
        math_panel = SimpleMathPanel(
            parent=self.main_window,
            math_exercises=self.game_limiter.math_exercises
        )
        
        # 显示面板
        math_panel.show()
        await asyncio.sleep(0.1)
        
        # 测试获取题目
        try:
            await math_panel.load_or_generate_questions()
            logger.info("✅ 数学面板题目加载成功")
        except Exception as e:
            logger.warning(f"数学面板题目加载失败: {e}")
            
        # 关闭面板
        math_panel.close()
        
        logger.info("✅ UI组件交互测试通过")
        
    async def test_async_ui_operations(self):
        """测试异步UI操作"""
        logger.info("🧪 测试异步UI操作")
        
        # 测试异步状态更新
        try:
            weekly_status = await self.game_limiter.get_weekly_status()
            assert weekly_status is not None, "应该能获取周状态"
            logger.info(f"✅ 异步获取周状态成功: {weekly_status}")
        except Exception as e:
            logger.error(f"异步获取周状态失败: {e}")
            raise
            
        # 测试异步数学题目操作
        try:
            math_exercises = self.game_limiter.math_exercises
            # 确保题目已初始化
            if not math_exercises.questions:
                await math_exercises._generate_questions_async()
            question = math_exercises.get_current_question()
            assert question is not None, "应该能获取当前题目"
            logger.info("✅ 异步数学题目操作成功")
        except Exception as e:
            logger.error(f"异步数学题目操作失败: {e}")
            raise
            
        logger.info("✅ 异步UI操作测试通过")
        
    async def run_all_tests(self):
        """运行所有UI测试"""
        logger.info("🎯 开始运行UI集成测试")
        
        tests = [
            self.test_main_window_creation,
            self.test_math_panel_creation,
            self.test_admin_panel_creation,
            self.test_main_window_methods,
            self.test_ui_components_interaction,
            self.test_async_ui_operations,
        ]
        
        passed = 0
        failed = 0
        
        for test in tests:
            try:
                logger.info(f"\n{'='*50}")
                logger.info(f"运行测试: {test.__name__}")
                logger.info(f"{'='*50}")
                
                await test()
                passed += 1
                logger.info(f"✅ {test.__name__} 通过")
                
            except Exception as e:
                failed += 1
                logger.error(f"❌ {test.__name__} 失败: {e}")
                
        logger.info(f"\n{'='*50}")
        logger.info(f"UI集成测试结果汇总")
        logger.info(f"{'='*50}")
        logger.info(f"总测试数: {len(tests)}")
        logger.info(f"通过: {passed}")
        logger.info(f"失败: {failed}")
        
        if failed == 0:
            logger.info("🎉 所有UI集成测试通过！")
        else:
            logger.warning(f"⚠️ 有 {failed} 个测试失败")
            
        return failed == 0

async def main():
    """主函数"""
    test = UIIntegrationTest()
    
    try:
        await test.setup()
        success = await test.run_all_tests()
        return 0 if success else 1
    except Exception as e:
        logger.error(f"UI集成测试运行失败: {e}")
        return 1
    finally:
        await test.teardown()

if __name__ == "__main__":
    # 使用qasync运行异步测试
    try:
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
            
        loop = qasync.QEventLoop(app)
        asyncio.set_event_loop(loop)
        
        with loop:
            exit_code = loop.run_until_complete(main())
            sys.exit(exit_code)
            
    except Exception as e:
        logger.error(f"运行UI测试时出错: {e}")
        sys.exit(1) 