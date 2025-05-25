#!/usr/bin/env python3
"""
测试解决方案显示改进
"""

import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QTextEdit, QPushButton, QFrame
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

class SolutionTestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("解决方案显示测试")
        self.resize(1200, 900)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # 创建结果显示区域
        self.result_frame = QFrame()
        self.result_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.result_frame.setFrameShadow(QFrame.Shadow.Raised)
        result_layout = QVBoxLayout(self.result_frame)
        
        self.result_display = QTextEdit()
        self.result_display.setReadOnly(True)
        self.result_display.setMinimumHeight(150)
        self.result_display.setMaximumHeight(300)
        result_font = QFont()
        result_font.setPointSize(12)
        self.result_display.setFont(result_font)
        result_layout.addWidget(self.result_display)
        
        layout.addWidget(self.result_frame)
        
        # 测试按钮
        btn_layout = QVBoxLayout()
        
        btn1 = QPushButton("测试短解释")
        btn1.clicked.connect(self.test_short_explanation)
        btn_layout.addWidget(btn1)
        
        btn2 = QPushButton("测试长解释")
        btn2.clicked.connect(self.test_long_explanation)
        btn_layout.addWidget(btn2)
        
        btn3 = QPushButton("测试ASCII解释")
        btn3.clicked.connect(self.test_ascii_explanation)
        btn_layout.addWidget(btn3)
        
        layout.addLayout(btn_layout)
        
    def test_short_explanation(self):
        """测试短解释"""
        result_style = """
            QTextEdit {
                background-color: #f8d7da;
                border: 2px solid #dc3545;
                border-radius: 8px;
                padding: 15px;
                color: #721c24;
            }
        """
        result_text = """
        <h3 style='color: #721c24; margin-top: 0;'>✗ Incorrect!</h3>
        <p><b>Correct Answer:</b> 30 平方单位</p>
        <p><b>Explanation:</b><br>
        三角形的面积公式是：面积 = (1/2) × 底边 × 高度<br>
        代入已知数值：面积 = (1/2) × 12 × 5 = 30 平方单位
        </p>
        """
        
        self.result_display.setStyleSheet(result_style)
        self.result_display.setHtml(result_text)
        
    def test_long_explanation(self):
        """测试长解释"""
        result_style = """
            QTextEdit {
                background-color: #f8d7da;
                border: 2px solid #dc3545;
                border-radius: 8px;
                padding: 15px;
                color: #721c24;
            }
        """
        result_text = """
        <h3 style='color: #721c24; margin-top: 0;'>✗ Incorrect!</h3>
        <p><b>Correct Answer:</b> 30 平方单位</p>
        <p><b>Explanation:</b><br>
        这是一个关于三角形面积计算的问题。让我们详细分析一下：<br><br>
        
        <b>1. 识别图形类型：</b><br>
        从题目描述可以看出，这是一个直角三角形，其中有一条垂直的高线从顶点A垂直下降到底边BC。<br><br>
        
        <b>2. 理解面积公式：</b><br>
        三角形的面积公式是：面积 = (1/2) × 底边 × 高度<br>
        这个公式适用于任何三角形，只要我们知道一条边的长度和对应的高度。<br><br>
        
        <b>3. 识别已知条件：</b><br>
        • 底边 (base) = 12 单位<br>
        • 高度 (h) = 5 单位<br><br>
        
        <b>4. 应用公式：</b><br>
        面积 = (1/2) × 底边 × 高度<br>
        面积 = (1/2) × 12 × 5<br>
        面积 = (1/2) × 60<br>
        面积 = 30 平方单位<br><br>
        
        <b>5. 验证答案：</b><br>
        我们可以通过检查单位来验证答案的合理性。长度单位相乘得到面积单位（平方单位），这是正确的。<br><br>
        
        因此，这个直角三角形的面积是 30 平方单位。
        </p>
        """
        
        self.result_display.setStyleSheet(result_style)
        self.result_display.setHtml(result_text)
        
    def test_ascii_explanation(self):
        """测试包含ASCII图形的解释"""
        result_style = """
            QTextEdit {
                background-color: #f8d7da;
                border: 2px solid #dc3545;
                border-radius: 8px;
                padding: 15px;
                color: #721c24;
            }
        """
        
        ascii_explanation = """让我们通过图形来理解这个问题：

      A
     /|\\
    / | \\
   /  |  \\
  /   |h=5\\
 /    |    \\
/     |     \\
B-----+-----C
   base=12

在这个直角三角形中：
- 底边BC = 12单位
- 高度h = 5单位（从A点垂直到BC）

面积计算：
面积 = (1/2) × 底边 × 高度
面积 = (1/2) × 12 × 5
面积 = 30 平方单位

这就是为什么答案是30平方单位。"""
        
        result_text = f"""
        <h3 style='color: #721c24; margin-top: 0;'>✗ Incorrect!</h3>
        <p><b>Correct Answer:</b> 30 平方单位</p>
        <p><b>Explanation:</b></p>
        <pre style='font-family: monospace; background-color: #f0f0f0; padding: 10px; border-radius: 4px; color: #333; white-space: pre-wrap;'>{ascii_explanation}</pre>
        """
        
        self.result_display.setStyleSheet(result_style)
        self.result_display.setHtml(result_text)

def main():
    app = QApplication(sys.argv)
    
    # 应用深色主题
    try:
        from ui.base import apply_dark_style
        apply_dark_style(app)
    except:
        pass
    
    window = SolutionTestWindow()
    window.show()
    
    return app.exec()

if __name__ == "__main__":
    sys.exit(main()) 