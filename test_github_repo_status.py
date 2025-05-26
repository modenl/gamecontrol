#!/usr/bin/env python3
"""
测试 GitHub 仓库状态和发布版本
用于诊断自动更新功能的问题
"""

import requests
import json
import sys
from version import __version__, GITHUB_RELEASES_URL, GITHUB_REPO_OWNER, GITHUB_REPO_NAME

def test_github_repo():
    """测试 GitHub 仓库状态"""
    print("=" * 70)
    print("🔍 GitHub 仓库状态测试")
    print("=" * 70)
    
    print(f"📋 当前版本: {__version__}")
    print(f"🌐 GitHub 仓库: {GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}")
    print(f"🔗 API 地址: {GITHUB_RELEASES_URL}")
    print()
    
    try:
        # 测试1: 基本网络连接
        print("📡 测试1: 基本网络连接...")
        response = requests.get("https://httpbin.org/get", timeout=10)
        print(f"✅ 基本网络连接正常: {response.status_code}")
        print()
        
        # 测试2: GitHub API 连接
        print("📡 测试2: GitHub API 连接...")
        response = requests.get("https://api.github.com/rate_limit", timeout=10)
        print(f"✅ GitHub API 连接正常: {response.status_code}")
        
        if response.status_code == 200:
            rate_data = response.json()
            print(f"   API 限制: {rate_data['rate']['remaining']}/{rate_data['rate']['limit']}")
            print(f"   重置时间: {rate_data['rate']['reset']}")
        print()
        
        # 测试3: 检查仓库是否存在
        print("📡 测试3: 检查仓库是否存在...")
        repo_url = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}"
        response = requests.get(repo_url, timeout=10)
        
        if response.status_code == 200:
            repo_data = response.json()
            print(f"✅ 仓库存在: {repo_data['full_name']}")
            print(f"   描述: {repo_data.get('description', 'N/A')}")
            print(f"   私有: {repo_data['private']}")
            print(f"   创建时间: {repo_data['created_at']}")
            print(f"   最后更新: {repo_data['updated_at']}")
        elif response.status_code == 404:
            print("❌ 仓库不存在或无法访问")
            print("   可能的原因:")
            print("   1. 仓库名称错误")
            print("   2. 仓库是私有的")
            print("   3. 用户名错误")
            return False
        else:
            print(f"⚠️ 意外的响应状态: {response.status_code}")
            print(f"   响应内容: {response.text[:200]}...")
        print()
        
        # 测试4: 检查发布版本
        print("📡 测试4: 检查发布版本...")
        response = requests.get(GITHUB_RELEASES_URL, timeout=10)
        
        if response.status_code == 200:
            releases = response.json()
            print(f"✅ 成功获取发布列表: {len(releases)} 个版本")
            
            if releases:
                print("\n📦 发布版本列表:")
                for i, release in enumerate(releases[:5]):  # 只显示前5个
                    print(f"   {i+1}. {release['tag_name']} - {release['name']}")
                    print(f"      发布时间: {release['published_at']}")
                    print(f"      预发布: {release['prerelease']}")
                    print(f"      草稿: {release['draft']}")
                    print(f"      资源数量: {len(release['assets'])}")
                    
                    # 显示资源文件
                    if release['assets']:
                        print("      资源文件:")
                        for asset in release['assets']:
                            size_mb = asset['size'] / (1024 * 1024)
                            print(f"        - {asset['name']} ({size_mb:.1f} MB)")
                    print()
                
                # 检查最新版本
                latest = releases[0]
                latest_version = latest['tag_name'].lstrip('v')
                print(f"🏷️ 最新版本: {latest_version}")
                print(f"📋 当前版本: {__version__}")
                
                # 版本比较
                if latest_version != __version__:
                    print("🎉 发现新版本可用!")
                    
                    # 查找 Windows 资源
                    windows_assets = []
                    for asset in latest['assets']:
                        name = asset['name'].lower()
                        if name.endswith('.exe') or (name.endswith('.zip') and 'windows' in name):
                            windows_assets.append(asset)
                    
                    if windows_assets:
                        print(f"💾 找到 {len(windows_assets)} 个 Windows 资源:")
                        for asset in windows_assets:
                            size_mb = asset['size'] / (1024 * 1024)
                            print(f"   - {asset['name']} ({size_mb:.1f} MB)")
                            print(f"     下载地址: {asset['browser_download_url']}")
                    else:
                        print("⚠️ 没有找到 Windows 版本的资源文件")
                else:
                    print("ℹ️ 当前版本是最新的")
            else:
                print("⚠️ 仓库中没有任何发布版本")
                print("   这就是为什么自动更新功能无法工作的原因!")
                print("   需要创建至少一个发布版本才能使用自动更新功能。")
                
        elif response.status_code == 404:
            print("❌ 无法访问发布列表")
            print("   可能的原因:")
            print("   1. 仓库不存在")
            print("   2. 没有发布权限")
        else:
            print(f"⚠️ 意外的响应状态: {response.status_code}")
            print(f"   响应内容: {response.text[:200]}...")
        
        print()
        
    except requests.exceptions.RequestException as e:
        print(f"❌ 网络请求失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 测试过程中出错: {e}")
        return False
    
    print("=" * 70)
    print("✅ 测试完成")
    print("=" * 70)
    return True

def test_update_simulation():
    """模拟更新检查过程"""
    print("\n🧪 模拟更新检查过程...")
    
    try:
        # 模拟 UpdateChecker.check_for_updates() 的逻辑
        response = requests.get(f"{GITHUB_RELEASES_URL}/latest", timeout=30)
        
        if response.status_code == 200:
            release_data = response.json()
            latest_version = release_data["tag_name"].lstrip("v")
            
            print(f"📋 API 返回的最新版本: {latest_version}")
            print(f"📋 当前版本: {__version__}")
            
            # 检查是否有新版本
            if latest_version != __version__:
                print("🎉 检测到新版本!")
                
                # 查找 Windows 资源
                windows_asset = None
                for asset in release_data["assets"]:
                    asset_name = asset["name"].lower()
                    if (asset_name.endswith(".exe") or 
                        asset_name.endswith(".zip") and "windows" in asset_name):
                        windows_asset = asset
                        break
                
                if windows_asset:
                    print("✅ 找到 Windows 版本资源:")
                    print(f"   文件名: {windows_asset['name']}")
                    print(f"   大小: {windows_asset['size']:,} 字节")
                    print(f"   下载地址: {windows_asset['browser_download_url']}")
                    print("✅ 自动更新功能应该可以正常工作")
                else:
                    print("❌ 没有找到 Windows 版本资源")
                    print("   自动更新功能无法工作")
            else:
                print("ℹ️ 当前版本是最新的")
                
        elif response.status_code == 404:
            print("❌ 无法获取最新版本信息 (404)")
            print("   可能没有任何发布版本")
        else:
            print(f"❌ API 请求失败: {response.status_code}")
            print(f"   响应: {response.text[:200]}...")
            
    except Exception as e:
        print(f"❌ 模拟更新检查失败: {e}")

if __name__ == "__main__":
    print("🚀 开始 GitHub 仓库状态测试...")
    
    # 基本测试
    success = test_github_repo()
    
    if success:
        # 模拟更新检查
        test_update_simulation()
    
    print("\n📝 总结:")
    print("如果看到 '仓库中没有任何发布版本' 或 '无法获取最新版本信息'，")
    print("这就是自动更新功能无法工作的根本原因。")
    print("需要在 GitHub 仓库中创建至少一个 release 才能使用自动更新功能。") 