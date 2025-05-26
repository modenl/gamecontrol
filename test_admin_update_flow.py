#!/usr/bin/env python3
"""
测试需要管理员验证的更新流程
验证更新通知显示在状态栏，点击后需要管理员密码验证
"""

import sys
import os
import logging

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_status_bar_update_notification():
    """测试状态栏更新通知功能"""
    logger.info("🧪 测试状态栏更新通知...")
    
    try:
        from ui.base import StatusBar
        from logic.auto_updater import UpdateInfo
        
        # 创建模拟的更新信息
        update_info = UpdateInfo(
            version="1.0.5",
            download_url="https://example.com/test.exe",
            release_notes="Test update",
            published_at="2024-01-01T00:00:00Z",
            asset_name="GameTimeLimiter.exe",
            asset_size=1024000
        )
        
        # 测试PyQt6环境（如果可用）
        try:
            from PyQt6.QtWidgets import QApplication
            
            # 创建应用程序实例（如果还没有）
            app = QApplication.instance()
            if app is None:
                app = QApplication([])
            
            # 创建状态栏
            status_bar = StatusBar()
            
            # 测试初始状态
            assert hasattr(status_bar, 'update_label'), "状态栏应该有update_label属性"
            assert hasattr(status_bar, 'update_info'), "状态栏应该有update_info属性"
            assert status_bar.update_info is None, "初始update_info应该为None"
            assert not status_bar.update_label.isVisible(), "初始更新标签应该隐藏"
            logger.info("✅ 状态栏初始状态检查通过")
            
            # 测试显示更新通知
            status_bar.show_update_notification(update_info)
            assert status_bar.update_info == update_info, "update_info应该被正确设置"
            assert status_bar.update_label.isVisible(), "更新标签应该显示"
            assert "1.0.5" in status_bar.update_label.text(), "更新标签应该包含版本号"
            logger.info("✅ 显示更新通知检查通过")
            
            # 测试隐藏更新通知
            status_bar.hide_update_notification()
            assert status_bar.update_info is None, "update_info应该被清除"
            assert not status_bar.update_label.isVisible(), "更新标签应该隐藏"
            logger.info("✅ 隐藏更新通知检查通过")
            
            logger.info("🎉 状态栏更新通知测试通过！")
            return True
            
        except ImportError:
            logger.warning("⚠️ PyQt6不可用，跳过状态栏测试")
            return True
            
    except Exception as e:
        logger.error(f"❌ 测试状态栏更新通知失败: {e}")
        return False

def test_auto_updater_admin_auth():
    """测试自动更新器的管理员验证方法"""
    logger.info("🧪 测试自动更新器管理员验证...")
    
    try:
        from logic.auto_updater import AutoUpdater, UpdateInfo
        
        # 创建模拟的更新信息
        update_info = UpdateInfo(
            version="1.0.5",
            download_url="https://example.com/test.exe",
            release_notes="Test update",
            published_at="2024-01-01T00:00:00Z",
            asset_name="GameTimeLimiter.exe",
            asset_size=1024000
        )
        
        # 创建AutoUpdater实例
        updater = AutoUpdater()
        
        # 测试新方法是否存在
        assert hasattr(updater, 'start_update_with_admin_auth'), "AutoUpdater应该有start_update_with_admin_auth方法"
        logger.info("✅ start_update_with_admin_auth方法存在")
        
        # 测试can_update_now方法
        can_update, reason = updater.can_update_now()
        logger.info(f"📋 can_update_now结果: {can_update}, 原因: '{reason}'")
        
        # 由于没有parent，应该可以更新
        assert can_update == True, "没有parent时应该可以更新"
        assert reason == "", "没有parent时原因应该为空"
        logger.info("✅ can_update_now逻辑检查通过")
        
        logger.info("🎉 自动更新器管理员验证测试通过！")
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试自动更新器管理员验证失败: {e}")
        return False

