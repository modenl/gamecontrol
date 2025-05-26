import asyncio
import datetime
from PyQt6.QtWidgets import (
    QDialog, QLabel, QVBoxLayout, QHBoxLayout, QWidget, QApplication, QFrame
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QPoint
from PyQt6.QtGui import QFont

from logic.constants import (
    THEME_DARK
)

class ToolTip(QWidget):
    """工具提示框"""
    def __init__(self, parent, text, delay=500, wrap_length=200):
        super().__init__(parent, Qt.WindowType.ToolTip)
        self.parent = parent
        self.text = text
        self.delay = delay
        self.wrap_length = wrap_length
        
        # 设置布局
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(8, 8, 8, 8)
        
        # 文本标签
        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setMaximumWidth(wrap_length)
        self.label.setStyleSheet("""
            background-color: #343a40;
            color: #ffffff;
            border-radius: 4px;
            padding: 4px;
        """)
        
        self.layout.addWidget(self.label)
        self.setLayout(self.layout)
        
        # 定时器
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.show_tip)
        
        # 事件过滤器
        parent.installEventFilter(self)
        
    def eventFilter(self, obj, event):
        """事件过滤器，处理鼠标事件"""
        try:
            if obj == self.parent:
                event_type = event.type()
                if event_type == event.Type.Enter:
                    self.timer.start(self.delay)
                elif event_type in (event.Type.Leave, event.Type.MouseButtonPress):
                    self.timer.stop()
                    self.hide()
            return super().eventFilter(obj, event)
        except Exception as e:
            # 如果事件处理出错，返回False让事件继续传播
            return False
        
    def show_tip(self):
        """显示提示框"""
        pos = self.parent.mapToGlobal(QPoint(self.parent.width(), 0))
        self.move(pos.x() + 10, pos.y() + 20)
        self.show()

class StatusBar(QWidget):
    """状态栏"""
    
    # 信号定义
    update_notification_clicked = pyqtSignal(object)  # 更新通知被点击
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 设置状态栏的固定高度，像普通程序一样小
        self.setFixedHeight(20)  # 更紧凑的状态栏高度
        
        # 设置状态栏样式，模仿Windows标准状态栏
        self.setStyleSheet("""
            StatusBar {
                background-color: #f0f0f0;
                border-top: 1px solid #d0d0d0;
                font-size: 11px;
            }
        """)
        
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(6, 1, 6, 1)  # 更紧凑的边距
        self.layout.setSpacing(8)  # 更紧凑的元素间距
        
        # 消息标签（左侧）
        self.label = QLabel("")
        self.label.setStyleSheet("""
            QLabel {
                color: #333333;
                font-size: 11px;
                background: transparent;
                border: none;
            }
        """)
        self.layout.addWidget(self.label)
        
        # 弹性空间
        self.layout.addStretch()
        
        # 更新通知标签（中间）
        self.update_label = QLabel("")
        self.update_label.setStyleSheet("""
            QLabel {
                color: #0066cc;
                background-color: #e6f2ff;
                border: 1px solid #b3d9ff;
                border-radius: 2px;
                padding: 1px 5px;
                font-weight: normal;
                font-size: 10px;
                max-height: 14px;
                min-height: 14px;
            }
            QLabel:hover {
                background-color: #cce6ff;
                border-color: #0066cc;
                cursor: pointer;
            }
        """)
        self.update_label.hide()  # 初始隐藏
        self.update_label.mousePressEvent = self._on_update_label_clicked
        self.layout.addWidget(self.update_label)
        
        # 弹性空间
        self.layout.addStretch()
        
        # 版本标签（右侧）
        try:
            from version import __version__
            version_text = f"v{__version__}"
        except ImportError:
            version_text = "v?.?.?"
        
        self.version_label = QLabel(version_text)
        self.version_label.setStyleSheet("""
            QLabel {
                color: #888888; 
                font-size: 10px;
                background: transparent;
                border: none;
            }
        """)
        self.layout.addWidget(self.version_label)
        
        self.setLayout(self.layout)
        self.message_timer = QTimer(self)
        self.message_timer.timeout.connect(self.clear_message)
        
        # 存储更新信息
        self.update_info = None
        
    def show_message(self, message, duration=3000):
        """显示临时消息"""
        self.label.setText(message)
        
        # 取消之前的计时器
        if self.message_timer.isActive():
            self.message_timer.stop()
            
        # 设置新的计时器
        self.message_timer.start(duration)
        
    def clear_message(self):
        """清除消息"""
        self.label.setText("")
        self.message_timer.stop()
    
    def show_update_notification(self, update_info):
        """显示更新通知"""
        self.update_info = update_info
        self.update_label.setText(f"🔄 New version {update_info.version} available - Click to update")
        self.update_label.setVisible(True)
        self.update_label.show()
    
    def hide_update_notification(self):
        """隐藏更新通知"""
        self.update_info = None
        self.update_label.setVisible(False)
        self.update_label.hide()
    
    def _on_update_label_clicked(self, event):
        """更新标签被点击"""
        if self.update_info:
            self.update_notification_clicked.emit(self.update_info)

