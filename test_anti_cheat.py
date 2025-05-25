#!/usr/bin/env python3
"""
测试防作弊功能
"""

import sys
import asyncio
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QLabel
from PyQt6.QtCore import Qt, QTimer

class AntiCheatTestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("防作弊功能测试")
        self.resize(600, 400)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # 状态显示
        self.status_label = QLabel("点击按钮开始测试")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        
        # 测试按钮
        btn1 = QPushButton("测试1: 正常答题流程")
        btn1.clicked.connect(self.test_normal_flow)
        layout.addWidget(btn1)
        
        btn2 = QPushButton("测试2: 检查中尝试关闭")
        btn2.clicked.connect(self.test_close_during_check)
        layout.addWidget(btn2)
        
        btn3 = QPushButton("测试3: 重复提交同一题")
        btn3.clicked.connect(self.test_duplicate_submission)
        layout.addWidget(btn3)
        
        btn4 = QPushButton("打开数学面板")
        btn4.clicked.connect(self.open_math_panel)
        layout.addWidget(btn4)
        
        self.math_panel = None
        
    def test_normal_flow(self):
        """测试正常答题流程"""
        self.status_label.setText("测试1: 正常答题流程 - 这应该正常工作")
        
    def test_close_during_check(self):
        """测试检查中尝试关闭"""
        self.status_label.setText("测试2: 检查中尝试关闭 - 打开数学面板，提交答案后立即尝试关闭")
        
    def test_duplicate_submission(self):
        """测试重复提交同一题"""
        self.status_label.setText("测试3: 重复提交同一题 - 应该被阻止")
        
    def open_math_panel(self):
        """打开数学面板进行实际测试"""
        try:
            from ui.math_panel_simple import SimpleMathPanel
            
            if self.math_panel is None:
                self.math_panel = SimpleMathPanel(self)
                self.math_panel.show()
                self.status_label.setText("数学面板已打开 - 可以进行实际测试")
            else:
                self.status_label.setText("数学面板已经打开")
                
        except Exception as e:
            self.status_label.setText(f"打开数学面板失败: {e}")

def main():
    app = QApplication(sys.argv)
    
    # 设置异步事件循环
    try:
        import qasync
        loop = qasync.QEventLoop(app)
        asyncio.set_event_loop(loop)
    except ImportError:
        print("Warning: qasync not available, some async features may not work")
    
    # 应用深色主题
    try:
        from ui.base import apply_dark_style
        apply_dark_style(app)
    except:
        pass
    
    window = AntiCheatTestWindow()
    window.show()
    
    try:
        if 'loop' in locals():
            with loop:
                return loop.run_forever()
        else:
            return app.exec()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    sys.exit(main()) 