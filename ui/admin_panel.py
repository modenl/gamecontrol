import asyncio
import logging
import sqlite3
import pygetwindow as gw
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QTabWidget,
    QLabel,
    QPushButton,
    QLineEdit,
    QTextEdit,
    QMessageBox,
    QFrame,
    QTreeWidget,
    QTreeWidgetItem,
    QGroupBox,
    QFormLayout,
    QSpinBox,
    QAbstractItemView,
    QApplication,
    QProgressDialog,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from logic.constants import (
    PADDING_MEDIUM,
    MAX_WEEKLY_LIMIT,
    THEME_DANGER,
    THEME_WARNING,
)

# 配置日志
logger = logging.getLogger("admin_panel")

class AdminPanel(QDialog):
    """管理员控制面板"""

    def __init__(self, parent=None, game_limiter=None):
        super().__init__(parent)
        
        self.parent = parent
        self.game_limiter = game_limiter

        # 设置窗口
        self.setWindowTitle("Administrator Control Panel")
        self.resize(900, 700)
        self.setMinimumSize(800, 600)
        self.setModal(True)

        # 确保窗口监控已停止，避免任务冲突
        if self.parent and hasattr(self.parent, 'window_monitor'):
            if self.parent.window_monitor.is_running:
                logger.info("管理员面板：确保窗口监控已停止")
                asyncio.create_task(self.parent.window_monitor.stop_monitoring())

        # 先设置UI，再加载数据
        self.setup_ui()

        # UI设置完成后再加载数据
        asyncio.create_task(self.load_data())

    def setup_ui(self):
        """设置UI组件"""
        # 主布局
        main_layout = QVBoxLayout(self)

        # 标题
        title_label = QLabel("Administrator Control Panel")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)

        # 选项卡面板
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # 创建各个选项卡
        self.create_time_management_tab()
        self.create_history_tab()
        self.create_system_tab()
        self.create_debug_tab()

        # 底部按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        button_layout.addWidget(close_button)
        main_layout.addLayout(button_layout)

    def create_time_management_tab(self):
        """创建时间管理选项卡"""
        time_tab = QWidget()
        layout = QVBoxLayout(time_tab)

        # 添加选项卡
        self.tab_widget.addTab(time_tab, "Time Management")

        # 标题
        title_label = QLabel("Game Time Management")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # 当前状态框架 - 使用占位符文本，稍后异步加载数据
        status_group = QGroupBox("Current Week Status")
        status_layout = QVBoxLayout(status_group)
        
        # 状态信息占位符
        self.week_start_status = QLabel("Week Start Date: Loading...")
        self.used_time_status = QLabel("Used Time: Loading...")
        self.extra_time_status = QLabel("Extra Reward Time: Loading...")
        self.weekly_limit_status = QLabel("Weekly Time Limit: Loading...")
        self.remaining_time_status = QLabel("Remaining Time: Loading...")
        
        status_layout.addWidget(self.week_start_status)
        status_layout.addWidget(self.used_time_status)
        status_layout.addWidget(self.extra_time_status)
        status_layout.addWidget(self.weekly_limit_status)
        status_layout.addWidget(self.remaining_time_status)

        layout.addWidget(status_group)

        # 修改已用时间框架
        modify_used_group = QGroupBox("Modify Used Time")
        modify_used_layout = QVBoxLayout(modify_used_group)

        # 修改已用时间输入
        modify_used_input_layout = QHBoxLayout()
        modify_used_input_layout.addWidget(QLabel("Adjust Minutes (+/-):"))

        self.modify_used_minutes = QSpinBox()
        self.modify_used_minutes.setMinimum(-MAX_WEEKLY_LIMIT)
        self.modify_used_minutes.setMaximum(MAX_WEEKLY_LIMIT)
        self.modify_used_minutes.setValue(0)
        modify_used_input_layout.addWidget(self.modify_used_minutes)
        modify_used_input_layout.addStretch()

        modify_used_layout.addLayout(modify_used_input_layout)

        # 提示信息
        modify_used_info = QLabel(
            "Positive values increase used time, negative values decrease used time. Used for manually adjusting offline game time."
        )
        modify_used_layout.addWidget(modify_used_info)

        # 按钮
        modify_used_button_layout = QHBoxLayout()

        modify_used_button = QPushButton("Apply Changes")
        modify_used_button.clicked.connect(lambda: asyncio.create_task(self.modify_used_time()))
        modify_used_button_layout.addWidget(modify_used_button)
        modify_used_button_layout.addStretch()

        modify_used_layout.addLayout(modify_used_button_layout)

        layout.addWidget(modify_used_group)
        
        # 添加额外时间框架
        extra_group = QGroupBox("Add Extra Game Time")
        extra_layout = QVBoxLayout(extra_group)
        
        # 额外时间输入
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("Extra Minutes:"))

        self.extra_minutes = QSpinBox()
        self.extra_minutes.setMinimum(0)
        self.extra_minutes.setMaximum(MAX_WEEKLY_LIMIT)
        self.extra_minutes.setValue(30)
        input_layout.addWidget(self.extra_minutes)
        input_layout.addStretch()

        extra_layout.addLayout(input_layout)
        
        # 提示信息
        warning_label = QLabel(f"Note: Weekly Total Time Limit is {MAX_WEEKLY_LIMIT} minutes")
        warning_label.setStyleSheet(f"color: {THEME_WARNING};")
        extra_layout.addWidget(warning_label)

        # 按钮
        button_layout = QHBoxLayout()

        add_button = QPushButton("Add Extra Time")
        add_button.clicked.connect(self.handle_add_extra_time)
        button_layout.addWidget(add_button)

        refresh_button = QPushButton("Refresh Status")
        refresh_button.clicked.connect(lambda: asyncio.create_task(self.refresh_time_tab()))
        button_layout.addWidget(refresh_button)

        button_layout.addStretch()

        extra_layout.addLayout(button_layout)

        layout.addWidget(extra_group)
        layout.addStretch()

    def create_history_tab(self):
        """创建历史记录选项卡"""
        history_tab = QWidget()
        layout = QVBoxLayout(history_tab)

        # 添加选项卡
        self.tab_widget.addTab(history_tab, "History")

        # 标题
        title_label = QLabel("History Management")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # 历史记录树
        self.history_tree = QTreeWidget()
        self.history_tree.setHeaderLabels(
            ["ID", "Start Time", "End Time", "Duration (minutes)", "Game", "Note"]
        )
        self.history_tree.setAlternatingRowColors(True)
        
        # 设置为扩展选择模式，允许多选
        self.history_tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

        # 设置列宽
        self.history_tree.setColumnWidth(0, 50)
        self.history_tree.setColumnWidth(1, 150)
        self.history_tree.setColumnWidth(2, 150)
        self.history_tree.setColumnWidth(3, 100)
        self.history_tree.setColumnWidth(4, 100)
        self.history_tree.setColumnWidth(5, 150)

        layout.addWidget(self.history_tree)
        
        # 添加选择提示
        tip_label = QLabel("Note: Press Ctrl to select multiple records, Press Shift to select range")
        tip_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        layout.addWidget(tip_label)

        # 按钮
        button_layout = QHBoxLayout()

        delete_button = QPushButton("Delete Selected Records")
        delete_button.clicked.connect(lambda: asyncio.create_task(self.delete_session()))
        button_layout.addWidget(delete_button)

        refresh_button = QPushButton("Refresh List")
        refresh_button.clicked.connect(lambda: asyncio.create_task(self.load_sessions()))
        button_layout.addWidget(refresh_button)

        button_layout.addStretch()

        layout.addLayout(button_layout)
        
    def create_system_tab(self):
        """创建系统设置标签页"""
        system_tab = QWidget()
        layout = QVBoxLayout(system_tab)

        # 添加选项卡
        self.tab_widget.addTab(system_tab, "System Settings")

        # 标题
        title_label = QLabel("System Settings")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # 窗口监控设置
        monitor_group = QGroupBox("Window Monitoring Settings")
        monitor_layout = QVBoxLayout(monitor_group)

        # 监控说明
        monitor_info = QLabel(
            "Window monitoring feature will detect and prevent unauthorized game usage when no game session is started."
        )
        monitor_layout.addWidget(monitor_info)

        # 检查间隔设置
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("Check Interval (seconds):"))

        self.monitor_interval = QSpinBox()
        self.monitor_interval.setMinimum(5)
        self.monitor_interval.setMaximum(60)
        # 安全地设置初始值
        if hasattr(self.parent, 'window_monitor'):
            self.monitor_interval.setValue(self.parent.window_monitor.check_interval)
        else:
            self.monitor_interval.setValue(15)  # 默认值
        self.monitor_interval.valueChanged.connect(self.update_monitor_interval)
        interval_layout.addWidget(self.monitor_interval)
        interval_layout.addStretch()

        monitor_layout.addLayout(interval_layout)

        # 监控状态控制
        monitor_control_layout = QHBoxLayout()

        # 启用/禁用监控按钮
        self.monitor_toggle_button = QPushButton()
        self.update_monitor_button_text()
        self.monitor_toggle_button.clicked.connect(self.toggle_monitor)
        monitor_control_layout.addWidget(self.monitor_toggle_button)

        # 测试监控按钮
        test_monitor_button = QPushButton("Test Monitoring Function")
        test_monitor_button.clicked.connect(self.test_monitor)
        monitor_control_layout.addWidget(test_monitor_button)

        monitor_control_layout.addStretch()

        monitor_layout.addLayout(monitor_control_layout)

        layout.addWidget(monitor_group)
        
        # 数学练习设置
        math_group = QGroupBox("Math Exercise Settings")
        math_layout = QVBoxLayout(math_group)

        reset_math_button = QPushButton("Reset Today's Math Questions")
        reset_math_button.clicked.connect(self.reset_math_questions_sync)
        math_layout.addWidget(reset_math_button)

        layout.addWidget(math_group)

        # Minecraft相关控制
        minecraft_group = QGroupBox("Minecraft Control")
        minecraft_layout = QVBoxLayout(minecraft_group)

        kill_button = QPushButton("End Minecraft Process")
        kill_button.clicked.connect(self.kill_minecraft)
        minecraft_layout.addWidget(kill_button)

        lock_button = QPushButton("Test Lock Screen Function")
        lock_button.clicked.connect(self.test_lock_screen)
        minecraft_layout.addWidget(lock_button)

        layout.addWidget(minecraft_group)
        layout.addStretch()

        return system_tab

    def create_debug_tab(self):
        """创建数据库调试选项卡"""
        debug_tab = QWidget()
        layout = QVBoxLayout(debug_tab)

        # 添加选项卡
        self.tab_widget.addTab(debug_tab, "Database Debugging")

        # 标题
        title_label = QLabel("Database Debugging")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # 查询输入
        query_group = QGroupBox("Execute SQL Query")
        query_layout = QVBoxLayout(query_group)

        self.query_edit = QTextEdit()
        self.query_edit.setPlaceholderText("Enter SQL Query...")
        self.query_edit.setMinimumHeight(100)
        query_layout.addWidget(self.query_edit)

        # 警告标签
        warning_label = QLabel("Warning: Executing improper SQL statements may destroy the database! Please be cautious.")
        warning_label.setStyleSheet(f"color: {THEME_DANGER};")
        warning_label.setWordWrap(True)
        query_layout.addWidget(warning_label)

        # 执行按钮
        exec_button = QPushButton("Execute Query")
        exec_button.clicked.connect(self.execute_query)
        query_layout.addWidget(exec_button)

        layout.addWidget(query_group)
        
        # 结果显示
        result_group = QGroupBox("Query Result")
        result_layout = QVBoxLayout(result_group)

        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setMinimumHeight(200)
        result_layout.addWidget(self.result_text)

        layout.addWidget(result_group)

        # GPT缓存清理
        cache_group = QGroupBox("GPT Cache Cleaning")
        cache_layout = QVBoxLayout(cache_group)

        clear_cache_button = QPushButton("Clear GPT Question Cache")
        clear_cache_button.clicked.connect(self.clear_gpt_cache)
        cache_layout.addWidget(clear_cache_button)

        # 提示信息
        tip_label = QLabel(
            "Note: Clearing GPT Question Cache will delete all cached GPT generated questions, but will not affect history records and math question progress."
        )
        tip_label.setWordWrap(True)
        tip_label.setStyleSheet("color: #6c757d;")
        cache_layout.addWidget(tip_label)

        layout.addWidget(cache_group)

    def handle_add_extra_time(self):
        """添加额外时间的点击处理函数"""
        asyncio.create_task(self.add_extra_time())

    async def add_extra_time(self):
        """添加额外游戏时间"""
        try:
            minutes = self.extra_minutes.value()
            if minutes <= 0:
                QMessageBox.warning(self, "Input Error", "Please enter a valid positive number of minutes")
                return
        except ValueError:
            QMessageBox.warning(self, "Input Error", "Please enter a valid number of minutes")
            return
            
        # 确认添加
        confirm = QMessageBox.question(
            self,
            "Confirm Addition",
            f"Are you sure you want to add {minutes} minutes of extra game time?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            try:
                # 添加额外时间
                await self.game_limiter.add_weekly_extra_time(minutes)
                QMessageBox.information(
                    self, "Success", f"Added {minutes} minutes of extra game time"
                )
                # 立即更新管理员面板显示
                await self.refresh_time_tab()
                # 立即更新主UI
                await self.update_parent_ui()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to add extra time: {str(e)}")
            
    async def refresh_time_tab(self):
        """刷新时间选项卡"""
        try:
            # 获取新状态
            status = await self.game_limiter.get_weekly_status()

            # 更新状态标签
            self.week_start_status.setText(f"Week Start Date: {status['week_start']}")
            self.used_time_status.setText(f"Used Time: {status['used_minutes']} minutes")
            self.extra_time_status.setText(f"Extra Reward Time: {status['extra_minutes']} minutes")
            self.weekly_limit_status.setText(f"Weekly Time Limit: {status['weekly_limit']} minutes")
            self.remaining_time_status.setText(f"Remaining Time: {status['remaining_minutes']} minutes")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to refresh status: {str(e)}")
        
    async def load_sessions(self):
        """加载历史记录Session"""
        try:
            # 清空树
            self.history_tree.clear()
            # 获取会话记录
            sessions = await self.game_limiter.get_sessions()
            # 添加到树
            for session in sessions:
                # 处理不同的表结构版本
                if len(session) == 7:  # 新版本：id, start_time, end_time, duration, game, note, game_name
                    sid, start_time, end_time, duration, game, note, game_name = session
                    # 使用game_name字段，如果为空则使用game字段
                    display_game = game_name or game or "Unknown"
                elif len(session) == 6:  # 旧版本：id, start_time, end_time, duration, game, note
                    sid, start_time, end_time, duration, game, note = session
                    display_game = game or "Unknown"
                elif len(session) == 5:  # 更旧版本：id, start_time, end_time, duration, game
                    sid, start_time, end_time, duration, game = session
                    note = ""
                    display_game = game or "Unknown"
                else:
                    # 如果结构不匹配，使用索引访问而不是直接解包
                    sid = session[0]
                    start_time = session[1]
                    end_time = session[2] if len(session) > 2 else None
                    duration = session[3] if len(session) > 3 else 0
                    display_game = session[4] if len(session) > 4 else "Unknown"
                    note = session[5] if len(session) > 5 else ""
                    
                item = QTreeWidgetItem([
                    str(sid),
                    start_time,
                    end_time or "In Progress",
                    str(duration or 0),
                    display_game,
                    note or "",
                ])
                self.history_tree.addTopLevelItem(item)
            # 自动调整列宽
            for i in range(6):
                self.history_tree.resizeColumnToContents(i)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load Session records: {str(e)}")
            
    async def delete_session(self):
        """删除选中的历史记录"""
        try:
            # 获取选中项
            selected = self.history_tree.selectedItems()
            if not selected:
                QMessageBox.warning(self, "Note", "Please select the record to delete first")
                return
            # 确认删除
            confirm = QMessageBox.question(
                self,
                "Confirm Deletion",
                f"Are you sure you want to delete {len(selected)} selected records? This operation cannot be undone.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
            # 执行删除
            for item in selected:
                session_id = int(item.text(0))
                await self.game_limiter.db.delete_session(session_id)
            # 刷新列表
            await self.load_sessions()
            # 立即更新主UI
            await self.update_parent_ui()
            # 显示成功消息
            QMessageBox.information(self, "Success", f"Deleted {len(selected)} records")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to delete record: {str(e)}")

    def reset_math_questions_sync(self):
        """重置数学题目的同步包装方法"""
        logger.info("管理员请求重置数学题目")
        # 创建异步任务
        asyncio.create_task(self.reset_math_questions())

    async def reset_math_questions(self):
        """重置数学题目"""
        try:
            # 确认操作
            confirm = QMessageBox.question(
                self,
                "Confirm Reset",
                "Are you sure you want to reset today's math questions? This will delete all answers for today!",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
                
            # 显示进度对话框
            progress_dialog = QProgressDialog(self)
            progress_dialog.setWindowTitle("Please Wait")
            progress_dialog.setLabelText("Resetting math questions...")
            progress_dialog.setMinimum(0)
            progress_dialog.setMaximum(100)
            progress_dialog.setValue(0)
            progress_dialog.setModal(True)
            progress_dialog.setCancelButton(None)
            progress_dialog.show()
            
            # 创建进度更新定时器
            self.reset_progress_timer = QTimer()
            self.reset_progress_value = 0
            self.reset_progress_step = 0
            
            def update_progress():
                self.reset_progress_step += 1
                # 模拟进度增长，但不超过95%
                if self.reset_progress_value < 95:
                    if self.reset_progress_step < 10:
                        self.reset_progress_value += 2  # 前5秒快速增长
                    elif self.reset_progress_step < 30:
                        self.reset_progress_value += 1  # 然后缓慢增长
                    else:
                        self.reset_progress_value += 0.5  # 最后非常缓慢
                
                progress_dialog.setValue(int(self.reset_progress_value))
                
                # 更新状态文本
                if self.reset_progress_step < 5:
                    progress_dialog.setLabelText("Clearing old questions...")
                elif self.reset_progress_step < 15:
                    progress_dialog.setLabelText("Generating new questions with AI...")
                elif self.reset_progress_step < 25:
                    progress_dialog.setLabelText("Processing AI responses...")
                else:
                    progress_dialog.setLabelText("Saving to database...")
                
                QApplication.processEvents()
            
            self.reset_progress_timer.timeout.connect(update_progress)
            self.reset_progress_timer.start(500)
            
            # 创建异步任务来处理重置，避免阻塞UI
            async def async_reset_task():
                try:
                    # 执行重置
                    await self.game_limiter.math_exercises.regenerate_daily_questions()
                    # 回到UI线程处理完成
                    self.on_reset_complete(progress_dialog)
                except Exception as e:
                    logger.error(f"重置数学题目失败: {e}")
                    # 回到UI线程处理错误
                    self.on_reset_error(progress_dialog, str(e))
            
            # 启动异步任务，不等待
            asyncio.create_task(async_reset_task())
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to reset math questions: {str(e)}")
            
    def on_reset_complete(self, dialog):
        """重置完成回调"""
        # 停止进度定时器
        if hasattr(self, 'reset_progress_timer'):
            self.reset_progress_timer.stop()
            self.reset_progress_timer.deleteLater()
            delattr(self, 'reset_progress_timer')
        
        # 设置进度为100%
        dialog.setValue(100)
        dialog.setLabelText("Complete!")
        QApplication.processEvents()
        
        dialog.close()
        # 显示成功消息
        QMessageBox.information(self, "Success", "Math questions have been reset successfully!")
        
    def on_reset_error(self, dialog, error_msg):
        """重置错误回调"""
        # 停止进度定时器
        if hasattr(self, 'reset_progress_timer'):
            self.reset_progress_timer.stop()
            self.reset_progress_timer.deleteLater()
            delattr(self, 'reset_progress_timer')
            
        dialog.close()
        QMessageBox.critical(self, "Error", f"Failed to reset math questions: {error_msg}")
            
    def kill_minecraft(self):
        """结束Minecraft进程"""
        try:
            # 确认操作
            confirm = QMessageBox.question(
                self,
                "Confirm Operation",
                "Are you sure you want to end all Minecraft processes?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
            # 创建异步任务
            async def async_kill_task():
                try:
                    # 结束进程
                    killed = await asyncio.to_thread(self.game_limiter.kill_minecraft)
                    # 返回到UI线程处理
                    self.on_kill_complete(killed)
                except Exception as e:
                    # 返回到UI线程显示错误
                    self.on_kill_error(str(e))
            # 启动异步任务
            asyncio.create_task(async_kill_task())
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to end process: {str(e)}")

    def on_kill_complete(self, killed):
        """结束进程完成回调"""
        if killed:
            QMessageBox.information(self, "Success", f"Ended {killed} Minecraft processes")
        else:
            QMessageBox.information(self, "Note", "No running Minecraft processes found")

    def on_kill_error(self, error_msg):
        """结束进程错误回调"""
        QMessageBox.critical(self, "Error", f"Failed to end process: {error_msg}")
            
    def test_lock_screen(self):
        """测试锁屏功能"""
        try:
            # 确认操作
            confirm = QMessageBox.question(
                self,
                "Confirm Operation",
                "Are you sure you want to test lock screen function? This will immediately lock the screen.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
            # 创建异步任务
            async def async_lock_task():
                try:
                    # 锁屏
                    await asyncio.to_thread(self.game_limiter.lock_screen)
                except Exception as e:
                    # 返回到UI线程显示错误
                    self.on_lock_error(str(e))
            # 启动异步任务
            asyncio.create_task(async_lock_task())
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to lock screen: {str(e)}")

    def on_lock_error(self, error_msg):
        """锁屏错误回调"""
        QMessageBox.critical(self, "Error", f"Failed to lock screen: {error_msg}")
        
    def execute_query(self):
        """执行SQL查询"""
        try:
            # 获取查询语句
            query = self.query_edit.toPlainText().strip()
            if not query:
                QMessageBox.warning(self, "Note", "Please enter SQL Query")
                return

            # 确认执行
            confirm = QMessageBox.question(
                self,
                "Confirm Execution",
                "Are you sure you want to execute this SQL query? Incorrect SQL may destroy the database.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

            # 执行查询
            try:
                result = self.game_limiter.db.execute_query(query)
                # 显示结果
                if isinstance(result, list):
                    # 查询结果
                    self.result_text.setText(f"<p>{result}</p>")
                else:
                    # 非查询操作
                    self.result_text.setText(f"<p>{result}</p>")
                    
            except sqlite3.Error as e:
                # 显示SQLite错误
                self.result_text.setText(f"<p>SQL Error: {str(e)}</p>")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to execute query: {str(e)}")
            
    def clear_gpt_cache(self):
        """清除GPT问题缓存"""
        try:
            # 确认清除
            confirm = QMessageBox.question(
                self,
                "Confirm Clearing",
                "Are you sure you want to clear GPT question cache? This will delete all cached GPT generated questions.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
            # 执行清除
            try:
                count = self.game_limiter.db.clear_gpt_cache()
                # 显示结果
                QMessageBox.information(self, "Success", f"Cleared {count} GPT cache records")
            except sqlite3.Error as e:
                QMessageBox.critical(self, "Error", f"Failed to clear cache: {str(e)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to clear cache: {str(e)}")

    async def modify_used_time(self):
        """修改已用时间"""
        try:
            # 获取调整的分钟数
            minutes = self.modify_used_minutes.value()
            if minutes == 0:
                QMessageBox.warning(self, "Input Error", "Please enter a non-zero adjustment value")
                return

            # 确认修改
            confirm = QMessageBox.question(
                self,
                "Confirm Modification",
                f"Are you sure you want to adjust used time by {minutes} minutes?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

            # 更新已用时间
            await self.game_limiter.modify_used_time(minutes)

            # 显示成功消息
            QMessageBox.information(
                self,
                "Success", 
                f"Successfully modified used time by {minutes} minutes"
            )
            
            # 刷新时间标签页
            await self.refresh_time_tab()
            # 立即更新主UI
            await self.update_parent_ui()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to modify used time: {str(e)}")

    def update_monitor_button_text(self):
        """更新监控按钮文字"""
        if hasattr(self.parent, 'window_monitor') and self.parent.window_monitor.is_running:
            self.monitor_toggle_button.setText("Stop Monitoring")
        else:
            self.monitor_toggle_button.setText("Start Monitoring")

    def toggle_monitor(self):
        """切换监控状态"""
        try:
            if not hasattr(self.parent, 'window_monitor'):
                QMessageBox.warning(self, "Error", "Window monitor not available")
                return
                
            if self.parent.window_monitor.is_running:
                # 停止监控
                asyncio.create_task(self.parent.window_monitor.stop_monitoring())
                QMessageBox.information(self, "Success", "Window monitoring stopped")
            else:
                # 启动监控
                asyncio.create_task(self.parent.window_monitor.start_monitoring())
                QMessageBox.information(self, "Success", "Window monitoring started")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error toggling window monitoring: {str(e)}")
        finally:
            self.update_monitor_button_text()

    def update_monitor_interval(self, value):
        """更新监控间隔"""
        if hasattr(self.parent, 'window_monitor'):
            self.parent.window_monitor.set_check_interval(value)

    def test_monitor(self):
        """测试监控功能"""
        if not hasattr(self.parent, 'window_monitor'):
            QMessageBox.warning(self, "Error", "Window monitor not available")
            return
            
        monitor = self.parent.window_monitor

        if not monitor.is_running:
            QMessageBox.warning(self, "提示", "窗口监控未启动，请先启用监控")
            return

        # 构造检测内容信息
        detection_info = ""

        # 检查Minecraft进程
        has_minecraft = monitor._check_restricted_processes()
        detection_info += (
            f"Minecraft进程: {'检测到' if has_minecraft else '未检测到'}\n"
        )

        # 创建异步任务检查Chrome标签
        async def check_chrome():
            # 检测Chrome窗口
            chrome_windows = [
                w for w in gw.getAllWindows() if "chrome" in w.title.lower()
            ]
            chrome_info = f"Chrome窗口数量: {len(chrome_windows)}\n"

            # 检查bloxd.io
            has_bloxd = await monitor._check_chrome_tabs()
            chrome_info += (
                f"bloxd.io (Chrome标签): {'检测到' if has_bloxd else '未检测到'}\n\n"
            )

            # 显示所有Chrome窗口标题
            if chrome_windows:
                chrome_info += "Chrome窗口标题:\n"
                for i, window in enumerate(chrome_windows):
                    # 截断过长的标题
                    title = window.title
                    if len(title) > 70:
                        title = title[:67] + "..."
                    chrome_info += f"{i+1}. {title}\n"

            # 显示结果对话框
            QMessageBox.information(
                self,
                "监控测试",
                f"当前监控状态: {'正在运行' if monitor.is_running else '已停止'}\n"
                + f"检查间隔: {monitor.check_interval}秒\n\n"
                + "受限应用检测结果:\n"
                + detection_info
                + chrome_info
                + "监控将在非游戏会话期间检测这些应用，并在检测到时锁定屏幕。",
            )

        # 创建并立即运行任务
        asyncio.create_task(check_chrome())

    async def load_data(self):
        """加载数据"""
        try:
            # 更新时间管理标签页状态
            await self.update_time_management_status()
            
            # 加载历史记录到历史标签页
            await self.load_sessions()
                
            # 更新监控按钮状态
            if hasattr(self, 'monitor_toggle_button'):
                self.update_monitor_button_text()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载数据失败: {str(e)}")

    async def update_time_management_status(self):
        """异步更新时间管理标签页的状态"""
        try:
            # 获取本周状态
            status = await self.game_limiter.get_weekly_status()
            
            # 更新状态标签
            self.week_start_status.setText(f"Week Start Date: {status['week_start']}")
            self.used_time_status.setText(f"Used Time: {status['used_minutes']} minutes")
            self.extra_time_status.setText(f"Extra Reward Time: {status['extra_minutes']} minutes")
            self.weekly_limit_status.setText(f"Weekly Time Limit: {status['weekly_limit']} minutes")
            self.remaining_time_status.setText(f"Remaining Time: {status['remaining_minutes']} minutes")
        except Exception as e:
            # 如果出错，显示错误信息
            error_msg = f"Error loading status: {str(e)}"
            self.week_start_status.setText(error_msg)
            self.used_time_status.setText(error_msg)
            self.extra_time_status.setText(error_msg)
            self.weekly_limit_status.setText(error_msg)
            self.remaining_time_status.setText(error_msg)

    async def update_parent_ui(self):
        """更新父窗口UI"""
        if self.parent and hasattr(self.parent, 'update_weekly_status'):
            try:
                await self.parent.update_weekly_status()
            except Exception as e:
                logger.error(f"Failed to update parent UI: {e}")

    def closeEvent(self, event):
        """关闭事件，触发父窗口更新"""
        logger.info("管理员面板正在关闭")
        
        if self.parent and hasattr(self.parent, 'refresh_weekly_status_async'):
            # 延迟触发父窗口状态更新，避免任务冲突
            QTimer.singleShot(200, self.parent.refresh_weekly_status_async)
            
        # 接受关闭事件，这会触发finished信号
        event.accept() 