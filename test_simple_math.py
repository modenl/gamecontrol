#!/usr/bin/env python3
"""
简单的数学面板测试
"""

import sys
import asyncio
from PyQt6.QtWidgets import QApplication
import qasync

def main():
    app = QApplication(sys.argv)
    
    # 设置异步事件循环
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    # 应用深色主题
    try:
        from ui.base import apply_dark_style
        apply_dark_style(app)
    except:
        pass
    
    # 创建数学面板
    try:
        from ui.math_panel_simple import SimpleMathPanel
        panel = SimpleMathPanel()
        panel.show()
        
        print("数学面板已打开，可以测试防作弊功能")
        
    except Exception as e:
        print(f"创建数学面板失败: {e}")
        return 1
    
    # 运行事件循环
    with loop:
        return loop.run_forever()

if __name__ == "__main__":
    sys.exit(main()) 