#!/usr/bin/env python3
"""
最终测试任务管理器在qasync环境中的表现
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

class FinalTaskManagerTest(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Final TaskManager Test - qasync Environment")
        self.setGeometry(100, 100, 700, 500)
        
        # 创建UI
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # 标题
        title = QLabel("Final TaskManager Test - qasync 环境测试")
        layout.addWidget(title)
        
        # 状态标签
        self.status_label = QLabel("Ready to test...")
        layout.addWidget(self.status_label)
        
        # 测试按钮
        self.test_button = QPushButton("Start Comprehensive Test")
        self.test_button.clicked.connect(self.start_comprehensive_test)
        layout.addWidget(self.test_button)
        
        # 日志区域
        self.log_area = QTextEdit()
        self.log_area.setMaximumHeight(300)
        layout.addWidget(self.log_area)
        
        # 获取任务管理器
        self.task_manager = get_task_manager()
        
        # 测试计数器
        self.test_count = 0
        self.completed_count = 0
        
    def log(self, message):
        """添加日志"""
        self.log_area.append(f"[{self.test_count:02d}] {message}")
        logger.info(message)
    
    def start_comprehensive_test(self):
        """开始综合测试"""
        self.log("🧪 开始综合测试 TaskManager 在 qasync 环境中的表现...")
        self.test_button.setEnabled(False)
        self.status_label.setText("Running comprehensive tests...")
        self.test_count = 0
        self.completed_count = 0
        
        # 测试1: 快速连续任务
        self.log("📋 测试1: 快速连续任务")
        for i in range(5):
            self.test_count += 1
            task_id = run_task_safe(
                self.quick_task(f"Quick{i+1}", 0.1),
                task_id=f"quick_{i+1}",
                on_complete=self.on_task_complete,
                on_error=self.on_task_error
            )
            self.log(f"启动快速任务: {task_id}")
        
        # 测试2: 延迟启动任务
        self.log("📋 测试2: 延迟启动任务")
        for i in range(3):
            self.test_count += 1
            task_id = run_task_safe(
                self.delayed_task(f"Delayed{i+1}", 0.2),
                task_id=f"delayed_{i+1}",
                on_complete=self.on_task_complete,
                on_error=self.on_task_error,
                delay_ms=i * 50  # 延迟启动
            )
            self.log(f"启动延迟任务: {task_id}")
        
        # 测试3: 长时间任务
        self.log("📋 测试3: 长时间任务")
        self.test_count += 1
        task_id = run_task_safe(
            self.long_task("LongTask", 1.0),
            task_id="long_task",
            on_complete=self.on_task_complete,
            on_error=self.on_task_error
        )
        self.log(f"启动长时间任务: {task_id}")
        
        # 5秒后检查结果
        QTimer.singleShot(5000, self.check_final_results)
    
    async def quick_task(self, name, duration):
        """快速任务"""
        self.log(f"⚡ 快速任务 {name} 开始")
        await asyncio.sleep(duration)
        self.log(f"⚡ 快速任务 {name} 完成")
        return f"{name}_result"
    
    async def delayed_task(self, name, duration):
        """延迟任务"""
        self.log(f"⏰ 延迟任务 {name} 开始")
        await asyncio.sleep(duration)
        self.log(f"⏰ 延迟任务 {name} 完成")
        return f"{name}_result"
    
    async def long_task(self, name, duration):
        """长时间任务"""
        self.log(f"🕐 长时间任务 {name} 开始")
        await asyncio.sleep(duration)
        self.log(f"🕐 长时间任务 {name} 完成")
        return f"{name}_result"
    
    def on_task_complete(self, result):
        """任务完成回调"""
        self.completed_count += 1
        self.log(f"✅ 任务完成: {result} (完成 {self.completed_count}/{self.test_count})")
    
    def on_task_error(self, error):
        """任务错误回调"""
        self.log(f"❌ 任务失败: {error}")
    
    def check_final_results(self):
        """检查最终结果"""
        running_tasks = self.task_manager.get_running_tasks()
        self.log(f"📊 当前任务状态: {running_tasks}")
        
        if self.completed_count == self.test_count:
            self.log("🎉 所有测试完美通过！没有 qasync 冲突！")
            self.status_label.setText("✅ All tests passed - No qasync conflicts!")
        elif self.completed_count > 0:
            self.log(f"⚠️ 部分测试完成: {self.completed_count}/{self.test_count}")
            self.status_label.setText(f"⚠️ Partial success: {self.completed_count}/{self.test_count}")
        else:
            self.log("❌ 测试失败，没有任务完成")
            self.status_label.setText("❌ Tests failed")
        
        self.test_button.setEnabled(True)
    
    def closeEvent(self, event):
        """关闭事件"""
        self.log("🔄 关闭应用程序...")
        # 取消所有任务（使用同步方法避免qasync冲突）
        self.task_manager.cancel_all_tasks_sync()
        event.accept()

def main():
    """主函数"""
    print("=" * 70)
    print("🧪 Final TaskManager Test - qasync Environment")
    print("=" * 70)
    print("This test verifies that the TaskManager works correctly")
    print("in a qasync environment without any conflicts.")
    print("=" * 70)
    
    app = QApplication(sys.argv)
    
    # 设置qasync事件循环
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    window = FinalTaskManagerTest()
    window.show()
    
    with loop:
        loop.run_forever()

if __name__ == "__main__":
    main() 