class OverlayWindow(QDialog):
    """覆盖窗口，用于倒计时显示"""
    def __init__(self, parent=None, width=300, height=150, corner=None, 
                 bg_color="#333333", fg_color="#ffffff", alpha=0.85):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(width, height)
        
        # 设置窗口位置
        screen_geo = QApplication.primaryScreen().geometry()
        if corner == "top-right":
            self.move(screen_geo.width() - width - 20, 20)
        elif corner == "bottom-right":
            self.move(screen_geo.width() - width - 20, screen_geo.height() - height - 20)
        elif corner == "top-left":
            self.move(20, 20)
        elif corner == "bottom-left":
            self.move(20, screen_geo.height() - height - 20)
        else:
            # 居中
            self.move((screen_geo.width() - width) // 2, (screen_geo.height() - height) // 2)
        
        # 设置样式
        self.setStyleSheet(f"""
            background-color: rgba({int(bg_color[1:3], 16)}, 
                                   {int(bg_color[3:5], 16)}, 
                                   {int(bg_color[5:7], 16)}, 
                                   {alpha});
            color: {fg_color};
            border-radius: 10px;
        """)
        
        # 创建布局
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题标签
        self.title_label = QLabel("")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        
        # 消息标签
        self.message_label = QLabel("")
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setWordWrap(True)
        message_font = QFont()
        message_font.setPointSize(24)
        message_font.setBold(True)
        self.message_label.setFont(message_font)
        
        self.layout.addWidget(self.title_label)
        self.layout.addWidget(self.message_label)
        
        # 计时器和回调
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.close_window)
        self.callback = None
    
    def show_message(self, title, message, duration=None, callback=None):
        """显示消息"""
        self.title_label.setText(title)
        self.message_label.setText(message)
        self.callback = callback
        
        # 如果设置了持续时间，设置计时器
        if duration:
            self.timer.start(duration)
            
        self.show()
    
    def update_message(self, message):
        """更新消息内容"""
        self.message_label.setText(message)
    
    def close_window(self):
        """关闭窗口"""
        self.timer.stop()
        self.hide()
        if self.callback:
            self.callback()
                
class SessionTimer(QWidget):
    """带回调的Session计时器"""
    # 定义信号
    timer_done_signal = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.is_running = False
        self.start_time = 0
        self.duration = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_timer)
        
        # 创建UI
        self.layout = QVBoxLayout(self)
        
        # 计时器标签
        self.timer_label = QLabel("00:00")
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(20)
        font.setBold(True)
        self.timer_label.setFont(font)
        
        self.layout.addWidget(self.timer_label)
        self.setLayout(self.layout)
        
        # 最后一分钟倒计时窗口
        self.countdown_window = None
        self.final_minute_shown = False
        
    def start(self, duration_minutes):
        """开始计时"""
        if self.is_running:
            return
            
        self.start_time = datetime.datetime.now()
        # 支持小数分钟，转换为秒
        self.duration = float(duration_minutes) * 60  # 转换为秒
        self.is_running = True
        self.final_minute_shown = False
        self.timer.start(1000)  # 每秒更新一次
        self.update_timer()
        
    def stop(self):
        """停止计时"""
        if not self.is_running:
            return
            
        self.is_running = False
        self.timer.stop()
        
        # 关闭倒计时窗口
        if self.countdown_window:
            self.countdown_window.hide()
            self.countdown_window = None
        
    def update_timer(self):
        """更新计时器显示"""
        if not self.is_running:
            return
            
        elapsed = (datetime.datetime.now() - self.start_time).total_seconds()
        remaining = max(0, self.duration - elapsed)
        
        # 更改为分钟:秒格式，不显示小时
        minutes, seconds = divmod(int(remaining), 60)
        
        self.timer_label.setText(f"{minutes:02d}:{seconds:02d}")
        
        # 最后一分钟显示倒计时窗口
        if remaining <= 60 and remaining > 0 and not self.final_minute_shown:
            self.show_final_minute_countdown()
            self.final_minute_shown = True
        
        # 如果倒计时窗口存在，更新倒计时
        if self.countdown_window and self.countdown_window.isVisible():
            if remaining <= 60:
                self.countdown_window.update_message(f"{int(remaining)}秒")
            else:
                self.countdown_window.hide()
        
        if remaining <= 0:
            self.is_running = False
            self.timer.stop()
            
            # 关闭倒计时窗口
            if self.countdown_window:
                self.countdown_window.hide()
                self.countdown_window = None
                
            self.timer_done_signal.emit()
            
    def show_final_minute_countdown(self):
        """显示最后一分钟倒计时"""
        if not self.countdown_window:
            # 创建半透明倒计时窗口，放在屏幕右上角
            self.countdown_window = OverlayWindow(
                self.parent, 
                width=250, 
                height=150, 
                corner="top-right",
                alpha=0.7  # 设置为半透明
            )
        
        self.countdown_window.show_message("Session即将结束", "60秒")
        
