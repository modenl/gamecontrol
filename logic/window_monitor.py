import os
import re
import time
import asyncio
import logging
import psutil
import pygetwindow as gw
import subprocess

# 导入任务管理器
from logic.task_manager import get_task_manager, run_task_safe
# 导入事件日志系统
from logic.event_logger import get_event_logger

# 配置日志
logger = logging.getLogger('window_monitor')

class WindowMonitor:
    """监控活动窗口，在非游戏会话期间阻止访问游戏"""
    def __init__(self, game_limiter, check_interval=15):
        """
        初始化窗口监控器
        
        Args:
            game_limiter: GameLimiter实例，用于访问会话状态和锁定屏幕
            check_interval: 检查间隔（秒），默认15秒
        """
        self.game_limiter = game_limiter
        self.check_interval = check_interval
        self.is_running = False
        self.monitor_task = None
        self.task_manager = get_task_manager()  # 使用任务管理器
        self._monitor_task_id = None  # 任务ID
        self.event_logger = get_event_logger()  # 事件日志记录器
        
        # 受限应用配置，可以在此处添加更多应用
        self.restricted_apps = [
            # 进程类型监控 (检查进程名称)
            {'name': 'minecraft', 'type': 'process', 
             'process_patterns': ['minecraft', 'java']},
             
            # Chrome标签页监控 (检查窗口标题中的URL)
            {'name': 'bloxd.io', 'type': 'chrome_tab', 
             'pattern': re.compile(r'bloxd\.io', re.IGNORECASE)},
             
            # 可以添加更多游戏
            {'name': 'roblox', 'type': 'process', 
             'process_patterns': ['roblox']},
             
            {'name': 'steam games', 'type': 'window', 
             'pattern': re.compile(r'steam', re.IGNORECASE)},
        ]
        
    async def start_monitoring(self):
        """开始监控活动窗口"""
        if self.is_running:
            logger.info("监控已经在运行中")
            return
            
        # 检查是否已有监控任务在运行
        if self._monitor_task_id and self.task_manager.is_task_running(self._monitor_task_id):
            logger.info("监控任务已在运行中")
            return
            
        self.is_running = True
        logger.info(f"开始监控活动窗口，检查间隔: {self.check_interval}秒")
        
        # 记录监控启动事件
        self.event_logger.log_monitor_started(self.check_interval)
        
        # 使用任务管理器创建监控任务
        self._monitor_task_id = run_task_safe(
            self._monitor_loop(),
            task_id="window_monitor",
            on_complete=None,
            on_error=lambda e: logger.error(f"监控任务出错: {e}"),
            delay_ms=50  # 小延迟避免冲突
        )
        
    async def stop_monitoring(self):
        """停止监控活动窗口"""
        if not self.is_running:
            logger.debug("监控已经停止")
            return
            
        logger.info("正在停止窗口监控...")
        self.is_running = False
        
        # 记录监控停止事件
        self.event_logger.log_monitor_stopped("手动停止")
        
        # 使用任务管理器取消监控任务
        if self._monitor_task_id:
            self.task_manager.cancel_task_safe(self._monitor_task_id)
            self._monitor_task_id = None
        
        # 兼容性：也处理旧的monitor_task
        if self.monitor_task:
            try:
                self.monitor_task.cancel()
                self.monitor_task = None
            except Exception as e:
                logger.error(f"取消旧监控任务时出错: {e}")
        
        logger.info("窗口监控已完全停止")
    
    def stop_monitoring_sync(self):
        """同步停止监控（用于应用退出时）"""
        logger.info("同步停止窗口监控...")
        self.is_running = False
        
        # 记录监控停止事件
        self.event_logger.log_monitor_stopped("应用退出")
        
        if self.monitor_task:
            try:
                self.monitor_task.cancel()
                self.monitor_task = None
                logger.info("监控任务已取消")
            except Exception as e:
                logger.error(f"同步取消监控任务时出错: {e}")
        
        logger.info("窗口监控已同步停止")
        
    async def _monitor_loop(self):
        """监控循环"""
        try:
            while self.is_running:
                await self._check_restricted_apps()
                await asyncio.sleep(self.check_interval)
        except asyncio.CancelledError:
            logger.info("监控任务被取消")
        except Exception as e:
            logger.error(f"监控过程中出错: {e}")
            self.is_running = False
            
    async def _check_restricted_apps(self):
        """检查受限应用"""
        try:
            # 如果会话正在进行中，不检查应用
            if self.game_limiter.current_session_start:
                return
            
            # 按类型分组检查应用
            detected_apps = []
            
            # 1. 检查进程类型应用
            process_apps = self._check_restricted_processes()
            if process_apps:
                detected_apps.extend(process_apps)
                
            # 2. 检查Chrome标签页
            chrome_apps = await self._check_chrome_tabs()
            if chrome_apps:
                detected_apps.extend(chrome_apps)
                
            # 3. 检查普通窗口
            window_apps = self._check_window_apps()
            if window_apps:
                detected_apps.extend(window_apps)
            
            # 如果检测到任何受限应用
            if detected_apps:
                app_names = ', '.join([app['name'] for app in detected_apps])
                logger.warning(f"检测到未授权使用游戏: {app_names}")
                
                # 记录检测到的每个受限应用
                for app in detected_apps:
                    self.event_logger.log_restricted_app_detected(
                        app['name'], 
                        app['type'],
                        details=app.get('details', {})
                    )
                
                # 对进程类型应用，尝试终止进程
                for app in detected_apps:
                    if app['type'] == 'process':
                        if app['name'] == 'minecraft':
                            # 使用现有方法终止Minecraft
                            await asyncio.to_thread(self.game_limiter.kill_minecraft)
                            self.event_logger.log_process_terminated('minecraft')
                
                # 锁定屏幕
                success = await asyncio.to_thread(self.game_limiter.lock_screen)
                if success:
                    logger.info("成功锁定屏幕")
                    self.event_logger.log_screen_locked(f"检测到禁止应用: {app_names}")
                else:
                    logger.error("锁定屏幕失败")
                    self.event_logger.log_error_event("锁定屏幕失败", "SCREEN_LOCK_FAILED")
                
        except Exception as e:
            logger.error(f"检查受限应用时出错: {e}")
    
    def _check_restricted_processes(self):
        """检查受限进程"""
        detected = []
        try:
            # 遍历所有受限进程类型的应用
            process_apps = [app for app in self.restricted_apps if app['type'] == 'process']
            
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    proc_name = proc.info['name'].lower()
                    
                    # 检查每个进程类型的应用
                    for app in process_apps:
                        for pattern in app['process_patterns']:
                            if pattern.lower() in proc_name:
                                logger.info(f"检测到受限进程: {app['name']} - {proc_name} (PID: {proc.info['pid']})")
                                # 添加详细信息到应用记录中
                                app_with_details = app.copy()
                                app_with_details['details'] = {
                                    'process_name': proc_name,
                                    'pid': proc.info['pid']
                                }
                                detected.append(app_with_details)
                                break
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
                    
            return detected
        except Exception as e:
            logger.error(f"检查受限进程时出错: {e}")
            return detected
    
    async def _check_chrome_tabs(self):
        """检查Chrome浏览器标签页"""
        detected = []
        try:
            # 获取所有Chrome窗口
            chrome_windows = [w for w in gw.getAllWindows() if "chrome" in w.title.lower()]
            
            if not chrome_windows:
                return detected
            
            # 检查所有Chrome窗口标题，不仅限于活动窗口
            for window in chrome_windows:
                window_title = window.title
                
                # 检查是否包含受限内容
                for app in self.restricted_apps:
                    if app['type'] == 'chrome_tab' and app['pattern'].search(window_title):
                        logger.warning(f"检测到受限网站: {app['name']} 在Chrome窗口中 (窗口标题: {window_title})")
                        if app not in detected:
                            detected.append(app)
            
            return detected
        except Exception as e:
            logger.error(f"检查Chrome标签页时出错: {e}")
            return detected
            
    def _check_window_apps(self):
        """检查窗口类型应用"""
        detected = []
        try:
            # 遍历所有窗口类型的受限应用
            window_apps = [app for app in self.restricted_apps if app['type'] == 'window']
            
            # 获取所有窗口
            all_windows = gw.getAllWindows()
            
            for window in all_windows:
                window_title = window.title.lower()
                
                # 检查每个窗口类型的应用
                for app in window_apps:
                    if app['pattern'].search(window_title):
                        logger.info(f"检测到受限窗口: {app['name']} - {window_title}")
                        if app not in detected:
                            detected.append(app)
                            
            return detected
        except Exception as e:
            logger.error(f"检查窗口应用时出错: {e}")
            return detected
    
    def set_check_interval(self, seconds):
        """设置检查间隔"""
        if seconds < 1:
            seconds = 1
        self.check_interval = seconds
        logger.info(f"已更新检查间隔: {self.check_interval}秒") 