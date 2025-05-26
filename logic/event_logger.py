#!/usr/bin/env python3
"""
事件日志系统

专门用于记录GameTimeLimiter应用程序的重要事件，包括：
- 监控的启动和关闭
- 检测到的禁止进程或Chrome标签页
- 会话的启动和结束
- 题目的回答
- 系统状态变化
"""

import logging
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path


class EventLogger:
    """事件日志记录器"""
    
    def __init__(self, log_file: str = "game_events.log"):
        """
        初始化事件日志记录器
        
        Args:
            log_file: 日志文件路径
        """
        self.log_file = Path(log_file)
        
        # 创建专门的事件日志记录器
        self.logger = logging.getLogger('GameEvents')
        self.logger.setLevel(logging.INFO)
        
        # 避免重复添加处理器
        if not self.logger.handlers:
            # 文件处理器 - 记录所有事件到文件
            file_handler = logging.FileHandler(
                self.log_file, 
                encoding='utf-8',
                mode='a'
            )
            file_handler.setLevel(logging.INFO)
            
            # 控制台处理器 - 只显示重要事件
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.WARNING)
            
            # 设置格式
            formatter = logging.Formatter(
                '%(asctime)s - [EVENT] - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)
            
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)
            
            # 防止消息传播到父logger，避免重复输出
            self.logger.propagate = False
        
        # 记录日志系统启动
        self.log_system_event("事件日志系统已启动")
    
    def _format_event(self, event_type: str, message: str, details: Optional[Dict[str, Any]] = None) -> str:
        """
        格式化事件消息
        
        Args:
            event_type: 事件类型
            message: 事件消息
            details: 事件详细信息
            
        Returns:
            格式化后的事件消息
        """
        event_data = {
            "type": event_type,
            "message": message,
            "timestamp": datetime.now().isoformat(),
        }
        
        if details:
            event_data["details"] = details
            
        return f"[{event_type}] {message}" + (f" | 详情: {json.dumps(details, ensure_ascii=False)}" if details else "")
    
    # 监控相关事件
    def log_monitor_started(self, check_interval: int = 15):
        """记录监控启动事件"""
        message = f"窗口监控已启动，检查间隔: {check_interval}秒"
        details = {"check_interval": check_interval}
        self.logger.info(self._format_event("MONITOR_START", message, details))
    
    def log_monitor_stopped(self, reason: str = "手动停止"):
        """记录监控停止事件"""
        message = f"窗口监控已停止，原因: {reason}"
        details = {"reason": reason}
        self.logger.info(self._format_event("MONITOR_STOP", message, details))
    
    def log_restricted_app_detected(self, app_name: str, app_type: str, details: Optional[Dict[str, Any]] = None):
        """记录检测到禁止应用事件"""
        message = f"检测到禁止应用: {app_name} (类型: {app_type})"
        event_details = {
            "app_name": app_name,
            "app_type": app_type,
            "detection_time": datetime.now().isoformat()
        }
        if details:
            event_details.update(details)
        
        self.logger.warning(self._format_event("RESTRICTED_APP", message, event_details))
    
    def log_process_terminated(self, process_name: str, pid: Optional[int] = None):
        """记录进程终止事件"""
        message = f"已终止禁止进程: {process_name}"
        details = {"process_name": process_name}
        if pid:
            details["pid"] = pid
            message += f" (PID: {pid})"
        
        self.logger.warning(self._format_event("PROCESS_KILL", message, details))
    
    def log_screen_locked(self, reason: str = "检测到禁止应用"):
        """记录屏幕锁定事件"""
        message = f"屏幕已锁定，原因: {reason}"
        details = {"reason": reason}
        self.logger.warning(self._format_event("SCREEN_LOCK", message, details))
    
    # 会话相关事件
    def log_session_started(self, duration_hours: float, session_type: str = "游戏会话"):
        """记录会话启动事件"""
        message = f"{session_type}已启动，时长: {duration_hours}小时"
        details = {
            "duration_hours": duration_hours,
            "session_type": session_type,
            "start_time": datetime.now().isoformat()
        }
        self.logger.info(self._format_event("SESSION_START", message, details))
    
    def log_session_ended(self, actual_duration: Optional[float] = None, reason: str = "正常结束"):
        """记录会话结束事件"""
        message = f"会话已结束，原因: {reason}"
        details = {"reason": reason}
        if actual_duration is not None:
            details["actual_duration_hours"] = actual_duration
            message += f"，实际时长: {actual_duration:.2f}小时"
        
        self.logger.info(self._format_event("SESSION_END", message, details))
    
    def log_session_extended(self, additional_hours: float, total_hours: float):
        """记录会话延长事件"""
        message = f"会话已延长 {additional_hours}小时，总时长: {total_hours}小时"
        details = {
            "additional_hours": additional_hours,
            "total_hours": total_hours
        }
        self.logger.info(self._format_event("SESSION_EXTEND", message, details))
    
    # 题目回答相关事件
    def log_question_presented(self, question_type: str, question_text: str, difficulty: Optional[str] = None):
        """记录题目展示事件"""
        message = f"展示{question_type}题目"
        details = {
            "question_type": question_type,
            "question_text": question_text,
            "presentation_time": datetime.now().isoformat()
        }
        if difficulty:
            details["difficulty"] = difficulty
            message += f" (难度: {difficulty})"
        
        self.logger.info(self._format_event("QUESTION_SHOW", message, details))
    
    def log_question_answered(self, question_type: str, user_answer: str, correct_answer: str, 
                            is_correct: bool, attempt_count: int = 1):
        """记录题目回答事件"""
        result = "正确" if is_correct else "错误"
        message = f"{question_type}题目回答{result}"
        details = {
            "question_type": question_type,
            "user_answer": user_answer,
            "correct_answer": correct_answer,
            "is_correct": is_correct,
            "attempt_count": attempt_count,
            "answer_time": datetime.now().isoformat()
        }
        
        if is_correct:
            self.logger.info(self._format_event("QUESTION_CORRECT", message, details))
        else:
            self.logger.warning(self._format_event("QUESTION_WRONG", message, details))
    
    def log_question_timeout(self, question_type: str, timeout_seconds: int):
        """记录题目超时事件"""
        message = f"{question_type}题目回答超时 ({timeout_seconds}秒)"
        details = {
            "question_type": question_type,
            "timeout_seconds": timeout_seconds
        }
        self.logger.warning(self._format_event("QUESTION_TIMEOUT", message, details))
    
    # 系统状态事件
    def log_admin_panel_opened(self, user_type: str = "管理员"):
        """记录管理面板打开事件"""
        message = f"{user_type}打开了管理面板"
        details = {"user_type": user_type}
        self.logger.info(self._format_event("ADMIN_OPEN", message, details))
    
    def log_admin_panel_closed(self, user_type: str = "管理员"):
        """记录管理面板关闭事件"""
        message = f"{user_type}关闭了管理面板"
        details = {"user_type": user_type}
        self.logger.info(self._format_event("ADMIN_CLOSE", message, details))
    
    def log_settings_changed(self, setting_name: str, old_value: Any, new_value: Any):
        """记录设置更改事件"""
        message = f"设置已更改: {setting_name}"
        details = {
            "setting_name": setting_name,
            "old_value": str(old_value),
            "new_value": str(new_value)
        }
        self.logger.info(self._format_event("SETTINGS_CHANGE", message, details))
    
    def log_system_event(self, message: str, details: Optional[Dict[str, Any]] = None):
        """记录系统事件"""
        self.logger.info(self._format_event("SYSTEM", message, details))
    
    def log_error_event(self, error_message: str, error_type: str = "UNKNOWN", details: Optional[Dict[str, Any]] = None):
        """记录错误事件"""
        message = f"系统错误: {error_message}"
        event_details = {"error_type": error_type}
        if details:
            event_details.update(details)
        
        self.logger.error(self._format_event("ERROR", message, event_details))
    
    # 应用生命周期事件
    def log_app_started(self):
        """记录应用启动事件"""
        message = "GameTimeLimiter应用程序已启动"
        details = {"start_time": datetime.now().isoformat()}
        self.logger.info(self._format_event("APP_START", message, details))
    
    def log_app_shutdown(self, reason: str = "正常退出"):
        """记录应用关闭事件"""
        message = f"GameTimeLimiter应用程序正在关闭，原因: {reason}"
        details = {
            "reason": reason,
            "shutdown_time": datetime.now().isoformat()
        }
        self.logger.info(self._format_event("APP_SHUTDOWN", message, details))
    
    def migrate_traditional_log(self, level: str, message: str, category: str = "LEGACY", details: Optional[Dict[str, Any]] = None):
        """
        迁移传统日志到事件日志系统
        
        Args:
            level: 日志级别 (INFO, WARNING, ERROR)
            message: 日志消息
            category: 事件类别
            details: 额外详细信息
        """
        event_type = f"LEGACY_{category.upper()}"
        
        if level.upper() == "ERROR":
            self.logger.error(self._format_event(event_type, message, details))
        elif level.upper() == "WARNING":
            self.logger.warning(self._format_event(event_type, message, details))
        else:
            self.logger.info(self._format_event(event_type, message, details))
    
    def close(self):
        """关闭事件日志记录器"""
        self.log_system_event("事件日志系统正在关闭")
        
        # 关闭所有处理器
        for handler in self.logger.handlers[:]:
            handler.close()
            self.logger.removeHandler(handler)


# 全局事件日志记录器实例
_event_logger = None

def get_event_logger() -> EventLogger:
    """获取全局事件日志记录器实例"""
    global _event_logger
    if _event_logger is None:
        _event_logger = EventLogger()
    return _event_logger

def close_event_logger():
    """关闭全局事件日志记录器"""
    global _event_logger
    if _event_logger is not None:
        _event_logger.close()
        _event_logger = None 