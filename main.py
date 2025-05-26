import sys
import time
import logging
import asyncio
import atexit
import os
import signal
from PyQt6.QtWidgets import QApplication, QSplashScreen, QWidget
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt, QTimer

# 应用程序属性设置

# 设置基本日志记录器，其他模块的导入放到后面延迟加载
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# 全局日志对象
logger = logging.getLogger("GameTimeLimiter")
logger.info("应用程序初始化中...")

# 记录启动目录信息
logger.info("========== 启动目录调试信息 ==========")
logger.info(f"当前工作目录: {os.getcwd()}")
logger.info(f"脚本文件路径: {os.path.abspath(__file__)}")
logger.info(f"脚本所在目录: {os.path.dirname(os.path.abspath(__file__))}")
logger.info(f"sys.executable: {sys.executable}")
logger.info(f"sys.argv[0]: {sys.argv[0]}")
if hasattr(sys, 'frozen'):
    logger.info("运行环境: 打包后的可执行文件")
else:
    logger.info("运行环境: Python脚本")
logger.info("========================================")

# 导入事件日志系统
from logic.event_logger import get_event_logger

# 全局变量用于资源清理
app = None
loop = None
game_limiter = None
window = None

def cleanup_resources():
    """清理应用程序资源"""
    global app, loop, game_limiter, window
    
    try:
        logger.info("开始清理应用程序资源...")
        
        # 记录应用关闭事件
        try:
            event_logger = get_event_logger()
            event_logger.log_app_shutdown("正常退出")
        except Exception as e:
            logger.error(f"记录应用关闭事件时出错: {e}")
        
        # 1. 首先停止窗口监控
        if window and hasattr(window, 'window_monitor'):
            logger.info("停止窗口监控...")
            try:
                # 使用同步方法停止监控
                window.window_monitor.stop_monitoring_sync()
            except Exception as e:
                logger.error(f"停止窗口监控时出错: {e}")
        
        # 2. 关闭主窗口
        if window:
            logger.info("关闭主窗口...")
            try:
                # 确保会话结束
                if hasattr(window, 'session_active') and window.session_active:
                    logger.info("强制结束活动会话...")
                    window.session_active = False
                    if hasattr(window, 'session_timer'):
                        window.session_timer.stop()
                
                window.close()
            except Exception as e:
                logger.error(f"关闭主窗口时出错: {e}")
        
        # 3. 关闭游戏限制器和数据库连接
        if game_limiter:
            logger.info("关闭游戏限制器...")
            try:
                # 关闭数学练习模块
                if hasattr(game_limiter, 'math_exercises') and game_limiter.math_exercises:
                    game_limiter.math_exercises.close()
                
                # 关闭数据库连接
                game_limiter.close()
            except Exception as e:
                logger.error(f"关闭游戏限制器时出错: {e}")
        
        # 4. 取消所有异步任务
        if loop:
            logger.info("取消所有异步任务...")
            try:
                # 获取所有未完成的任务
                pending_tasks = [task for task in asyncio.all_tasks(loop) if not task.done()]
                if pending_tasks:
                    logger.info(f"发现 {len(pending_tasks)} 个未完成的任务，正在取消...")
                    for task in pending_tasks:
                        task.cancel()
            except Exception as e:
                logger.error(f"取消异步任务时出错: {e}")
        
        # 5. 停止事件循环
        if loop and loop.is_running():
            logger.info("停止事件循环...")
            try:
                loop.stop()
            except Exception as e:
                logger.error(f"停止事件循环时出错: {e}")
                
        # 6. 改进的应用程序资源清理
        logger.info("清理应用程序相关资源...")
        try:
            if app:
                # 重置鼠标双击间隔到系统默认值
                logger.info("重置鼠标双击间隔...")
                app.setDoubleClickInterval(500)  # 重置为默认值
                
                # 处理所有待处理的事件
                app.processEvents()
                
                # 删除所有顶级窗口
                for widget in app.topLevelWidgets():
                    try:
                        if widget and not widget.isHidden():
                            widget.close()
                        widget.deleteLater()
                    except:
                        pass
                
                # 再次处理事件确保删除完成
                app.processEvents()
                
                # 清理事件过滤器
                logger.info("清理事件过滤器...")
                try:
                    app.removeEventFilter(app)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"清理应用程序资源时出错: {e}")
                
        # 7. 立即强制退出，不等待Qt清理
        logger.info("立即强制退出应用程序")
        try:
            os._exit(0)
        except:
            # 如果os._exit失败，尝试其他方法
            try:
                import sys
                sys.exit(0)
            except:
                # 最后的手段
                import signal
                os.kill(os.getpid(), signal.SIGTERM)
                
    except Exception as e:
        logger.error(f"清理资源时出错: {e}")
        # 即使清理失败也要强制退出
        try:
            os._exit(1)
        except:
            pass