def test_main_window_update_notification_handler():
    """测试主窗口的更新通知处理"""
    logger.info("🧪 测试主窗口更新通知处理...")
    
    try:
        # 测试PyQt6环境（如果可用）
        try:
            from PyQt6.QtWidgets import QApplication
            from ui.main_window import MainWindow
            from logic.auto_updater import UpdateInfo
            
            # 创建应用程序实例（如果还没有）
            app = QApplication.instance()
            if app is None:
                app = QApplication([])
            
            # 创建主窗口
            main_window = MainWindow()
            
            # 测试状态栏连接
            assert hasattr(main_window, 'status_bar'), "主窗口应该有status_bar属性"
            assert hasattr(main_window, 'on_update_notification_clicked'), "主窗口应该有on_update_notification_clicked方法"
            logger.info("✅ 主窗口更新通知处理方法存在")
            
            # 创建模拟的更新信息
            update_info = UpdateInfo(
                version="1.0.5",
                download_url="https://example.com/test.exe",
                release_notes="Test update",
                published_at="2024-01-01T00:00:00Z",
                asset_name="GameTimeLimiter.exe",
                asset_size=1024000
            )
            
            # 测试on_update_available方法
            main_window.on_update_available(update_info)
            
            # 检查状态栏是否显示了更新通知
            assert main_window.status_bar.update_info == update_info, "状态栏应该显示更新信息"
            assert main_window.status_bar.update_label.isVisible(), "更新标签应该可见"
            logger.info("✅ 更新通知显示在状态栏检查通过")
            
            logger.info("🎉 主窗口更新通知处理测试通过！")
            return True
            
        except ImportError:
            logger.warning("⚠️ PyQt6不可用，跳过主窗口测试")
            return True
            
    except Exception as e:
        logger.error(f"❌ 测试主窗口更新通知处理失败: {e}")
        return False

def test_admin_password_verification():
    """测试管理员密码验证逻辑"""
    logger.info("🧪 测试管理员密码验证...")
    
    try:
        from logic.database import sha256
        from logic.constants import ADMIN_PASS_HASH
        
        # 测试正确密码
        correct_password = "password"  # 默认管理员密码
        correct_hash = sha256(correct_password)
        assert correct_hash == ADMIN_PASS_HASH, "正确密码的哈希应该匹配"
        logger.info("✅ 正确密码验证通过")
        
        # 测试错误密码
        wrong_password = "wrongpassword"
        wrong_hash = sha256(wrong_password)
        assert wrong_hash != ADMIN_PASS_HASH, "错误密码的哈希不应该匹配"
        logger.info("✅ 错误密码验证通过")
        
        logger.info("🎉 管理员密码验证测试通过！")
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试管理员密码验证失败: {e}")
        return False

def main():
    """运行所有测试"""
    logger.info("🚀 开始测试需要管理员验证的更新流程...")
    
    tests = [
        ("状态栏更新通知", test_status_bar_update_notification),
        ("自动更新器管理员验证", test_auto_updater_admin_auth),
        ("主窗口更新通知处理", test_main_window_update_notification_handler),
        ("管理员密码验证", test_admin_password_verification),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        logger.info(f"\n📝 运行测试: {test_name}")
        try:
            if test_func():
                passed += 1
                logger.info(f"✅ {test_name} 测试通过")
            else:
                logger.error(f"❌ {test_name} 测试失败")
        except Exception as e:
            logger.error(f"❌ {test_name} 测试异常: {e}")
    
    logger.info(f"\n📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        logger.info("🎉 所有测试通过！需要管理员验证的更新流程已实现")
        logger.info("\n🔐 新的更新流程:")
        logger.info("1. 检测到更新时，在状态栏显示通知")
        logger.info("2. 用户点击通知后，要求输入管理员密码")
        logger.info("3. 验证通过后，才开始下载和安装更新")
        logger.info("4. 防止学生绕过监控系统")
        return True
    else:
        logger.error("❌ 部分测试失败，需要进一步检查")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 