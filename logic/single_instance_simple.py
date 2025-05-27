#!/usr/bin/env python3
"""
简单可靠的单实例管理模块
使用TCP端口绑定方式，跨平台兼容，无需复杂的进程检查
"""

import socket
import hashlib
import logging
import sys
import os

logger = logging.getLogger(__name__)

class SimpleSingleInstance:
    """简单的单实例管理器 - 基于TCP端口绑定"""
    
    def __init__(self, app_name="GameControl"):
        """
        初始化单实例管理器
        
        Args:
            app_name: 应用程序名称
        """
        self.app_name = app_name
        self.socket = None
        self.port = self._generate_port()
        
    def _generate_port(self):
        """根据应用名称和脚本路径生成固定端口"""
        # 使用应用名称和脚本绝对路径生成唯一标识
        script_path = os.path.abspath(sys.argv[0])
        unique_id = f"{self.app_name}:{script_path}"
        
        # 生成哈希值并转换为端口号
        hash_value = hashlib.md5(unique_id.encode()).hexdigest()
        # 使用哈希值的前4位，映射到50000-59999端口范围
        port_offset = int(hash_value[:4], 16) % 10000
        port = 50000 + port_offset
        
        logger.debug(f"应用标识: {unique_id}")
        logger.debug(f"生成端口: {port}")
        return port
    
    def acquire_lock(self):
        """
        获取单实例锁
        
        Returns:
            bool: 成功获取锁返回True，否则返回False
        """
        try:
            # 创建TCP socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            
            # 不设置SO_REUSEADDR，确保端口独占
            # self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # 尝试绑定端口
            self.socket.bind(('127.0.0.1', self.port))
            self.socket.listen(1)
            
            logger.info(f"成功获取单实例锁，端口: {self.port}")
            return True
            
        except socket.error as e:
            logger.warning(f"端口 {self.port} 已被占用，检测到其他实例正在运行: {e}")
            self._cleanup()
            return False
        except Exception as e:
            logger.error(f"获取单实例锁失败: {e}")
            self._cleanup()
            return False
    
    def release_lock(self):
        """释放单实例锁"""
        self._cleanup()
        logger.info("已释放单实例锁")
    
    def _cleanup(self):
        """清理资源"""
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
    
    def __enter__(self):
        """上下文管理器入口"""
        if self.acquire_lock():
            return self
        else:
            raise RuntimeError("无法获取单实例锁，可能已有其他实例在运行")
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.release_lock()

def check_single_instance_simple(app_name="GameControl"):
    """
    简单的单实例检查函数
    
    Args:
        app_name: 应用程序名称
        
    Returns:
        SimpleSingleInstance: 单实例管理器对象，如果获取锁失败则返回None
    """
    instance_manager = SimpleSingleInstance(app_name)
    if instance_manager.acquire_lock():
        return instance_manager
    else:
        return None

def show_already_running_message():
    """显示程序已在运行的消息"""
    try:
        from PyQt6.QtWidgets import QApplication, QMessageBox
        from PyQt6.QtCore import Qt
        
        # 创建临时应用程序实例（如果还没有）
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 显示消息框
        msg_box = QMessageBox()
        msg_box.setWindowTitle("GameControl")
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setText("程序已在运行")
        msg_box.setInformativeText(
            "GameControl 已有一个实例在运行。\n\n"
            "为了确保数据安全和程序稳定性，不允许同时运行多个副本。\n\n"
            "请检查系统托盘或任务管理器中是否已有程序在运行。"
        )
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.setDefaultButton(QMessageBox.StandardButton.Ok)
        
        # 设置窗口置顶
        msg_box.setWindowFlags(msg_box.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        
        msg_box.exec()
        
    except ImportError:
        # 如果PyQt6不可用，使用控制台输出
        print("=" * 50)
        print("GameControl - 程序已在运行")
        print("=" * 50)
        print("检测到 GameControl 已有一个实例在运行。")
        print("为了确保数据安全和程序稳定性，不允许同时运行多个副本。")
        print("请检查系统托盘或任务管理器中是否已有程序在运行。")
        print("=" * 50)
        input("按回车键退出...")
    except Exception as e:
        logger.error(f"显示已运行消息时出错: {e}")
        print(f"程序已在运行。错误: {e}")

# 测试函数
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    print("测试简单单实例检查...")
    
    # 第一次获取锁
    instance1 = check_single_instance_simple("TestApp")
    if instance1:
        print("✅ 第一个实例成功获取锁")
        
        # 尝试第二次获取锁（应该失败）
        instance2 = check_single_instance_simple("TestApp")
        if instance2:
            print("❌ 第二个实例不应该获取到锁")
            instance2.release_lock()
        else:
            print("✅ 第二个实例正确被阻止")
        
        # 释放第一个锁
        instance1.release_lock()
        print("✅ 第一个实例释放锁")
        
        # 再次尝试获取锁（应该成功）
        instance3 = check_single_instance_simple("TestApp")
        if instance3:
            print("✅ 释放后重新获取锁成功")
            instance3.release_lock()
        else:
            print("❌ 释放后重新获取锁失败")
    else:
        print("❌ 第一个实例获取锁失败")
    
    print("测试完成") 