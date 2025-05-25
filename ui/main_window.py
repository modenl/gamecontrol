import sys
import asyncio
import datetime
import logging
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QLineEdit,
    QProgressBar,
    QMessageBox,
    QInputDialog,
    QFrame,
    QApplication,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QFont

from logic.constants import (
    UI_TITLE,
    UI_WIDTH,
    UI_HEIGHT,
    UI_MIN_WIDTH,
    UI_MIN_HEIGHT,
    PADDING_MEDIUM,
    ADMIN_PASS_HASH,
)
from logic.game_limiter import GameLimiter
from logic.database import sha256
from logic.window_monitor import WindowMonitor
from ui.base import StatusBar, SessionTimer, OverlayWindow, ShakeEffect
from ui.math_panel_simple import SimpleMathPanel
from ui.admin_panel import AdminPanel
from ui.history_panel import HistoryPanel

# 配置日志
logger = logging.getLogger("main_window")


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self, game_limiter=None):
        super().__init__()
        self.game_limiter = game_limiter or GameLimiter()
        self.session_active = False
        self.countdown_window = None
        self.window_monitor = WindowMonitor(self.game_limiter, check_interval=15)
        self.setup_window()
        self.setup_ui()
        self.refresh_weekly_status_async()
        QTimer.singleShot(1000, self.delayed_start_monitoring)

    # --- 工具方法 ---
    def make_label(self, text: str, bold: bool = False, align: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignCenter) -> QLabel:
        """创建带样式的标签"""
        label = QLabel(text)
        label.setAlignment(align)
        if bold:
            font = label.font()
            font.setBold(True)
            label.setFont(font)
        return label

    def make_line_edit(self, text: str = "", width: int = 100) -> QLineEdit:
        """创建带默认宽度的输入框"""
        edit = QLineEdit(text)
        edit.setFixedWidth(width)
        return edit

    def create_button(self, text: str, callback, enabled: bool = True, width: int = None, height: int = None) -> QPushButton:
        """统一按钮工厂，便于后续批量样式和行为管理"""
        btn = QPushButton(text)
        btn.setEnabled(enabled)
        btn.clicked.connect(callback)
        if width:
            btn.setFixedWidth(width)
        if height:
            btn.setFixedHeight(height)
        return btn

    def refresh_weekly_status_async(self) -> None:
        self.run_async(self.update_weekly_status())

    def run_async(self, coro) -> None:
        asyncio.create_task(coro)

    def show_warning(self, msg: str) -> None:
        logger.warning(msg)
        QMessageBox.warning(self, "Warning", msg)

    def show_error(self, msg: str) -> None:
        logger.error(msg)
        QMessageBox.critical(self, "Error", msg)

    # --- UI 分块 ---
    def setup_window(self) -> None:
        """设置窗口属性"""
        self.setWindowTitle(UI_TITLE)
        self.resize(UI_WIDTH, UI_HEIGHT)
        self.setMinimumSize(UI_MIN_WIDTH, UI_MIN_HEIGHT)
        try:
            self.setWindowIcon(QIcon("app.ico"))
        except Exception:
            logger.info("未能设置窗口图标")
        
    def setup_ui(self) -> None:
        """设置UI组件"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(PADDING_MEDIUM, PADDING_MEDIUM, PADDING_MEDIUM, PADDING_MEDIUM)
        main_layout.setSpacing(PADDING_MEDIUM)
        main_layout.addWidget(self._create_status_panel())
        main_layout.addWidget(self._create_timer_panel())
        main_layout.addWidget(self._create_control_panel())
        self.status_bar = StatusBar()
        main_layout.addWidget(self.status_bar)

    def _create_status_panel(self) -> QFrame:
        status_frame = QFrame()
        status_frame.setFrameShape(QFrame.Shape.StyledPanel)
        status_frame.setFrameShadow(QFrame.Shadow.Raised)
        status_layout = QVBoxLayout(status_frame)
        week_status_layout = QHBoxLayout()
        # 周开始日期
        week_layout = QVBoxLayout()
        week_layout.addWidget(self.make_label("Week Start Date"))
        self.week_start_label = self.make_label("Loading...", bold=True)
        week_layout.addWidget(self.week_start_label)
        week_status_layout.addLayout(week_layout)
        # 已用时间
        used_layout = QVBoxLayout()
        used_layout.addWidget(self.make_label("Used Time"))
        self.used_time_label = self.make_label("0 minutes", bold=True)
        used_layout.addWidget(self.used_time_label)
        week_status_layout.addLayout(used_layout)
        # 额外时间
        extra_layout = QVBoxLayout()
        extra_layout.addWidget(self.make_label("Extra Time"))
        self.extra_time_label = self.make_label("0 minutes", bold=True)
        extra_layout.addWidget(self.extra_time_label)
        week_status_layout.addLayout(extra_layout)
        # 剩余时间
        remaining_layout = QVBoxLayout()
        remaining_layout.addWidget(self.make_label("Remaining Time"))
        self.remaining_time_label = self.make_label("0 minutes", bold=True)
        remaining_layout.addWidget(self.remaining_time_label)
        week_status_layout.addLayout(remaining_layout)
        status_layout.addLayout(week_status_layout)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%v%")
        status_layout.addWidget(self.progress_bar)
        return status_frame

    def _create_timer_panel(self) -> QFrame:
        timer_frame = QFrame()
        timer_frame.setFrameShape(QFrame.Shape.StyledPanel)
        timer_frame.setFrameShadow(QFrame.Shadow.Raised)
        timer_layout = QVBoxLayout(timer_frame)
        timer_title = self.make_label("Game Time", bold=True)
        title_font = timer_title.font()
        title_font.setPointSize(14)
        timer_title.setFont(title_font)
        timer_layout.addWidget(timer_title)
        self.session_timer = SessionTimer()
        self.session_timer.timer_done_signal.connect(self.timer_done)
        timer_layout.addWidget(self.session_timer)
        self.session_status = self.make_label("Not Started", bold=True)
        status_font = self.session_status.font()
        status_font.setPointSize(12)
        self.session_status.setFont(status_font)
        timer_layout.addWidget(self.session_status)
        return timer_frame

    def _create_control_panel(self) -> QFrame:
        control_frame = QFrame()
        control_frame.setFrameShape(QFrame.Shape.StyledPanel)
        control_frame.setFrameShadow(QFrame.Shadow.Raised)
        control_layout = QVBoxLayout(control_frame)
        # 第一行
        first_row = QHBoxLayout()
        duration_layout = QHBoxLayout()
        duration_label = self.make_label("Session Duration (minutes):")
        self.duration_entry = self.make_line_edit("30", 100)
        duration_layout.addWidget(duration_label)
        duration_layout.addWidget(self.duration_entry)
        session_buttons = QHBoxLayout()
        session_buttons.setSpacing(PADDING_MEDIUM)
        self.start_button = self.create_button("Start Game", lambda: self.run_async(self.start_session_with_effect()))
        self.stop_button = self.create_button("End Early", self.end_session_early, enabled=False)
        session_buttons.addWidget(self.start_button)
        session_buttons.addWidget(self.stop_button)
        first_row.addLayout(duration_layout)
        first_row.addSpacing(PADDING_MEDIUM)
        first_row.addLayout(session_buttons)
        first_row.addSpacing(PADDING_MEDIUM)
        self.math_button = self.create_button("Earn Rewards", self.show_math_panel)
        first_row.addWidget(self.math_button)
        first_row.addStretch()
        # 第二行
        second_row = QHBoxLayout()
        self.history_button = self.create_button("History", self.show_history)
        self.admin_button = self.create_button("Admin", self.admin_login)
        second_row.addWidget(self.history_button)
        second_row.addWidget(self.admin_button)
        second_row.addStretch()
        control_layout.addLayout(first_row)
        control_layout.addLayout(second_row)
        return control_frame

    # --- 业务逻辑与事件 ---
    def show_math_panel(self) -> None:
        """显示数学练习面板"""
        # 检查是否有活动的session
        if self.session_active:
            self.show_warning("Game Session is in progress, unable to do math exercises.\n\nPlease come back after the Session ends.")
            return
            
        logger.info("打开数学练习面板")
        self.math_panel = SimpleMathPanel(self)
        self.math_panel.on_complete_signal.connect(self.on_math_complete)
        self.math_panel.show()

    def on_math_complete(self, reward_minutes: float = 0) -> None:
        """数学练习完成回调"""
        logger.info(f"数学练习完成，奖励分钟数: {reward_minutes}")
        self.refresh_weekly_status_async()

    def show_history(self) -> None:
        """显示历史记录面板"""
        logger.info("打开历史记录面板")
        self.history_panel = HistoryPanel(self, self.game_limiter)
        self.history_panel.show()
        self.refresh_weekly_status_async()

    def admin_login(self) -> None:
        """管理员登录"""
        logger.info("管理员登录尝试")
        password, ok = QInputDialog.getText(self, "Administrator Login", "Please enter administrator password:", QLineEdit.EchoMode.Password)
        if not ok or not password:
            logger.info("管理员登录取消或未输入密码")
            return
        password_hash = sha256(password)
        if password_hash == ADMIN_PASS_HASH:
            logger.info("管理员登录成功")
            self.show_admin_panel()
        else:
            logger.warning("管理员密码错误")
            self.show_warning("Incorrect password")
            self.run_async(ShakeEffect.shake(self))

    def show_admin_panel(self) -> None:
        """显示管理面板"""
        logger.info("打开管理面板")
        
        # 停止窗口监控，避免任务冲突
        if hasattr(self, 'window_monitor') and self.window_monitor.is_running:
            logger.info("进入管理员模式，停止窗口监控")
            asyncio.create_task(self.window_monitor.stop_monitoring())
        
        self.admin_panel = AdminPanel(self, self.game_limiter)
        # 连接关闭信号，在关闭admin面板时恢复监控
        self.admin_panel.finished.connect(self.on_admin_panel_closed)
        self.admin_panel.show()
        
    def on_admin_panel_closed(self):
        """管理员面板关闭后的回调"""
        logger.info("管理员面板已关闭，恢复窗口监控")
        # 延迟1秒后重新启动监控，确保面板完全关闭
        QTimer.singleShot(1000, self.resume_monitoring)
        
    def resume_monitoring(self):
        """恢复窗口监控"""
        if hasattr(self, 'window_monitor') and not self.window_monitor.is_running:
            logger.info("恢复窗口监控")
            asyncio.create_task(self.window_monitor.start_monitoring())

    def end_session_early(self) -> None:
        """提前结束会话"""
        logger.info("用户请求提前结束会话")
        confirm = QMessageBox.question(self, "Confirm End", "Are you sure you want to end the current game Session early?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            self.run_async(self.end_session())

    async def end_session(self) -> None:
        """结束游戏会话"""
        if not self.session_active:
            logger.info("无活动会话，无需结束")
            return
        self.session_timer.stop()
        # 自动锁屏
        await asyncio.to_thread(self.game_limiter.lock_screen)
        try:
            await self.game_limiter.end_session()
        except Exception as e:
            logger.exception(f"结束会话出错: {e}")
        self.session_active = False
        self.session_status.setText("Ended")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.duration_entry.setEnabled(True)
        # 重新启用数学练习按钮
        self.math_button.setEnabled(True)
        await self.post_session_actions()

    async def post_session_actions(self) -> None:
        """会话结束后的清理和更新操作"""
        if self.countdown_window:
            self.countdown_window.close()
            self.countdown_window = None
        await self.update_weekly_status()
        self.update_session_display()

    async def start_session_with_effect(self) -> None:
        """带视觉效果的开始会话"""
        try:
            duration_text = self.duration_entry.text().strip()
            if not duration_text:
                self.show_warning("Please enter a valid duration")
                await ShakeEffect.shake(self.duration_entry)
                return
            
            try:
                duration = float(duration_text)
                duration = round(duration, 2)
                if duration <= 0:
                    raise ValueError("Duration must be positive")
            except ValueError:
                self.show_warning("Please enter a valid number")
                await ShakeEffect.shake(self.duration_entry)
                return
            
            status = await self.game_limiter.get_weekly_status()
            if duration > status["remaining_minutes"]:
                self.show_warning(f"This week's remaining game time is {status['remaining_minutes']} minutes, unable to start a {duration}-minute Session")
                await ShakeEffect.shake(self.duration_entry)
                return
                
            await self.start_session()
        except Exception as e:
            self.show_error(f"Error starting Session: {str(e)}")
            logger.exception(f"开始会话时出错: {str(e)}")

    async def start_session(self) -> bool:
        """开始游戏会话"""
        try:
            duration_text = self.duration_entry.text().strip()
            if not duration_text:
                self.show_warning("Please enter a valid game duration")
                return False
            try:
                duration = float(duration_text)
                if duration <= 0:
                    self.show_warning("Game duration must be greater than 0")
                    return False
            except ValueError:
                self.show_warning("Please enter a valid number")
                return False
            status = await self.game_limiter.get_weekly_status()
            if status["remaining_minutes"] <= 0:
                self.show_warning("This week's game time has been exhausted, unable to start a new game Session.\n\nYou can get extra time through [Earn Rewards].")
                return False
            if status["remaining_minutes"] < duration:
                confirm = QMessageBox.question(self, "Insufficient Time", f"This week's remaining time is only {status['remaining_minutes']} minutes, which is less than the requested {duration} minutes.\n\nWould you like to use all remaining time?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if confirm != QMessageBox.StandardButton.Yes:
                    return False
                duration = status["remaining_minutes"]
            self.game_limiter.start_session(duration)
            self.session_active = True
            self.session_timer.start(duration)
            self.session_status.setText("In Progress")
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.duration_entry.setEnabled(False)
            self.math_button.setEnabled(False)
            await self.window_monitor.stop_monitoring()
            return True
        except Exception as e:
            self.show_error(f"Error starting game Session: {str(e)}")
            logger.exception(f"开始游戏Session时出错: {str(e)}")
            return False

    async def update_weekly_status(self) -> None:
        """更新周状态"""
        try:
            status = await self.game_limiter.get_weekly_status()
            week_start = status["week_start"]
            week_start_date = datetime.datetime.strptime(week_start, "%Y-%m-%d").date()
            formatted_date = week_start_date.strftime("%Y-%m-%d")
            self.week_start_label.setText(formatted_date)
            used_minutes = status["used_minutes"]
            extra_minutes = status["extra_minutes"]
            remaining_minutes = status["remaining_minutes"]
            self.used_time_label.setText(f"{used_minutes} minutes")
            self.extra_time_label.setText(f"{extra_minutes} minutes")
            self.remaining_time_label.setText(f"{remaining_minutes} minutes")
            weekly_limit = status["weekly_limit"]
            if weekly_limit > 0:
                progress = min(100, int((used_minutes / weekly_limit) * 100))
                self.progress_bar.setValue(progress)
            else:
                self.progress_bar.setValue(0)
        except Exception as e:
            logger.exception(f"更新周状态出错: {e}")

    def update_session_display(self) -> None:
        """更新会话显示"""
        if self.session_active:
            try:
                start_time_str = self.session_timer.start_time.strftime("%Y-%m-%d %H:%M:%S")
                now = datetime.datetime.now()
                elapsed = (now - self.session_timer.start_time).total_seconds() / 60
                total = self.session_timer.duration / 60
                status_text = f"Session started at: {start_time_str}\n"
                status_text += f"Elapsed: {int(elapsed)} minutes / Total: {int(total)} minutes"
                self.session_status.setText(status_text)
            except Exception as e:
                logger.error(f"更新Session显示出错: {e}")
                self.status_bar.show_message(f"Error updating Session display: {e}")

    def closeEvent(self, event) -> None:
        """窗口关闭事件"""
        try:
            logger.info("窗口关闭事件触发，验证管理员密码")
            
            # 首先停止窗口监控，避免异步问题
            if hasattr(self, 'window_monitor') and self.window_monitor.is_running:
                logger.info("停止窗口监控...")
                self.window_monitor.is_running = False
                if self.window_monitor.monitor_task:
                    self.window_monitor.monitor_task.cancel()
            
            # 验证管理员密码
            password, ok = QInputDialog.getText(self, "Administrator Verification", "Please enter administrator password:", QLineEdit.EchoMode.Password)
            if ok and password:
                if sha256(password) == ADMIN_PASS_HASH:
                    if self.session_active:
                        confirm = QMessageBox.question(self, "Confirm Exit", "A game Session is currently in progress. Exiting will end the current Session.\n\nAre you sure you want to exit?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                        if confirm == QMessageBox.StandardButton.Yes:
                            # 结束会话
                            logger.info("强制结束活动会话...")
                            self.session_active = False
                            if hasattr(self, 'session_timer'):
                                self.session_timer.stop()
                            
                            # 简单清理并强制退出
                            self._force_exit()
                            event.accept()
                        else:
                            event.ignore()
                    else:
                        # 简单清理并强制退出
                        self._force_exit()
                        event.accept()
                else:
                    self.show_warning("Incorrect administrator password, unable to close application.")
                    event.ignore()
            else:
                event.ignore()
        except Exception as e:
            logger.error(f"关闭窗口时出错: {e}")
            event.ignore()
    
    def _force_exit(self):
        """强制退出应用程序"""
        try:
            logger.info("开始强制退出...")
            
            # 重置鼠标设置到系统默认值
            try:
                app = QApplication.instance()
                if app:
                    logger.info("重置鼠标设置...")
                    app.setDoubleClickInterval(500)  # 重置为系统默认值
                    app.setStartDragDistance(4)      # 重置为默认值
                    app.setStartDragTime(500)        # 重置为默认值
                    app.processEvents()              # 处理事件确保设置生效
            except Exception as e:
                logger.error(f"重置鼠标设置时出错: {e}")
            
            # 简单清理
            try:
                if hasattr(self, 'game_limiter') and self.game_limiter:
                    self.game_limiter.close()
            except:
                pass
            
            logger.info("立即强制退出应用程序")
            
            # 立即强制退出整个应用程序
            import os
            os._exit(0)
            
        except Exception as e:
            logger.error(f"强制退出时出错: {e}")
            # 即使出错也要强制退出
            import os
            os._exit(1)
    
    def cleanup_resources(self):
        """清理窗口资源"""
        try:
            logger.info("清理主窗口资源...")
            
            # 停止所有计时器
            if hasattr(self, 'session_timer'):
                self.session_timer.stop()
            
            # 关闭倒计时窗口
            if hasattr(self, 'countdown_window') and self.countdown_window:
                self.countdown_window.close()
                self.countdown_window = None
            
            # 关闭所有子面板
            for attr_name in ['admin_panel', 'math_panel', 'history_panel']:
                if hasattr(self, attr_name):
                    panel = getattr(self, attr_name)
                    if panel and hasattr(panel, 'close'):
                        try:
                            panel.close()
                        except:
                            pass
            
            # 清理应用程序资源
            try:
                logger.info("清理应用程序资源...")
                
                # 处理所有待处理的Qt事件
                from PyQt6.QtWidgets import QApplication
                app = QApplication.instance()
                if app:
                    app.processEvents()
                        
            except Exception as e:
                logger.error(f"清理应用程序资源时出错: {e}")
            
            # 关闭游戏限制器
            if hasattr(self, 'game_limiter') and self.game_limiter:
                self.game_limiter.close()
                
            logger.info("主窗口资源清理完成")
        except Exception as e:
            logger.error(f"清理主窗口资源时出错: {e}")

    def delayed_start_monitoring(self) -> None:
        """延迟启动窗口监控器"""
        self.run_async(self.window_monitor.start_monitoring())

    def timer_done(self) -> None:
        """计时器结束回调"""
        if self.session_active:
            logger.info("计时器结束，自动结束会话")
            self.run_async(self.end_session())
