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
import requests
from PyQt6.QtCore import QObject, pyqtSignal, QThread, QTimer
from PyQt6.QtWidgets import QMessageBox, QProgressDialog, QApplication

# 使用线程池执行异步任务，避免qasync兼容性问题

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
    __version__ = "1.0.1"
    GITHUB_RELEASES_URL = "https://api.github.com/repos/yourusername/gamecontrol/releases"
    UPDATE_CHECK_INTERVAL = 24 * 60 * 60
    UPDATE_DOWNLOAD_TIMEOUT = 300
    UPDATE_BACKUP_ENABLED = True
    APP_DISPLAY_NAME = "Game Time Limiter"
    
    def is_newer_version(current, new):
        """检查新版本是否比当前版本更新
        
        Args:
            current (str): 当前版本，格式如 "1.0.4"
            new (str): 新版本，格式如 "1.0.3"
        
        Returns:
            bool: 如果新版本更新则返回True
        """
        def parse_version(version_str):
            # 移除v前缀和预发布信息，只比较主版本号
            clean_version = version_str.lstrip('v').split('-')[0].split('+')[0]
            return tuple(map(int, clean_version.split('.')))
        
        try:
            current_tuple = parse_version(current)
            new_tuple = parse_version(new)
            return new_tuple > current_tuple
        except (ValueError, AttributeError) as e:
            logger.warning(f"版本比较失败: current={current}, new={new}, error={e}")
            return False

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
            
            # 使用requests库进行同步请求，避免qasync兼容性问题
            import requests
            import concurrent.futures
            
            def sync_request():
                """同步HTTP请求，带重试机制"""
                import time
                max_retries = 3
                retry_delay = 2  # 秒
                
                for attempt in range(max_retries):
                    try:
                        logger.info(f"🌐 请求GitHub API... (尝试 {attempt + 1}/{max_retries})")
                        response = requests.get(
                            f"{GITHUB_RELEASES_URL}/latest",
                            timeout=30,
                            headers={'User-Agent': 'GameTimeLimiter-AutoUpdater/1.0'}
                        )
                        logger.info(f"📡 API响应状态: {response.status_code}")
                        
                        # 检查是否是临时错误（5xx）
                        if response.status_code >= 500:
                            if attempt < max_retries - 1:
                                logger.warning(f"⚠️ 服务器错误 {response.status_code}，{retry_delay}秒后重试...")
                                time.sleep(retry_delay)
                                retry_delay *= 2  # 指数退避
                                continue
                        
                        response.raise_for_status()
                        return response.json()
                        
                    except requests.exceptions.Timeout as e:
                        if attempt < max_retries - 1:
                            logger.warning(f"⚠️ 请求超时，{retry_delay}秒后重试...")
                            time.sleep(retry_delay)
                            retry_delay *= 2
                            continue
                        else:
                            raise e
                    except requests.exceptions.ConnectionError as e:
                        if attempt < max_retries - 1:
                            logger.warning(f"⚠️ 连接错误，{retry_delay}秒后重试...")
                            time.sleep(retry_delay)
                            retry_delay *= 2
                            continue
                        else:
                            raise e
                
                # 如果所有重试都失败了，抛出最后一个异常
                raise Exception("所有重试尝试都失败了")
            
            # 在线程池中运行同步请求
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                release_data = await loop.run_in_executor(executor, sync_request)
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
            
        except requests.exceptions.Timeout as e:
            error_msg = "网络连接超时，请检查网络连接后重试"
            logger.error(f"请求超时: {e}")
            raise Exception(error_msg)
        except requests.exceptions.ConnectionError as e:
            error_msg = "无法连接到GitHub服务器，请检查网络连接"
            logger.error(f"连接错误: {e}")
            raise Exception(error_msg)
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                error_msg = "未找到更新信息，可能仓库配置有误"
            elif e.response.status_code >= 500:
                error_msg = "GitHub服务器暂时不可用，请稍后重试"
            else:
                error_msg = f"服务器返回错误: {e.response.status_code}"
            logger.error(f"HTTP错误: {e}")
            raise Exception(error_msg)
        except requests.RequestException as e:
            error_msg = f"网络请求失败: {e}"
            logger.error(error_msg)
            raise Exception(error_msg)
        except json.JSONDecodeError as e:
            error_msg = "服务器返回的数据格式错误"
            logger.error(f"JSON解析失败: {e}")
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"检查更新失败: {e}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    async def close(self):
        """关闭HTTP客户端"""
        # 使用requests库，无需特殊关闭操作
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
                    logger.info(f"📏 开始下载，总大小: {total_size:,} 字节")
                    
                    with open(download_path, 'wb') as f:
                        chunk_count = 0
                        for chunk in response.iter_content(chunk_size=8192):
                            if self.cancelled:
                                logger.info("下载被用户取消")
                                raise Exception("下载被用户取消")
                            
                            if chunk:  # 过滤掉保持连接的chunk
                                f.write(chunk)
                                downloaded_size += len(chunk)
                                chunk_count += 1
                                
                                # 每10个chunk更新一次进度，减少信号发送频率
                                if chunk_count % 10 == 0 or downloaded_size >= total_size:
                                    # 直接发送信号，Qt会自动处理线程安全
                                    try:
                                        percentage = int((downloaded_size / total_size) * 100) if total_size > 0 else 0
                                        logger.info(f"📊 下载进度: {downloaded_size:,}/{total_size:,} 字节 ({percentage}%)")
                                        self.download_progress.emit(downloaded_size, total_size)
                                    except Exception as e:
                                        logger.warning(f"发送进度信号失败: {e}")
                        
                        # 确保最终进度为100%
                        if downloaded_size > 0:
                            self.download_progress.emit(downloaded_size, total_size)
                    
                    return download_path
            
            # 在线程池中运行下载
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                download_path = await loop.run_in_executor(executor, sync_download)
            
            logger.info(f"下载完成: {download_path}")
            return download_path
                
        except requests.HTTPError as e:
            error_msg = f"HTTP错误: {e}"
            logger.error(error_msg)
            
            # 清理临时文件
            if 'download_path' in locals() and os.path.exists(download_path):
                try:
                    os.remove(download_path)
                except:
                    pass
            raise Exception(error_msg)
        except requests.RequestException as e:
            error_msg = f"网络请求错误: {e}"
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
        # 使用requests库，无需特殊关闭操作
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
        
        # 连接信号 - 只连接checker的信号到处理方法
        self.checker.update_available.connect(self.on_update_available)
        self.checker.no_update_available.connect(self.on_no_update_available)
        self.checker.check_failed.connect(self.on_check_failed)
        
        # 任务状态跟踪
        self._check_task_id = None
        self._download_task_id = None
        
        # 添加手动检查标志
        self._is_manual_check = False
        
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
        
        # 保存手动检查标志
        self._is_manual_check = manual
        
        # 检查是否需要更新
        should_check = manual or self.should_check_for_updates()
        logger.info(f"📋 是否需要检查: {should_check}")
        
        if should_check:
            logger.info("🚀 开始检查更新...")
            self.update_check_started.emit()
            
            # 检查是否已有检查任务在运行
            if self._check_task_id:
                logger.warning("⚠️ 更新检查任务已在运行中，跳过此次请求")
                return
            
            logger.info("📝 创建更新检查任务...")
            # 减少延迟，50ms足够
            try:
                from PyQt6.QtCore import QTimer
                # 延迟50ms执行，减少等待时间
                QTimer.singleShot(50, lambda: self._create_check_task())
                logger.info("✅ 已安排更新检查任务")
            except Exception as e:
                logger.error(f"❌ 安排更新检查任务失败: {e}")
                self._handle_check_error(e)
        else:
            logger.info("ℹ️ 不需要检查更新（时间间隔未到）")
    
    def _create_check_task(self):
        """创建检查任务的辅助方法"""
        try:
            # 直接在线程中运行，避免qasync冲突
            import threading
            import concurrent.futures
            
            def run_check():
                """在线程中运行检查"""
                try:
                    # 创建新的事件循环
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    # 运行检查
                    result = loop.run_until_complete(self._async_check_for_updates())
                    loop.close()
                    
                except Exception as e:
                    logger.error(f"线程中检查更新失败: {e}")
                    # 在主线程中发送错误信号
                    from PyQt6.QtCore import QTimer
                    QTimer.singleShot(0, lambda: self.update_check_failed.emit(str(e)))
            
            # 在后台线程中运行
            thread = threading.Thread(target=run_check, daemon=True)
            thread.start()
            
            self._check_task_id = "update_check"
            logger.info(f"✅ 更新检查任务已创建: {self._check_task_id}")
            
            # 设置任务完成后的清理
            def clear_check_task():
                self._check_task_id = None
                logger.info("✅ 检查任务状态已清理")
            
            # 10秒后自动清理任务状态（防止状态卡住）
            QTimer.singleShot(10000, clear_check_task)
        except Exception as e:
            logger.error(f"❌ 创建更新检查任务失败: {e}")
            self._handle_check_error(e)
    
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
                logger.info(f"🎉 _async_check_for_updates发现新版本: {update_info.version}")
                logger.info(f"📋 准备通过checker信号发送到主线程...")
                
                # 直接通过checker发送信号，这样信号会正确路由到AutoUpdater.on_update_available
                try:
                    logger.info(f"🚀 通过checker.update_available.emit发送信号...")
                    self.checker.update_available.emit(update_info)
                    logger.info(f"✅ checker.update_available.emit已调用")
                    
                except Exception as e:
                    logger.error(f"❌ 通过checker发送信号失败: {e}")
                    # 备用方法：使用QTimer
                    try:
                        logger.info(f"🔄 尝试备用方法：QTimer.singleShot...")
                        from PyQt6.QtCore import QTimer
                        QTimer.singleShot(0, lambda: self.on_update_available(update_info))
                        logger.info(f"✅ QTimer.singleShot备用方法已调用")
                    except Exception as e2:
                        logger.error(f"❌ 备用方法也失败: {e2}")
                        
            else:
                logger.info("ℹ️ 当前版本是最新的")
                # 在主线程中调用处理方法
                try:
                    self.checker.no_update_available.emit()
                    logger.info("✅ no_update_available信号已发送")
                except Exception as e:
                    logger.error(f"❌ 发送no_update_available信号失败: {e}")
                
        except Exception as e:
            logger.error(f"❌ 异步检查更新失败: {e}", exc_info=True)
            # 在主线程中发送信号
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self.update_check_failed.emit(str(e)))
    
    def on_update_available(self, update_info: UpdateInfo):
        """处理发现更新"""
        logger.info(f"🎯 AutoUpdater.on_update_available 被调用!")
        logger.info(f"   新版本: {update_info.version}")
        logger.info(f"   当前parent: {self.parent}")
        logger.info(f"   parent类型: {type(self.parent).__name__ if self.parent else 'None'}")
        
        # 发送信号通知主窗口，让主窗口决定如何处理
        logger.info("📡 发送update_available信号到主窗口...")
        try:
            # 检查信号连接状态
            try:
                receivers = self.update_available.receivers()
                logger.info(f"📊 update_available信号接收者数量: {receivers}")
            except AttributeError:
                logger.info("📊 信号接收者检查跳过（PyQt6兼容性）")
            
            self.update_available.emit(update_info)
            logger.info("✅ update_available信号已发送")
        except Exception as e:
            logger.error(f"❌ 发送update_available信号失败: {e}")
        
        # 不再自动显示更新对话框，由主窗口控制
    
    def on_no_update_available(self):
        """处理无更新可用"""
        logger.info("当前已是最新版本")
        
        # 如果是手动检查，显示提示对话框
        if self._is_manual_check and self.parent:
            logger.info("📋 手动检查更新，显示'已是最新版本'提示")
            try:
                from PyQt6.QtWidgets import QMessageBox
                from datetime import datetime
                
                # 格式化当前时间
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
                
                message = f"""您当前使用的已是最新版本！

当前版本: {__version__}
检查时间: {current_time}

感谢您使用 {APP_DISPLAY_NAME}！"""
                
                QMessageBox.information(
                    self.parent,
                    f"{APP_DISPLAY_NAME} - 检查更新",
                    message
                )
                logger.info("✅ 已显示'最新版本'提示对话框")
                
            except Exception as e:
                logger.error(f"❌ 显示'最新版本'提示失败: {e}")
        
        # 重置手动检查标志
        self._is_manual_check = False
        
        # 发送信号给主窗口
        self.no_update_available.emit()
    
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
    
    def start_update_with_admin_auth(self, update_info: UpdateInfo):
        """需要管理员验证的更新流程"""
        try:
            logger.info("🔐 开始需要管理员验证的更新流程...")
            
            # 检查是否可以更新
            can_update, reason = self.can_update_now()
            logger.info(f"🔍 can_update_now结果: can_update={can_update}, reason='{reason}'")
            
            if not can_update:
                logger.warning(f"⚠️ 当前无法更新: {reason}")
                QMessageBox.warning(
                    self.parent,
                    "无法更新",
                    f"当前无法进行更新：{reason}\n\n请在游戏会话结束且没有数学练习进行时再试。"
                )
                return
            
            # 显示更新对话框
            logger.info("📋 显示更新确认对话框...")
            self.show_update_dialog(update_info)
            
        except Exception as e:
            logger.error(f"❌ 管理员验证更新流程失败: {e}", exc_info=True)
            QMessageBox.critical(
                self.parent,
                "更新失败",
                f"启动更新流程失败: {e}"
            )
    
    def start_update_process(self, update_info: UpdateInfo):
        """开始更新过程"""
        try:
            logger.info("🚀 开始更新过程...")
            logger.info(f"📦 准备下载: {update_info.asset_name}")
            logger.info(f"📏 文件大小: {update_info.asset_size:,} 字节")
            logger.info(f"🔗 下载地址: {update_info.download_url}")
            
            # 检查是否已有下载任务在运行
            if self._download_task_id:
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
            
            # 直接在线程中运行下载，避免qasync冲突
            try:
                import threading
                
                def run_download():
                    """在线程中运行下载"""
                    try:
                        # 创建新的事件循环
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        
                        # 运行下载
                        result = loop.run_until_complete(self._start_download_task(update_info))
                        loop.close()
                        
                    except Exception as e:
                        logger.error(f"线程中下载失败: {e}")
                        # 在主线程中发送错误信号
                        from PyQt6.QtCore import QTimer
                        QTimer.singleShot(0, lambda: self.downloader.download_failed.emit(str(e)))
                
                # 在后台线程中运行
                thread = threading.Thread(target=run_download, daemon=True)
                thread.start()
                
                self._download_task_id = "update_download"
                logger.info(f"✅ 下载任务已创建: {self._download_task_id}")
                
                # 设置任务完成后的清理
                def clear_download_task():
                    self._download_task_id = None
                    logger.info("✅ 下载任务状态已清理")
                
                # 30秒后自动清理任务状态（防止状态卡住）
                QTimer.singleShot(30000, clear_download_task)
            except Exception as e:
                logger.error(f"❌ 创建下载任务失败: {e}")
                progress_dialog.close()
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
            
            # 直接发送信号，Qt会自动处理线程安全
            logger.info(f"📡 发送download_completed信号: {download_path}")
            self.downloader.download_completed.emit(download_path)
            logger.info(f"✅ download_completed信号已发送")
            
        except Exception as e:
            logger.error(f"❌ 下载任务失败: {e}")
            # 直接发送信号，Qt会自动处理线程安全
            logger.info(f"📡 发送download_failed信号: {str(e)}")
            self.downloader.download_failed.emit(str(e))
            logger.info(f"✅ download_failed信号已发送")
    
    def _cancel_download(self):
        """取消下载"""
        logger.info("用户请求取消下载")
        self.downloader.cancel_download()
        logger.info("下载取消请求已发送")
    
    def update_download_progress(self, progress_dialog, downloaded, total):
        """更新下载进度"""
        logger.info(f"🔄 update_download_progress被调用: {downloaded:,}/{total:,} 字节")
        
        if total > 0:
            percentage = int((downloaded / total) * 100)
            logger.info(f"📊 设置进度条值: {percentage}%")
            progress_dialog.setValue(percentage)
            
            # 更新标签文本
            downloaded_mb = downloaded / (1024 * 1024)
            total_mb = total / (1024 * 1024)
            label_text = f"正在下载更新... {downloaded_mb:.1f}/{total_mb:.1f} MB ({percentage}%)"
            logger.info(f"📝 设置标签文本: {label_text}")
            progress_dialog.setLabelText(label_text)
        else:
            logger.warning("⚠️ total_size为0，无法计算进度")
    
    def on_download_completed(self, progress_dialog, download_path):
        """下载完成处理"""
        logger.info(f"🎯 on_download_completed被调用!")
        logger.info(f"   下载路径: {download_path}")
        logger.info(f"   进度对话框: {progress_dialog}")
        
        try:
            logger.info("🔄 关闭进度对话框...")
            progress_dialog.close()
            logger.info("✅ 进度对话框已关闭")
            
            logger.info(f"📁 验证下载文件是否存在: {download_path}")
            if os.path.exists(download_path):
                file_size = os.path.getsize(download_path)
                logger.info(f"✅ 下载文件存在，大小: {file_size:,} 字节")
            else:
                logger.error(f"❌ 下载文件不存在: {download_path}")
                raise Exception(f"下载文件不存在: {download_path}")
            
            logger.info("🚀 准备调用install_update...")
            # 安装更新
            self.install_update(download_path)
            logger.info("✅ install_update调用完成")
            
        except Exception as e:
            logger.error(f"❌ on_download_completed处理失败: {e}", exc_info=True)
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
            logger.info("🚀 开始安装更新...")
            logger.info(f"📁 更新文件路径: {update_file_path}")
            
            # 检查更新文件是否存在
            if not os.path.exists(update_file_path):
                raise Exception(f"更新文件不存在: {update_file_path}")
            
            # 获取文件大小
            file_size = os.path.getsize(update_file_path)
            logger.info(f"📏 更新文件大小: {file_size:,} 字节")
            
            # 获取当前可执行文件路径
            if hasattr(sys, 'frozen'):
                current_exe = sys.executable
                logger.info("🔧 运行环境: 打包后的可执行文件")
            else:
                current_exe = os.path.abspath(sys.argv[0])
                logger.info("🔧 运行环境: Python脚本")
            
            logger.info(f"📍 当前可执行文件: {current_exe}")
            current_dir = os.path.dirname(current_exe)
            logger.info(f"📂 当前目录: {current_dir}")
            
            # 检查当前可执行文件是否存在
            if not os.path.exists(current_exe):
                logger.warning(f"⚠️ 当前可执行文件不存在: {current_exe}")
            
            # 备份当前版本（如果启用）
            backup_path = None
            if UPDATE_BACKUP_ENABLED:
                logger.info("💾 开始创建备份...")
                backup_path = self.create_backup(current_exe)
                logger.info(f"✅ 已备份当前版本到: {backup_path}")
            else:
                logger.info("⚠️ 备份功能已禁用")
            
            # 创建更新脚本
            logger.info("📝 创建更新脚本...")
            update_script = self.create_update_script(
                update_file_path, current_exe, current_dir, backup_path
            )
            logger.info(f"✅ 更新脚本已创建: {update_script}")
            
            # 显示详细的确认信息
            update_file_name = os.path.basename(update_file_path)
            update_file_ext = os.path.splitext(update_file_path)[1].lower()
            size_mb = file_size / (1024 * 1024)
            
            message = f"""更新文件已下载完成，准备安装：

📁 文件名: {update_file_name}
📏 文件大小: {size_mb:.1f} MB
🔧 文件类型: {update_file_ext}
📍 安装位置: {current_exe}
💾 备份位置: {backup_path if backup_path else "无备份"}

程序将重启以完成安装。

确定要继续吗？"""
            
            reply = QMessageBox.question(
                self.parent,
                "准备安装更新",
                message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                logger.info("👤 用户确认安装更新")
                logger.info("🚀 执行更新脚本并退出程序...")
                logger.info(f"📝 脚本路径: {update_script}")
                
                # 执行更新脚本并退出程序
                process = subprocess.Popen([update_script], shell=True)
                logger.info(f"✅ 更新脚本已启动，进程ID: {process.pid}")
                
                # 发送更新安装信号
                self.update_installed.emit()
                
                # 给脚本一点时间启动
                import time
                time.sleep(0.5)  # 减少等待时间
                
                # 设置更新标志，跳过管理员密码验证
                if self.parent:
                    self.parent._updating = True
                    logger.info("🔧 设置更新标志，跳过管理员密码验证")
                
                # 退出应用程序
                logger.info("🔚 退出应用程序以完成更新...")
                QApplication.quit()
            else:
                logger.info("❌ 用户取消安装更新")
            
        except Exception as e:
            logger.error(f"❌ 安装更新失败: {e}", exc_info=True)
            self.update_failed.emit(str(e))
            QMessageBox.critical(
                self.parent,
                "安装失败",
                f"安装更新失败: {e}\n\n请检查日志文件获取详细信息。"
            )
    
    def create_backup(self, current_exe: str) -> str:
        """创建当前版本的备份
        
        Args:
            current_exe: 当前可执行文件路径
            
        Returns:
            str: 备份文件路径
        """
        try:
            backup_dir = os.path.join(os.path.dirname(current_exe), "backup")
            os.makedirs(backup_dir, exist_ok=True)
            logger.info(f"📂 备份目录: {backup_dir}")
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 根据当前文件类型确定备份文件名
            if current_exe.endswith('.exe'):
                backup_name = f"GameTimeLimiter_v{__version__}_{timestamp}.exe"
            elif current_exe.endswith('.py'):
                backup_name = f"main_v{__version__}_{timestamp}.py"
            else:
                # 保持原始扩展名
                base_name = os.path.basename(current_exe)
                name, ext = os.path.splitext(base_name)
                backup_name = f"{name}_v{__version__}_{timestamp}{ext}"
            
            backup_path = os.path.join(backup_dir, backup_name)
            logger.info(f"📝 备份文件名: {backup_name}")
            
            # 检查源文件是否存在
            if not os.path.exists(current_exe):
                raise Exception(f"源文件不存在: {current_exe}")
            
            # 获取源文件大小
            source_size = os.path.getsize(current_exe)
            logger.info(f"📏 源文件大小: {source_size:,} 字节")
            
            # 执行备份
            shutil.copy2(current_exe, backup_path)
            
            # 验证备份文件
            if os.path.exists(backup_path):
                backup_size = os.path.getsize(backup_path)
                logger.info(f"✅ 备份完成，备份文件大小: {backup_size:,} 字节")
                
                if backup_size != source_size:
                    logger.warning(f"⚠️ 备份文件大小与源文件不匹配: {backup_size} != {source_size}")
                else:
                    logger.info("✅ 备份文件大小验证通过")
            else:
                raise Exception("备份文件创建失败")
            
            return backup_path
            
        except Exception as e:
            logger.error(f"❌ 创建备份失败: {e}")
            raise Exception(f"创建备份失败: {e}")
    
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
        
        # 获取更新文件的扩展名
        update_file_ext = os.path.splitext(update_file)[1].lower()
        
        # 确保路径使用正确的分隔符并转义特殊字符
        update_file = update_file.replace('/', '\\')
        current_exe = current_exe.replace('/', '\\')
        current_dir = current_dir.replace('/', '\\')
        if backup_path:
            backup_path = backup_path.replace('/', '\\')
        
        # 构建脚本内容
        log_file = os.path.join(current_dir, "update_script.log").replace('/', '\\')
        
        script_content = f"""@echo off
setlocal enabledelayedexpansion
set "LOG_FILE={log_file}"
echo Starting GameTimeLimiter update process... > "%LOG_FILE%"
echo Update file: {update_file} >> "%LOG_FILE%"
echo Target executable: {current_exe} >> "%LOG_FILE%"
echo Backup path: {backup_path if backup_path else "None"} >> "%LOG_FILE%"
echo Script started at: %DATE% %TIME% >> "%LOG_FILE%"

echo Starting GameTimeLimiter update process...
echo Update file: {update_file}
echo Target executable: {current_exe}
echo Backup path: {backup_path if backup_path else "None"}

REM Wait for main process to exit gracefully (allow time for admin password input)
echo Waiting for main process to exit gracefully...
set /a "wait_count=0"
:wait_loop
timeout /t 1 /nobreak >nul
set /a "wait_count+=1"

REM Check if the main process is still running
tasklist /FI "IMAGENAME eq GameTimeLimiter.exe" 2>NUL | find /I /N "GameTimeLimiter.exe">NUL
if "%ERRORLEVEL%"=="0" (
    if %wait_count% LSS 30 (
        echo Main process still running, waiting... (%wait_count%/30)
        goto wait_loop
    ) else (
        echo Main process still running after 30 seconds, force closing...
        taskkill /F /IM "GameTimeLimiter.exe" 2>nul
        timeout /t 1 /nobreak >nul
    )
) else (
    echo Main process has exited cleanly after %wait_count% seconds
)

REM Check if update file exists
if not exist "{update_file}" (
    echo Error: Update file not found: {update_file}
    pause
    exit /b 1
)

REM Check if update file is ZIP or EXE based on actual file extension
if /i "{update_file_ext}"==".zip" (
    echo Extracting update from ZIP file...
    echo Extracting: {update_file}
    echo To directory: {current_dir}
    
    REM Create temporary extraction directory
    set "TEMP_EXTRACT_DIR=%TEMP%\\gamecontrol_extract_%RANDOM%"
    mkdir "%TEMP_EXTRACT_DIR%"
    
    REM Use PowerShell to extract ZIP file to temp directory first
    powershell -command "try {{ Expand-Archive -Path '{update_file}' -DestinationPath '%TEMP_EXTRACT_DIR%' -Force; Write-Host 'Extraction completed successfully' }} catch {{ Write-Host 'Extraction failed:' $_.Exception.Message; exit 1 }}"
    if errorlevel 1 (
        echo Failed to extract update ZIP file
        if exist "{backup_path}" (
            echo Restoring backup...
            copy /y "{backup_path}" "{current_exe}"
        )
        rmdir /s /q "%TEMP_EXTRACT_DIR%" 2>nul
        pause
        exit /b 1
    )
    
    REM Find the executable in the extracted files
    set "NEW_EXE_PATH="
    for /r "%TEMP_EXTRACT_DIR%" %%f in (GameTimeLimiter.exe) do (
        set "NEW_EXE_PATH=%%f"
        goto :found_exe
    )
    
    :found_exe
    if not defined NEW_EXE_PATH (
        echo Error: GameTimeLimiter.exe not found in extracted files
        dir "%TEMP_EXTRACT_DIR%" /s /b
        if exist "{backup_path}" (
            echo Restoring backup...
            copy /y "{backup_path}" "{current_exe}"
        )
        rmdir /s /q "%TEMP_EXTRACT_DIR%" 2>nul
        pause
        exit /b 1
    )
    
    echo Found executable at: %NEW_EXE_PATH%
    
    REM Copy the new executable
    copy /y "%NEW_EXE_PATH%" "{current_exe}"
    if errorlevel 1 (
        echo Failed to copy new executable
        if exist "{backup_path}" (
            echo Restoring backup...
            copy /y "{backup_path}" "{current_exe}"
        )
        rmdir /s /q "%TEMP_EXTRACT_DIR%" 2>nul
        pause
        exit /b 1
    )
    
    REM Copy any additional files from the extracted directory
    echo Copying additional files...
    for %%f in ("%TEMP_EXTRACT_DIR%\\*") do (
        if not "%%~nxf"=="GameTimeLimiter.exe" (
            copy /y "%%f" "{current_dir}\\" 2>nul
        )
    )
    
    REM Clean up temporary extraction directory
    rmdir /s /q "%TEMP_EXTRACT_DIR%" 2>nul
    
) else (
    echo Installing update executable...
    echo Copying: {update_file}
    echo To: {current_exe}
    
    REM Backup current executable if backup path is provided
    if exist "{backup_path}" (
        echo Backup already created at: {backup_path}
    )
    
    REM Copy the new executable
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
    echo Executable updated successfully
)

REM Verify the new executable
echo Verifying new executable...
if not exist "{current_exe}" (
    echo Error: New executable not found after update
    if exist "{backup_path}" (
        echo Restoring backup...
        copy /y "{backup_path}" "{current_exe}"
    )
    pause
    exit /b 1
)

REM Clean up temporary files
echo Cleaning up temporary files...
del /q "{update_file}" 2>nul

echo Update completed successfully!
echo Restarting application...
timeout /t 1 /nobreak >nul

REM Start the updated application with clean environment
echo Starting application with clean environment...
echo Target: {current_exe}
echo Working directory: {current_dir}

cd /d "{current_dir}"
echo Current directory after cd: %CD%

REM Clear ALL PyInstaller environment variables that could interfere
echo Clearing PyInstaller environment variables...
set "_MEIPASS="
set "_MEIPASS2="
set "_PYI_APPLICATION_HOME_DIR="
set "_PYI_ARCHIVE_FILE="
set "_PYI_PARENT_PROCESS_LEVEL="
set "PYINSTALLER_RUNTIME_TMPDIR="
set "QML2_IMPORT_PATH="
set "QT_PLUGIN_PATH="

REM Clean the PATH variable to remove PyInstaller temp directories
echo Cleaning PATH variable...
set "CLEAN_PATH="
for %%i in ("%PATH:;=" "%") do (
    echo %%i | findstr /C:"_MEI" >nul
    if errorlevel 1 (
        if defined CLEAN_PATH (
            set "CLEAN_PATH=!CLEAN_PATH!;%%~i"
        ) else (
            set "CLEAN_PATH=%%~i"
        )
    )
)
set "PATH=%CLEAN_PATH%"

REM Use start command with clean environment to launch the application
echo Starting application with clean environment...
start "" "{current_exe}"

REM Wait briefly for the application to start
timeout /t 2 /nobreak >nul

REM Verify the application started
tasklist /FI "IMAGENAME eq GameTimeLimiter.exe" 2>NUL | find /I /N "GameTimeLimiter.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo Application started successfully!
) else (
    echo Warning: Application may not have started properly
    echo Please try starting it manually: {current_exe}
    echo Press any key to continue...
    pause >nul
)

REM Clean up this script
del /q "%~f0" 2>nul
"""
        
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        logger.info(f"更新脚本已创建: {script_path}")
        logger.info(f"更新文件类型: {update_file_ext}")
        
        return script_path
    
    def reconnect_signals_to_parent(self, new_parent):
        """重新连接信号到新的父窗口"""
        try:
            logger.info(f"重新连接AutoUpdater信号到新父窗口: {new_parent}")
            
            # 断开旧的连接（如果存在）
            try:
                self.update_available.disconnect()
                self.update_check_failed.disconnect()
                logger.info("已断开旧的信号连接")
            except:
                pass  # 如果没有连接则忽略
            
            # 连接到新的父窗口
            if new_parent and hasattr(new_parent, 'on_update_available'):
                self.update_available.connect(new_parent.on_update_available)
                logger.info("已连接update_available信号")
            
            if new_parent and hasattr(new_parent, 'on_update_check_failed'):
                self.update_check_failed.connect(new_parent.on_update_check_failed)
                logger.info("已连接update_check_failed信号")
                
        except Exception as e:
            logger.error(f"重新连接信号失败: {e}")

    async def close(self):
        """关闭更新器"""
        try:
            logger.info("关闭自动更新器...")
            
            # 停止定时器
            self.check_timer.stop()
            
            # 清理任务状态
            if self._check_task_id:
                logger.info("清理检查更新任务状态")
                self._check_task_id = None
            
            if self._download_task_id:
                logger.info("清理下载任务状态")
                self._download_task_id = None
            
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
        logger.info(f"创建新的AutoUpdater实例，parent: {parent}")
        _updater_instance = AutoUpdater(parent)
    else:
        # 如果实例已存在但parent不同，更新parent并重新连接信号
        if parent is not None and _updater_instance.parent != parent:
            logger.info(f"更新AutoUpdater的parent: {_updater_instance.parent} -> {parent}")
            _updater_instance.parent = parent
            _updater_instance.reconnect_signals_to_parent(parent)
    return _updater_instance 