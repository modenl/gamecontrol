import os
import sys
import time
import json
import asyncio
import datetime
import logging
import sqlite3
import pygetwindow as gw
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QTabWidget,
    QLabel, QPushButton, QLineEdit, QTextEdit, QMessageBox,
    QFrame, QTreeWidget, QTreeWidgetItem, QScrollArea,
    QGroupBox, QFormLayout, QSpinBox, QComboBox, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QFont

from logic.constants import (
    PADDING_SMALL, PADDING_MEDIUM, PADDING_LARGE,
    MAX_WEEKLY_LIMIT, THEME_PRIMARY, THEME_WARNING, THEME_DANGER, THEME_SUCCESS
)
from ui.base import ShakeEffect

class AdminPanel(QDialog):
    """管理员控制面板"""
    # 定义信号
    update_signal = pyqtSignal()
    
    def __init__(self, parent=None, game_limiter=None):
        super().__init__(parent)
        
        self.parent = parent
        self.game_limiter = game_limiter
        
        # 设置窗口
        self.setWindowTitle("管理员控制面板")
        self.resize(800, 600)
        self.setModal(True)
        
        # 设置UI
        self.setup_ui()
        
    def setup_ui(self):
        """设置UI组件"""
        # 主布局
        main_layout = QVBoxLayout(self)
        
        # 标题
        title_label = QLabel("管理员控制面板")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)
        
        # 选项卡面板
        self.tab_widget = QTabWidget()
        
        # 创建各个选项卡
        self.create_time_tab()
        self.create_history_tab()
        self.create_system_tab()
        self.create_debug_tab()
        
        main_layout.addWidget(self.tab_widget)
        
        # 底部按钮
        button_layout = QHBoxLayout()
        
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.close)
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        
        main_layout.addLayout(button_layout)
        
    def create_time_tab(self):
        """创建时间管理选项卡"""
        time_tab = QWidget()
        layout = QVBoxLayout(time_tab)
        
        # 添加选项卡
        self.tab_widget.addTab(time_tab, "时间管理")
        
        # 标题
        title_label = QLabel("游戏时间管理")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # 当前状态框架
        status_group = QGroupBox("本周状态")
        status_layout = QVBoxLayout(status_group)
        
        # 获取本周状态
        status = self.game_limiter.get_weekly_status()
        
        # 状态信息
        status_layout.addWidget(QLabel(f"本周开始日期: {status['week_start']}"))
        status_layout.addWidget(QLabel(f"已使用时间: {status['used_minutes']} 分钟"))
        status_layout.addWidget(QLabel(f"额外奖励时间: {status['extra_minutes']} 分钟"))
        status_layout.addWidget(QLabel(f"本周时间上限: {status['weekly_limit']} 分钟"))
        status_layout.addWidget(QLabel(f"剩余时间: {status['remaining_minutes']} 分钟"))
        
        layout.addWidget(status_group)
        
        # 修改已用时间框架
        modify_used_group = QGroupBox("修改已用时间")
        modify_used_layout = QVBoxLayout(modify_used_group)
        
        # 修改已用时间输入
        modify_used_input_layout = QHBoxLayout()
        modify_used_input_layout.addWidget(QLabel("调整分钟数 (+/-)："))
        
        self.modify_used_minutes = QSpinBox()
        self.modify_used_minutes.setMinimum(-MAX_WEEKLY_LIMIT)  # 允许负值减少已用时间
        self.modify_used_minutes.setMaximum(MAX_WEEKLY_LIMIT)
        self.modify_used_minutes.setValue(0)
        modify_used_input_layout.addWidget(self.modify_used_minutes)
        modify_used_input_layout.addStretch()
        
        modify_used_layout.addLayout(modify_used_input_layout)
        
        # 提示信息
        modify_used_info = QLabel("正数值增加已用时间，负数值减少已用时间。用于手动调整离线使用的游戏时间。")
        modify_used_layout.addWidget(modify_used_info)
        
        # 按钮
        modify_used_button_layout = QHBoxLayout()
        
        modify_used_button = QPushButton("应用修改")
        modify_used_button.clicked.connect(self.modify_used_time)
        modify_used_button_layout.addWidget(modify_used_button)
        modify_used_button_layout.addStretch()
        
        modify_used_layout.addLayout(modify_used_button_layout)
        
        layout.addWidget(modify_used_group)
        
        # 添加额外时间框架
        extra_group = QGroupBox("添加额外游戏时间")
        extra_layout = QVBoxLayout(extra_group)
        
        # 额外时间输入
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("额外分钟数:"))
        
        self.extra_minutes = QSpinBox()
        self.extra_minutes.setMinimum(0)
        self.extra_minutes.setMaximum(MAX_WEEKLY_LIMIT)
        self.extra_minutes.setValue(30)
        input_layout.addWidget(self.extra_minutes)
        input_layout.addStretch()
        
        extra_layout.addLayout(input_layout)
        
        # 提示信息
        warning_label = QLabel(f"注意: 本周总时间上限为 {MAX_WEEKLY_LIMIT} 分钟")
        warning_label.setStyleSheet(f"color: {THEME_WARNING};")
        extra_layout.addWidget(warning_label)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        add_button = QPushButton("添加额外时间")
        add_button.clicked.connect(self.handle_add_extra_time)
        button_layout.addWidget(add_button)
        
        refresh_button = QPushButton("刷新状态")
        refresh_button.clicked.connect(self.refresh_time_tab)
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
        self.tab_widget.addTab(history_tab, "历史记录")
        
        # 标题
        title_label = QLabel("历史记录管理")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # 历史记录树
        self.history_tree = QTreeWidget()
        self.history_tree.setHeaderLabels(["ID", "开始时间", "结束时间", "时长(分钟)", "游戏", "备注"])
        self.history_tree.setAlternatingRowColors(True)
        
        # 设置列宽
        self.history_tree.setColumnWidth(0, 50)
        self.history_tree.setColumnWidth(1, 150)
        self.history_tree.setColumnWidth(2, 150)
        self.history_tree.setColumnWidth(3, 100)
        self.history_tree.setColumnWidth(4, 100)
        self.history_tree.setColumnWidth(5, 150)
        
        layout.addWidget(self.history_tree)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        delete_button = QPushButton("删除所选记录")
        delete_button.clicked.connect(self.delete_session)
        button_layout.addWidget(delete_button)
        
        refresh_button = QPushButton("刷新列表")
        refresh_button.clicked.connect(self.load_sessions)
        button_layout.addWidget(refresh_button)
        
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        # 初始加载历史记录
        self.load_sessions()
        
    def create_system_tab(self):
        """创建系统设置选项卡"""
        system_tab = QWidget()
        layout = QVBoxLayout(system_tab)
        
        # 添加选项卡
        self.tab_widget.addTab(system_tab, "系统设置")
        
        # 标题
        title_label = QLabel("系统设置")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # 窗口监控设置
        monitor_group = QGroupBox("窗口监控设置")
        monitor_layout = QVBoxLayout(monitor_group)
        
        # 监控说明
        monitor_info = QLabel("窗口监控功能会在未开始游戏会话时检测并阻止未授权的游戏使用。")
        monitor_layout.addWidget(monitor_info)
        
        # 检查间隔设置
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("检查间隔（秒）:"))
        
        self.monitor_interval = QSpinBox()
        self.monitor_interval.setMinimum(5)
        self.monitor_interval.setMaximum(60)
        self.monitor_interval.setValue(self.parent.window_monitor.check_interval)
        self.monitor_interval.valueChanged.connect(self.update_monitor_interval)
        interval_layout.addWidget(self.monitor_interval)
        interval_layout.addStretch()
        
        monitor_layout.addLayout(interval_layout)
        
        # 监控状态控制
        monitor_control_layout = QHBoxLayout()
        
        # 启用/禁用监控按钮
        self.monitor_toggle_button = QPushButton()
        self.update_monitor_button_text()
        self.monitor_toggle_button.clicked.connect(self.toggle_window_monitor)
        monitor_control_layout.addWidget(self.monitor_toggle_button)
        
        # 测试监控按钮
        test_monitor_button = QPushButton("测试监控功能")
        test_monitor_button.clicked.connect(self.test_monitor)
        monitor_control_layout.addWidget(test_monitor_button)
        
        monitor_control_layout.addStretch()
        
        monitor_layout.addLayout(monitor_control_layout)
        
        layout.addWidget(monitor_group)
        
        # 数学练习设置
        math_group = QGroupBox("数学练习设置")
        math_layout = QVBoxLayout(math_group)
        
        reset_math_button = QPushButton("重置今天的数学题目")
        reset_math_button.clicked.connect(self.reset_math_questions)
        math_layout.addWidget(reset_math_button)
        
        layout.addWidget(math_group)
        
        # Minecraft相关控制
        minecraft_group = QGroupBox("Minecraft控制")
        minecraft_layout = QVBoxLayout(minecraft_group)
        
        kill_button = QPushButton("结束Minecraft进程")
        kill_button.clicked.connect(self.kill_minecraft)
        minecraft_layout.addWidget(kill_button)
        
        lock_button = QPushButton("测试锁屏功能")
        lock_button.clicked.connect(self.test_lock_screen)
        minecraft_layout.addWidget(lock_button)
        
        layout.addWidget(minecraft_group)
        layout.addStretch()
        
    def create_debug_tab(self):
        """创建数据库调试选项卡"""
        debug_tab = QWidget()
        layout = QVBoxLayout(debug_tab)
        
        # 添加选项卡
        self.tab_widget.addTab(debug_tab, "数据库调试")
        
        # 标题
        title_label = QLabel("数据库调试")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # 查询输入
        query_group = QGroupBox("执行SQL查询")
        query_layout = QVBoxLayout(query_group)
        
        self.query_edit = QTextEdit()
        self.query_edit.setPlaceholderText("输入SQL查询语句...")
        self.query_edit.setMinimumHeight(100)
        query_layout.addWidget(self.query_edit)
        
        # 警告标签
        warning_label = QLabel(
            "警告: 执行不当的SQL语句可能会破坏数据库！请谨慎操作。"
        )
        warning_label.setStyleSheet(f"color: {THEME_DANGER};")
        warning_label.setWordWrap(True)
        query_layout.addWidget(warning_label)
        
        # 执行按钮
        exec_button = QPushButton("执行查询")
        exec_button.clicked.connect(self.execute_query)
        query_layout.addWidget(exec_button)
        
        layout.addWidget(query_group)
        
        # 结果显示
        result_group = QGroupBox("查询结果")
        result_layout = QVBoxLayout(result_group)
        
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setMinimumHeight(200)
        result_layout.addWidget(self.result_text)
        
        layout.addWidget(result_group)
        
        # GPT缓存清理
        cache_group = QGroupBox("GPT缓存清理")
        cache_layout = QVBoxLayout(cache_group)
        
        clear_cache_button = QPushButton("清除GPT问题缓存")
        clear_cache_button.clicked.connect(self.clear_gpt_cache)
        cache_layout.addWidget(clear_cache_button)
        
        # 提示信息
        tip_label = QLabel(
            "提示: 清除GPT问题缓存会删除所有缓存的GPT生成的问题，但不会影响历史记录和数学习题进度。"
        )
        tip_label.setWordWrap(True)
        tip_label.setStyleSheet("color: #6c757d;")
        cache_layout.addWidget(tip_label)
        
        layout.addWidget(cache_group)
        
    def handle_add_extra_time(self):
        """添加额外时间的点击处理函数"""
        # 创建异步任务来处理添加额外时间
        asyncio.create_task(self.add_extra_time())
        
    async def add_extra_time(self):
        """添加额外游戏时间"""
        try:
            minutes = self.extra_minutes.value()
            if minutes <= 0:
                QMessageBox.warning(self, "输入错误", "请输入有效的时间数量")
                return
                
            # 检查是否超过总上限
            status = self.game_limiter.get_weekly_status()
            current_total = status['used_minutes'] + status['extra_minutes']
            if current_total + minutes > MAX_WEEKLY_LIMIT:
                confirm = QMessageBox.question(
                    self,
                    "确认添加",
                    f"添加{minutes}分钟后将超过每周上限{MAX_WEEKLY_LIMIT}分钟，是否继续？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if confirm != QMessageBox.StandardButton.Yes:
                    return
            
            # 添加额外时间
            self.game_limiter.add_weekly_extra_time(minutes)
            
            # 更新状态
            self.refresh_time_tab()
            
            # 触发更新信号
            self.update_signal.emit()
            
            # 显示成功消息
            QMessageBox.information(self, "成功", f"已添加{minutes}分钟额外游戏时间")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"添加额外时间失败: {str(e)}")
            
    def refresh_time_tab(self):
        """刷新时间选项卡"""
        try:
            # 获取新状态
            status = self.game_limiter.get_weekly_status()
            
            # 更新选项卡内容 - 获取QGroupBox的第一个子布局的所有标签
            status_group = self.tab_widget.widget(0).findChildren(QGroupBox)[0]
            status_labels = status_group.findChildren(QLabel)
            
            # 更新标签内容
            status_labels[0].setText(f"本周开始日期: {status['week_start']}")
            status_labels[1].setText(f"已使用时间: {status['used_minutes']} 分钟")
            status_labels[2].setText(f"额外奖励时间: {status['extra_minutes']} 分钟")
            status_labels[3].setText(f"本周时间上限: {status['weekly_limit']} 分钟")
            status_labels[4].setText(f"剩余时间: {status['remaining_minutes']} 分钟")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"刷新状态失败: {str(e)}")
    
    def load_sessions(self):
        """加载历史记录Session"""
        try:
            # 清空树
            self.history_tree.clear()
            
            # 获取会话记录
            sessions = self.game_limiter.db.get_sessions()
            
            # 添加到树
            for session in sessions:
                # 使用索引访问而不是直接解包
                sid = session[0]
                start_time = session[1]
                end_time = session[2]
                duration = session[3]
                game = session[4]
                note = session[5]
                
                item = QTreeWidgetItem([
                    str(sid),
                    start_time,
                    end_time or "进行中",
                    str(duration or 0),
                    game or "未知",
                    note or ""
                ])
                self.history_tree.addTopLevelItem(item)
                
            # 自动调整列宽
            for i in range(6):
                self.history_tree.resizeColumnToContents(i)
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载Session记录失败: {str(e)}")
    
    def delete_session(self):
        """删除选中的历史记录"""
        try:
            # 获取选中项
            selected = self.history_tree.selectedItems()
            if not selected:
                QMessageBox.warning(self, "提示", "请先选择要删除的记录")
                return
            
            # 确认删除
            confirm = QMessageBox.question(
                self,
                "确认删除",
                f"确定要删除选中的{len(selected)}条记录吗？此操作不可恢复。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
                
            # 执行删除
            for item in selected:
                session_id = int(item.text(0))
                self.game_limiter.db.delete_session(session_id)
            
            # 刷新列表
            self.load_sessions()
            
            # 更新主窗口状态
            self.update_signal.emit()
            
            # 显示成功消息
            QMessageBox.information(self, "成功", f"已删除{len(selected)}条记录")
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"删除记录失败: {str(e)}")
    
    def reset_math_questions(self):
        """重置数学题目"""
        try:
            # 确认操作
            confirm = QMessageBox.question(
                self,
                "确认重置",
                "确定要重置今天的数学题目吗？这将删除今天所有的作答记录！",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
                
            # 显示进度对话框
            progress_dialog = QMessageBox(self)
            progress_dialog.setWindowTitle("请稍候")
            progress_dialog.setText("正在重置数学题目...")
            progress_dialog.setStandardButtons(QMessageBox.StandardButton.NoButton)
            progress_dialog.show()
            
            # 创建异步任务
            async def async_reset_task():
                try:
                    # 执行重置
                    await asyncio.to_thread(self.game_limiter.math_exercises.regenerate_daily_questions)
                    
                    # 返回到UI线程处理
                    self.on_reset_complete(progress_dialog)
                except Exception as e:
                    # 返回到UI线程显示错误
                    self.on_reset_error(progress_dialog, str(e))
                    
            # 启动异步任务
            asyncio.create_task(async_reset_task())
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"重置数学题目失败: {str(e)}")
            
    def on_reset_complete(self, dialog):
        """重置完成回调"""
        dialog.close()
        
        # 更新主窗口状态
        self.update_signal.emit()
        
        # 显示成功消息
        QMessageBox.information(self, "成功", "数学题目已重置")
        
    def on_reset_error(self, dialog, error_msg):
        """重置错误回调"""
        dialog.close()
        QMessageBox.critical(self, "错误", f"重置数学题目失败: {error_msg}")
        
    def kill_minecraft(self):
        """结束Minecraft进程"""
        try:
            # 确认操作
            confirm = QMessageBox.question(
                self,
                "确认操作",
                "确定要结束所有Minecraft进程吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
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
            QMessageBox.critical(self, "错误", f"结束进程失败: {str(e)}")
            
    def on_kill_complete(self, killed):
        """结束进程完成回调"""
        if killed:
            QMessageBox.information(self, "成功", f"已结束{killed}个Minecraft进程")
        else:
            QMessageBox.information(self, "提示", "未找到运行中的Minecraft进程")
            
    def on_kill_error(self, error_msg):
        """结束进程错误回调"""
        QMessageBox.critical(self, "错误", f"结束进程失败: {error_msg}")
        
    def test_lock_screen(self):
        """测试锁屏功能"""
        try:
            # 确认操作
            confirm = QMessageBox.question(
                self,
                "确认操作",
                "确定要测试锁屏功能吗？这将立即锁定屏幕。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
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
            QMessageBox.critical(self, "错误", f"锁屏操作失败: {str(e)}")
            
    def on_lock_error(self, error_msg):
        """锁屏错误回调"""
        QMessageBox.critical(self, "错误", f"锁屏操作失败: {error_msg}")
        
    def execute_query(self):
        """执行SQL查询"""
        try:
            # 获取查询语句
            query = self.query_edit.toPlainText().strip()
            if not query:
                QMessageBox.warning(self, "提示", "请输入SQL查询语句")
                return
                
            # 确认执行
            confirm = QMessageBox.question(
                self,
                "确认执行",
                "确定要执行此SQL查询吗？错误的SQL可能会破坏数据库。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
                
            # 执行查询
            try:
                result = self.game_limiter.db.execute_query(query)
                
                # 显示结果
                if isinstance(result, list):
                    # 查询结果
                    html = "<table border='1' cellspacing='0' cellpadding='5'>"
                    
                    # 表头
                    if result and len(result) > 0:
                        html += "<tr>"
                        for col in result[0].keys():
                            html += f"<th>{col}</th>"
                        html += "</tr>"
                        
                        # 数据行
                        for row in result:
                            html += "<tr>"
                            for value in row:
                                html += f"<td>{value}</td>"
                            html += "</tr>"
                    
                    html += "</table>"
                    self.result_text.setHtml(html)
                else:
                    # 非查询操作
                    self.result_text.setPlainText(f"操作成功，影响了{result}行")
                    
            except sqlite3.Error as e:
                self.result_text.setPlainText(f"SQL错误: {str(e)}")
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"执行查询失败: {str(e)}")
            
    def clear_gpt_cache(self):
        """清除GPT问题缓存"""
        try:
            # 确认清除
            confirm = QMessageBox.question(
                self,
                "确认清除",
                "确定要清除GPT问题缓存吗？这将删除所有缓存的GPT生成的问题。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
                
            # 执行清除
            try:
                count = self.game_limiter.db.clear_gpt_cache()
                
                # 显示结果
                QMessageBox.information(self, "成功", f"已清除{count}条GPT缓存记录")
                
            except sqlite3.Error as e:
                QMessageBox.critical(self, "错误", f"清除缓存失败: {str(e)}")
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"清除缓存操作失败: {str(e)}")
            
    def optimize_database(self):
        """优化数据库"""
        try:
            # 确认操作
            confirm = QMessageBox.question(
                self,
                "确认操作",
                "确定要优化数据库吗？这将压缩数据库文件并修复可能的问题。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
                
            # 显示进度对话框
            progress_dialog = QMessageBox(self)
            progress_dialog.setWindowTitle("请稍候")
            progress_dialog.setText("正在优化数据库...")
            progress_dialog.setStandardButtons(QMessageBox.StandardButton.NoButton)
            progress_dialog.show()
            
            # 创建异步任务
            async def async_optimize_task():
                try:
                    # 执行优化
                    result = await asyncio.to_thread(self.game_limiter.db.optimize_database)
                    
                    # 返回到UI线程处理
                    self.on_optimize_complete(progress_dialog)
                    
                except Exception as e:
                    # 返回到UI线程显示错误
                    self.on_optimize_error(progress_dialog, str(e))
                    
            # 启动异步任务
            asyncio.create_task(async_optimize_task())
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"优化数据库失败: {str(e)}")
            
    def on_optimize_complete(self, dialog):
        """优化完成回调"""
        dialog.close()
        
        # 显示成功消息
        QMessageBox.information(
            self, 
            "成功", 
            "数据库优化完成！如果数据库较大，性能提升会更明显。"
        )
        
    def on_optimize_error(self, dialog, error_msg):
        """优化错误回调"""
        dialog.close()
        QMessageBox.critical(self, "错误", f"优化数据库失败: {error_msg}")

    def modify_used_time(self):
        """修改已用时间"""
        try:
            # 获取调整的分钟数
            minutes = self.modify_used_minutes.value()
            
            # 更新已用时间
            self.game_limiter.modify_used_time(minutes)
            
            # 刷新时间选项卡
            self.refresh_time_tab()
            
            # 更新主窗口状态
            self.update_signal.emit()
            
            # 显示成功消息
            QMessageBox.information(self, "成功", f"已修改已用时间，当前已用时间: {self.game_limiter.get_weekly_status()['used_minutes']} 分钟")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"修改已用时间失败: {str(e)}")

    def update_monitor_button_text(self):
        """更新监控按钮文本"""
        if self.parent.window_monitor.is_running:
            self.monitor_toggle_button.setText("禁用窗口监控")
            self.monitor_toggle_button.setStyleSheet(f"background-color: {THEME_DANGER}; color: white;")
        else:
            self.monitor_toggle_button.setText("启用窗口监控")
            self.monitor_toggle_button.setStyleSheet(f"background-color: {THEME_SUCCESS}; color: white;")
            
    def update_monitor_interval(self, value):
        """更新监控间隔"""
        self.parent.window_monitor.set_check_interval(value)
        
    def toggle_window_monitor(self):
        """切换窗口监控状态"""
        monitor = self.parent.window_monitor
        
        if monitor.is_running:
            # 停止监控
            asyncio.create_task(self._stop_monitor())
        else:
            # 启动监控
            asyncio.create_task(self._start_monitor())
        
    async def _stop_monitor(self):
        """停止监控"""
        try:
            await self.parent.window_monitor.stop_monitoring()
            self.update_monitor_button_text()
            QMessageBox.information(self, "成功", "已停止窗口监控")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"停止窗口监控时出错: {str(e)}")
            
    async def _start_monitor(self):
        """启动监控"""
        try:
            await self.parent.window_monitor.start_monitoring()
            self.update_monitor_button_text()
            QMessageBox.information(self, "成功", "已启动窗口监控")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"启动窗口监控时出错: {str(e)}")
            
    def test_monitor(self):
        """测试监控功能"""
        monitor = self.parent.window_monitor
        
        if not monitor.is_running:
            QMessageBox.warning(self, "提示", "窗口监控未启动，请先启用监控")
            return
            
        # 构造检测内容信息
        detection_info = ""
        
        # 检查Minecraft进程
        has_minecraft = monitor._check_minecraft_processes()
        detection_info += f"Minecraft进程: {'检测到' if has_minecraft else '未检测到'}\n"
        
        # 创建异步任务检查Chrome标签
        async def check_chrome():
            # 检测Chrome窗口
            chrome_windows = [w for w in gw.getAllWindows() if "chrome" in w.title.lower()]
            chrome_info = f"Chrome窗口数量: {len(chrome_windows)}\n"
            
            # 检查bloxd.io
            has_bloxd = await monitor._check_chrome_tabs()
            chrome_info += f"bloxd.io (Chrome标签): {'检测到' if has_bloxd else '未检测到'}\n\n"
            
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
                f"当前监控状态: {'正在运行' if monitor.is_running else '已停止'}\n" +
                f"检查间隔: {monitor.check_interval}秒\n\n" +
                "受限应用检测结果:\n" +
                detection_info +
                chrome_info +
                "监控将在非游戏会话期间检测这些应用，并在检测到时锁定屏幕。"
            )
            
        # 创建并立即运行任务
        asyncio.create_task(check_chrome()) 