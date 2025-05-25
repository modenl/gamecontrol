#!/usr/bin/env python3
"""
简单测试脚本 - 测试应用启动和退出
"""

import sys
import time
import logging
from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SimpleTestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("简单测试窗口")
        self.resize(400, 300)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # 添加标签
        label = QLabel("这是一个简单的测试窗口")
        layout.addWidget(label)
        
        # 添加关闭按钮
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.close)
        layout.addWidget(close_button)
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        logger.info("窗口关闭事件触发")
        event.accept()

def main():
    logger.info("开始简单测试...")
    
    app = QApplication(sys.argv)
    
    logger.info("创建测试窗口...")
    window = SimpleTestWindow()
    window.show()
    
    logger.info("应用程序开始运行...")
    result = app.exec()
    
    logger.info("应用程序退出")
    return result

if __name__ == "__main__":
    sys.exit(main()) 