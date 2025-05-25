import asyncio
import datetime
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, 
    QLabel, QPushButton, QComboBox, QTreeWidget, QTreeWidgetItem,
    QFrame, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from qasync import asyncSlot

from logic.constants import (
    PADDING_MEDIUM,
    DEFAULT_WEEKLY_LIMIT
)

class HistoryPanel(QDialog):
    """历史记录面板"""
    
    def __init__(self, parent=None, game_limiter=None):
        super().__init__(parent)
        
        self.parent = parent
        self.game_limiter = game_limiter
        
        # 设置窗口
        self.setWindowTitle("Game History")
        self.resize(900, 600)
        self.setMinimumSize(800, 500)
        self.setModal(True)
        
        # 设置UI
        self.setup_ui()
        
        # 加载数据
        asyncio.create_task(self.async_load_data())
        
    def setup_ui(self):
        """设置UI组件"""
        # 主布局
        main_layout = QVBoxLayout(self)
        
        # 顶部控制栏
        control_layout = QHBoxLayout()
        
        # 标题
        title_label = QLabel("Game History")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_font.setItalic(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        control_layout.addWidget(title_label)
        
        # 弹性空间
        control_layout.addStretch()
        
        # 周选择
        week_layout = QHBoxLayout()
        week_layout.addWidget(QLabel("Select Week:"))
        
        # 初始化空的周下拉列表，稍后在async_load_data中填充
        self.week_combo = QComboBox()
        self.week_combo.addItem("Loading...")  # 临时占位项
        self.week_combo.currentIndexChanged.connect(lambda: asyncio.create_task(self.on_week_changed()))
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
        self.history_tree.setHeaderLabels(["ID", "Start Time", "End Time", "Duration (minutes)", "Game", "Note"])
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
        self.total_label = QLabel("Total Duration This Week: 0 minutes")
        stats_layout.addWidget(self.total_label)
        
        self.extra_label = QLabel("Extra Reward: 0 minutes")
        stats_layout.addWidget(self.extra_label)
        
        self.remaining_label = QLabel("Remaining Time: 0 minutes")
        stats_layout.addWidget(self.remaining_label)
        
        main_layout.addWidget(stats_frame)
        
        # 底部按钮框架
        button_layout = QHBoxLayout()
        
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(lambda: asyncio.create_task(self._load_history_async()))
        button_layout.addWidget(self.refresh_button)
        
        # 弹性空间
        button_layout.addStretch()
        
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        button_layout.addWidget(self.close_button)
        
        main_layout.addLayout(button_layout)
        
    async def get_available_weeks(self):
        """获取可选的周列表"""
        # 获取第一条记录的时间
        sessions = await self.game_limiter.get_sessions()
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
        
    async def async_load_data(self):
        """加载历史数据"""
        try:
            # 获取可用的周列表
            self.weeks = await self.get_available_weeks()
            
            # 清空并填充周下拉列表
            self.week_combo.clear()
            self.week_combo.addItems(self.weeks)
            self.week_combo.setCurrentIndex(0)
            
            # 获取会话记录
            self.all_sessions = await self.game_limiter.get_sessions()
            
            # 根据当前筛选填充树视图
            await self.filter_and_display_sessions()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load history: {str(e)}")
    
    async def filter_and_display_sessions(self):
        """根据筛选条件显示会话"""
        self.history_tree.clear()
        
        if not self.all_sessions:
            return
            
        # 获取当前筛选器值
        filter_option = self.week_combo.currentText()
        
        # 准备要显示的会话
        filtered_sessions = []
        
        # 检查是否为日期格式的周开始日期
        try:
            # 尝试解析为日期格式 (YYYY-MM-DD)
            selected_week_start = datetime.datetime.strptime(filter_option, "%Y-%m-%d").date()
            selected_week_end = selected_week_start + datetime.timedelta(days=7)
            
            # 筛选指定周的会话
            for session in self.all_sessions:
                session_date_str = session[1].split(" ")[0]  # 取start_time的日期部分
                session_date = datetime.datetime.strptime(session_date_str, "%Y-%m-%d").date()
                if selected_week_start <= session_date < selected_week_end:
                    filtered_sessions.append(session)
                    
            # 获取该周的统计信息
            used, extra = await self.game_limiter.db.get_week_total(filter_option)
            
            # 添加周总计
            self.add_summary_item(filter_option, used, extra)
            
        except ValueError:
            # 如果不是日期格式，使用旧的逻辑
            if filter_option == "All Records":
                filtered_sessions = self.all_sessions
            elif filter_option == "This Week Records":
                today = datetime.date.today()
                week_start = today - datetime.timedelta(days=today.weekday())
                
                used, extra = await self.game_limiter.db.get_week_total(week_start.strftime("%Y-%m-%d"))
                
                # 记录周总计
                self.add_summary_item(week_start.strftime("%Y-%m-%d"), used, extra)
                
                # 筛选本周会话
                for session in self.all_sessions:
                    session_date = session[1].split(" ")[0]  # 取start_time的日期部分
                    if session_date >= week_start.strftime("%Y-%m-%d"):
                        filtered_sessions.append(session)
            elif filter_option == "Last Week Records":
                today = datetime.date.today()
                this_week_start = today - datetime.timedelta(days=today.weekday())
                last_week_start = (this_week_start - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
                this_week_start_str = this_week_start.strftime("%Y-%m-%d")
                
                # 筛选上周会话
                for session in self.all_sessions:
                    session_date = session[1].split(" ")[0]  # 取start_time的日期部分
                    if session_date >= last_week_start and session_date < this_week_start_str:
                        filtered_sessions.append(session)
        
        # 添加会话到树视图
        for session in filtered_sessions:
            self.add_session_item(session)
    
    def add_summary_item(self, week_start, used, extra):
        """添加周总计项"""
        item = QTreeWidgetItem([
            "Total",
            week_start,
            "",
            str(used),
            "",
            f"Total Duration This Week: {used} minutes, Extra Reward: {extra} minutes"
        ])
        self.history_tree.addTopLevelItem(item)
    
    def add_session_item(self, session):
        """添加会话项 - 修复以支持7列数据库结构"""
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
            # 如果结构不匹配，记录错误并使用安全的默认值
            print(f"Warning: Unexpected session structure with {len(session)} columns: {session}")
            sid = session[0] if len(session) > 0 else "?"
            start_time = session[1] if len(session) > 1 else "Unknown"
            end_time = session[2] if len(session) > 2 else None
            duration = session[3] if len(session) > 3 else 0
            display_game = "Unknown"
            note = ""
        
        item = QTreeWidgetItem([
            str(sid),
            start_time,
            end_time or "In Progress",
            str(duration or 0),
            display_game,
            note or ""
        ])
        self.history_tree.addTopLevelItem(item)
    
    def load_history(self):
        """加载历史记录 - 避免UI冻结"""
        # 避免重复加载
        if hasattr(self, '_loading_history') and self._loading_history:
            return
            
        # 创建异步任务来加载数据
        try:
            asyncio.create_task(self._load_history_async())
        except RuntimeError:
            # 如果事件循环没有运行，创建新的事件循环
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._load_history_async())
            loop.close()
    
    async def _load_history_async(self):
        """异步加载历史记录"""
        if hasattr(self, '_loading_history') and self._loading_history:
            return
            
        self._loading_history = True
        try:
            await self.async_load_data()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load history: {str(e)}")
        finally:
            self._loading_history = False
    
    async def update_statistics(self, week_start):
        """更新统计信息 - 修复为异步调用"""
        try:
            # 使用异步方法获取该周的总时长和额外时间
            used, extra = await self.game_limiter.db.get_week_total(week_start)
            
            # 计算剩余时间
            from logic.constants import MAX_WEEKLY_LIMIT
            weekly_limit = min(DEFAULT_WEEKLY_LIMIT + extra, MAX_WEEKLY_LIMIT)
            remaining = max(0, weekly_limit - used)
            
            # 更新标签
            self.total_label.setText(f"Total Duration This Week: {used} minutes")
            self.extra_label.setText(f"Extra Reward: {extra} minutes")
            self.remaining_label.setText(f"Remaining Time: {remaining} minutes")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update statistics: {str(e)}")
    
    async def delete_session(self):
        """删除所选会话"""
        selected_items = self.history_tree.selectedItems()
        if not selected_items:
            return
            
        if selected_items[0].parent() is None:
            # 不能删除摘要项
            QMessageBox.warning(self, "Warning", "Cannot delete summary item")
            return
            
        # 获取会话ID
        session_id = int(selected_items[0].text(0))
        
        # 确认删除
        confirm = QMessageBox.question(
            self, 
            "Confirm Delete", 
            f"Are you sure you want to delete the session record with ID {session_id}? This operation cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirm == QMessageBox.StandardButton.Yes:
            try:
                # 删除会话
                await self.game_limiter.db.delete_session(session_id)
                
                # 重新加载数据
                await self.async_load_data()
                
                QMessageBox.information(self, "Success", "Session record deleted")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete session record: {str(e)}")
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        event.accept()
    
    async def on_week_changed(self):
        """周选择改变时的异步处理"""
        if hasattr(self, 'all_sessions'):
            await self.filter_and_display_sessions() 