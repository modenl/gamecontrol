#!/usr/bin/env python3
"""
进程清理工具
用于检查和清理GameTimeLimiter应用相关的残留进程
"""

import os
import sys
import time
import psutil
import logging
from pathlib import Path
import argparse
import signal
from typing import List, Set

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class ProcessCleaner:
    """进程清理器"""
    
    def __init__(self):
        self.target_processes = {
            'GameTimeLimiter.exe',
            'python.exe',
            'python3.13.exe',
            'pythonw.exe',
            'QtWebEngineProcess.exe',  # Qt WebEngine 子进程
            'QtWebEngineProcess',
        }
        
        self.target_keywords = [
            'gamecontrol',
            'GameTimeLimiter',
            'game_limiter',
            'main.py',
            'QtWebEngine',
        ]
        
        self.workspace_path = os.path.abspath(os.getcwd())
        
    def is_target_process(self, proc: psutil.Process) -> bool:
        """判断是否为目标进程"""
        try:
            # 检查进程名
            proc_name = proc.name()
            if proc_name in self.target_processes:
                # 对于QtWebEngine进程，需要进一步验证是否与我们的应用相关
                if 'QtWebEngine' in proc_name:
                    return self._is_our_qtwebengine(proc)
                return True
            
            # 检查命令行参数
            try:
                cmdline = ' '.join(proc.cmdline())
                for keyword in self.target_keywords:
                    if keyword.lower() in cmdline.lower():
                        return True
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass
            
            # 检查工作目录
            try:
                cwd = proc.cwd()
                if self.workspace_path.lower() in cwd.lower():
                    return True
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass
            
            # 检查可执行文件路径
            try:
                exe = proc.exe()
                if self.workspace_path.lower() in exe.lower():
                    return True
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass
                
            return False
            
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
    
    def _is_our_qtwebengine(self, proc: psutil.Process) -> bool:
        """检查QtWebEngine进程是否属于我们的应用"""
        try:
            # 检查父进程
            parent = proc.parent()
            if parent:
                parent_name = parent.name()
                if parent_name in ['GameTimeLimiter.exe', 'python.exe', 'python3.13.exe']:
                    return True
                
                # 检查父进程的命令行
                try:
                    parent_cmdline = ' '.join(parent.cmdline())
                    if any(keyword in parent_cmdline.lower() for keyword in ['gametimelimiter', 'gamecontrol', 'main.py']):
                        return True
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    pass
            
            return False
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
    
    def find_related_processes(self) -> List[psutil.Process]:
        """查找相关进程"""
        related_processes = []
        current_pid = os.getpid()
        
        for proc in psutil.process_iter(['pid', 'name', 'create_time']):
            try:
                # 跳过当前进程
                if proc.info['pid'] == current_pid:
                    continue
                    
                if self.is_target_process(proc):
                    related_processes.append(proc)
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        return related_processes
    
    def find_child_processes(self, parent_processes: List[psutil.Process]) -> Set[psutil.Process]:
        """查找子进程"""
        all_children = set()
        
        for parent in parent_processes:
            try:
                children = parent.children(recursive=True)
                all_children.update(children)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
                
        return all_children
    
    def graceful_terminate_process(self, proc: psutil.Process, timeout: int = 10) -> bool:
        """温和地终止进程"""
        try:
            proc_name = proc.name()
            proc_pid = proc.pid
            
            logger.info(f"温和终止进程: {proc_pid} - {proc_name}")
            
            # 首先尝试温和终止
            proc.terminate()
            
            # 等待进程自然退出
            try:
                proc.wait(timeout=timeout)
                logger.info(f"进程 {proc_pid} 已正常退出")
                return True
            except psutil.TimeoutExpired:
                logger.warning(f"进程 {proc_pid} 在 {timeout} 秒后仍未退出")
                return False
                
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.warning(f"无法终止进程 {proc.pid}: {e}")
            return False
    
    def cleanup_processes(self, auto_mode: bool = False) -> int:
        """清理进程"""
        logger.info("开始进程清理检查...")
        
        # 查找相关进程
        related_processes = self.find_related_processes()
        
        if not related_processes:
            logger.info("未发现相关进程")
            return 0
        
        # 查找所有子进程
        all_children = self.find_child_processes(related_processes)
        all_processes = set(related_processes) | all_children
        
        logger.info(f"找到 {len(all_processes)} 个相关进程:")
        logger.info("-" * 80)
        logger.info(f"{'PID':<8} {'进程名':<20} {'创建时间':<20} {'命令行'}")
        logger.info("-" * 80)
        
        for proc in all_processes:
            try:
                create_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(proc.create_time()))
                cmdline = ' '.join(proc.cmdline())
                if len(cmdline) > 50:
                    cmdline = cmdline[:47] + "..."
                logger.info(f"{proc.pid:<8} {proc.name():<20} {create_time:<20} {cmdline}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                logger.info(f"{proc.pid:<8} {'<无法访问>':<20}")
        
        if not auto_mode:
            response = input(f"\n发现 {len(all_processes)} 个相关进程，是否温和终止它们？(y/N): ")
            if response.lower() not in ['y', 'yes']:
                logger.info("用户取消操作")
                return 0
        else:
            logger.info(f"自动模式：发现 {len(all_processes)} 个相关进程，正在温和终止...")
        
        # 按优先级排序进程（子进程优先）
        processes_to_terminate = []
        main_processes = []
        
        for proc in all_processes:
            try:
                proc_name = proc.name()
                if proc_name in ['QtWebEngineProcess.exe', 'QtWebEngineProcess']:
                    processes_to_terminate.insert(0, proc)  # 优先处理
                elif proc_name in ['GameTimeLimiter.exe']:
                    main_processes.append(proc)  # 最后处理
                else:
                    processes_to_terminate.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        # 添加主进程到最后
        processes_to_terminate.extend(main_processes)
        
        terminated_count = 0
        for proc in processes_to_terminate:
            try:
                if self.graceful_terminate_process(proc, timeout=5):
                    terminated_count += 1
            except Exception as e:
                logger.error(f"终止进程 {proc.pid} 时出错: {e}")
        
        logger.info(f"已温和终止 {terminated_count} 个进程")
        
        # 等待一段时间后再次检查
        time.sleep(3)
        remaining_processes = self.find_related_processes()
        if remaining_processes:
            logger.warning(f"仍有 {len(remaining_processes)} 个进程未被清理:")
            for proc in remaining_processes:
                try:
                    logger.warning(f"  - {proc.pid}: {proc.name()}")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            logger.info("提示：这些进程可能需要手动关闭应用程序来清理")
        else:
            logger.info("所有相关进程已清理完成")
        
        logger.info("清理检查完成")
        return terminated_count

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='GameTimeLimiter 进程清理工具')
    parser.add_argument('--auto', action='store_true', help='自动模式，不询问直接清理')
    args = parser.parse_args()
    
    cleaner = ProcessCleaner()
    try:
        terminated_count = cleaner.cleanup_processes(auto_mode=args.auto)
        if terminated_count > 0:
            logger.info(f"清理完成，共温和终止 {terminated_count} 个进程")
        return 0
    except KeyboardInterrupt:
        logger.info("用户中断操作")
        return 1
    except Exception as e:
        logger.error(f"清理过程中出错: {e}")
        return 1

if __name__ == "__main__":
    exit(main()) 