def main():
    """主入口函数"""
    global app, loop, game_limiter, window
    
    # 处理命令行参数 - 版本覆盖测试
    test_version = None
    for i, arg in enumerate(sys.argv):
        if arg == "--test-version" and i + 1 < len(sys.argv):
            test_version = sys.argv[i + 1]
            logger.info(f"🧪 测试模式：版本覆盖为 {test_version}")
            break
        elif arg.startswith("--test-version="):
            test_version = arg.split("=", 1)[1]
            logger.info(f"🧪 测试模式：版本覆盖为 {test_version}")
            break
    
    # 如果有测试版本，动态修改version模块
    if test_version:
        try:
            import version
            # 保存原始版本
            original_version = version.__version__
            # 覆盖版本
            version.__version__ = test_version
            version.VERSION_INFO["major"], version.VERSION_INFO["minor"], version.VERSION_INFO["patch"] = map(int, test_version.split('.'))
            logger.info(f"✅ 版本已覆盖：{original_version} -> {test_version}")
        except Exception as e:
            logger.error(f"❌ 版本覆盖失败: {e}")
    
    start_time = time.time()
    logger.info("应用程序启动")
    
    try:
        # 首先检查单实例
        logger.info("检查单实例...")
        from logic.single_instance import check_single_instance, show_already_running_message
        
        instance_manager = check_single_instance("GameControl")
        if instance_manager is None:
            logger.warning("检测到程序已在运行，退出当前实例")
            show_already_running_message()
            sys.exit(1)
        
        logger.info("单实例检查通过，继续启动程序")
        
        # 注册退出时的清理函数
        def cleanup_with_instance():
            try:
                cleanup_resources()
            finally:
                # 确保释放单实例锁
                if instance_manager:
                    instance_manager.release_lock()
        
        atexit.register(cleanup_with_instance)
        
        # 创建应用程序
        app = QApplication(sys.argv)
        app.setApplicationName("GameTimeLimiter")
        
        # 设置鼠标相关参数，防止退出后鼠标行为异常
        logger.info("设置鼠标参数...")
        app.setDoubleClickInterval(400)  # 设置双击间隔为400ms
        app.setStartDragDistance(4)      # 设置拖拽距离
        app.setStartDragTime(500)        # 设置拖拽时间

        # 创建启动画面
        splash_pixmap = QPixmap("app.ico") if hasattr(sys, 'frozen') else None
        splash = None
        
        if splash_pixmap and not splash_pixmap.isNull():
            splash = QSplashScreen(splash_pixmap)
            splash.show()
            app.processEvents()
            splash.showMessage("正在加载应用程序...", Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, Qt.GlobalColor.white)
        
        # 延迟导入其他模块，这样可以更快地显示启动画面
        def load_app():
            nonlocal splash
            global loop, game_limiter, window
            
            try:
                # 显示加载消息
                if splash:
                    splash.showMessage("正在加载UI样式...", Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, Qt.GlobalColor.white)
                    app.processEvents()

                # 延迟导入UI样式模块
                from ui.base import apply_dark_style
                apply_dark_style(app)
                
                if splash:
                    splash.showMessage("正在加载事件循环...", Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, Qt.GlobalColor.white)
                    app.processEvents()
                
                # 延迟导入事件循环模块
                import qasync
                
                # 设置qasync循环
                loop = qasync.QEventLoop(app)
                asyncio.set_event_loop(loop)
                
                if splash:
                    splash.showMessage("正在加载主窗口...", Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, Qt.GlobalColor.white)
                    app.processEvents()
                
                # 延迟导入主窗口和游戏限制器模块
                from logic.game_limiter import GameLimiter
                from ui.main_window import MainWindow

                # 创建并初始化GameLimiter
                async def initialize_game_limiter():
                    global game_limiter
                    game_limiter = GameLimiter()
                    await game_limiter.initialize()
                    return game_limiter

                # 初始化并创建主窗口
                async def create_and_show_window():
                    global window
                    # 初始化游戏限制器
                    game_limiter = await initialize_game_limiter()
                    
                    # 创建主窗口
                    window = MainWindow(game_limiter)
                    
                    # 在退出时记录
                    app.aboutToQuit.connect(lambda: logger.info("应用程序退出"))
                    
                    # 显示主窗口
                    window.show()
                    
                    # 如果有启动画面，关闭它
                    if splash:
                        splash.finish(window)
                    
                    # 记录启动时间
                    logger.info(f"应用程序启动完成，耗时: {time.time() - start_time:.2f} 秒")
                    
                    # 记录应用启动事件
                    try:
                        event_logger = get_event_logger()
                        event_logger.log_app_started()
                    except Exception as e:
                        logger.error(f"记录应用启动事件时出错: {e}")

                # 使用asyncio运行初始化任务
                with loop:
                    loop.run_until_complete(create_and_show_window())
                    loop.run_forever()
                    
            except Exception as e:
                logger.error(f"加载应用程序时出错: {e}", exc_info=True)
                if splash:
                    splash.close()
                sys.exit(1)
        
        # 使用短延迟让启动画面能够显示
        if splash:
            app.processEvents()
            # 使用QTimer延迟执行，不阻塞UI
            QTimer.singleShot(100, load_app)
        else:
            # 如果没有启动画面，直接加载
            load_app()
        
        return app.exec()
        
    except Exception as e:
        logger.error(f"应用程序初始化失败: {e}", exc_info=True)
        cleanup_resources()
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main()) 
    except Exception as e:
        logger = logging.getLogger("GameTimeLimiter")
        logger.error(f"应用程序异常退出: {e}", exc_info=True)
        cleanup_resources()
        sys.exit(1) 