#!/usr/bin/env python3
"""
自动更新功能测试脚本
"""

import sys
import asyncio
import logging
from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel
from PyQt6.QtCore import QTimer

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 导入自动更新模块
try:
    from logic.auto_updater import AutoUpdater, UpdateChecker
    from version import __version__, is_newer_version
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保已安装所有依赖: pip install httpx")
    sys.exit(1)


class UpdateTestWindow(QMainWindow):
    """更新测试窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Auto Updater Test - v{__version__}")
        self.resize(600, 400)
        
        # 创建UI
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # 版本信息
        self.version_label = QLabel(f"当前版本: {__version__}")
        layout.addWidget(self.version_label)
        
        # 状态标签
        self.status_label = QLabel("就绪")
        layout.addWidget(self.status_label)
        
        # 测试按钮
        self.check_button = QPushButton("检查更新")
        self.check_button.clicked.connect(self.test_check_updates)
        layout.addWidget(self.check_button)
        
        self.version_test_button = QPushButton("测试版本比较")
        self.version_test_button.clicked.connect(self.test_version_comparison)
        layout.addWidget(self.version_test_button)
        
        self.mock_update_button = QPushButton("模拟发现更新")
        self.mock_update_button.clicked.connect(self.test_mock_update)
        layout.addWidget(self.mock_update_button)
        
        # 初始化更新器
        self.updater = AutoUpdater(self)
        self.updater.update_available.connect(self.on_update_available)
        self.updater.no_update_available.connect(self.on_no_update)
        self.updater.update_check_failed.connect(self.on_check_failed)
        
        logger.info("测试窗口初始化完成")
    
    def test_check_updates(self):
        """测试检查更新"""
        logger.info("开始测试检查更新...")
        self.status_label.setText("正在检查更新...")
        self.check_button.setEnabled(False)
        
        # 开始检查
        self.updater.check_for_updates(manual=True)
        
        # 10秒后恢复按钮
        QTimer.singleShot(10000, self.restore_button)
    
    def restore_button(self):
        """恢复按钮状态"""
        self.check_button.setEnabled(True)
        if self.status_label.text() == "正在检查更新...":
            self.status_label.setText("检查完成")
    
    def test_version_comparison(self):
        """测试版本比较功能"""
        logger.info("测试版本比较功能...")
        
        test_cases = [
            ("1.0.0", "1.0.1", True),   # 新版本
            ("1.0.0", "1.1.0", True),   # 新版本
            ("1.0.0", "2.0.0", True),   # 新版本
            ("1.0.1", "1.0.0", False),  # 旧版本
            ("1.0.0", "1.0.0", False),  # 相同版本
            ("1.0.0-beta", "1.0.0", True),  # 预发布版本
        ]
        
        results = []
        for current, new, expected in test_cases:
            result = is_newer_version(current, new)
            status = "✓" if result == expected else "✗"
            results.append(f"{status} {current} -> {new}: {result} (期望: {expected})")
            logger.info(f"版本比较: {current} -> {new} = {result} (期望: {expected})")
        
        self.status_label.setText("版本比较测试完成:\n" + "\n".join(results))
    
    def test_mock_update(self):
        """模拟发现更新"""
        logger.info("模拟发现更新...")
        
        from logic.auto_updater import UpdateInfo
        
        # 创建模拟更新信息
        mock_update = UpdateInfo(
            version="999.0.0",  # 一个肯定比当前版本新的版本号
            download_url="https://github.com/example/repo/releases/download/v999.0.0/GameTimeLimiter.exe",
            release_notes="这是一个测试更新\n\n新功能:\n- 测试功能1\n- 测试功能2\n\n修复:\n- 修复了一些bug",
            published_at="2024-01-01T00:00:00Z",
            asset_name="GameTimeLimiter.exe",
            asset_size=50 * 1024 * 1024  # 50MB
        )
        
        # 触发更新可用信号
        self.updater.on_update_available(mock_update)
        self.status_label.setText("模拟更新对话框已显示")
    
    def on_update_available(self, update_info):
        """处理更新可用"""
        logger.info(f"发现更新: {update_info.version}")
        self.status_label.setText(f"发现新版本: {update_info.version}")
    
    def on_no_update(self):
        """处理无更新"""
        logger.info("当前已是最新版本")
        self.status_label.setText("当前已是最新版本")
    
    def on_check_failed(self, error_msg):
        """处理检查失败"""
        logger.error(f"检查更新失败: {error_msg}")
        self.status_label.setText(f"检查失败: {error_msg}")
    
    async def cleanup(self):
        """清理资源"""
        if hasattr(self, 'updater'):
            await self.updater.close()


async def test_update_checker():
    """测试更新检查器（无UI）"""
    logger.info("测试更新检查器...")
    
    checker = UpdateChecker()
    
    try:
        # 测试检查更新
        update_info = await checker.check_for_updates()
        
        if update_info:
            logger.info(f"发现更新: {update_info}")
            print(f"新版本: {update_info.version}")
            print(f"下载地址: {update_info.download_url}")
            print(f"文件大小: {update_info.asset_size / (1024*1024):.1f} MB")
            print(f"发布说明: {update_info.release_notes[:200]}...")
        else:
            logger.info("当前已是最新版本")
            print("当前已是最新版本")
            
    except Exception as e:
        logger.error(f"检查更新失败: {e}")
        print(f"检查更新失败: {e}")
    
    finally:
        await checker.close()


def main():
    """主函数"""
    print("自动更新功能测试")
    print("=" * 50)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--no-ui":
        # 无UI测试
        print("运行无UI测试...")
        asyncio.run(test_update_checker())
    else:
        # UI测试
        print("运行UI测试...")
        app = QApplication(sys.argv)
        
        # 创建事件循环
        import qasync
        loop = qasync.QEventLoop(app)
        asyncio.set_event_loop(loop)
        
        # 创建测试窗口
        window = UpdateTestWindow()
        window.show()
        
        try:
            with loop:
                loop.run_forever()
        except KeyboardInterrupt:
            pass
        finally:
            # 清理
            loop.run_until_complete(window.cleanup())


if __name__ == "__main__":
    main() 