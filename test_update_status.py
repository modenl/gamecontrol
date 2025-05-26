#!/usr/bin/env python3
"""
测试更新状态检查的脚本
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
from logic.auto_updater import get_updater

class UpdateStatusTest(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Update Status Test")
        self.setGeometry(100, 100, 400, 300)
        
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
        self.status_label = QLabel("Initializing...")
        layout.addWidget(self.status_label)
        
        # 测试按钮
        self.test_button = QPushButton("Test Update Check")
        self.test_button.clicked.connect(self.test_update)
        layout.addWidget(self.test_button)
        
        # 状态切换按钮
        self.session_button = QPushButton("Toggle Session Active")
        self.session_button.clicked.connect(self.toggle_session)
        layout.addWidget(self.session_button)
        
        self.math_button = QPushButton("Toggle Math Panel")
        self.math_button.clicked.connect(self.toggle_math)
        layout.addWidget(self.math_button)
        
        # 状态显示
        self.session_status = QLabel("Session Active: False")
        layout.addWidget(self.session_status)
        
        self.math_status = QLabel("Math Panel: None")
        layout.addWidget(self.math_status)
        
    def init_updater(self):
        """初始化自动更新器"""
        try:
            self.auto_updater = get_updater(self)
            self.auto_updater.update_available.connect(self.on_update_available)
            self.auto_updater.update_check_failed.connect(self.on_update_failed)
            
            self.status_label.setText("Auto updater initialized")
            logger.info("✓ Auto updater initialized successfully")
            
        except Exception as e:
            self.status_label.setText(f"Error: {e}")
            logger.error(f"✗ Failed to initialize auto updater: {e}")
    
    def toggle_session(self):
        """切换会话状态"""
        self.session_active = not self.session_active
        self.session_status.setText(f"Session Active: {self.session_active}")
        logger.info(f"Session active toggled to: {self.session_active}")
        
    def toggle_math(self):
        """切换数学练习状态"""
        if self.math_panel is None:
            self.math_panel = "dummy_panel"  # 模拟有数学练习
        else:
            self.math_panel = None
        self.math_status.setText(f"Math Panel: {self.math_panel}")
        logger.info(f"Math panel toggled to: {self.math_panel}")
        
    def test_update(self):
        """测试更新检查"""
        logger.info("🧪 Testing update check...")
        self.test_button.setEnabled(False)
        self.test_button.setText("Checking...")
        
        # 检查是否可以更新
        can_update, reason = self.auto_updater.can_update_now()
        logger.info(f"🔍 Can update: {can_update}")
        if reason:
            logger.info(f"   Reason: {reason}")
        
        if not can_update:
            self.status_label.setText(f"Cannot update: {reason}")
            logger.warning(f"❌ Cannot update: {reason}")
            self.restore_button()
            return
        
        # 开始检查更新 - 使用异步方式
        logger.info("🌐 Starting update check...")
        asyncio.create_task(self.async_check_update())
        
        # 10秒后恢复按钮
        QTimer.singleShot(10000, self.restore_button)
        
    async def async_check_update(self):
        """异步检查更新"""
        try:
            await self.auto_updater._async_check_for_updates()
        except Exception as e:
            logger.error(f"❌ Async update check failed: {e}")
            self.status_label.setText(f"Check failed: {e}")
            self.restore_button()
        
    def restore_button(self):
        """恢复按钮"""
        self.test_button.setEnabled(True)
        self.test_button.setText("Test Update Check")
        
    def on_update_available(self, update_info):
        """更新可用"""
        logger.info(f"🎉 UPDATE AVAILABLE!")
        logger.info(f"   Version: {update_info.version}")
        logger.info(f"   Download URL: {update_info.download_url}")
        logger.info(f"   File size: {update_info.asset_size:,} bytes")
        self.status_label.setText(f"Update available: v{update_info.version}")
        self.restore_button()
        
    def on_update_failed(self, error_msg):
        """更新检查失败"""
        logger.error(f"❌ Update check failed: {error_msg}")
        self.status_label.setText(f"Check failed: {error_msg}")
        self.restore_button()

def main():
    """主函数"""
    print("=" * 60)
    print("🧪 Update Status Test")
    print("=" * 60)
    print("This will test the update status checking logic.")
    print("You can toggle session and math panel states to see")
    print("how they affect the update availability.")
    print("=" * 60)
    
    app = QApplication(sys.argv)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    window = UpdateStatusTest()
    window.show()
    
    with loop:
        loop.run_forever()

if __name__ == "__main__":
    main() 