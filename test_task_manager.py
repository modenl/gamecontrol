#!/usr/bin/env python3
"""
测试任务管理器是否能解决qasync冲突问题
"""

import sys
import asyncio
import logging
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QLabel, QTextEdit
from PyQt6.QtCore import QTimer
import qasync

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 导入任务管理器
from logic.task_manager import get_task_manager, run_task_safe

class TaskManagerTest(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Task Manager Test - qasync Conflict Fix")
        self.setGeometry(100, 100, 600, 400)
        
        # 创建UI
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # 标题
        title = QLabel("Task Manager Test - 测试qasync冲突修复")
        layout.addWidget(title)
        
        # 状态标签
        self.status_label = QLabel("Ready to test...")
        layout.addWidget(self.status_label)
        
        # 测试按钮
        self.test_button = QPushButton("Start Concurrent Tasks Test")
        self.test_button.clicked.connect(self.test_concurrent_tasks)
        layout.addWidget(self.test_button)
        
        # 日志区域
        self.log_area = QTextEdit()
        self.log_area.setMaximumHeight(250)
        layout.addWidget(self.log_area)
        
        # 获取任务管理器
        self.task_manager = get_task_manager()
        
    def log(self, message):
        """添加日志"""
        self.log_area.append(f"[{asyncio.get_event_loop().time():.2f}] {message}")
        logger.info(message)
    
    def test_concurrent_tasks(self):
        """测试并发任务"""
        self.log("🧪 开始测试并发任务...")
        self.test_button.setEnabled(False)
        self.status_label.setText("Testing concurrent tasks...")
        
        # 创建多个模拟任务
        async def task1():
            self.log("📋 任务1开始")
            await asyncio.sleep(1)
            self.log("📋 任务1完成")
            return "task1_result"
        
        async def task2():
            self.log("📋 任务2开始")
            await asyncio.sleep(0.5)
            self.log("📋 任务2完成")
            return "task2_result"
        
        async def task3():
            self.log("📋 任务3开始")
            await asyncio.sleep(1.5)
            self.log("📋 任务3完成")
            return "task3_result"
        
        # 使用任务管理器同时启动多个任务
        def on_task_complete(result):
            self.log(f"✅ 任务完成: {result}")
        
        def on_task_error(error):
            self.log(f"❌ 任务失败: {error}")
        
        # 启动任务
        task_id1 = run_task_safe(task1(), "test_task_1", on_task_complete, on_task_error)
        task_id2 = run_task_safe(task2(), "test_task_2", on_task_complete, on_task_error)
        task_id3 = run_task_safe(task3(), "test_task_3", on_task_complete, on_task_error)
        
        self.log(f"🚀 启动了3个并发任务: {task_id1}, {task_id2}, {task_id3}")
        
        # 5秒后检查结果
        QTimer.singleShot(5000, self.check_test_results)
    
    def check_test_results(self):
        """检查测试结果"""
        running_tasks = self.task_manager.get_running_tasks()
        self.log(f"📊 当前任务状态: {running_tasks}")
        
        if all(running_tasks.values()):
            self.log("🎉 所有任务都已完成，没有发生qasync冲突！")
            self.status_label.setText("✅ Test passed - No qasync conflicts!")
        else:
            self.log("⚠️ 还有任务在运行中...")
            self.status_label.setText("⏳ Some tasks still running...")
        
        self.test_button.setEnabled(True)
    
    def closeEvent(self, event):
        """关闭事件"""
        self.log("🔄 关闭应用程序...")
        # 取消所有任务（使用同步方法避免qasync冲突）
        self.task_manager.cancel_all_tasks_sync()
        event.accept()

def main():
    """主函数"""
    print("=" * 60)
    print("🧪 Task Manager Test - qasync Conflict Fix")
    print("=" * 60)
    print("This test will verify that the TaskManager prevents")
    print("qasync conflicts when running concurrent async tasks.")
    print("=" * 60)
    
    app = QApplication(sys.argv)
    
    # 设置qasync事件循环
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    window = TaskManagerTest()
    window.show()
    
    with loop:
        loop.run_forever()

if __name__ == "__main__":
    main() 