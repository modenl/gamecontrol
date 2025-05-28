#!/usr/bin/env python3
"""
简化的单实例检查实现
使用TCP端口绑定方式，简单可靠
"""

import socket
import hashlib
import os
import sys
import time
import logging

logger = logging.getLogger(__name__)

class SingleInstanceChecker:
    """简化的单实例检查器"""
    
    def __init__(self, app_name="GameTimeLimiter"):
        self.app_name = app_name
        self.port = self._generate_port()
        self.socket = None
        
    def _generate_port(self):
        """基于应用名称和脚本路径生成唯一端口"""
        # 获取脚本的绝对路径
        script_path = os.path.abspath(sys.argv[0])
        
        # 组合应用名称和脚本路径
        unique_string = f"{self.app_name}_{script_path}"
        
        # 生成哈希
        hash_object = hashlib.md5(unique_string.encode())
        hash_hex = hash_object.hexdigest()
        
        # 转换为端口号 (49152-65535 范围内的动态端口)
        port = 49152 + (int(hash_hex[:8], 16) % 16384)
        
        logger.info(f"为应用 '{self.app_name}' 生成端口: {port}")
        return port
    
    def acquire_lock(self):
        """尝试获取单实例锁"""
        try:
            # 创建TCP socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # 尝试绑定端口
            self.socket.bind(('127.0.0.1', self.port))
            self.socket.listen(1)
            
            logger.info(f"成功获取单实例锁，端口: {self.port}")
            return True
            
        except OSError as e:
            logger.warning(f"端口 {self.port} 已被占用，检测到其他实例正在运行: {e}")
            
            # 尝试通知现有实例
            self._notify_existing_instance()
            
            return False
    
    def _notify_existing_instance(self):
        """通知现有实例用户尝试启动新实例"""
        try:
            # 尝试连接到现有实例
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(2.0)  # 2秒超时
            
            client_socket.connect(('127.0.0.1', self.port))
            
            # 发送激活信号
            message = "ACTIVATE_WINDOW"
            client_socket.send(message.encode())
            
            # 等待响应
            response = client_socket.recv(1024).decode()
            if response == "OK":
                logger.info("成功通知现有实例激活窗口")
            
            client_socket.close()
            
        except Exception as e:
            logger.warning(f"无法通知现有实例: {e}")
    
    def start_listener(self, callback=None):
        """启动监听器，处理来自其他实例的请求"""
        if not self.socket:
            return
        
        def handle_requests():
            """处理来自其他实例的请求"""
            while True:
                try:
                    client_socket, addr = self.socket.accept()
                    
                    # 接收消息
                    message = client_socket.recv(1024).decode()
                    
                    if message == "ACTIVATE_WINDOW":
                        logger.info("收到窗口激活请求")
                        
                        # 调用回调函数激活窗口
                        if callback:
                            try:
                                callback()
                                client_socket.send("OK".encode())
                            except Exception as e:
                                logger.error(f"激活窗口回调失败: {e}")
                                client_socket.send("ERROR".encode())
                        else:
                            client_socket.send("NO_CALLBACK".encode())
                    
                    client_socket.close()
                    
                except Exception as e:
                    logger.error(f"处理客户端请求时出错: {e}")
                    break
        
        # 在后台线程中启动监听器
        import threading
        listener_thread = threading.Thread(target=handle_requests, daemon=True)
        listener_thread.start()
        logger.info("单实例监听器已启动")
    
    def release_lock(self):
        """释放单实例锁"""
        if self.socket:
            try:
                self.socket.close()
                logger.info(f"已释放单实例锁，端口: {self.port}")
            except:
                pass
            finally:
                self.socket = None

# 全局实例
_instance_checker = None

def check_single_instance(app_name="GameTimeLimiter", activate_callback=None):
    """
    检查单实例，如果已有实例运行则尝试激活现有窗口
    
    Args:
        app_name: 应用程序名称
        activate_callback: 当收到激活请求时的回调函数
    
    Returns:
        bool: True表示可以继续运行，False表示应该退出
    """
    global _instance_checker
    
    _instance_checker = SingleInstanceChecker(app_name)
    
    if _instance_checker.acquire_lock():
        # 成功获取锁，启动监听器
        if activate_callback:
            _instance_checker.start_listener(activate_callback)
        return True
    else:
        # 已有实例运行，应该退出
        return False

def release_single_instance():
    """释放单实例锁"""
    global _instance_checker
    if _instance_checker:
        _instance_checker.release_lock()
        _instance_checker = None

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
    instance1 = check_single_instance("TestApp")
    if instance1:
        print("✅ 第一个实例成功获取锁")
        
        # 尝试第二次获取锁（应该失败）
        instance2 = check_single_instance("TestApp")
        if instance2:
            print("❌ 第二个实例不应该获取到锁")
            instance2.release_lock()
        else:
            print("✅ 第二个实例正确被阻止")
        
        # 释放第一个锁
        instance1.release_lock()
        print("✅ 第一个实例释放锁")
        
        # 再次尝试获取锁（应该成功）
        instance3 = check_single_instance("TestApp")
        if instance3:
            print("✅ 释放后重新获取锁成功")
            instance3.release_lock()
        else:
            print("❌ 释放后重新获取锁失败")
    else:
        print("❌ 第一个实例获取锁失败")
    
    print("测试完成") 