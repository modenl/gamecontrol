#!/usr/bin/env python3
"""
简单的ASCII art测试
"""

import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

class SimpleTestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("简单ASCII测试")
        self.resize(600, 400)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # 创建标签
        label = QLabel()
        label.setWordWrap(True)
        label.setStyleSheet("""
            QLabel {
                background-color: #3d3d3d;
                color: #ffffff;
                border: 1px solid #6c757d;
                border-radius: 8px;
                padding: 20px;
            }
        """)
        
        # 简单的ASCII art测试
        test_html = '''
        <h3>ASCII Art 测试</h3>
        
        <div style="margin: 20px auto; text-align: center; max-width: 90%;">
        <pre style="font-family: 'Courier New', monospace; 
                   background-color: #1e1e1e; 
                   color: #d4d4d4; 
                   padding: 20px; 
                   border: 2px solid #404040; 
                   border-radius: 8px; 
                   text-align: left; 
                   white-space: pre; 
                   overflow-x: auto; 
                   line-height: 1.1; 
                   font-size: 14px; 
                   font-weight: 400;
                   display: block;
                   margin: 0 auto;
                   width: fit-content;
                   max-width: 100%;">      A
     /|\\
    / | \\
   /  |  \\
  /   |h  \\
 /    |    \\
/     |     \\
B-----+-----C
    base</pre>
        </div>
        
        <p>这是一个简单的三角形图形测试。</p>
        '''
        
        label.setText(test_html)
        layout.addWidget(label)

def main():
    app = QApplication(sys.argv)
    
    # 应用深色主题
    try:
        from ui.base import apply_dark_style
        apply_dark_style(app)
    except:
        pass
    
    window = SimpleTestWindow()
    window.show()
    
    return app.exec()

if __name__ == "__main__":
    sys.exit(main()) 