"""
任务管理器 - 专门处理qasync环境下的异步任务调度
使用顺序执行避免qasync冲突
"""
import asyncio
import logging
import weakref
from typing import Dict, Set, Optional, Callable, Any, List
from PyQt6.QtCore import QTimer, QObject, pyqtSignal
import queue
import threading

logger = logging.getLogger(__name__)

class TaskManager(QObject):
    """
    任务管理器 - 使用顺序执行解决qasync环境下的任务冲突问题
    """
    
    # 信号定义
    task_completed = pyqtSignal(str, object)  # task_id, result
    task_failed = pyqtSignal(str, str)        # task_id, error_message
    
    def __init__(self):
        super().__init__()
        self._task_counter = 0
        self._is_processing = False
        self._task_queue = []  # 任务队列
        self._current_task = None
        self._shutdown = False
        
    def generate_task_id(self, prefix: str = "task") -> str:
        """生成唯一的任务ID"""
        self._task_counter += 1
        return f"{prefix}_{self._task_counter}"
    
    def run_task_safe(self, coro, task_id: str = None, 
                     on_complete: Callable = None, 
                     on_error: Callable = None, 
                     delay_ms: int = 0) -> str:
        """
        安全地运行异步任务（顺序执行）
        
        Args:
            coro: 协程对象
            task_id: 任务ID
            on_complete: 完成回调
            on_error: 错误回调
            delay_ms: 延迟启动时间（毫秒）
            
        Returns:
            str: 任务ID
        """
        if task_id is None:
            task_id = self.generate_task_id()
        
        if self._shutdown:
            logger.warning(f"TaskManager已关闭，无法添加任务: {task_id}")
            return task_id
        
        # 将任务添加到队列
        task_info = {
            'id': task_id,
            'coro': coro,
            'on_complete': on_complete,
            'on_error': on_error
        }
        
        self._task_queue.append(task_info)
        
        # 延迟启动处理器
        def start_processor():
            if not self._shutdown:
                if not self._is_processing:
                    self._start_processing()
                else:
                    # 即使处理器在运行，也要确保队列中的任务被处理
                    if self._task_queue and not self._current_task:
                        self._is_processing = False  # 重置状态
                        self._start_processing()
        
        # 如果没有延迟，立即启动；否则延迟启动
        if delay_ms <= 0:
            # 使用小延迟确保在正确的时机启动
            QTimer.singleShot(10, start_processor)
        else:
            QTimer.singleShot(delay_ms, start_processor)
        return task_id
    
    def _start_processing(self):
        """开始处理任务队列"""
        if self._is_processing or self._shutdown:
            return
        
        if not self._task_queue:
            return
        
        self._is_processing = True
        
        # 使用QTimer来顺序处理任务，避免qasync冲突
        self._process_next_task()
    
    def _process_next_task(self):
        """处理下一个任务"""
        if self._shutdown:
            self._is_processing = False
            return
        
        if not self._task_queue:
            self._is_processing = False
            return
        
        # 取出下一个任务
        task_info = self._task_queue.pop(0)
        self._current_task = task_info
        
        # 使用QTimer延迟执行，确保在正确的时机执行
        QTimer.singleShot(10, lambda: self._execute_task(task_info))
    
    def _execute_task(self, task_info, retry_count=0):
        """执行单个任务"""
        try:
            # 检查事件循环状态
            try:
                loop = asyncio.get_running_loop()
                if not loop.is_running():
                    # 如果事件循环未运行，等待一下再重试
                    if retry_count < 3:
                        QTimer.singleShot(100, lambda: self._execute_task(task_info, retry_count + 1))
                        return
                    else:
                        logger.warning(f"事件循环未运行，跳过任务: {task_info['id']}")
                        self._task_completed(task_info, None)
                        return
            except RuntimeError:
                # 如果没有运行中的事件循环，等待一下再重试
                if retry_count < 3:
                    QTimer.singleShot(100, lambda: self._execute_task(task_info, retry_count + 1))
                    return
                else:
                    logger.warning(f"没有运行中的事件循环，跳过任务: {task_info['id']}")
                    self._task_completed(task_info, None)
                    return
            
            # 创建任务包装器
            async def task_wrapper():
                try:
                    result = await task_info['coro']
                    return result
                except Exception as e:
                    logger.error(f"任务执行失败: {task_info['id']}, 错误: {e}")
                    raise
            
            # 使用ensure_future执行任务
            future = asyncio.ensure_future(task_wrapper())
            
            # 添加完成回调
            future.add_done_callback(lambda f: self._on_task_done(task_info, f))
            
        except Exception as e:
            logger.error(f"执行任务失败: {task_info['id']}, 错误: {e}")
            self._task_failed(task_info, str(e))
    
    def _on_task_done(self, task_info, future):
        """任务完成回调"""
        try:
            if future.cancelled():
                logger.info(f"任务被取消: {task_info['id']}")
                self._task_completed(task_info, None)
            elif future.exception():
                error = future.exception()
                logger.error(f"任务执行异常: {task_info['id']}, 错误: {error}")
                self._task_failed(task_info, str(error))
            else:
                result = future.result()
                self._task_completed(task_info, result)
        except Exception as e:
            logger.error(f"处理任务完成回调时出错: {task_info['id']}, 错误: {e}")
            self._task_failed(task_info, str(e))
    
    def _task_completed(self, task_info, result):
        """任务完成处理"""
        try:
            # 发送完成信号
            self.task_completed.emit(task_info['id'], result)
            
            # 调用完成回调
            if task_info['on_complete']:
                try:
                    if asyncio.iscoroutinefunction(task_info['on_complete']):
                        # 对于协程回调，添加到队列中执行
                        self._task_queue.insert(0, {
                            'id': f"{task_info['id']}_callback",
                            'coro': task_info['on_complete'](result),
                            'on_complete': None,
                            'on_error': None
                        })
                    else:
                        task_info['on_complete'](result)
                except Exception as e:
                    logger.error(f"任务完成回调出错: {task_info['id']}, 错误: {e}")
        except Exception as e:
            logger.error(f"处理任务完成时出错: {task_info['id']}, 错误: {e}")
        finally:
            self._current_task = None
            # 继续处理下一个任务
            QTimer.singleShot(50, self._process_next_task)
    
    def _task_failed(self, task_info, error_msg):
        """任务失败处理"""
        try:
            # 发送失败信号
            self.task_failed.emit(task_info['id'], error_msg)
            
            # 调用错误回调
            if task_info['on_error']:
                try:
                    if asyncio.iscoroutinefunction(task_info['on_error']):
                        # 对于协程回调，添加到队列中执行
                        self._task_queue.insert(0, {
                            'id': f"{task_info['id']}_error_callback",
                            'coro': task_info['on_error'](Exception(error_msg)),
                            'on_complete': None,
                            'on_error': None
                        })
                    else:
                        task_info['on_error'](Exception(error_msg))
                except Exception as e:
                    logger.error(f"任务错误回调出错: {task_info['id']}, 错误: {e}")
        except Exception as e:
            logger.error(f"处理任务失败时出错: {task_info['id']}, 错误: {e}")
        finally:
            self._current_task = None
            # 继续处理下一个任务
            QTimer.singleShot(50, self._process_next_task)
    
    def cancel_task_safe(self, task_id: str, timeout: float = 2.0):
        """
        安全地取消任务
        """
        # 从队列中移除任务，并清理协程
        removed_tasks = []
        new_queue = []
        for task in self._task_queue:
            if task['id'] == task_id:
                removed_tasks.append(task)
                # 清理协程
                if hasattr(task['coro'], 'close'):
                    try:
                        task['coro'].close()
                    except:
                        pass
            else:
                new_queue.append(task)
        
        self._task_queue = new_queue
        
        # 如果是当前正在执行的任务，标记为取消
        if self._current_task and self._current_task['id'] == task_id:
            logger.info(f"取消当前任务: {task_id}")
            # 当前任务无法直接取消，让它自然完成
        
        if removed_tasks:
            logger.debug(f"任务已从队列中移除: {task_id}")
    
    def cancel_all_tasks_sync(self):
        """
        同步取消所有任务
        """
        logger.info(f"取消所有任务，队列中有 {len(self._task_queue)} 个任务")
        
        # 清理所有协程
        for task in self._task_queue:
            if hasattr(task['coro'], 'close'):
                try:
                    task['coro'].close()
                except:
                    pass
        
        # 清空任务队列
        self._task_queue.clear()
        
        # 标记关闭状态
        self._shutdown = True
        self._is_processing = False
        self._current_task = None
        
        logger.info("所有任务已取消")
    
    async def cancel_all_tasks(self, timeout: float = 5.0):
        """
        异步取消所有任务（兼容性方法）
        """
        self.cancel_all_tasks_sync()
    
    def get_running_tasks(self) -> Dict[str, bool]:
        """
        获取运行中的任务状态
        """
        result = {}
        
        # 队列中的任务都是未完成的
        for task in self._task_queue:
            result[task['id']] = False
        
        # 当前任务也是未完成的
        if self._current_task:
            result[self._current_task['id']] = False
        
        return result
    
    def is_task_running(self, task_id: str) -> bool:
        """
        检查任务是否在运行
        """
        # 检查队列中是否有该任务
        for task in self._task_queue:
            if task['id'] == task_id:
                return True
        
        # 检查是否是当前任务
        if self._current_task and self._current_task['id'] == task_id:
            return True
        
        return False


# 全局任务管理器实例
_task_manager = None

def get_task_manager() -> TaskManager:
    """获取全局任务管理器实例"""
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager

def run_task_safe(coro, task_id: str = None, 
                 on_complete: Callable = None, 
                 on_error: Callable = None, 
                 delay_ms: int = 0) -> str:
    """
    便捷函数：安全地运行异步任务
    """
    return get_task_manager().run_task_safe(
        coro, task_id, on_complete, on_error, delay_ms
    )

def cancel_task_safe(task_id: str, timeout: float = 2.0):
    """
    便捷函数：安全地取消任务
    """
    get_task_manager().cancel_task_safe(task_id, timeout) 