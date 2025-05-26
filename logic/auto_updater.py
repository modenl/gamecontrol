import os
import sys
import json
import shutil
import tempfile
import subprocess
import logging
import asyncio
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import httpx
import requests
from PyQt6.QtCore import QObject, pyqtSignal, QThread, QTimer
from PyQt6.QtWidgets import QMessageBox, QProgressDialog, QApplication

# 注意：不再使用 TaskManager，直接使用 asyncio.create_task
# from logic.task_manager import get_task_manager, run_task_safe

# 导入版本信息
try:
    from version import (
        __version__, 
        GITHUB_RELEASES_URL, 
        UPDATE_CHECK_INTERVAL,
        UPDATE_DOWNLOAD_TIMEOUT,
        UPDATE_BACKUP_ENABLED,
        is_newer_version,
        APP_DISPLAY_NAME
    )
except ImportError:
    # 如果版本文件不存在，使用默认值
    __version__ = "1.0.0"
    GITHUB_RELEASES_URL = "https://api.github.com/repos/yourusername/gamecontrol/releases"
    UPDATE_CHECK_INTERVAL = 24 * 60 * 60
    UPDATE_DOWNLOAD_TIMEOUT = 300
    UPDATE_BACKUP_ENABLED = True
    APP_DISPLAY_NAME = "Game Time Limiter"
    
    def is_newer_version(current, new):
        return current != new

logger = logging.getLogger(__name__)


class UpdateInfo:
    """更新信息类"""
    
    def __init__(self, version: str, download_url: str, release_notes: str, 
                 published_at: str, asset_name: str, asset_size: int):
        self.version = version
        self.download_url = download_url
        self.release_notes = release_notes
        self.published_at = published_at
        self.asset_name = asset_name
        self.asset_size = asset_size
    
    def __str__(self):
        return f"UpdateInfo(version={self.version}, size={self.asset_size})"


class UpdateChecker(QObject):
    """更新检查器 - 在后台线程中运行"""
    
    # 信号定义
    update_available = pyqtSignal(object)  # UpdateInfo对象
    no_update_available = pyqtSignal()
    check_failed = pyqtSignal(str)  # 错误信息
    
    def __init__(self):
        super().__init__()
        self.client = None
    
    async def check_for_updates(self) -> Optional[UpdateInfo]:
        """检查是否有可用更新
        
        Returns:
            UpdateInfo: 如果有更新可用，返回更新信息；否则返回None
        """
        try:
            logger.info("🔍 UpdateChecker 开始检查更新...")
            logger.info(f"📋 当前版本: {__version__}")
            logger.info(f"🔗 GitHub API URL: {GITHUB_RELEASES_URL}/latest")
            
            # 创建HTTP客户端
            if not self.client:
                logger.info("📡 创建HTTP客户端...")
                self.client = httpx.AsyncClient(
                    timeout=30.0,
                    follow_redirects=True  # 自动跟随重定向
                )
                logger.info("✅ HTTP客户端创建成功")
            
            # 获取最新发布信息
            logger.info("🌐 请求GitHub API...")
            response = await self.client.get(f"{GITHUB_RELEASES_URL}/latest")
            logger.info(f"📡 API响应状态: {response.status_code}")
            
            response.raise_for_status()
            
            release_data = response.json()
            latest_version = release_data["tag_name"].lstrip("v")  # 移除v前缀
            
            logger.info(f"📋 当前版本: {__version__}")
            logger.info(f"📋 最新版本: {latest_version}")
            logger.info(f"📅 发布时间: {release_data['published_at']}")
            logger.info(f"📦 资源数量: {len(release_data['assets'])}")
            
            # 检查是否有新版本
            if not is_newer_version(__version__, latest_version):
                logger.info("ℹ️ 当前已是最新版本")
                return None
            
            logger.info("🎉 发现新版本可用!")
            
            # 查找Windows可执行文件
            logger.info("🔍 查找Windows版本资源...")
            windows_asset = None
            for i, asset in enumerate(release_data["assets"]):
                asset_name = asset["name"].lower()
                logger.info(f"   资源 {i+1}: {asset['name']} ({asset['size']:,} 字节)")
                
                if (asset_name.endswith(".exe") or 
                    asset_name.endswith(".zip") and "windows" in asset_name):
                    windows_asset = asset
                    logger.info(f"✅ 找到Windows资源: {asset['name']}")
                    break
            
            if not windows_asset:
                logger.warning("⚠️ 未找到Windows版本的下载文件")
                return None
            
            # 创建更新信息
            update_info = UpdateInfo(
                version=latest_version,
                download_url=windows_asset["browser_download_url"],
                release_notes=release_data.get("body", ""),
                published_at=release_data["published_at"],
                asset_name=windows_asset["name"],
                asset_size=windows_asset["size"]
            )
            
            logger.info(f"📦 更新信息创建成功:")
            logger.info(f"   版本: {update_info.version}")
            logger.info(f"   文件: {update_info.asset_name}")
            logger.info(f"   大小: {update_info.asset_size:,} 字节")
            logger.info(f"   URL: {update_info.download_url}")
            
            return update_info
            
        except httpx.HTTPError as e:
            error_msg = f"网络请求失败: {e}"
            logger.error(error_msg)
            raise Exception(error_msg)
        except json.JSONDecodeError as e:
            error_msg = f"解析响应数据失败: {e}"
            logger.error(error_msg)
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"检查更新失败: {e}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    async def close(self):
        """关闭HTTP客户端"""
        if self.client:
            await self.client.aclose()
            self.client = None


