#!/usr/bin/env python3
"""
正确处理异步事件循环的自动更新测试脚本
"""

import sys
import asyncio
import logging
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QLabel, QTextEdit
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QFont
import qasync

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 导入自动更新器
from logic.auto_updater import get_updater

class AsyncUpdateTest(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Async Auto Update Test")
        self.setGeometry(100, 100, 600, 400)
        
        # 创建UI
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # 标题
        title = QLabel("Auto Update Test (Async)")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # 状态标签
        self.status_label = QLabel("Initializing...")
        layout.addWidget(self.status_label)
        
        # 测试按钮
        self.test_button = QPushButton("Test Update Check")
        self.test_button.clicked.connect(self.test_update)
        layout.addWidget(self.test_button)
        
        # 日志区域
        self.log_area = QTextEdit()
        self.log_area.setMaximumHeight(250)
        layout.addWidget(self.log_area)
        
        # 初始化自动更新器
        self.init_updater()
        
    def init_updater(self):
        """初始化自动更新器"""
        try:
            self.auto_updater = get_updater(self)
            self.auto_updater.update_available.connect(self.on_update_available)
            self.auto_updater.update_check_failed.connect(self.on_update_failed)
            
            self.log("✓ Auto updater initialized successfully")
            self.status_label.setText("Ready - Will auto-test in 2 seconds")
            
            # 2秒后自动测试
            QTimer.singleShot(2000, self.auto_test)
            
        except Exception as e:
            self.log(f"✗ Failed to initialize auto updater: {e}")
            self.status_label.setText(f"Error: {e}")
    
    def log(self, message):
        """添加日志"""
        logger.info(message)
        self.log_area.append(f"{message}")
        
    def auto_test(self):
        """自动测试"""
        self.log("🚀 Starting automatic update check test...")
        self.test_update()
        
    def test_update(self):
        """测试更新检查"""
        self.log("📡 Testing update check...")
        self.test_button.setEnabled(False)
        self.test_button.setText("Checking...")
        self.status_label.setText("Checking for updates...")
        
        try:
            # 检查是否可以更新
            can_update, reason = self.auto_updater.can_update_now()
            self.log(f"🔍 Can update: {can_update}")
            if reason:
                self.log(f"   Reason: {reason}")
            
            if not can_update:
                self.status_label.setText(f"Cannot update: {reason}")
                self.restore_button()
                return
            
            # 开始检查更新 - 使用异步方式
            self.log("🌐 Starting GitHub API check...")
            asyncio.create_task(self.async_check_update())
            
        except Exception as e:
            self.log(f"❌ Error during update check: {e}")
            self.status_label.setText(f"Error: {e}")
            self.restore_button()
        
    async def async_check_update(self):
        """异步检查更新"""
        try:
            # 直接调用异步方法
            await self.auto_updater._async_check_for_updates()
            
            # 如果没有触发信号，说明没有更新
            QTimer.singleShot(1000, lambda: self.check_no_update())
            
        except Exception as e:
            self.log(f"❌ Async update check failed: {e}")
            self.status_label.setText(f"Check failed: {e}")
            self.restore_button()
    
    def check_no_update(self):
        """检查是否没有更新"""
        if self.status_label.text() == "Checking for updates...":
            self.log("ℹ️ No updates available (current version is latest)")
            self.status_label.setText("No updates available")
            self.restore_button()
    
    def restore_button(self):
        """恢复按钮"""
        self.test_button.setEnabled(True)
        self.test_button.setText("Test Update Check")
    
    def on_update_available(self, update_info):
        """更新可用"""
        self.log(f"🎉 UPDATE AVAILABLE!")
        self.log(f"   Version: {update_info.version}")
        self.log(f"   Download URL: {update_info.download_url}")
        self.log(f"   File size: {update_info.file_size:,} bytes")
        self.log(f"   Release notes: {update_info.release_notes[:100]}...")
        self.status_label.setText(f"Update available: v{update_info.version}")
        self.restore_button()
        
    def on_update_failed(self, error_msg):
        """更新检查失败"""
        self.log(f"❌ Update check failed: {error_msg}")
        self.status_label.setText(f"Check failed: {error_msg}")
        self.restore_button()
        
    def closeEvent(self, event):
        """关闭事件"""
        self.log("🔄 Closing auto updater...")
        if hasattr(self, 'auto_updater') and self.auto_updater:
            # 在事件循环中关闭
            asyncio.create_task(self.auto_updater.close())
        event.accept()

async def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    window = AsyncUpdateTest()
    window.show()
    
    # 运行应用
    await app.exec()

def run_app():
    """运行应用"""
    app = QApplication(sys.argv)
    
    # 设置异步事件循环
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    window = AsyncUpdateTest()
    window.show()
    
    with loop:
        loop.run_until_complete(main())

if __name__ == "__main__":
    run_app() 