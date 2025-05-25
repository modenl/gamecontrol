#!/usr/bin/env python3
"""
单实例管理模块 - 防止程序同时启动多个副本
"""

import os
import sys
import time
import logging
import tempfile
import psutil
from pathlib import Path

logger = logging.getLogger(__name__)

class SingleInstance:
    """单实例管理器"""
    
    def __init__(self, app_name="GameControl", lock_timeout=30):
        """
        初始化单实例管理器
        
        Args:
            app_name: 应用程序名称
            lock_timeout: 锁文件超时时间（秒）
        """
        self.app_name = app_name
        self.lock_timeout = lock_timeout
        
        # 使用临时目录存放锁文件
        self.lock_dir = Path(tempfile.gettempdir()) / "gamecontrol_locks"
        self.lock_dir.mkdir(exist_ok=True)
        
        # 锁文件路径
        self.lock_file = self.lock_dir / f"{app_name}.lock"
        self.pid_file = self.lock_dir / f"{app_name}.pid"
        
        self.is_locked = False
        
    def acquire_lock(self):
        """
        获取单实例锁
        
        Returns:
            bool: 成功获取锁返回True，否则返回False
        """
        try:
            # 检查是否已有其他实例在运行
            if self._check_existing_instance():
                logger.warning("检测到其他实例正在运行")
                return False
            
            # 创建锁文件
            current_pid = os.getpid()
            
            # 写入PID文件
            with open(self.pid_file, 'w') as f:
                f.write(str(current_pid))
            
            # 写入锁文件（包含时间戳）
            with open(self.lock_file, 'w') as f:
                f.write(f"{current_pid}\n{time.time()}\n")
            
            self.is_locked = True
            logger.info(f"成功获取单实例锁，PID: {current_pid}")
            return True
            
        except Exception as e:
            logger.error(f"获取单实例锁失败: {e}")
            return False
    
    def _check_existing_instance(self):
        """
        检查是否已有其他实例在运行
        
        Returns:
            bool: 有其他实例返回True，否则返回False
        """
        try:
            # 检查锁文件是否存在
            if not self.lock_file.exists():
                return False
            
            # 读取锁文件内容
            with open(self.lock_file, 'r') as f:
                lines = f.read().strip().split('\n')
                if len(lines) < 2:
                    # 锁文件格式不正确，删除它
                    self._cleanup_lock_files()
                    return False
                
                try:
                    existing_pid = int(lines[0])
                    lock_time = float(lines[1])
                except (ValueError, IndexError):
                    # 锁文件内容无效，删除它
                    self._cleanup_lock_files()
                    return False
            
            # 检查锁文件是否超时
            if time.time() - lock_time > self.lock_timeout:
                logger.warning(f"锁文件已超时，删除过期锁文件")
                self._cleanup_lock_files()
                return False
            
            # 检查进程是否仍在运行
            if self._is_process_running(existing_pid):
                # 进一步检查是否是同一个程序
                if self._is_same_program(existing_pid):
                    logger.warning(f"检测到同一程序的其他实例正在运行，PID: {existing_pid}")
                    return True
                else:
                    # 不是同一个程序，删除锁文件
                    logger.info(f"PID {existing_pid} 不是同一程序，清理锁文件")
                    self._cleanup_lock_files()
                    return False
            else:
                # 进程已不存在，删除锁文件
                logger.info(f"PID {existing_pid} 进程已不存在，清理锁文件")
                self._cleanup_lock_files()
                return False
                
        except Exception as e:
            logger.error(f"检查现有实例时出错: {e}")
            # 出错时清理锁文件，允许启动
            self._cleanup_lock_files()
            return False
    
    def _is_process_running(self, pid):
        """
        检查指定PID的进程是否在运行
        
        Args:
            pid: 进程ID
            
        Returns:
            bool: 进程在运行返回True，否则返回False
        """
        try:
            return psutil.pid_exists(pid)
        except Exception as e:
            logger.error(f"检查进程状态时出错: {e}")
            return False
    
    def _is_same_program(self, pid):
        """
        检查指定PID是否是同一个程序
        
        Args:
            pid: 进程ID
            
        Returns:
            bool: 是同一程序返回True，否则返回False
        """
        try:
            process = psutil.Process(pid)
            
            # 获取进程的可执行文件路径
            exe_path = process.exe()
            current_exe = sys.executable
            
            # 比较可执行文件路径
            if os.path.normpath(exe_path) == os.path.normpath(current_exe):
                return True
            
            # 如果是Python脚本，比较命令行参数
            cmdline = process.cmdline()
            current_script = os.path.abspath(sys.argv[0])
            
            for arg in cmdline:
                if os.path.isfile(arg) and os.path.abspath(arg) == current_script:
                    return True
            
            # 检查进程名称是否包含我们的应用名称
            process_name = process.name().lower()
            if self.app_name.lower() in process_name:
                return True
                
            return False
            
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return False
        except Exception as e:
            logger.error(f"检查程序一致性时出错: {e}")
            return False
    
    def release_lock(self):
        """释放单实例锁"""
        try:
            if self.is_locked:
                self._cleanup_lock_files()
                self.is_locked = False
                logger.info("已释放单实例锁")
        except Exception as e:
            logger.error(f"释放单实例锁时出错: {e}")
    
    def _cleanup_lock_files(self):
        """清理锁文件"""
        try:
            if self.lock_file.exists():
                self.lock_file.unlink()
            if self.pid_file.exists():
                self.pid_file.unlink()
        except Exception as e:
            logger.error(f"清理锁文件时出错: {e}")
    
    def __enter__(self):
        """上下文管理器入口"""
        if self.acquire_lock():
            return self
        else:
            raise RuntimeError("无法获取单实例锁，可能已有其他实例在运行")
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.release_lock()

def check_single_instance(app_name="GameControl"):
    """
    简单的单实例检查函数
    
    Args:
        app_name: 应用程序名称
        
    Returns:
        SingleInstance: 单实例管理器对象，如果获取锁失败则返回None
    """
    instance_manager = SingleInstance(app_name)
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