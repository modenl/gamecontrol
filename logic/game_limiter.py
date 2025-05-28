import os
import sys
import time
import psutil
import datetime
import subprocess
import logging
from logic.database import Database, get_week_start
from logic.constants import MAX_WEEKLY_LIMIT, DEFAULT_WEEKLY_LIMIT, ENABLE_LOCK_SCREEN, TEST_MODE
from logic.math_exercises import MathExercises
from logic.math_exercises_mock import MockMathExercises
from logic.event_logger import get_event_logger

# 配置日志
logger = logging.getLogger('game_limiter')

class GameLimiter:
    def __init__(self, db_path=None):
        self.db = Database(db_path)
        self.current_session_start = None
        self.current_session_duration = 0
        self.current_game_name = "Minecraft"
        self.auto_optimize_interval = 7 * 24 * 60 * 60  # 7天（秒）
        self.last_optimize_time = 0
        
        # 初始化数学练习模块（测试模式下使用Mock）
        if TEST_MODE:
            self.math_exercises = MockMathExercises()
            logger.info("使用Mock数学练习模块（测试模式）")
        else:
            self.math_exercises = MathExercises()
        
        # 初始化事件日志记录器
        self.event_logger = get_event_logger()
        
        # 尝试自动优化数据库
        self._check_auto_optimize()
        
        # 执行周重置检查 (注意: 现在是异步方法，需要在initialize中调用)
        # self.weekly_reset_check()
        
    async def initialize(self):
        """异步初始化各组件"""
        # 初始化数学练习模块
        await self.math_exercises.initialize()
        
        # 执行周重置检查
        await self.weekly_reset_check()
        
        return self
        
    def start_session(self, duration, game_name="Minecraft"):
        """开始一个游戏Session"""
        try:
            self.current_session_start = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.current_session_duration = duration
            self.current_game_name = game_name
            logger.info(f"开始游戏Session: {game_name}, 时长: {duration}分钟")
            
            # 记录会话启动事件
            self.event_logger.log_session_started(
                duration_hours=duration / 60.0,
                session_type=f"{game_name}游戏会话"
            )
            
            return self.current_session_start, self.current_session_duration
        except Exception as e:
            logger.error(f"开始Session时出错: {e}")
            self.event_logger.log_error_event(f"开始Session时出错: {e}", "SESSION_START_ERROR")
            raise Exception(f"无法开始游戏Session: {e}")
        
    async def end_session(self, note=None):
        """结束当前Session"""
        if not self.current_session_start:
            logger.warning("尝试结束不存在的Session")
            return None
            
        try:
            # 确保数据库连接有效
            if hasattr(self.db, 'conn') and self.db.conn is None:
                logger.info("检测到数据库连接已关闭，正在重新连接...")
                self.db.reconnect()
            
            end_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # 计算实际持续时间（分钟）
            start_dt = datetime.datetime.strptime(self.current_session_start, "%Y-%m-%d %H:%M:%S")
            end_dt = datetime.datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
            actual_duration = int((end_dt - start_dt).total_seconds() / 60)
            
            # 保存会话记录
            await self.db.add_session(
                self.current_session_start, 
                end_time, 
                actual_duration,
                self.current_game_name,
                note
            )
            
            # 记录日志
            logger.info(f"结束游戏Session: {self.current_game_name}, 实际时长: {actual_duration}分钟, 备注: {note}")
            
            # 记录会话结束事件
            self.event_logger.log_session_ended(
                actual_duration=actual_duration / 60.0,
                reason=note if note else "正常结束"
            )
            
            # 重置当前会话
            temp_start = self.current_session_start
            self.current_session_start = None
            self.current_session_duration = 0
            
            # 定期优化数据库
            self._check_auto_optimize()
            
            return temp_start, end_time, actual_duration
        except Exception as e:
            logger.error(f"结束Session时出错: {e}")
            self.event_logger.log_error_event(f"结束Session时出错: {e}", "SESSION_END_ERROR")
            raise Exception(f"无法结束游戏Session: {e}")
        
    def kill_minecraft(self):
        """结束Minecraft进程"""
        killed = False
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    # 检查是否为Minecraft进程
                    proc_name = proc.info['name'].lower()
                    if "java" in proc_name or "minecraft" in proc_name:
                        proc.kill()
                        killed = True
                        logger.info(f"已结束进程: {proc.info['name']} (PID: {proc.info['pid']})")
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
                    logger.debug(f"处理进程时出错: {e}")
                    continue
            
            if not killed:
                logger.info("没有找到Minecraft相关进程")
            return killed
        except Exception as e:
            logger.error(f"结束Minecraft进程时出错: {e}")
            return False
        
    def lock_screen(self):
        """锁定Windows屏幕"""
        # 测试模式下不锁屏
        if not ENABLE_LOCK_SCREEN:
            if TEST_MODE:
                logger.info("测试模式：跳过锁屏操作")
            else:
                logger.info("锁屏功能已禁用")
            return True
            
        try:
            if sys.platform == "win32":
                # Windows平台使用ctypes锁屏
                import ctypes
                result = ctypes.windll.user32.LockWorkStation()
                if result:
                    logger.info("成功锁定屏幕")
                    return True
                else:
                    logger.error("锁屏API调用失败")
                    return False
            else:
                logger.warning("锁屏功能仅支持Windows系统")
                return False
        except Exception as e:
            logger.error(f"锁屏失败: {str(e)}")
            return False
        
    async def check_week_reset(self):
        """检查是否需要重置每周限制"""
        try:
            today = datetime.date.today()
            week_start = get_week_start(today).strftime("%Y-%m-%d")
            
            # 获取本周已使用时间和额外奖励时间
            used, extra = await self.db.get_week_total(week_start)
            return week_start, used, extra
        except Exception as e:
            logger.error(f"检查周重置时出错: {e}")
            # 返回默认值
            today = datetime.date.today()
            week_start = get_week_start(today).strftime("%Y-%m-%d")
            return week_start, 0, 0
        
    async def get_weekly_status(self):
        """获取本周游戏时间状态"""
        try:
            # 确保数据库连接有效
            if hasattr(self.db, 'conn') and self.db.conn is None:
                logger.info("检测到数据库连接已关闭，正在重新连接...")
                self.db.reconnect()
            
            today = datetime.date.today()
            week_start = get_week_start(today).strftime("%Y-%m-%d")
            
            # 获取本周已使用时间和额外奖励时间
            used, extra = await self.db.get_week_total(week_start)
            
            # 计算本周剩余时间
            weekly_limit = min(DEFAULT_WEEKLY_LIMIT + extra, MAX_WEEKLY_LIMIT)
            remaining = max(0, weekly_limit - used)
            
            return {
                'week_start': week_start,
                'used_minutes': used,
                'extra_minutes': extra,
                'weekly_limit': weekly_limit,
                'remaining_minutes': remaining
            }
        except Exception as e:
            logger.error(f"获取每周状态时出错: {e}")
            # 返回默认值
            return {
                'week_start': datetime.date.today().strftime("%Y-%m-%d"),
                'used_minutes': 0,
                'extra_minutes': 0,
                'weekly_limit': DEFAULT_WEEKLY_LIMIT,
                'remaining_minutes': DEFAULT_WEEKLY_LIMIT
            }
        
    async def add_weekly_extra_time(self, minutes):
        """添加每周额外游戏时间"""
        try:
            # 确保数据库连接有效
            if hasattr(self.db, 'conn') and self.db.conn is None:
                logger.info("检测到数据库连接已关闭，正在重新连接...")
                self.db.reconnect()
            
            today = datetime.date.today()
            week_start = get_week_start(today).strftime("%Y-%m-%d")
            
            # 获取当前额外时间
            _, current_extra = await self.db.get_week_total(week_start)
            
            # 添加额外时间，确保不超过上限
            max_extra = MAX_WEEKLY_LIMIT - DEFAULT_WEEKLY_LIMIT
            new_extra = min(max_extra, current_extra + minutes)
            
            # 计算实际添加的时间
            actual_added = new_extra - current_extra
            
            # 如果实际添加时间小于请求添加时间，记录警告
            if actual_added < minutes:
                logger.warning(f"请求添加{minutes}分钟，但达到上限，实际添加{actual_added}分钟")
            
            await self.db.add_weekly_extra_time(week_start, new_extra)
            
            logger.info(f"已添加{actual_added}分钟额外时间，当前额外时间: {new_extra}分钟")
            return new_extra
        except Exception as e:
            logger.error(f"添加额外时间时出错: {e}")
            raise Exception(f"无法添加额外时间: {e}")
        
    async def modify_used_time(self, minutes_to_add):
        """修改本周已用时间（仅管理员使用）
        
        Args:
            minutes_to_add: 要增加或减少的分钟数（正数增加，负数减少）
            
        Returns:
            new_used_minutes: 修改后的已用时间
        """
        try:
            # 确保数据库连接有效
            if hasattr(self.db, 'conn') and self.db.conn is None:
                logger.info("检测到数据库连接已关闭，正在重新连接...")
                self.db.reconnect()
            
            today = datetime.date.today()
            week_start = get_week_start(today).strftime("%Y-%m-%d")
            
            # 获取当前已用时间
            current_used, _ = await self.db.get_week_total(week_start)
            
            # 创建一个手动调整的Session记录
            start_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            end_time = start_time  # 同一时间
            
            # 添加一个特殊的Session记录，正数表示增加时间，负数表示减少时间
            note = f"管理员手动调整: {'+' if minutes_to_add > 0 else ''}{minutes_to_add}分钟"
            await self.db.add_session(start_time, end_time, minutes_to_add, "手动调整", note)
            
            # 计算新的已用时间
            new_used = current_used + minutes_to_add
            
            logger.info(f"管理员手动调整时间: {minutes_to_add}分钟, 调整前: {current_used}分钟, 调整后: {new_used}分钟")
            return new_used
        except Exception as e:
            logger.error(f"修改已用时间时出错: {e}")
            raise Exception(f"无法修改已用时间: {e}")
        
    async def get_sessions(self, week_start=None):
        """获取游戏会话记录
        
        Args:
            week_start: 周开始日期，如果为None，则获取所有记录
            
        Returns:
            会话记录列表
        """
        try:
            return await self.db.get_sessions(week_start)
        except Exception as e:
            logger.error(f"获取会话记录时出错: {e}")
            return []
        
    def _check_auto_optimize(self):
        """检查是否需要自动优化数据库"""
        try:
            # 确保数据库连接有效
            if hasattr(self.db, 'conn') and self.db.conn is None:
                logger.info("检测到数据库连接已关闭，正在重新连接...")
                self.db.reconnect()
            
            current_time = time.time()
            
            # 如果从未优化过，或者距离上次优化已经超过间隔时间
            if self.last_optimize_time == 0 or (current_time - self.last_optimize_time) > self.auto_optimize_interval:
                logger.info("开始自动优化数据库...")
                success = self.db.optimize_database()
                if success:
                    self.last_optimize_time = current_time
        except Exception as e:
            logger.error(f"数据库自动优化检查失败: {e}")
        
    def optimize_now(self):
        """立即优化数据库"""
        try:
            # 确保数据库连接有效
            if hasattr(self.db, 'conn') and self.db.conn is None:
                logger.info("检测到数据库连接已关闭，正在重新连接...")
                self.db.reconnect()
            
            logger.info("手动优化数据库...")
            success = self.db.optimize_database()
            if success:
                self.last_optimize_time = time.time()
            return success
        except Exception as e:
            logger.error(f"数据库手动优化失败: {e}")
            return False
        
    def close(self):
        """关闭数据库连接"""
        try:
            if self.db:
                self.db.close()
                logger.info("数据库连接已关闭")
        except Exception as e:
            logger.error(f"关闭数据库连接时出错: {e}")
        
    async def weekly_reset_check(self):
        """检查并执行每周重置"""
        try:
            today = datetime.date.today()
            current_week_start = get_week_start(today).strftime("%Y-%m-%d")
            
            # 获取上次重置时间
            last_reset = await self.db.get_setting("last_weekly_reset", None)
            
            # 如果没有记录或者上次重置的周不是本周，则执行重置
            if not last_reset or last_reset != current_week_start:
                logger.info(f"执行每周重置，上次重置: {last_reset}, 本周开始: {current_week_start}")
                
                # 更新最后重置时间
                await self.db.set_setting("last_weekly_reset", current_week_start)
                
                # 可以在这里添加其他重置逻辑
                
                return True
            return False
        except Exception as e:
            logger.error(f"周重置检查错误: {e}")
            return False 