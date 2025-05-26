#!/usr/bin/env python3
"""
详细的自动更新测试脚本
提供完整的日志输出，用于定位更新功能问题
"""

import sys
import asyncio
import logging
import traceback
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QLabel, QTextEdit
from PyQt6.QtCore import QTimer
import qasync

# 设置详细日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('update_test_detailed.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# 导入相关模块
try:
    from logic.auto_updater import AutoUpdater, UpdateChecker, UpdateDownloader
    from version import __version__, GITHUB_RELEASES_URL, GITHUB_REPO_OWNER, GITHUB_REPO_NAME
    logger.info("✅ 成功导入自动更新模块")
except ImportError as e:
    logger.error(f"❌ 导入模块失败: {e}")
    sys.exit(1)

class DetailedUpdateTest(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Detailed Auto-Update Test")
        self.setGeometry(100, 100, 900, 700)
        
        # 创建UI
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # 标题
        title = QLabel("详细自动更新测试 - 完整日志输出")
        layout.addWidget(title)
        
        # 版本信息
        version_info = QLabel(f"当前版本: {__version__}")
        layout.addWidget(version_info)
        
        # GitHub 信息
        github_info = QLabel(f"GitHub: {GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}")
        layout.addWidget(github_info)
        
        # API URL
        api_info = QLabel(f"API URL: {GITHUB_RELEASES_URL}")
        layout.addWidget(api_info)
        
        # 状态标签
        self.status_label = QLabel("准备开始测试...")
        layout.addWidget(self.status_label)
        
        # 测试按钮
        self.test_button = QPushButton("开始详细测试")
        self.test_button.clicked.connect(self.start_detailed_test)
        layout.addWidget(self.test_button)
        
        # 单独测试按钮
        self.check_button = QPushButton("仅测试检查更新")
        self.check_button.clicked.connect(self.test_check_only)
        layout.addWidget(self.check_button)
        
        # 网络测试按钮
        self.network_button = QPushButton("测试网络连接")
        self.network_button.clicked.connect(self.test_network)
        layout.addWidget(self.network_button)
        
        # 日志区域
        self.log_area = QTextEdit()
        self.log_area.setMaximumHeight(400)
        layout.addWidget(self.log_area)
        
        # 初始化组件
        self.auto_updater = None
        self.update_checker = None
        
        # 记录初始状态
        self.log_detailed("🚀 应用程序启动")
        self.log_detailed(f"📋 当前版本: {__version__}")
        self.log_detailed(f"🌐 GitHub仓库: {GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}")
        self.log_detailed(f"🔗 API地址: {GITHUB_RELEASES_URL}")
        
    def log_detailed(self, message):
        """详细日志输出"""
        self.log_area.append(message)
        logger.info(message)
        
    def start_detailed_test(self):
        """开始详细测试"""
        self.log_detailed("=" * 60)
        self.log_detailed("🧪 开始详细自动更新测试")
        self.log_detailed("=" * 60)
        
        self.test_button.setEnabled(False)
        self.status_label.setText("正在进行详细测试...")
        
        try:
            # 步骤1: 创建AutoUpdater
            self.log_detailed("📝 步骤1: 创建AutoUpdater实例")
            self.auto_updater = AutoUpdater(self)
            
            # 连接信号
            self.auto_updater.update_check_started.connect(
                lambda: self.log_detailed("🔄 更新检查已开始")
            )
            self.auto_updater.update_available.connect(self.on_update_available)
            self.auto_updater.no_update_available.connect(
                lambda: self.log_detailed("ℹ️ 没有可用更新")
            )
            self.auto_updater.update_check_failed.connect(self.on_update_failed)
            
            self.log_detailed("✅ AutoUpdater创建成功")
            
            # 步骤2: 检查网络连接
            self.log_detailed("📝 步骤2: 检查网络连接")
            self.test_network_connection()
            
            # 步骤3: 检查更新
            self.log_detailed("📝 步骤3: 开始检查更新")
            self.auto_updater.check_for_updates(manual=True)
            
            # 15秒后检查结果
            QTimer.singleShot(15000, self.check_test_results)
            
        except Exception as e:
            self.log_detailed(f"❌ 测试过程中出错: {e}")
            self.log_detailed(f"📋 错误详情: {traceback.format_exc()}")
            self.test_button.setEnabled(True)
    
    def test_check_only(self):
        """仅测试检查更新功能"""
        self.log_detailed("=" * 40)
        self.log_detailed("🔍 仅测试检查更新功能")
        self.log_detailed("=" * 40)
        
        self.check_button.setEnabled(False)
        
        try:
            # 创建独立的UpdateChecker
            self.log_detailed("📝 创建独立的UpdateChecker")
            self.update_checker = UpdateChecker()
            
            # 异步检查
            asyncio.create_task(self.async_check_update())
            
        except Exception as e:
            self.log_detailed(f"❌ 检查更新失败: {e}")
            self.log_detailed(f"📋 错误详情: {traceback.format_exc()}")
            self.check_button.setEnabled(True)
    
    async def async_check_update(self):
        """异步检查更新"""
        try:
            self.log_detailed("🌐 开始异步检查更新...")
            
            # 直接调用检查方法
            update_info = await self.update_checker.check_for_updates()
            
            if update_info:
                self.log_detailed("🎉 发现可用更新!")
                self.log_detailed(f"   新版本: {update_info.version}")
                self.log_detailed(f"   下载地址: {update_info.download_url}")
                self.log_detailed(f"   文件大小: {update_info.asset_size:,} 字节")
                self.log_detailed(f"   发布时间: {update_info.published_at}")
                self.log_detailed(f"   更新说明: {update_info.release_notes[:200]}...")
            else:
                self.log_detailed("ℹ️ 没有可用更新（当前版本是最新的）")
                
        except Exception as e:
            self.log_detailed(f"❌ 异步检查更新失败: {e}")
            self.log_detailed(f"📋 错误详情: {traceback.format_exc()}")
        finally:
            self.check_button.setEnabled(True)
            if self.update_checker:
                await self.update_checker.close()
    
    def test_network(self):
        """测试网络连接"""
        self.log_detailed("=" * 40)
        self.log_detailed("🌐 测试网络连接")
        self.log_detailed("=" * 40)
        
        self.network_button.setEnabled(False)
        asyncio.create_task(self.async_test_network())
    
    async def async_test_network(self):
        """异步测试网络连接"""
        import httpx
        
        try:
            self.log_detailed("📡 测试基本网络连接...")
            
            # 测试1: 基本HTTP连接
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get("https://httpbin.org/get")
                self.log_detailed(f"✅ 基本HTTP连接: {response.status_code}")
            
            # 测试2: GitHub API连接
            self.log_detailed("📡 测试GitHub API连接...")
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get("https://api.github.com/rate_limit")
                self.log_detailed(f"✅ GitHub API连接: {response.status_code}")
                data = response.json()
                self.log_detailed(f"   API限制: {data['rate']['remaining']}/{data['rate']['limit']}")
            
            # 测试3: 目标仓库连接
            self.log_detailed(f"📡 测试目标仓库连接: {GITHUB_RELEASES_URL}")
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(GITHUB_RELEASES_URL)
                self.log_detailed(f"   仓库API响应: {response.status_code}")
                
                if response.status_code == 200:
                    releases = response.json()
                    self.log_detailed(f"   发现 {len(releases)} 个发布版本")
                    if releases:
                        latest = releases[0]
                        self.log_detailed(f"   最新版本: {latest['tag_name']}")
                        self.log_detailed(f"   发布时间: {latest['published_at']}")
                    else:
                        self.log_detailed("   ⚠️ 仓库中没有任何发布版本")
                elif response.status_code == 404:
                    self.log_detailed("   ❌ 仓库不存在或无法访问")
                else:
                    self.log_detailed(f"   ⚠️ 意外的响应状态: {response.status_code}")
                    self.log_detailed(f"   响应内容: {response.text[:200]}...")
                    
        except Exception as e:
            self.log_detailed(f"❌ 网络测试失败: {e}")
            self.log_detailed(f"📋 错误详情: {traceback.format_exc()}")
        finally:
            self.network_button.setEnabled(True)
    
    def test_network_connection(self):
        """测试网络连接（同步版本）"""
        try:
            import requests
            self.log_detailed("🌐 测试网络连接...")
            
            # 测试基本连接
            response = requests.get("https://httpbin.org/get", timeout=5)
            self.log_detailed(f"✅ 基本网络连接正常: {response.status_code}")
            
            # 测试GitHub API
            response = requests.get("https://api.github.com/rate_limit", timeout=5)
            self.log_detailed(f"✅ GitHub API连接正常: {response.status_code}")
            
        except Exception as e:
            self.log_detailed(f"⚠️ 网络连接测试失败: {e}")
    
    def on_update_available(self, update_info):
        """处理发现更新"""
        self.log_detailed("🎉 收到更新可用信号!")
        self.log_detailed(f"   版本: {update_info.version}")
        self.log_detailed(f"   下载URL: {update_info.download_url}")
        self.log_detailed(f"   文件名: {update_info.asset_name}")
        self.log_detailed(f"   文件大小: {update_info.asset_size:,} 字节")
        self.log_detailed(f"   发布时间: {update_info.published_at}")
        
        # 显示更新对话框的详细信息
        self.log_detailed("📋 准备显示更新对话框...")
        
        # 这里可以选择是否真的显示对话框
        # self.auto_updater.show_update_dialog(update_info)
        
        self.status_label.setText(f"发现更新: v{update_info.version}")
    
    def on_update_failed(self, error_msg):
        """处理更新检查失败"""
        self.log_detailed(f"❌ 更新检查失败: {error_msg}")
        self.status_label.setText(f"检查失败: {error_msg}")
    
    def check_test_results(self):
        """检查测试结果"""
        self.log_detailed("=" * 40)
        self.log_detailed("📊 测试结果总结")
        self.log_detailed("=" * 40)
        
        if self.status_label.text().startswith("发现更新"):
            self.log_detailed("✅ 测试成功: 发现了可用更新")
        elif "没有可用更新" in self.log_area.toPlainText():
            self.log_detailed("ℹ️ 测试完成: 当前版本是最新的")
        elif "检查失败" in self.status_label.text():
            self.log_detailed("❌ 测试失败: 更新检查出错")
        else:
            self.log_detailed("⚠️ 测试状态不明确")
        
        self.test_button.setEnabled(True)
    
    def closeEvent(self, event):
        """关闭事件"""
        self.log_detailed("🔄 关闭应用程序...")
        if self.auto_updater:
            asyncio.create_task(self.auto_updater.close())
        if self.update_checker:
            asyncio.create_task(self.update_checker.close())
        event.accept()

def main():
    """主函数"""
    print("=" * 70)
    print("🧪 Detailed Auto-Update Test")
    print("=" * 70)
    print("This test provides detailed logging for auto-update functionality")
    print("Check both console output and 'update_test_detailed.log' file")
    print("=" * 70)
    
    app = QApplication(sys.argv)
    
    # 设置qasync事件循环
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    window = DetailedUpdateTest()
    window.show()
    
    with loop:
        loop.run_forever()

if __name__ == "__main__":
    main() 