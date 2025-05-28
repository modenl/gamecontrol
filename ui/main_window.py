import sys
import asyncio
import datetime
import logging
import threading
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
    TEST_MODE,
    TEST_ADMIN_PASS_HASH,
)
from logic.game_limiter import GameLimiter
from logic.database import sha256
from logic.window_monitor import WindowMonitor
from logic.task_manager import get_task_manager, run_task_safe
from ui.base import StatusBar, SessionTimer, OverlayWindow, ShakeEffect
from ui.math_panel_simple import SimpleMathPanel
from ui.admin_panel import AdminPanel
from ui.history_panel import HistoryPanel
from logic.auto_updater import get_updater

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
        self._updating = False  # 更新标志，用于跳过管理员密码验证
        
        # 初始化任务管理器
        self.task_manager = get_task_manager()
        
        # 延迟初始化自动更新器，确保qasync事件循环已准备好
        self.auto_updater = None
        self._auto_updater_init_attempts = 0
        self._auto_updater_ready = False
        # 不在构造函数中初始化，而是在showEvent中初始化
        
        self.setup_window()
        self.setup_ui()
        self.refresh_weekly_status_async()
        
        # 在测试模式下跳过窗口监控
        if not TEST_MODE:
            QTimer.singleShot(1000, self.delayed_start_monitoring)
        else:
            logger.info("🧪 测试模式：跳过窗口监控启动")

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

    def run_async(self, coro) -> str:
        """安全地运行异步任务"""
        return run_task_safe(coro, delay_ms=10)
    
    def _start_button_clicked(self):
        """开始按钮点击事件"""
        # 检查是否在关闭过程中
        if hasattr(self, '_updating') and self._updating:
            logger.warning("应用程序正在更新中，忽略按钮点击")
            return
        
        self.run_async(self.start_session_with_effect())

    def show_warning(self, msg: str) -> None:
        logger.warning(msg)
        QMessageBox.warning(self, "Warning", msg)

    def show_error(self, msg: str) -> None:
        logger.error(msg)
        QMessageBox.critical(self, "Error", msg)

    # --- UI 分块 ---
    def setup_window(self) -> None:
        """设置窗口属性"""
        # 导入版本信息并设置窗口标题
        try:
            from version import __version__
            window_title = f"{UI_TITLE} v{__version__}"
        except ImportError:
            window_title = UI_TITLE
            logger.warning("无法导入版本信息，使用默认标题")
        
        self.setWindowTitle(window_title)
        self.resize(UI_WIDTH, UI_HEIGHT)
        self.setMinimumSize(UI_MIN_WIDTH, UI_MIN_HEIGHT)
        try:
            self.setWindowIcon(QIcon("app.ico"))
        except Exception:
            logger.info("未能设置窗口图标")
    
    def showEvent(self, event):
        """窗口显示事件 - 在这里初始化自动更新器"""
        super().showEvent(event)
        
        # 在测试模式下完全跳过所有自动更新器相关操作
        if TEST_MODE:
            logger.info("🧪 测试模式：完全跳过自动更新器相关操作")
            return
        
        # 只在第一次显示时初始化自动更新器
        if not hasattr(self, '_auto_updater_initialized'):
            self._auto_updater_initialized = True
            
            logger.info("🪟 主窗口已显示，准备初始化自动更新器...")
            # 减少延迟时间，2秒足够确保组件稳定
            QTimer.singleShot(2000, self._init_auto_updater)
        
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
        # 连接更新通知点击信号
        self.status_bar.update_notification_clicked.connect(self.on_update_notification_clicked)
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
        self.start_button = self.create_button("Start Game", lambda: self._start_button_clicked())
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
        self.update_button = self.create_button("Check Updates", self.check_for_updates_manual)
        second_row.addWidget(self.history_button)
        second_row.addWidget(self.admin_button)
        second_row.addWidget(self.update_button)
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
        logger.info(f"传递给数学面板的math_exercises实例: id={id(self.game_limiter.math_exercises)}")
        self.math_panel = SimpleMathPanel(self, self.game_limiter.math_exercises)
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
        
        # 在测试模式下使用测试密码，避免阻塞
        if TEST_MODE:
            logger.info("🧪 测试模式：使用测试管理员密码")
            password_hash = TEST_ADMIN_PASS_HASH
        else:
            password, ok = QInputDialog.getText(self, "Administrator Login", "Please enter administrator password:", QLineEdit.EchoMode.Password)
            if not ok or not password:
                logger.info("管理员登录取消或未输入密码")
                return
            password_hash = sha256(password)
        
        if password_hash == ADMIN_PASS_HASH or (TEST_MODE and password_hash == TEST_ADMIN_PASS_HASH):
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
            self._safe_stop_monitoring()
        
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
        try:
            # 检查是否有活动会话，如果有则不启动监控
            if self.session_active:
                logger.info("检测到活动会话，不启动窗口监控")
                return
                
            if hasattr(self, 'window_monitor') and not self.window_monitor.is_running:
                logger.info("恢复窗口监控")
                self._safe_start_monitoring()
            else:
                logger.info("窗口监控已在运行或不可用")
        except Exception as e:
            logger.error(f"恢复窗口监控时出错: {e}")
    
    # --- 自动更新相关方法 ---
    def startup_update_check(self):
        """启动时的自动更新检查"""
        logger.info("🚀 开始启动时的自动更新检查")
        try:
            # 检查自动更新器是否正确初始化
            if not self.auto_updater or not self._auto_updater_ready:
                logger.warning("⚠️ 自动更新器尚未就绪，跳过启动时检查")
                return
            
            logger.info(f"📋 自动更新器类型: {type(self.auto_updater).__name__}")
            
            # 检查是否可以更新
            can_update, reason = self.auto_updater.can_update_now()
            logger.info(f"🔍 更新检查状态: can_update={can_update}, reason='{reason}'")
            
            if not can_update:
                logger.info(f"ℹ️ 启动时暂不检查更新: {reason}")
                return
            
            # 开始自动检查
            logger.info("🌐 开始自动检查更新...")
            self.auto_updater.check_for_updates(manual=False)
            
        except Exception as e:
            logger.error(f"❌ 启动时更新检查失败: {e}", exc_info=True)
    
    def check_for_updates_manual(self):
        """手动检查更新"""
        logger.info("👤 用户手动检查更新")
        
        # 在测试模式下跳过更新检查
        if TEST_MODE:
            logger.info("🧪 测试模式：跳过手动更新检查")
            return
        
        try:
            # 检查自动更新器状态
            if not self.auto_updater or not self._auto_updater_ready:
                logger.warning("⚠️ 自动更新器尚未就绪")
                self.show_warning("自动更新器正在初始化中，请稍后再试")
                return
            
            logger.info(f"📋 自动更新器类型: {type(self.auto_updater).__name__}")
            
            # 检查是否可以更新
            can_update, reason = self.auto_updater.can_update_now()
            logger.info(f"🔍 手动更新检查状态: can_update={can_update}, reason='{reason}'")
            
            if not can_update:
                logger.warning(f"⚠️ 当前无法检查更新: {reason}")
                self.show_warning(f"当前无法检查更新：{reason}\n\n请在游戏会话结束且没有数学练习进行时再试。")
                return
            
            # 显示检查中的状态
            logger.info("🔄 设置按钮为检查中状态")
            self.update_button.setEnabled(False)
            self.update_button.setText("Checking...")
            
            # 开始检查
            logger.info("🌐 开始手动检查更新...")
            self.auto_updater.check_for_updates(manual=True)
            
            # 减少恢复按钮的等待时间
            logger.info("⏰ 设置6秒后恢复按钮状态")
            QTimer.singleShot(6000, self.restore_update_button)
            
        except Exception as e:
            logger.error(f"❌ 手动更新检查失败: {e}", exc_info=True)
            self.show_error(f"检查更新时出错: {e}")
            self.restore_update_button()
    
    def restore_update_button(self):
        """恢复更新按钮状态"""
        logger.info("🔄 恢复更新按钮状态")
        try:
            self.update_button.setEnabled(True)
            self.update_button.setText("Check Updates")
            logger.info("✅ 更新按钮状态已恢复")
        except Exception as e:
            logger.error(f"❌ 恢复更新按钮状态失败: {e}")
    
    def on_update_available(self, update_info):
        """处理发现更新的信号"""
        logger.info(f"🎯 MainWindow.on_update_available 被调用!")
        logger.info(f"   新版本: {update_info.version}")
        logger.info(f"   文件名: {update_info.asset_name}")
        logger.info(f"   文件大小: {update_info.asset_size:,} 字节")
        logger.info(f"   下载地址: {update_info.download_url}")
        
        try:
            # 恢复按钮状态
            self.restore_update_button()
            
            # 在状态栏显示更新通知，而不是直接显示对话框
            logger.info("📋 在状态栏显示更新通知...")
            self.status_bar.show_update_notification(update_info)
            logger.info("✅ 更新通知已显示在状态栏")
            
        except Exception as e:
            logger.error(f"❌ 主窗口处理更新可用信号失败: {e}", exc_info=True)
    
    def on_update_check_failed(self, error_msg):
        """处理更新检查失败的信号"""
        logger.error(f"❌ 更新检查失败: {error_msg}")
        
        try:
            self.restore_update_button()
            
            # 如果是手动检查，显示错误信息
            if hasattr(self, 'update_button') and not self.update_button.isEnabled():
                logger.info("📋 显示更新检查失败对话框")
                
                # 根据错误类型显示不同的提示
                if "超时" in error_msg or "timeout" in error_msg.lower():
                    title = "网络超时"
                    message = f"检查更新时网络连接超时。\n\n{error_msg}\n\n建议：\n• 检查网络连接是否正常\n• 稍后重试\n• 如果问题持续，可能是GitHub服务器暂时不可用"
                elif "连接" in error_msg or "connection" in error_msg.lower():
                    title = "网络连接问题"
                    message = f"无法连接到更新服务器。\n\n{error_msg}\n\n建议：\n• 检查网络连接\n• 检查防火墙设置\n• 确认可以访问GitHub"
                elif "服务器" in error_msg or "server" in error_msg.lower():
                    title = "服务器问题"
                    message = f"更新服务器暂时不可用。\n\n{error_msg}\n\n建议：\n• 稍后重试\n• GitHub服务器可能正在维护"
                else:
                    title = "检查更新失败"
                    message = f"检查更新时发生错误：\n\n{error_msg}\n\n请检查网络连接后重试。"
                
                QMessageBox.information(self, title, message)
            else:
                logger.info("ℹ️ 自动更新检查失败，不显示对话框")
                
        except Exception as e:
            logger.error(f"❌ 处理更新检查失败信号时出错: {e}", exc_info=True)
    
    def on_no_update_available(self):
        """处理无更新可用的信号"""
        logger.info("📋 主窗口收到无更新可用信号")
        
        try:
            # 恢复更新按钮状态
            self.restore_update_button()
            
            # 隐藏可能存在的更新通知
            self.status_bar.hide_update_notification()
            
            logger.info("✅ 更新按钮状态已恢复，更新通知已隐藏")
            
        except Exception as e:
            logger.error(f"❌ 处理无更新可用信号时出错: {e}", exc_info=True)
    
    def on_update_notification_clicked(self, update_info):
        """处理更新通知点击事件"""
        logger.info(f"🖱️ 用户点击了更新通知: {update_info.version}")
        
        # 在测试模式下跳过更新通知处理
        if TEST_MODE:
            logger.info("🧪 测试模式：跳过更新通知处理")
            return
        
        try:
            # 要求管理员身份验证
            logger.info("🔐 要求管理员身份验证...")
            password, ok = QInputDialog.getText(
                self, 
                "Administrator Verification", 
                "Administrator password is required to download and install updates.\n\nPlease enter administrator password:", 
                QLineEdit.EchoMode.Password
            )
            
            if not ok or not password:
                logger.info("❌ 用户取消管理员验证或未输入密码")
                return
            
            # 验证管理员密码
            from logic.database import sha256
            from logic.constants import ADMIN_PASS_HASH
            
            password_hash = sha256(password)
            if password_hash != ADMIN_PASS_HASH:
                logger.warning("❌ 管理员密码错误")
                self.show_warning("Incorrect administrator password. Update cancelled.")
                self.run_async(ShakeEffect.shake(self))
                return
            
            logger.info("✅ 管理员身份验证成功")
            
            # 隐藏状态栏的更新通知
            self.status_bar.hide_update_notification()
            
            # 检查自动更新器状态
            if not self.auto_updater or not self._auto_updater_ready:
                logger.error("❌ 自动更新器不可用")
                self.show_error("Auto-updater is not available. Please try again later.")
                return
            
            # 开始需要管理员验证的更新流程
            logger.info("🚀 开始管理员验证的更新流程...")
            self.auto_updater.start_update_with_admin_auth(update_info)
            
        except Exception as e:
            logger.error(f"❌ 处理更新通知点击失败: {e}", exc_info=True)
            self.show_error(f"Failed to process update request: {e}")

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
        
        # 重要：会话结束后重新启动窗口监控
        logger.info("会话结束，重新启动窗口监控")
        self._safe_start_monitoring()

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
            
            logger.info(f"开始游戏会话: {duration} 分钟")
            self.game_limiter.start_session(duration)
            
            # 更新UI状态
            self.session_active = True
            self.session_timer.start(duration)
            self.session_status.setText("In Progress")
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.duration_entry.setEnabled(False)
            self.math_button.setEnabled(False)
            
            # 强制处理Qt事件确保UI更新
            app = QApplication.instance()
            if app:
                app.processEvents()
            
            self._safe_stop_monitoring()
            logger.info("游戏会话已启动")
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
            logger.info("窗口关闭事件触发")
            
            # 立即禁用所有UI控件，防止在关闭过程中进行操作
            self._disable_all_controls()
            
            # 首先停止窗口监控，避免异步问题
            if hasattr(self, 'window_monitor') and self.window_monitor.is_running:
                logger.info("停止窗口监控...")
                self.window_monitor.is_running = False
                if self.window_monitor.monitor_task:
                    self.window_monitor.monitor_task.cancel()
            
            # 在测试模式下跳过管理员密码验证
            if TEST_MODE:
                logger.info("🧪 测试模式：跳过管理员密码验证，直接退出")
                if self.session_active:
                    logger.info("测试模式：强制结束活动会话...")
                    self.session_active = False
                    if hasattr(self, 'session_timer'):
                        self.session_timer.stop()
                
                # 简单清理并强制退出
                self._force_exit()
                event.accept()
                return
            
            # 检查是否是更新退出（跳过管理员密码验证）
            if hasattr(self, '_updating') and self._updating:
                logger.info("检测到更新退出，跳过管理员密码验证")
                if self.session_active:
                    logger.info("更新时强制结束活动会话...")
                    self.session_active = False
                    if hasattr(self, 'session_timer'):
                        self.session_timer.stop()
                
                # 简单清理并强制退出
                self._force_exit()
                event.accept()
                return
            
            # 正常退出时验证管理员密码
            logger.info("正常退出，验证管理员密码")
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
            
            # 取消所有任务管理器中的任务（使用同步方法）
            try:
                logger.info("取消所有任务...")
                self.task_manager.cancel_all_tasks_sync()
            except Exception as e:
                logger.error(f"取消任务时出错: {e}")
            
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
            
            # 清理自动更新器
            if hasattr(self, 'auto_updater') and self.auto_updater:
                try:
                    logger.info("清理自动更新器...")
                    asyncio.create_task(self.auto_updater.close())
                except Exception as e:
                    logger.error(f"清理自动更新器时出错: {e}")
            
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

    def _is_ready_for_auto_updater(self):
        """快速检查是否准备好初始化自动更新器"""
        try:
            # 检查窗口状态
            if not self.isVisible():
                return False, "窗口未显示"
            
            # 检查事件循环
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if not loop or not loop.is_running():
                    return False, "事件循环未运行"
            except:
                return False, "无法获取事件循环"
            
            return True, "准备就绪"
        except Exception as e:
            return False, f"检查失败: {e}"

    def _init_auto_updater(self):
        """延迟初始化自动更新器"""
        try:
            self._auto_updater_init_attempts += 1
            logger.info(f"🔄 初始化自动更新器 (尝试 {self._auto_updater_init_attempts}/3)...")
            
            # 减少重试次数，避免过度延迟
            if self._auto_updater_init_attempts > 3:
                logger.error("❌ 自动更新器初始化重试次数超限，放弃初始化")
                self.auto_updater = None
                return
            
            # 快速检查是否准备就绪
            ready, reason = self._is_ready_for_auto_updater()
            if not ready:
                logger.warning(f"⚠️ 尚未准备就绪: {reason}，延迟重试")
                # 根据原因调整延迟时间
                delay = 1000 if "窗口" in reason else 1500
                QTimer.singleShot(delay, self._init_auto_updater)
                return
            
            logger.info("🚀 创建自动更新器...")
            from logic.auto_updater import get_updater
            self.auto_updater = get_updater(self)
            
            # get_updater会自动处理信号连接，但我们再确认一次
            try:
                # 先断开可能存在的连接
                self.auto_updater.update_available.disconnect(self.on_update_available)
                self.auto_updater.update_check_failed.disconnect(self.on_update_check_failed)
                self.auto_updater.no_update_available.disconnect(self.on_no_update_available)
            except:
                pass  # 如果没有连接则忽略
            
            # 重新连接信号
            self.auto_updater.update_available.connect(self.on_update_available)
            self.auto_updater.update_check_failed.connect(self.on_update_check_failed)
            self.auto_updater.no_update_available.connect(self.on_no_update_available)
            self._auto_updater_ready = True
            logger.info("✅ 自动更新器初始化完成，信号已连接")
            
            # 立即开始启动检查，不再延迟
            logger.info("🚀 立即开始启动更新检查")
            self.startup_update_check()
            
        except Exception as e:
            logger.error(f"❌ 自动更新器初始化失败: {e}")
            self.auto_updater = None
            
            # 减少重试延迟
            if self._auto_updater_init_attempts < 3:
                logger.info(f"⏰ 将在1.5秒后重试初始化...")
                QTimer.singleShot(1500, self._init_auto_updater)

    def delayed_start_monitoring(self) -> None:
        """延迟启动窗口监控器"""
        self._safe_start_monitoring()

    def timer_done(self) -> None:
        """计时器结束回调"""
        if self.session_active:
            logger.info("计时器结束，自动结束会话")
            self.run_async(self.end_session())

    def _safe_start_monitoring(self):
        """安全地启动监控"""
        run_task_safe(
            self.window_monitor.start_monitoring(),
            task_id="start_monitoring",
            delay_ms=10
        )
    
    def _safe_stop_monitoring(self):
        """安全地停止监控"""
        run_task_safe(
            self.window_monitor.stop_monitoring(),
            task_id="stop_monitoring", 
            delay_ms=10
        )
    
    def _disable_all_controls(self):
        """禁用所有UI控件"""
        try:
            # 禁用主要按钮
            if hasattr(self, 'start_button'):
                self.start_button.setEnabled(False)
            
            if hasattr(self, 'stop_button'):
                self.stop_button.setEnabled(False)
            
            if hasattr(self, 'math_button'):
                self.math_button.setEnabled(False)
            
            if hasattr(self, 'history_button'):
                self.history_button.setEnabled(False)
            
            if hasattr(self, 'admin_button'):
                self.admin_button.setEnabled(False)
            
            if hasattr(self, 'update_button'):
                self.update_button.setEnabled(False)
            
            # 禁用输入框
            if hasattr(self, 'duration_entry'):
                self.duration_entry.setEnabled(False)
            
        except Exception as e:
            logger.error(f"禁用UI控件时出错: {e}")