class UpdateDownloader(QObject):
    """更新下载器"""
    
    # 信号定义
    download_progress = pyqtSignal(int, int)  # 已下载字节数, 总字节数
    download_completed = pyqtSignal(str)      # 下载完成的文件路径
    download_failed = pyqtSignal(str)         # 错误信息
    
    def __init__(self):
        super().__init__()
        self.client = None
        self.cancelled = False
    
    def cancel_download(self):
        """取消下载"""
        self.cancelled = True
    
    def _emit_progress(self, downloaded, total):
        """发送进度信号的辅助方法"""
        self.download_progress.emit(downloaded, total)
    
    async def download_update(self, update_info: UpdateInfo) -> str:
        """下载更新文件
        
        Args:
            update_info: 更新信息
            
        Returns:
            str: 下载的文件路径
        """
        try:
            logger.info(f"开始下载更新: {update_info.asset_name}")
            
            # 创建临时目录
            temp_dir = tempfile.mkdtemp(prefix="gamecontrol_update_")
            download_path = os.path.join(temp_dir, update_info.asset_name)
            
            # 使用requests进行下载，它对重定向处理更好
            logger.info("使用requests库进行下载以更好地处理重定向...")
            
            # 在线程池中运行同步下载
            import concurrent.futures
            import threading
            
            def sync_download():
                """同步下载函数"""
                with requests.Session() as session:
                    session.headers.update({
                        'User-Agent': 'GameTimeLimiter-AutoUpdater/1.0'
                    })
                    
                    # 开始下载
                    response = session.get(
                        update_info.download_url, 
                        stream=True,
                        timeout=UPDATE_DOWNLOAD_TIMEOUT,
                        allow_redirects=True
                    )
                    response.raise_for_status()
                    
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded_size = 0
                    
                    with open(download_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if self.cancelled:
                                logger.info("下载被用户取消")
                                raise Exception("下载被用户取消")
                            
                            if chunk:  # 过滤掉保持连接的chunk
                                f.write(chunk)
                                downloaded_size += len(chunk)
                                
                                # 发送进度信号（使用简单的方式）
                                # 由于在线程中，我们需要使用QTimer来在主线程中发送信号
                                from PyQt6.QtCore import QTimer
                                QTimer.singleShot(0, lambda: self.download_progress.emit(downloaded_size, total_size))
                    
                    return download_path
            
            # 在线程池中运行下载
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                download_path = await loop.run_in_executor(executor, sync_download)
            
            logger.info(f"下载完成: {download_path}")
            return download_path
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 302:
                error_msg = f"重定向错误 (302): 可能是网络或权限问题。请稍后重试。"
                logger.error(f"HTTP 302 重定向错误: {e}")
                logger.error(f"请求URL: {e.request.url}")
                if hasattr(e.response, 'headers') and 'location' in e.response.headers:
                    logger.error(f"重定向到: {e.response.headers['location']}")
            else:
                error_msg = f"HTTP错误 {e.response.status_code}: {e}"
                logger.error(error_msg)
            
            # 清理临时文件
            if 'download_path' in locals() and os.path.exists(download_path):
                try:
                    os.remove(download_path)
                except:
                    pass
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"下载失败: {e}"
            logger.error(error_msg)
            # 清理临时文件
            if 'download_path' in locals() and os.path.exists(download_path):
                try:
                    os.remove(download_path)
                except:
                    pass
            raise Exception(error_msg)
    
    async def close(self):
        """关闭HTTP客户端"""
        if self.client:
            await self.client.aclose()
            self.client = None


class AutoUpdater(QObject):
    """自动更新管理器"""
    
    # 信号定义
    update_check_started = pyqtSignal()
    update_available = pyqtSignal(object)     # UpdateInfo对象
    no_update_available = pyqtSignal()
    update_check_failed = pyqtSignal(str)
    update_installed = pyqtSignal()
    update_failed = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        
        # 创建组件
        self.checker = UpdateChecker()
        self.downloader = UpdateDownloader()
        
        # 连接信号
        self.checker.update_available.connect(self.on_update_available)
        self.checker.no_update_available.connect(self.on_no_update_available)
        self.checker.check_failed.connect(self.on_check_failed)
        
        # 任务管理 - 直接使用 asyncio.Task 而不是 TaskManager
        self._check_task = None
        self._check_task_id = None
        self._download_task = None
        self._download_task_id = None
        
        # 加载上次检查时间
        self.last_check_time = self.load_last_check_time()
        
        # 设置定时检查
        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self.check_for_updates_if_needed)
        self.check_timer.start(60 * 60 * 1000)  # 每小时检查一次
    
    def load_last_check_time(self):
        """加载上次检查时间"""
        try:
            settings_file = "update_settings.json"
            if os.path.exists(settings_file):
                with open(settings_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    last_check_str = data.get("last_check_time")
                    if last_check_str:
                        self.last_check_time = datetime.fromisoformat(last_check_str)
        except Exception as e:
            logger.warning(f"加载上次检查时间失败: {e}")
    
    def save_last_check_time(self):
        """保存上次检查时间"""
        try:
            settings_file = "update_settings.json"
            data = {
                "last_check_time": datetime.now().isoformat(),
                "current_version": __version__
            }
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"保存检查时间失败: {e}")
    
    def should_check_for_updates(self) -> bool:
        """检查是否应该检查更新"""
        if not self.last_check_time:
            return True
        
        time_since_last_check = datetime.now() - self.last_check_time
        return time_since_last_check.total_seconds() >= UPDATE_CHECK_INTERVAL
    
    def can_update_now(self) -> Tuple[bool, str]:
        """检查当前是否可以进行更新
        
        Returns:
            Tuple[bool, str]: (是否可以更新, 不能更新的原因)
        """
        if not self.parent:
            return True, ""
        
        # 检查是否有活动的游戏会话
        if hasattr(self.parent, 'session_active') and self.parent.session_active:
            return False, "游戏会话正在进行中，无法更新"
        
        # 检查是否有数学练习窗口打开
        if hasattr(self.parent, 'math_panel') and self.parent.math_panel:
            return False, "数学练习正在进行中，无法更新"
        
        return True, ""
    
    def check_for_updates_if_needed(self):
        """如果需要，检查更新"""
        if self.should_check_for_updates():
            self.check_for_updates()
    
    def check_for_updates(self, manual=False):
        """检查更新（异步）
        
        Args:
            manual: 是否为手动检查
        """
        logger.info(f"🔍 检查更新请求: manual={manual}")
        
        # 检查是否需要更新
        should_check = manual or self.should_check_for_updates()
        logger.info(f"📋 是否需要检查: {should_check}")
        
        if should_check:
            logger.info("🚀 开始检查更新...")
            self.update_check_started.emit()
            
            # 检查是否已有检查任务在运行
            if self._check_task and not self._check_task.done():
                logger.warning("⚠️ 更新检查任务已在运行中，跳过此次请求")
                return
            
            logger.info("📝 创建更新检查任务...")
            # 直接使用 asyncio.create_task 而不是 TaskManager
            # 因为 TaskManager 在 qasync 环境中有兼容性问题
            try:
                loop = asyncio.get_event_loop()
                self._check_task = asyncio.create_task(self._async_check_for_updates())
                self._check_task_id = "update_check"
                logger.info(f"✅ 直接创建更新检查任务: {self._check_task_id}")
            except Exception as e:
                logger.error(f"❌ 创建更新检查任务失败: {e}")
                self._handle_check_error(e)
            logger.info(f"✅ 更新检查任务已创建: {self._check_task_id}")
        else:
            logger.info("ℹ️ 不需要检查更新（时间间隔未到）")
    
    def _handle_check_error(self, error):
        """处理检查错误"""
        logger.error(f"❌ 更新检查任务失败: {error}")
        self.update_check_failed.emit(str(error))
    
    async def _async_check_for_updates(self):
        """异步检查更新"""
        try:
            logger.info("🌐 开始异步检查更新...")
            
            # 检查网络连接
            logger.info("📡 检查网络连接...")
            
            update_info = await self.checker.check_for_updates()
            logger.info("✅ 更新检查完成")
            
            # 保存检查时间
            self.last_check_time = datetime.now()
            self.save_last_check_time()
            logger.info(f"💾 保存检查时间: {self.last_check_time}")
            
            if update_info:
                logger.info(f"🎉 发现新版本: {update_info.version}")
                # 使用 QTimer.singleShot 在主线程中发送信号
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(0, lambda: self.update_available.emit(update_info))
            else:
                logger.info("ℹ️ 当前版本是最新的")
                # 使用 QTimer.singleShot 在主线程中发送信号
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(0, lambda: self.no_update_available.emit())
                
        except Exception as e:
            logger.error(f"❌ 异步检查更新失败: {e}", exc_info=True)
            # 使用 QTimer.singleShot 在主线程中发送信号
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self.update_check_failed.emit(str(e)))
    
    def on_update_available(self, update_info: UpdateInfo):
        """处理发现更新"""
        logger.info(f"发现新版本: {update_info.version}")
        
        # 检查是否可以更新
        can_update, reason = self.can_update_now()
        if not can_update:
            logger.info(f"当前无法更新: {reason}")
            # 可以选择稍后提醒用户
            return
        
        # 显示更新对话框
        self.show_update_dialog(update_info)
    
    def on_no_update_available(self):
        """处理无更新可用"""
        logger.info("当前已是最新版本")
    
    def on_check_failed(self, error_msg: str):
        """处理检查失败"""
        logger.error(f"检查更新失败: {error_msg}")
        self.update_check_failed.emit(error_msg)
    
    def show_update_dialog(self, update_info: UpdateInfo):
        """显示更新对话框"""
        try:
            logger.info("📋 开始显示更新对话框...")
            logger.info(f"   版本: {update_info.version}")
            logger.info(f"   文件: {update_info.asset_name}")
            
            # 格式化文件大小
            size_mb = update_info.asset_size / (1024 * 1024)
            size_text = f"{size_mb:.1f} MB"
            logger.info(f"   大小: {size_text}")
            
            # 格式化发布时间
            try:
                pub_date = datetime.fromisoformat(update_info.published_at.replace('Z', '+00:00'))
                date_text = pub_date.strftime("%Y-%m-%d")
            except:
                date_text = "未知"
            logger.info(f"   发布日期: {date_text}")
            
            # 构建消息文本
            message = f"""
发现新版本可用！

当前版本: {__version__}
最新版本: {update_info.version}
发布日期: {date_text}
文件大小: {size_text}

更新内容:
{update_info.release_notes[:500]}{'...' if len(update_info.release_notes) > 500 else ''}

是否现在下载并安装更新？
注意：更新过程中程序将会重启。
            """.strip()
            
            logger.info("💬 显示更新确认对话框...")
            
            # 显示确认对话框
            reply = QMessageBox.question(
                self.parent,
                f"{APP_DISPLAY_NAME} - 发现新版本",
                message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            logger.info(f"👤 用户选择: {'Yes' if reply == QMessageBox.StandardButton.Yes else 'No'}")
            
            if reply == QMessageBox.StandardButton.Yes:
                logger.info("🚀 用户确认更新，开始更新过程...")
                self.start_update_process(update_info)
            else:
                logger.info("❌ 用户取消更新")
                
        except Exception as e:
            logger.error(f"❌ 显示更新对话框失败: {e}", exc_info=True)
    
    def start_update_process(self, update_info: UpdateInfo):
        """开始更新过程"""
        try:
            logger.info("🚀 开始更新过程...")
            logger.info(f"📦 准备下载: {update_info.asset_name}")
            logger.info(f"📏 文件大小: {update_info.asset_size:,} 字节")
            logger.info(f"🔗 下载地址: {update_info.download_url}")
            
            # 检查是否已有下载任务在运行
            if self._download_task and not self._download_task.done():
                logger.warning("⚠️ 下载任务已在运行中，跳过此次请求")
                QMessageBox.warning(
                    self.parent,
                    "下载进行中",
                    "已有下载任务在进行中，请等待完成后再试。"
                )
                return
            
            # 创建进度对话框
            progress_dialog = QProgressDialog(
                "正在下载更新...", "取消", 0, 100, self.parent
            )
            progress_dialog.setWindowTitle(f"{APP_DISPLAY_NAME} - 下载更新")
            progress_dialog.setModal(True)
            progress_dialog.show()
            
            # 连接下载器信号
            self.downloader.download_progress.connect(
                lambda downloaded, total: self.update_download_progress(
                    progress_dialog, downloaded, total
                )
            )
            self.downloader.download_completed.connect(
                lambda path: self.on_download_completed(progress_dialog, path)
            )
            self.downloader.download_failed.connect(
                lambda error: self.on_download_failed(progress_dialog, error)
            )
            
            # 处理取消按钮
            progress_dialog.canceled.connect(self._cancel_download)
            
            # 直接使用 asyncio.create_task 开始下载
            try:
                loop = asyncio.get_event_loop()
                self._download_task = asyncio.create_task(self._start_download_task(update_info))
                self._download_task_id = "update_download"
                logger.info(f"✅ 直接创建下载任务: {self._download_task_id}")
            except Exception as e:
                logger.error(f"❌ 创建下载任务失败: {e}")
                QMessageBox.critical(
                    self.parent,
                    "下载失败",
                    f"创建下载任务失败: {e}"
                )
            
        except Exception as e:
            logger.error(f"启动更新过程失败: {e}")
            QMessageBox.critical(
                self.parent,
                "更新失败",
                f"启动更新过程失败: {e}"
            )
    
    async def _start_download_task(self, update_info: UpdateInfo):
        """启动下载任务的异步包装器"""
        try:
            logger.info(f"🚀 开始下载任务: {update_info.asset_name}")
            download_path = await self.downloader.download_update(update_info)
            logger.info(f"✅ 下载完成: {download_path}")
            
            # 使用 QTimer.singleShot 在主线程中发送信号
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self.downloader.download_completed.emit(download_path))
            
        except Exception as e:
            logger.error(f"❌ 下载任务失败: {e}")
            # 使用 QTimer.singleShot 在主线程中发送信号
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self.downloader.download_failed.emit(str(e)))
    
    def _cancel_download(self):
        """取消下载"""
        self.downloader.cancel_download()
        if self._download_task and not self._download_task.done():
            self._download_task.cancel()
            logger.info("下载任务已取消")
    
    def update_download_progress(self, progress_dialog, downloaded, total):
        """更新下载进度"""
        if total > 0:
            percentage = int((downloaded / total) * 100)
            progress_dialog.setValue(percentage)
            
            # 更新标签文本
            downloaded_mb = downloaded / (1024 * 1024)
            total_mb = total / (1024 * 1024)
            progress_dialog.setLabelText(
                f"正在下载更新... {downloaded_mb:.1f}/{total_mb:.1f} MB ({percentage}%)"
            )
    
    def on_download_completed(self, progress_dialog, download_path):
        """下载完成处理"""
        progress_dialog.close()
        
        try:
            logger.info(f"下载完成: {download_path}")
            
            # 安装更新
            self.install_update(download_path)
            
        except Exception as e:
            logger.error(f"安装更新失败: {e}")
            QMessageBox.critical(
                self.parent,
                "更新失败",
                f"安装更新失败: {e}"
            )
    
    def on_download_failed(self, progress_dialog, error_msg):
        """下载失败处理"""
        progress_dialog.close()
        
        logger.error(f"下载失败: {error_msg}")
        QMessageBox.critical(
            self.parent,
            "下载失败",
            f"下载更新失败: {error_msg}"
        )
    
    def install_update(self, update_file_path: str):
        """安装更新
        
        Args:
            update_file_path: 更新文件路径
        """
        try:
            logger.info("开始安装更新...")
            
            # 获取当前可执行文件路径
            if hasattr(sys, 'frozen'):
                current_exe = sys.executable
            else:
                current_exe = os.path.abspath(sys.argv[0])
            
            current_dir = os.path.dirname(current_exe)
            
            # 备份当前版本（如果启用）
            backup_path = None
            if UPDATE_BACKUP_ENABLED:
                backup_path = self.create_backup(current_exe)
                logger.info(f"已备份当前版本到: {backup_path}")
            
            # 创建更新脚本
            update_script = self.create_update_script(
                update_file_path, current_exe, current_dir, backup_path
            )
            
            # 显示最后确认
            reply = QMessageBox.question(
                self.parent,
                "准备安装更新",
                "更新文件已下载完成，程序将重启以完成安装。\n\n确定要继续吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # 执行更新脚本并退出程序
                logger.info("执行更新脚本并退出程序...")
                subprocess.Popen([update_script], shell=True)
                
                # 发送更新安装信号
                self.update_installed.emit()
                
                # 退出应用程序
                QApplication.quit()
            
        except Exception as e:
            logger.error(f"安装更新失败: {e}")
            self.update_failed.emit(str(e))
            QMessageBox.critical(
                self.parent,
                "安装失败",
                f"安装更新失败: {e}"
            )
    
    def create_backup(self, current_exe: str) -> str:
        """创建当前版本的备份
        
        Args:
            current_exe: 当前可执行文件路径
            
        Returns:
            str: 备份文件路径
        """
        backup_dir = os.path.join(os.path.dirname(current_exe), "backup")
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"GameTimeLimiter_v{__version__}_{timestamp}.exe"
        backup_path = os.path.join(backup_dir, backup_name)
        
        shutil.copy2(current_exe, backup_path)
        return backup_path
    
    def create_update_script(self, update_file: str, current_exe: str, 
                           current_dir: str, backup_path: Optional[str]) -> str:
        """创建更新脚本
        
        Args:
            update_file: 更新文件路径
            current_exe: 当前可执行文件路径
            current_dir: 当前目录
            backup_path: 备份文件路径
            
        Returns:
            str: 更新脚本路径
        """
        script_path = os.path.join(tempfile.gettempdir(), "gamecontrol_update.bat")
        
        script_content = f"""@echo off
echo Starting GameTimeLimiter update process...

REM Wait for main process to exit
timeout /t 3 /nobreak >nul

REM Check if update file is ZIP or EXE
if /i "%~x1"==".zip" (
    echo Extracting update from ZIP file...
    powershell -command "Expand-Archive -Path '{update_file}' -DestinationPath '{current_dir}' -Force"
    if errorlevel 1 (
        echo Failed to extract update
        pause
        exit /b 1
    )
) else (
    echo Installing update executable...
    copy /y "{update_file}" "{current_exe}"
    if errorlevel 1 (
        echo Failed to copy update file
        if exist "{backup_path}" (
            echo Restoring backup...
            copy /y "{backup_path}" "{current_exe}"
        )
        pause
        exit /b 1
    )
)

REM Clean up temporary files
del /q "{update_file}" 2>nul

echo Update completed successfully!
echo Restarting application...

REM Start the updated application
start "" "{current_exe}"

REM Clean up this script
del /q "%~f0" 2>nul
"""
        
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        return script_path
    
    async def close(self):
        """关闭更新器"""
        try:
            logger.info("关闭自动更新器...")
            
            # 停止定时器
            self.check_timer.stop()
            
            # 取消正在运行的任务
            if self._check_task and not self._check_task.done():
                self._check_task.cancel()
                logger.info("检查更新任务已取消")
            
            if self._download_task and not self._download_task.done():
                self._download_task.cancel()
                logger.info("下载任务已取消")
            
            # 关闭组件
            await self.checker.close()
            await self.downloader.close()
            
            logger.info("自动更新器已关闭")
            
        except Exception as e:
            logger.error(f"关闭更新器失败: {e}")


# 全局更新器实例
_updater_instance = None

def get_updater(parent=None) -> AutoUpdater:
    """获取全局更新器实例"""
    global _updater_instance
    if _updater_instance is None:
        _updater_instance = AutoUpdater(parent)
    return _updater_instance 