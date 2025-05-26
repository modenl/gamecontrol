#!/usr/bin/env python3
"""
简单的更新检测测试 - 不使用Qt
"""

import asyncio
import logging
import requests
import json

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_github_api():
    """测试GitHub API访问"""
    try:
        from version import GITHUB_RELEASES_URL, __version__, is_newer_version
        
        logger.info("🧪 开始测试GitHub API访问...")
        logger.info(f"📋 当前版本: {__version__}")
        logger.info(f"🔗 GitHub API URL: {GITHUB_RELEASES_URL}/latest")
        
        # 发送HTTP请求
        logger.info("🌐 请求GitHub API...")
        response = requests.get(
            f"{GITHUB_RELEASES_URL}/latest",
            timeout=30,
            headers={'User-Agent': 'GameTimeLimiter-AutoUpdater/1.0'}
        )
        
        logger.info(f"📡 API响应状态: {response.status_code}")
        response.raise_for_status()
        
        # 解析响应
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
        
        # 显示更新信息
        logger.info(f"📦 更新信息:")
        logger.info(f"   版本: {latest_version}")
        logger.info(f"   文件: {windows_asset['name']}")
        logger.info(f"   大小: {windows_asset['size']:,} 字节")
        logger.info(f"   URL: {windows_asset['browser_download_url']}")
        
        return {
            'version': latest_version,
            'asset_name': windows_asset['name'],
            'asset_size': windows_asset['size'],
            'download_url': windows_asset['browser_download_url']
        }
        
    except requests.RequestException as e:
        logger.error(f"❌ 网络请求失败: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"❌ 解析响应数据失败: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}", exc_info=True)
        return None

def test_version_comparison():
    """测试版本比较功能"""
    try:
        from version import is_newer_version, compare_versions
        
        logger.info("🧪 开始测试版本比较功能...")
        
        test_cases = [
            ("1.0.0", "1.1.0", True),   # 1.1.0 > 1.0.0
            ("1.1.0", "1.0.0", False),  # 1.0.0 < 1.1.0
            ("1.1.0", "1.1.0", False),  # 相等
            ("1.1.0", "1.1.1", True),   # 1.1.1 > 1.1.0
            ("2.0.0", "1.9.9", False),  # 1.9.9 < 2.0.0
        ]
        
        for current, new, expected in test_cases:
            result = is_newer_version(current, new)
            status = "✅" if result == expected else "❌"
            logger.info(f"{status} {current} vs {new}: {result} (期望: {expected})")
        
        logger.info("✅ 版本比较测试完成")
        
    except Exception as e:
        logger.error(f"❌ 版本比较测试失败: {e}", exc_info=True)

def main():
    """主函数"""
    logger.info("🚀 开始简单更新检测测试")
    
    print("\n" + "="*60)
    print("测试 1: 版本比较功能")
    print("="*60)
    test_version_comparison()
    
    print("\n" + "="*60)
    print("测试 2: GitHub API访问")
    print("="*60)
    update_info = test_github_api()
    
    if update_info:
        logger.info("🎉 发现可用更新!")
    else:
        logger.info("ℹ️ 当前版本是最新的或检测失败")
    
    logger.info("🎉 测试完成")

if __name__ == "__main__":
    main() 