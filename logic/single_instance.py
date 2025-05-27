#!/usr/bin/env python3
"""
单实例管理模块 - 防止程序同时启动多个副本
这是一个向后兼容的包装器，实际使用简单可靠的TCP端口绑定方式
"""

# 导入简单可靠的实现
from .single_instance_simple import (
    SimpleSingleInstance,
    check_single_instance_simple,
    show_already_running_message
)

# 向后兼容的别名
SingleInstance = SimpleSingleInstance

def check_single_instance(app_name="GameControl"):
    """
    向后兼容的单实例检查函数
    
    Args:
        app_name: 应用程序名称
        
    Returns:
        SimpleSingleInstance: 单实例管理器对象，如果获取锁失败则返回None
    """
    return check_single_instance_simple(app_name) 