#!/usr/bin/env python3
"""
直接测试更新对话框显示的脚本
"""

import sys
import logging
import asyncio
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QLabel
from PyQt6.QtCore import QTimer
import qasync

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 导入自动更新器
from logic.auto_updater import get_updater, UpdateInfo

class UpdateDialogTest(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Update Dialog Test")
        self.setGeometry(100, 100, 400, 200)
        
        # 模拟主窗口的状态
        self.session_active = False  # 没有活动会话
        self.math_panel = None       # 没有数学练习
        
        self.setup_ui()
        self.init_updater()
        
    def setup_ui(self):
        """设置UI"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # 状态标签
        self.status_label = QLabel("Ready to test update dialog")
        layout.addWidget(self.status_label)
        
        # 测试按钮
        self.test_button = QPushButton("Show Mock Update Dialog")
        self.test_button.clicked.connect(self.show_mock_dialog)
        layout.addWidget(self.test_button)
        
    def init_updater(self):
        """初始化自动更新器"""
        try:
            self.auto_updater = get_updater(self)
            logger.info("✓ Auto updater initialized successfully")
            
        except Exception as e:
            self.status_label.setText(f"Error: {e}")
            logger.error(f"✗ Failed to initialize auto updater: {e}")
    
    def show_mock_dialog(self):
        """显示模拟的更新对话框"""
        logger.info("🧪 Testing update dialog display...")
        
        # 创建模拟的更新信息
        mock_update_info = UpdateInfo(
            version="1.0.1",
            download_url="https://github.com/modenl/gamecontrol/releases/download/v1.0.1/GameTimeLimiter.exe",
            release_notes="# GameTimeLimiter v1.0.1\n\n## 新功能\n\n- 测试自动更新功能\n- 修复已知问题",
            published_at="2025-05-26T01:34:16Z",
            asset_name="GameTimeLimiter.exe",
            asset_size=51799892
        )
        
        logger.info(f"📦 Mock update info: {mock_update_info}")
        
        # 检查是否可以更新
        can_update, reason = self.auto_updater.can_update_now()
        logger.info(f"🔍 Can update: {can_update}")
        if reason:
            logger.info(f"   Reason: {reason}")
        
        if not can_update:
            self.status_label.setText(f"Cannot update: {reason}")
            logger.warning(f"❌ Cannot update: {reason}")
            return
        
        # 直接调用显示对话框方法
        logger.info("🎯 Calling show_update_dialog directly...")
        try:
            self.auto_updater.show_update_dialog(mock_update_info)
            self.status_label.setText("Update dialog should be shown")
        except Exception as e:
            logger.error(f"❌ Failed to show update dialog: {e}")
            self.status_label.setText(f"Dialog error: {e}")

def main():
    """主函数"""
    print("=" * 60)
    print("🧪 Update Dialog Test")
    print("=" * 60)
    print("This will test the update dialog display directly.")
    print("Click the button to show a mock update dialog.")
    print("=" * 60)
    
    app = QApplication(sys.argv)
    
    # 设置qasync事件循环
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    window = UpdateDialogTest()
    window.show()
    
    with loop:
        loop.run_forever()

if __name__ == "__main__":
    main() 