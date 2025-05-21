import sys
import asyncio
import datetime
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, 
    QLabel, QPushButton, QComboBox, QTreeWidget, QTreeWidgetItem,
    QFrame, QProgressBar, QMessageBox, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont

from logic.constants import (
    PADDING_SMALL, PADDING_MEDIUM, PADDING_LARGE,
    DEFAULT_WEEKLY_LIMIT, MAX_WEEKLY_LIMIT
)

class HistoryPanel(QDialog):
    """历史记录面板"""
    
    def __init__(self, parent=None, game_limiter=None):
        super().__init__(parent)
        
        self.parent = parent
        self.game_limiter = game_limiter
        
        # 设置窗口
        self.setWindowTitle("游戏历史记录")
        self.resize(800, 600)
        self.setModal(True)
        
        # 设置UI
        self.setup_ui()
        
        # 加载历史记录
        self.load_history()
        
    def setup_ui(self):
        """设置UI组件"""
        # 主布局
        main_layout = QVBoxLayout(self)
        
        # 顶部控制栏
        control_layout = QHBoxLayout()
        
        # 标题
        title_label = QLabel("游戏历史记录")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        control_layout.addWidget(title_label)
        
        # 弹性空间
        control_layout.addStretch()
        
        # 周选择
        week_layout = QHBoxLayout()
        week_layout.addWidget(QLabel("选择周:"))
        
        # 获取可选的周
        self.weeks = self.get_available_weeks()
        self.week_combo = QComboBox()
        self.week_combo.addItems(self.weeks)
        self.week_combo.setCurrentIndex(0)
        self.week_combo.currentIndexChanged.connect(self.load_history)
        week_layout.addWidget(self.week_combo)
        
        control_layout.addLayout(week_layout)
        
        main_layout.addLayout(control_layout)
        
        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(separator)
        
        # 历史记录列表
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
        
        main_layout.addWidget(self.history_tree)
        
        # 统计信息框架
        stats_frame = QFrame()
        stats_frame.setFrameShape(QFrame.Shape.StyledPanel)
        stats_frame.setFrameShadow(QFrame.Shadow.Raised)
        stats_layout = QHBoxLayout(stats_frame)
        
        # 统计信息标签
        self.total_label = QLabel("本周总时长: 0 分钟")
        stats_layout.addWidget(self.total_label)
        
        self.extra_label = QLabel("额外奖励: 0 分钟")
        stats_layout.addWidget(self.extra_label)
        
        self.remaining_label = QLabel("剩余时间: 0 分钟")
        stats_layout.addWidget(self.remaining_label)
        
        main_layout.addWidget(stats_frame)
        
        # 底部按钮框架
        button_layout = QHBoxLayout()
        
        self.refresh_button = QPushButton("刷新")
        self.refresh_button.clicked.connect(self.load_history)
        button_layout.addWidget(self.refresh_button)
        
        # 弹性空间
        button_layout.addStretch()
        
        self.close_button = QPushButton("关闭")
        self.close_button.clicked.connect(self.close)
        button_layout.addWidget(self.close_button)
        
        main_layout.addLayout(button_layout)
        
    def get_available_weeks(self):
        """获取可选的周列表"""
        # 获取第一条记录的时间
        sessions = self.game_limiter.get_sessions()
        weeks = []
        
        if not sessions:
            # 如果没有记录，只显示本周
            today = datetime.date.today()
            week_start = today - datetime.timedelta(days=today.weekday())
            weeks.append(week_start.strftime("%Y-%m-%d"))
            return weeks
            
        # 获取第一条记录的日期
        first_session = sessions[-1] if sessions else None
        if first_session:
            first_date_str = first_session[1].split()[0]  # 取开始时间的日期部分
            first_date = datetime.datetime.strptime(first_date_str, "%Y-%m-%d").date()
            
            # 获取第一条记录所在周的起始日期
            first_week_start = first_date - datetime.timedelta(days=first_date.weekday())
            
            # 获取当前日期所在周的起始日期
            today = datetime.date.today()
            current_week_start = today - datetime.timedelta(days=today.weekday())
            
            # 生成所有周的列表
            current_date = current_week_start
            while current_date >= first_week_start:
                weeks.append(current_date.strftime("%Y-%m-%d"))
                current_date -= datetime.timedelta(days=7)
        else:
            # 如果没有记录，只显示本周
            today = datetime.date.today()
            week_start = today - datetime.timedelta(days=today.weekday())
            weeks.append(week_start.strftime("%Y-%m-%d"))
            
        return weeks
        
    def load_history(self):
        """加载历史记录"""
        try:
            # 清空树
            self.history_tree.clear()
            
            # 获取选中的周
            selected_week = self.week_combo.currentText()
            if not selected_week:
                return
                
            # 获取会话记录
            sessions = self.game_limiter.get_sessions(selected_week)
            
            # 添加到树
            for session in sessions:
                sid, start_time, end_time, duration, game, note = session
                item = QTreeWidgetItem([
                    str(sid),
                    start_time,
                    end_time or "进行中",
                    str(duration or 0),
                    game or "未知",
                    note or ""
                ])
                self.history_tree.addTopLevelItem(item)
                
            # 更新统计信息
            self.update_statistics(selected_week)
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载历史记录失败: {str(e)}")
        
    def update_statistics(self, week_start):
        """更新统计信息"""
        try:
            # 获取该周的总时长和额外时间
            used, extra = self.game_limiter.db.get_week_total(week_start)
            
            # 计算剩余时间
            weekly_limit = min(DEFAULT_WEEKLY_LIMIT + extra, MAX_WEEKLY_LIMIT)
            remaining = max(0, weekly_limit - used)
            
            # 更新标签
            self.total_label.setText(f"本周总时长: {used} 分钟")
            self.extra_label.setText(f"额外奖励: {extra} 分钟")
            self.remaining_label.setText(f"剩余时间: {remaining} 分钟")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"更新统计信息失败: {str(e)}")
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        event.accept() 