class ShakeEffect:
    """控件抖动效果"""
    @staticmethod
    async def shake(widget, offset=10, duration=50, cycles=5):
        """使控件抖动
        
        Args:
            widget: 要抖动的控件
            offset: 最大抖动偏移量（像素）
            duration: 每次移动的持续时间（毫秒）
            cycles: 抖动周期数
        """
        orig_pos = widget.pos()
        
        for i in range(cycles):
            # 左右移动
            animation = QPropertyAnimation(widget, b"pos")
            animation.setDuration(duration)
            animation.setStartValue(QPoint(orig_pos.x() - offset, orig_pos.y()))
            animation.setEndValue(QPoint(orig_pos.x() + offset, orig_pos.y()))
            animation.start()
            await asyncio.sleep(duration / 1000)
            
            # 回到中间
            animation = QPropertyAnimation(widget, b"pos")
            animation.setDuration(duration)
            animation.setStartValue(QPoint(orig_pos.x() + offset, orig_pos.y()))
            animation.setEndValue(orig_pos)
            animation.start()
            await asyncio.sleep(duration / 1000)
        
        # 确保回到原位
        widget.move(orig_pos)

def apply_dark_style(app):
    """应用深色主题样式"""
    app.setStyle("Fusion")
    app.setStyleSheet("""
        QMainWindow, QDialog {
            background-color: #2d2d2d;
            color: #ffffff;
        }
        QWidget {
            background-color: #2d2d2d;
            color: #ffffff;
        }
        QLabel {
            color: #ffffff;
        }
        QPushButton {
            background-color: #0d6efd;
            color: #ffffff;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            min-height: 30px;
        }
        QPushButton:hover {
            background-color: #0b5ed7;
        }
        QPushButton:pressed {
            background-color: #0a58ca;
        }
        QPushButton:disabled {
            background-color: #6c757d;
        }
        QLineEdit, QTextEdit, QPlainTextEdit {
            background-color: #3d3d3d;
            color: #ffffff;
            border: 1px solid #6c757d;
            border-radius: 4px;
            padding: 4px;
        }
        QComboBox {
            background-color: #3d3d3d;
            color: #ffffff;
            border: 1px solid #6c757d;
            border-radius: 4px;
            padding: 4px;
        }
        QTabWidget::pane {
            border: 1px solid #6c757d;
            background-color: #2d2d2d;
        }
        QTabBar::tab {
            background-color: #3d3d3d;
            color: #ffffff;
            padding: 8px 16px;
            margin-right: 2px;
        }
        QTabBar::tab:selected {
            background-color: #0d6efd;
        }
        QProgressBar {
            border: 1px solid #6c757d;
            border-radius: 4px;
            background-color: #3d3d3d;
            text-align: center;
            color: #ffffff;
        }
        QProgressBar::chunk {
            background-color: #0d6efd;
            width: 10px;
        }
        QTableView, QTreeView, QListView {
            background-color: #3d3d3d;
            color: #ffffff;
            border: 1px solid #6c757d;
            border-radius: 4px;
        }
        QHeaderView::section {
            background-color: #4d4d4d;
            color: #ffffff;
            padding: 4px;
            border: 1px solid #6c757d;
        }
    """) 