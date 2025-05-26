#!/usr/bin/env python3
"""
简化的自动更新测试脚本
"""

import sys
import asyncio
import logging
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QLabel, QTextEdit
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QFont

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 导入自动更新器
from logic.auto_updater import get_updater

class SimpleUpdateTest(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simple Auto Update Test")
        self.setGeometry(100, 100, 500, 300)
        
        # 创建UI
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # 状态标签
        self.status_label = QLabel("Initializing auto updater...")
        layout.addWidget(self.status_label)
        
        # 测试按钮
        self.test_button = QPushButton("Test Update Check")
        self.test_button.clicked.connect(self.test_update)
        layout.addWidget(self.test_button)
        
        # 日志区域
        self.log_area = QTextEdit()
        layout.addWidget(self.log_area)
        
        # 初始化自动更新器
        self.init_updater()
        
    def init_updater(self):
        """初始化自动更新器"""
        try:
            self.auto_updater = get_updater(self)
            self.auto_updater.update_available.connect(self.on_update_available)
            self.auto_updater.update_check_failed.connect(self.on_update_failed)
            
            self.log("Auto updater initialized successfully")
            self.status_label.setText("Ready - Click button to test")
            
            # 1秒后自动测试
            QTimer.singleShot(1000, self.auto_test)
            
        except Exception as e:
            self.log(f"Failed to initialize auto updater: {e}")
            self.status_label.setText(f"Error: {e}")
    
    def log(self, message):
        """添加日志"""
        logger.info(message)
        self.log_area.append(f"{message}")
        
    def auto_test(self):
        """自动测试"""
        self.log("Starting automatic test...")
        self.test_update()
        
    def test_update(self):
        """测试更新检查"""
        self.log("Testing update check...")
        self.test_button.setEnabled(False)
        self.status_label.setText("Checking for updates...")
        
        try:
            # 检查是否可以更新
            can_update, reason = self.auto_updater.can_update_now()
            self.log(f"Can update: {can_update}, Reason: {reason}")
            
            if not can_update:
                self.status_label.setText(f"Cannot update: {reason}")
                self.test_button.setEnabled(True)
                return
            
            # 开始检查更新
            self.log("Starting update check...")
            self.auto_updater.check_for_updates(manual=True)
            
        except Exception as e:
            self.log(f"Error during update check: {e}")
            self.status_label.setText(f"Error: {e}")
            self.test_button.setEnabled(True)
        
        # 10秒后恢复按钮
        QTimer.singleShot(10000, self.restore_button)
    
    def restore_button(self):
        """恢复按钮"""
        self.test_button.setEnabled(True)
        if self.status_label.text() == "Checking for updates...":
            self.status_label.setText("Check completed")
    
    def on_update_available(self, update_info):
        """更新可用"""
        self.log(f"UPDATE AVAILABLE!")
        self.log(f"Version: {update_info.version}")
        self.log(f"Download URL: {update_info.download_url}")
        self.log(f"File size: {update_info.file_size} bytes")
        self.status_label.setText(f"Update available: v{update_info.version}")
        
    def on_update_failed(self, error_msg):
        """更新检查失败"""
        self.log(f"Update check failed: {error_msg}")
        self.status_label.setText(f"Check failed: {error_msg}")

def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    window = SimpleUpdateTest()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 