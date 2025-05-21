import sys
import asyncio
import datetime
import logging
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QLineEdit, QProgressBar, 
    QMessageBox, QInputDialog, QFrame, QTreeWidget, 
    QTreeWidgetItem, QSplitter, QApplication, QTabWidget,
    QGridLayout, QSpacerItem, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QFont

from logic.constants import (
    UI_TITLE, UI_WIDTH, UI_HEIGHT, UI_MIN_WIDTH, UI_MIN_HEIGHT,
    PADDING_SMALL, PADDING_MEDIUM, PADDING_LARGE,
    BUTTON_HEIGHT, BUTTON_WIDTH, BUTTON_PADX, BUTTON_PADY,
    DEFAULT_WEEKLY_LIMIT, MAX_WEEKLY_LIMIT, ADMIN_PASS_HASH
)
from logic.game_limiter import GameLimiter
from logic.database import sha256, get_week_start
from logic.window_monitor import WindowMonitor
from ui.base import StatusBar, SessionTimer, OverlayWindow, ShakeEffect
from ui.math_panel import MathPanel
from ui.admin_panel import AdminPanel
from ui.history_panel import HistoryPanel

# 配置日志
logger = logging.getLogger('main_window')

class MainWindow(QMainWindow):
    """主窗口"""
    def __init__(self):
        super().__init__()
        
        # 初始化游戏限制器
        self.game_limiter = GameLimiter()
        self.session_active = False
        self.countdown_window = None
        
        # 初始化窗口监控器
        self.window_monitor = WindowMonitor(self.game_limiter, check_interval=15)
        
        # 设置窗口
        self.setup_window()
        
        # 设置UI
        self.setup_ui()
        
        # 更新周状态
        self.update_weekly_status()
        
        # 使用QTimer延迟启动窗口监控（解决事件循环问题）
        QTimer.singleShot(1000, self.delayed_start_monitoring)
        
    def setup_window(self):
        """设置窗口属性"""
        self.setWindowTitle(UI_TITLE)
        self.resize(UI_WIDTH, UI_HEIGHT)
        self.setMinimumSize(UI_MIN_WIDTH, UI_MIN_HEIGHT)
        
        # 设置窗口图标
        try:
            self.setWindowIcon(QIcon("app.ico"))
        except Exception:
            pass
        
    def setup_ui(self):
        """设置UI组件"""
        # 创建中央窗口部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(PADDING_MEDIUM, PADDING_MEDIUM, PADDING_MEDIUM, PADDING_MEDIUM)
        main_layout.setSpacing(PADDING_MEDIUM)
        
        # 顶部状态部分
        status_frame = QFrame()
        status_frame.setFrameShape(QFrame.Shape.StyledPanel)
        status_frame.setFrameShadow(QFrame.Shadow.Raised)
        status_layout = QVBoxLayout(status_frame)
        
        # 周状态面板
        week_status_layout = QHBoxLayout()
        
        # 周开始日期
        week_layout = QVBoxLayout()
        week_title = QLabel("本周开始日期")
        week_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.week_start_label = QLabel("加载中...")
        self.week_start_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.week_start_label.setStyleSheet("font-weight: bold;")
        week_layout.addWidget(week_title)
        week_layout.addWidget(self.week_start_label)
        week_status_layout.addLayout(week_layout)
        
        # 已用时间
        used_layout = QVBoxLayout()
        used_title = QLabel("已用时间")
        used_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.used_time_label = QLabel("0 分钟")
        self.used_time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.used_time_label.setStyleSheet("font-weight: bold;")
        used_layout.addWidget(used_title)
        used_layout.addWidget(self.used_time_label)
        week_status_layout.addLayout(used_layout)
        
        # 额外时间
        extra_layout = QVBoxLayout()
        extra_title = QLabel("额外时间")
        extra_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.extra_time_label = QLabel("0 分钟")
        self.extra_time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.extra_time_label.setStyleSheet("font-weight: bold;")
        extra_layout.addWidget(extra_title)
        extra_layout.addWidget(self.extra_time_label)
        week_status_layout.addLayout(extra_layout)
        
        # 剩余时间
        remaining_layout = QVBoxLayout()
        remaining_title = QLabel("剩余时间")
        remaining_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.remaining_time_label = QLabel("0 分钟")
        self.remaining_time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.remaining_time_label.setStyleSheet("font-weight: bold;")
        remaining_layout.addWidget(remaining_title)
        remaining_layout.addWidget(self.remaining_time_label)
        week_status_layout.addLayout(remaining_layout)
        
        status_layout.addLayout(week_status_layout)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%v%")
        status_layout.addWidget(self.progress_bar)
        
        main_layout.addWidget(status_frame)
        
        # 计时器部分
        timer_frame = QFrame()
        timer_frame.setFrameShape(QFrame.Shape.StyledPanel)
        timer_frame.setFrameShadow(QFrame.Shadow.Raised)
        timer_layout = QVBoxLayout(timer_frame)
        
        # 计时器标签
        timer_title = QLabel("游戏时间")
        timer_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        timer_title.setFont(title_font)
        timer_layout.addWidget(timer_title)
        
        # 计时器组件
        self.session_timer = SessionTimer()
        self.session_timer.timer_done_signal.connect(self.timer_done)
        timer_layout.addWidget(self.session_timer)
        
        # 会话状态
        self.session_status = QLabel("未开始")
        self.session_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_font = QFont()
        status_font.setPointSize(12)
        status_font.setBold(True)
        self.session_status.setFont(status_font)
        timer_layout.addWidget(self.session_status)
        
        main_layout.addWidget(timer_frame)
        
        # 控制部分
        control_frame = QFrame()
        control_frame.setFrameShape(QFrame.Shape.StyledPanel)
        control_frame.setFrameShadow(QFrame.Shadow.Raised)
        control_layout = QVBoxLayout(control_frame)
        
        # 第一行 - 会话时间和控制按钮
        first_row = QHBoxLayout()
        
        # 时长选择
        duration_layout = QHBoxLayout()
        duration_label = QLabel("Session时长(分钟):")
        self.duration_entry = QLineEdit("30")
        self.duration_entry.setFixedWidth(100)
        duration_layout.addWidget(duration_label)
        duration_layout.addWidget(self.duration_entry)
        
        # 会话控制按钮
        session_buttons = QHBoxLayout()
        session_buttons.setSpacing(PADDING_SMALL)
        
        # 开始按钮
        self.start_button = QPushButton("开始游戏")
        self.start_button.clicked.connect(lambda: asyncio.create_task(self.start_session_with_effect()))
        
        # 结束按钮
        self.stop_button = QPushButton("提前结束")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.end_session_early)
        
        session_buttons.addWidget(self.start_button)
        session_buttons.addWidget(self.stop_button)
        
        # 构建第一行
        first_row.addLayout(duration_layout)
        first_row.addSpacing(PADDING_MEDIUM)
        first_row.addLayout(session_buttons)
        first_row.addSpacing(PADDING_MEDIUM)
        
        # 数学练习按钮
        self.math_button = QPushButton("赢取奖励")
        self.math_button.clicked.connect(self.show_math_panel)
        first_row.addWidget(self.math_button)
        
        first_row.addStretch()
        
        # 第二行 - 其他功能按钮
        second_row = QHBoxLayout()
        
        # 历史记录按钮
        self.history_button = QPushButton("历史记录")
        self.history_button.clicked.connect(self.show_history)
        
        # 管理员按钮
        self.admin_button = QPushButton("管理")
        self.admin_button.clicked.connect(self.admin_login)
        
        # 添加按钮到第二行
        second_row.addWidget(self.history_button)
        second_row.addWidget(self.admin_button)
        second_row.addStretch()
        
        # 将两行添加到控制布局
        control_layout.addLayout(first_row)
        control_layout.addLayout(second_row)
        
        main_layout.addWidget(control_frame)
        
        # 状态栏
        self.status_bar = StatusBar()
        main_layout.addWidget(self.status_bar)
        
    async def start_session_with_effect(self):
        """带视觉效果的开始会话"""
        try:
            # 获取时长
            duration_text = self.duration_entry.text().strip()
            if not duration_text:
                QMessageBox.warning(self, "输入错误", "请输入有效的时长")
                await ShakeEffect.shake(self.duration_entry)
                return
                
            try:
                # 修改为浮点数，支持小数
                duration = float(duration_text)
                # 限制为2位小数
                duration = round(duration, 2)
                if duration <= 0:
                    raise ValueError("时长必须为正数")
            except ValueError:
                QMessageBox.warning(self, "输入错误", "请输入有效的数字")
                await ShakeEffect.shake(self.duration_entry)
                return
                
            # 获取周状态
            status = self.game_limiter.get_weekly_status()
            if duration > status["remaining_minutes"]:
                QMessageBox.warning(
                    self, 
                    "时间不足", 
                    f"本周剩余游戏时间为{status['remaining_minutes']}分钟，"
                    f"无法开始{duration}分钟的Session"
                )
                await ShakeEffect.shake(self.duration_entry)
                return
                
            # 直接开始会话，不使用倒计时
            await self.start_session()
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"开始Session时出错: {str(e)}")
            logger.error(f"开始会话时出错: {str(e)}")
    
    async def start_session(self):
        """开始游戏会话"""
        try:
            # 获取会话时长（分钟）
            duration_text = self.duration_entry.text().strip()
            
            # 支持小数分钟，转换为秒
            if not duration_text:
                QMessageBox.warning(self, "输入错误", "请输入有效的游戏时长")
                return False
                
            try:
                duration = float(duration_text)
                if duration <= 0:
                    QMessageBox.warning(self, "输入错误", "游戏时长必须大于0")
                    return False
            except ValueError:
                QMessageBox.warning(self, "输入错误", "请输入有效的数字")
                return False
                
            # 检查本周剩余时间
            status = self.game_limiter.get_weekly_status()
            if status['remaining_minutes'] <= 0:
                QMessageBox.warning(
                    self, 
                    "时间用完", 
                    "本周游戏时间已用完，无法开始新的游戏Session。\n\n可以通过【获取奖励】获得额外时间。"
                )
                return False
                
            # 如果剩余时间小于要求的时间，提示并调整
            if status['remaining_minutes'] < duration:
                confirm = QMessageBox.question(
                    self,
                    "时间不足",
                    f"本周剩余时间仅剩{status['remaining_minutes']}分钟，小于请求的{duration}分钟。\n\n是否使用剩余的全部时间？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if confirm != QMessageBox.StandardButton.Yes:
                    return False
                duration = status['remaining_minutes']
                
            # 开始会话
            self.game_limiter.start_session(duration)
            self.session_active = True
            
            # 设置会话定时器
            self.session_timer.start(duration)  # SessionTimer内部会转换为秒
            self.session_status.setText("进行中")
            
            # 更新按钮状态
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.duration_entry.setEnabled(False)
            
            # 停止窗口监控（会话期间）
            await self.window_monitor.stop_monitoring()
            
            return True
        except Exception as e:
            QMessageBox.critical(self, "错误", f"开始游戏Session时出错: {str(e)}")
            return False
    
    def end_session_early(self):
        """提前结束会话"""
        confirm = QMessageBox.question(
            self,
            "确认结束",
            "确定要提前结束当前游戏Session吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirm == QMessageBox.StandardButton.Yes:
            asyncio.create_task(self.end_session())
    
    async def end_session(self):
        """结束游戏会话"""
        if not self.session_active:
            return
            
        try:
            # 取消定时器
            self.session_timer.stop()
            
            # 结束会话
            start_time, end_time, duration = self.game_limiter.end_session()
            self.session_active = False
            
            # 更新UI状态
            self.session_status.setText("已结束")
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.duration_entry.setEnabled(True)
            
            # 更新周状态
            self.update_weekly_status()
            
            # 执行会话结束后的操作（锁屏等）
            await self.post_session_actions()
            
            # 启动窗口监控（会话结束后）
            asyncio.create_task(self.window_monitor.start_monitoring())
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"结束游戏Session时出错: {str(e)}")
    
    async def post_session_actions(self):
        """会话结束后的操作"""
        # 使用 asyncio.to_thread 代替线程
        await asyncio.to_thread(self.game_limiter.kill_minecraft)
        
        # 锁屏也使用 asyncio.to_thread
        await asyncio.to_thread(self.game_limiter.lock_screen)
        
        # 显示最终倒计时
        self.show_final_countdown()
    
    async def show_countdown_window(self):
        """显示倒计时窗口"""
        if not self.countdown_window:
            self.countdown_window = OverlayWindow(self, width=400, height=250, corner="top-right")
        
        self.countdown_window.show_message("准备开始", "5", callback=lambda: asyncio.create_task(self.update_countdown(5)))
    
    async def update_countdown(self, seconds):
        """更新倒计时"""
        if seconds <= 0:
            self.countdown_window.hide()
            await self.start_session()
            return
            
        self.countdown_window.update_message(str(seconds))
        await asyncio.sleep(1)
        asyncio.create_task(self.update_countdown(seconds - 1))
        
    def show_final_countdown(self):
        """显示会话结束最终倒计时"""
        if not self.countdown_window:
            self.countdown_window = OverlayWindow(self, width=400, height=250)
        
        self.countdown_window.show_message(
            "Session已结束", 
            "屏幕将在 10 秒后锁定",
            callback=lambda: asyncio.create_task(self.update_final_countdown(10))
        )
    
    async def update_final_countdown(self, seconds):
        """更新最终倒计时"""
        if seconds <= 0:
            self.countdown_window.hide()
            # 强制执行锁屏操作
            await asyncio.to_thread(self.game_limiter.lock_screen)
            logger.info("倒计时结束，屏幕已锁定")
            return
            
        text = f"屏幕将在 {seconds} 秒后锁定" if seconds > 1 else "即将锁定屏幕..."
        self.countdown_window.update_message(text)
        await asyncio.sleep(1)
        asyncio.create_task(self.update_final_countdown(seconds - 1))
    
    def timer_done(self):
        """计时器结束回调"""
        if self.session_active:
            logger.info("计时器结束，自动结束会话")
            asyncio.create_task(self.end_session())
        
    def update_weekly_status(self):
        """更新周状态信息"""
        try:
            status = self.game_limiter.get_weekly_status()
            
            # 更新标签
            self.week_start_label.setText(status['week_start'])
            self.used_time_label.setText(f"{status['used_minutes']} 分钟")
            self.extra_time_label.setText(f"{status['extra_minutes']} 分钟")
            self.remaining_time_label.setText(f"{status['remaining_minutes']} 分钟")
            
            # 更新进度条
            if status['weekly_limit'] > 0:
                progress = int(100 * status['used_minutes'] / status['weekly_limit'])
                self.progress_bar.setValue(progress)
                
                # 根据剩余时间更改进度条颜色
                if status['remaining_minutes'] <= 15:
                    self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #dc3545; }")
                elif status['remaining_minutes'] <= 30:
                    self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #ffc107; }")
                else:
                    self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #28a745; }")
            else:
                self.progress_bar.setValue(0)
                
        except Exception as e:
            self.status_bar.show_message(f"更新周状态出错: {e}")
            
    def update_session_display(self):
        """更新会话显示"""
        if self.session_active:
            try:
                # 计算已用时间
                start_time_str = self.session_timer.start_time.strftime("%Y-%m-%d %H:%M:%S")
                now = datetime.datetime.now()
                elapsed = (now - self.session_timer.start_time).total_seconds() / 60
                total = self.session_timer.duration / 60  # 从秒转换为分钟
                
                # 更新状态
                status_text = f"Session开始于: {start_time_str}\n"
                status_text += f"已进行: {int(elapsed)} 分钟 / 总计: {int(total)} 分钟"
                
                self.session_status.setText(status_text)
            except Exception as e:
                self.status_bar.show_message(f"更新Session显示出错: {e}")
            
    def show_math_panel(self):
        """显示数学练习面板"""
        self.math_panel = MathPanel(self)
        self.math_panel.on_complete_signal.connect(self.on_math_complete)
        self.math_panel.show()
        
    def on_math_complete(self, reward_minutes=0):
        """数学练习完成回调"""
        if reward_minutes > 0:
            self.game_limiter.add_weekly_extra_time(reward_minutes)
            self.update_weekly_status()
            self.status_bar.show_message(f"获得额外游戏时间: {reward_minutes}分钟")
        
    def show_history(self):
        """显示历史记录"""
        self.history_panel = HistoryPanel(self, self.game_limiter)
        self.history_panel.show()
        
    def admin_login(self):
        """管理员登录"""
        password, ok = QInputDialog.getText(
            self, 
            "管理员登录", 
            "请输入管理员密码:", 
            QLineEdit.EchoMode.Password
        )
        
        if not ok or not password:
            return
            
        # 验证密码
        password_hash = sha256(password)
        if password_hash == ADMIN_PASS_HASH:
            self.show_admin_panel()
        else:
            QMessageBox.warning(self, "验证失败", "密码错误")
            # 抖动窗口
            asyncio.create_task(ShakeEffect.shake(self))
    
    def show_admin_panel(self):
        """显示管理面板"""
        self.admin_panel = AdminPanel(self, self.game_limiter)
        self.admin_panel.update_signal.connect(self.update_weekly_status)
        self.admin_panel.show()
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        try:
            # 停止窗口监控
            asyncio.create_task(self.window_monitor.stop_monitoring())
            
            # 要求输入管理员密码
            password, ok = QInputDialog.getText(
                self,
                "管理员验证",
                "请输入管理员密码:",
                QLineEdit.EchoMode.Password
            )
            
            if ok and password:
                # 验证密码
                if sha256(password) == ADMIN_PASS_HASH:
                    # 密码正确，检查是否有活动的会话
                    if self.session_active:
                        # 如果有活动的会话，提示用户
                        confirm = QMessageBox.question(
                            self, 
                            "确认退出", 
                            "当前有游戏Session正在进行，退出将结束当前Session。\n\n确定要退出吗？",
                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                        )
                        
                        if confirm == QMessageBox.StandardButton.Yes:
                            # 结束会话
                            asyncio.create_task(self.end_session())
                            # 关闭游戏限制器
                            self.game_limiter.close()
                            event.accept()
                        else:
                            event.ignore()
                    else:
                        # 没有活动的会话，直接关闭
                        self.game_limiter.close()
                        event.accept()
                else:
                    # 密码错误，拒绝关闭
                    QMessageBox.warning(
                        self,
                        "验证失败",
                        "管理员密码错误，无法关闭应用。"
                    )
                    event.ignore()
            else:
                # 用户取消输入，拒绝关闭
                event.ignore()
        except Exception as e:
            logging.error(f"关闭窗口时出错: {e}")
            event.ignore()  # 出错时也拒绝关闭

    def delayed_start_monitoring(self):
        """延迟启动窗口监控"""
        asyncio.create_task(self.window_monitor.start_monitoring()) 