#!/usr/bin/env python3
"""
统一日志系统

提供一个包装器，逐步将传统日志迁移到事件日志系统。
对于重要的业务逻辑事件，使用事件日志系统；
对于调试和技术细节，保留传统日志。
"""

import logging
from typing import Dict, Any, Optional
from logic.event_logger import get_event_logger


class UnifiedLogger:
    """统一日志记录器，结合传统日志和事件日志"""
    
    def __init__(self, name: str):
        """
        初始化统一日志记录器
        
        Args:
            name: 日志记录器名称
        """
        self.traditional_logger = logging.getLogger(name)
        self.event_logger = get_event_logger()
        self.name = name
    
    # 会话相关日志
    def log_session_start(self, game_name: str, duration_minutes: int):
        """记录会话启动"""
        message = f"开始游戏Session: {game_name}, 时长: {duration_minutes}分钟"
        self.traditional_logger.info(message)
        self.event_logger.log_session_started(
            duration_hours=duration_minutes / 60.0,
            session_type=f"{game_name}游戏会话"
        )
    
    def log_session_end(self, game_name: str, actual_duration_minutes: int, note: Optional[str] = None):
        """记录会话结束"""
        message = f"结束游戏Session: {game_name}, 实际时长: {actual_duration_minutes}分钟"
        if note:
            message += f", 备注: {note}"
        self.traditional_logger.info(message)
        self.event_logger.log_session_ended(
            actual_duration=actual_duration_minutes / 60.0,
            reason=note if note else "正常结束"
        )
    
    def log_session_error(self, operation: str, error: str):
        """记录会话相关错误"""
        message = f"{operation}时出错: {error}"
        self.traditional_logger.error(message)
        self.event_logger.log_error_event(message, f"SESSION_{operation.upper()}_ERROR")
    
    # 监控相关日志
    def log_monitor_start(self, check_interval: int):
        """记录监控启动"""
        message = f"开始监控活动窗口，检查间隔: {check_interval}秒"
        self.traditional_logger.info(message)
        self.event_logger.log_monitor_started(check_interval)
    
    def log_monitor_stop(self, reason: str = "手动停止"):
        """记录监控停止"""
        message = f"正在停止窗口监控，原因: {reason}"
        self.traditional_logger.info(message)
        self.event_logger.log_monitor_stopped(reason)
    
    def log_monitor_error(self, error: str):
        """记录监控错误"""
        message = f"监控过程中出错: {error}"
        self.traditional_logger.error(message)
        self.event_logger.log_error_event(message, "MONITOR_ERROR")
    
    def log_restricted_app_detected(self, app_name: str, app_type: str, details: Optional[Dict[str, Any]] = None):
        """记录检测到禁止应用"""
        message = f"检测到未授权使用游戏: {app_name}"
        self.traditional_logger.warning(message)
        self.event_logger.log_restricted_app_detected(app_name, app_type, details)
    
    # 题目相关日志
    def log_question_load(self, count: int, source: str = "数据库"):
        """记录题目加载"""
        message = f"从{source}加载题目，共{count}道"
        self.traditional_logger.info(message)
        # 对于题目加载，使用系统事件记录
        self.event_logger.log_system_event(message, {"count": count, "source": source})
    
    def log_question_answer_check(self, question_index: int, user_answer: str, is_correct: bool):
        """记录题目答案检查"""
        result = "正确" if is_correct else "错误"
        message = f"题目 {question_index} 答案检查完成: {result}"
        self.traditional_logger.info(message)
        # 具体的答案记录由MathExercises模块直接调用event_logger处理
    
    def log_question_error(self, operation: str, error: str):
        """记录题目相关错误"""
        message = f"{operation}时出错: {error}"
        self.traditional_logger.error(message)
        self.event_logger.log_error_event(message, f"QUESTION_{operation.upper()}_ERROR")
    
    # 管理面板相关日志
    def log_admin_panel_open(self):
        """记录管理面板打开"""
        message = "打开管理面板"
        self.traditional_logger.info(message)
        self.event_logger.log_admin_panel_opened("管理员")
    
    def log_admin_panel_close(self):
        """记录管理面板关闭"""
        message = "管理员面板已关闭"
        self.traditional_logger.info(message)
        self.event_logger.log_admin_panel_closed("管理员")
    
    # 传统日志方法（保持兼容性）
    def info(self, message: str, use_event_log: bool = False, event_category: str = "INFO"):
        """记录信息日志"""
        self.traditional_logger.info(message)
        if use_event_log:
            self.event_logger.log_system_event(message)
    
    def warning(self, message: str, use_event_log: bool = False, event_category: str = "WARNING"):
        """记录警告日志"""
        self.traditional_logger.warning(message)
        if use_event_log:
            self.event_logger.migrate_traditional_log("WARNING", message, event_category)
    
    def error(self, message: str, use_event_log: bool = True, event_category: str = "ERROR"):
        """记录错误日志"""
        self.traditional_logger.error(message)
        if use_event_log:
            self.event_logger.log_error_event(message, f"LEGACY_{event_category}")
    
    def debug(self, message: str):
        """记录调试日志（不使用事件日志）"""
        self.traditional_logger.debug(message)


# 全局统一日志记录器缓存
_unified_loggers = {}

def get_unified_logger(name: str) -> UnifiedLogger:
    """获取统一日志记录器实例"""
    if name not in _unified_loggers:
        _unified_loggers[name] = UnifiedLogger(name)
    return _unified_loggers[name] 