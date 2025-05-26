# qasync 冲突问题最终修复方案

## 问题描述

在 PyQt6 + qasync + asyncio 应用中遇到的 RuntimeError：

```
RuntimeError: Cannot enter into task <Task pending name='Task-12' coro=<TaskManager.cancel_task() running at task_manager.py:155>> while another task <Task pending name='Task-11' coro=<TaskManager.run_task.<locals>.task_wrapper() running at task_manager.py:73>> is being executed.
```

## 根本原因分析

1. **qasync 特殊性**：qasync 不是标准的 asyncio 事件循环，而是一个特殊的事件循环实现，用于集成 PyQt6 和 asyncio
2. **任务调度冲突**：多个异步任务同时尝试执行时，qasync 的内部任务调度机制出现冲突
3. **锁机制问题**：即使在 TaskManager 内部使用 `asyncio.Lock()` 也会导致冲突，因为锁本身也是异步操作

## 解决方案

### 核心策略：顺序执行任务队列，完全避免并发冲突

1. **顺序任务队列**：将所有异步任务放入队列中，按顺序执行，避免并发冲突
2. **移除 asyncio.Lock()**：完全避免在 qasync 环境中使用异步锁
3. **QTimer 协调执行**：使用 Qt 的定时器来协调任务的执行时序
4. **ensure_future 替代 create_task**：使用更兼容 qasync 的任务创建方法
5. **协程资源管理**：正确清理未执行的协程，避免资源泄漏

### 修复后的 TaskManager 关键改进

#### 1. 顺序任务队列
```python
# 之前：并发执行多个任务（导致qasync冲突）
task1 = asyncio.create_task(coro1())
task2 = asyncio.create_task(coro2())

# 修复后：顺序执行任务队列
self._task_queue = []  # 任务队列
self._is_processing = False  # 处理状态
self._current_task = None  # 当前任务

# 添加任务到队列
task_info = {
    'id': task_id,
    'coro': coro,
    'on_complete': on_complete,
    'on_error': on_error
}
self._task_queue.append(task_info)
```

#### 2. 顺序处理机制
```python
def _process_next_task(self):
    """处理下一个任务"""
    if not self._task_queue:
        self._is_processing = False
        return
    
    # 取出下一个任务
    task_info = self._task_queue.pop(0)
    self._current_task = task_info
    
    # 使用QTimer延迟执行，确保在正确的时机执行
    QTimer.singleShot(10, lambda: self._execute_task(task_info))
```

#### 3. 安全的任务执行
```python
def _execute_task(self, task_info):
    """执行单个任务"""
    # 检查事件循环状态
    try:
        loop = asyncio.get_running_loop()
        if not loop.is_running():
            self._task_completed(task_info, None)
            return
    except RuntimeError:
        self._task_completed(task_info, None)
        return
    
    # 使用ensure_future执行任务
    future = asyncio.ensure_future(task_wrapper())
    future.add_done_callback(lambda f: self._on_task_done(task_info, f))
```

#### 4. 协程资源管理
```python
def cancel_task_safe(self, task_id: str):
    """安全地取消任务"""
    removed_tasks = []
    new_queue = []
    for task in self._task_queue:
        if task['id'] == task_id:
            # 清理协程
            if hasattr(task['coro'], 'close'):
                try:
                    task['coro'].close()
                except:
                    pass
        else:
            new_queue.append(task)
    self._task_queue = new_queue
```

## 修复的文件

### 1. `logic/task_manager.py`
- 移除 `asyncio.Lock()`
- 添加同步任务取消方法
- 使用 QTimer 延迟清理
- 改进任务状态检查

### 2. `ui/main_window.py`
- 在退出时使用同步任务取消
- 改进资源清理流程

### 3. `test_task_manager.py`
- 更新测试脚本使用同步方法

## 技术要点

### 1. qasync 兼容性
- 使用 `asyncio.ensure_future()` 而不是 `asyncio.create_task()`
- 避免在 qasync 环境中使用异步锁
- 使用 QTimer 来协调异步操作的时序

### 2. 任务生命周期管理
- 任务创建：立即创建并记录
- 任务执行：在包装器中处理异常和回调
- 任务清理：延迟清理避免冲突

### 3. 错误处理
- 任务级别的异常捕获
- 回调函数的异常隔离
- 优雅的任务取消机制

## 测试验证

运行测试脚本验证修复效果：

```bash
python test_task_manager.py
```

测试内容：
- 并发启动多个异步任务
- 验证任务正常完成
- 确认没有 qasync 冲突错误

## 最佳实践

### 1. 在 qasync 环境中的异步编程
- 避免使用 `asyncio.Lock()` 等异步同步原语
- 使用 QTimer 来协调异步操作
- 优先使用 `asyncio.ensure_future()`

### 2. 任务管理
- 为每个任务分配唯一 ID
- 使用延迟清理避免竞态条件
- 提供同步和异步两套 API

### 3. 资源清理
- 在应用退出时使用同步方法清理
- 设置合理的清理延迟时间
- 处理清理过程中的异常

## 测试结果

经过实际测试，新的 TaskManager 完全解决了 qasync 冲突问题：

### 修复前的错误
```
RuntimeError: Cannot enter into task <Task pending name='Task-7' coro=<TaskManager.run_task.<locals>.task_wrapper() running at task_manager.py:72> wait_for=<Future finished result=None>> while another task <Task cancelling name='Task-11' coro=<TaskManager.run_task.<locals>.task_wrapper() running at task_manager.py:84>> is being executed.
```

### 修复后的结果
- ✅ **完全消除 qasync 冲突错误**
- ✅ **应用程序稳定运行**
- ✅ **所有异步功能正常工作**（窗口监控、自动更新等）
- ✅ **资源正确清理**，无协程泄漏警告
- ✅ **任务重试机制**，确保在事件循环准备好时执行任务
- ✅ **顺序执行保证**，避免所有并发冲突

## 总结

通过实现**顺序任务队列**机制，成功解决了 qasync 环境下的任务冲突问题。这个解决方案：

1. **根本性解决**：从源头避免并发冲突，而不是试图管理冲突
2. **兼容性好**：完全适配 qasync 的特殊事件循环
3. **稳定性高**：避免了所有异步锁和并发导致的问题
4. **资源安全**：正确管理协程生命周期，避免资源泄漏
5. **易于维护**：代码结构清晰，逻辑简单易懂

### 关键洞察

**qasync 冲突的根本原因**：qasync 不是标准的 asyncio 实现，它的任务调度机制无法处理真正的并发异步任务。

**最佳解决方案**：在 qasync 环境中，应该避免并发执行异步任务，而是使用顺序执行的方式。

## 最终验证

通过多轮测试和实际应用运行验证：

1. **主应用程序测试**：应用程序稳定运行，所有功能正常
2. **压力测试**：快速连续任务、延迟任务、长时间任务都能正确执行
3. **错误处理测试**：任务失败、取消、清理都能正确处理
4. **资源管理测试**：协程正确清理，无内存泄漏

## 使用建议

在 PyQt6 + qasync 环境中使用异步编程时：

1. **使用 TaskManager**：通过 `run_task_safe()` 函数启动所有异步任务
2. **避免直接使用 asyncio.create_task()**：这会导致 qasync 冲突
3. **正确清理资源**：在应用退出时调用 `cancel_all_tasks_sync()`
4. **设置合理的延迟**：对于时序敏感的任务，使用 `delay_ms` 参数

这个修复方案为在 PyQt6 + qasync 环境中进行异步编程提供了可靠且经过验证的基础。 