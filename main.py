import sys
import time
import logging
import asyncio
from PyQt6.QtWidgets import QApplication, QSplashScreen
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt, QTimer
from ui.main_window import MainWindow

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

def main():
    """主入口函数"""
    start_time = time.time()
    logger.info("应用程序启动")
    
    # 创建应用程序
    app = QApplication(sys.argv)
    app.setApplicationName("GameTimeLimiter")

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

        # 创建并初始化GameLimiter
        async def initialize_game_limiter():
            game_limiter = GameLimiter()
            await game_limiter.initialize()
            return game_limiter

        # 初始化并创建主窗口
        async def create_and_show_window():
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

        # 使用asyncio运行初始化任务
        with loop:
            loop.run_until_complete(create_and_show_window())
            loop.run_forever()
    
    # 使用短延迟让启动画面能够显示
    if splash:
        app.processEvents()
        # 使用QTimer延迟执行，不阻塞UI
        QTimer.singleShot(100, load_app)
    else:
        # 如果没有启动画面，直接加载
        load_app()
    
    return app.exec()

if __name__ == "__main__":
    try:
        sys.exit(main()) 
    except Exception as e:
        logger = logging.getLogger("GameTimeLimiter")
        logger.error(f"应用程序异常退出: {e}", exc_info=True)
        sys.exit(1) 