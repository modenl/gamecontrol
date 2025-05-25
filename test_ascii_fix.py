#!/usr/bin/env python3
"""
测试ASCII art修复效果
"""

import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QTextEdit, QPushButton
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

class ASCIITestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ASCII Art 修复测试")
        self.resize(800, 600)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # 创建文本编辑器
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #3d3d3d;
                color: #ffffff;
                border: 1px solid #6c757d;
                border-radius: 8px;
                padding: 20px;
            }
        """)
        layout.addWidget(self.text_edit)
        
        # 测试按钮
        btn_layout = QVBoxLayout()
        
        btn1 = QPushButton("测试三角形")
        btn1.clicked.connect(self.test_triangle)
        btn_layout.addWidget(btn1)
        
        btn2 = QPushButton("测试复杂图形")
        btn2.clicked.connect(self.test_complex)
        
        btn_layout.addWidget(btn2)
        
        layout.addLayout(btn_layout)
        
    def test_triangle(self):
        """测试简单三角形"""
        triangle_text = """考虑下面的三角形:

```
      A
     /|\\
    / | \\
   /  |  \\
  /   |h  \\
 /    |    \\
/     |     \\
B-----+-----C
    base
```

在这个直角三角形中，已知：
• 底边 base = 12 单位
• 高度 h = 5 单位

请计算三角形的面积。"""
        
        # 使用纯文本模式显示
        self.text_edit.setPlainText(triangle_text)
        # 设置等宽字体
        mono_font = QFont("Courier New", 12)
        mono_font.setStyleHint(QFont.StyleHint.Monospace)
        self.text_edit.setFont(mono_font)
        
    def test_complex(self):
        """测试复杂图形"""
        complex_text = """几何题目测试:

```
        Y
        ^
        |
        |    * (3,4)
        |   /|
        |  / |
        | /  |
        |/   |
        +----+-----> X
        |    |
        |    |
        |    * (3,-4)
        |
```

这是一个坐标系中的点分布图。"""
        
        # 使用纯文本模式显示
        self.text_edit.setPlainText(complex_text)
        # 设置等宽字体
        mono_font = QFont("Courier New", 12)
        mono_font.setStyleHint(QFont.StyleHint.Monospace)
        self.text_edit.setFont(mono_font)

def main():
    app = QApplication(sys.argv)
    
    # 应用深色主题
    try:
        from ui.base import apply_dark_style
        apply_dark_style(app)
    except:
        pass
    
    window = ASCIITestWindow()
    window.show()
    
    return app.exec()

if __name__ == "__main__":
    sys.exit(main()) 