#!/usr/bin/env python3
"""
测试GitHub下载链接重定向处理的脚本
"""

import asyncio
import httpx
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_github_download():
    """测试GitHub下载链接"""
    
    # GitHub API URL
    api_url = "https://api.github.com/repos/modenl/gamecontrol/releases/latest"
    
    print("=" * 60)
    print("🧪 GitHub Download Redirect Test")
    print("=" * 60)
    
    try:
        # 1. 获取最新发布信息
        print("📡 Step 1: Getting latest release info...")
        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            limits=httpx.Limits(max_redirects=10)
        ) as client:
            
            response = await client.get(api_url)
            response.raise_for_status()
            
            release_data = response.json()
            print(f"✓ Latest version: {release_data['tag_name']}")
            
            # 2. 找到Windows可执行文件
            print("\n📦 Step 2: Finding Windows executable...")
            windows_asset = None
            for asset in release_data["assets"]:
                asset_name = asset["name"].lower()
                if asset_name.endswith(".exe"):
                    windows_asset = asset
                    break
            
            if not windows_asset:
                print("❌ No Windows executable found")
                return
            
            download_url = windows_asset["browser_download_url"]
            file_size = windows_asset["size"]
            
            print(f"✓ Found: {windows_asset['name']}")
            print(f"✓ Size: {file_size:,} bytes ({file_size/1024/1024:.1f} MB)")
            print(f"✓ URL: {download_url}")
            
            # 3. 测试下载链接（只下载前1KB来测试重定向）
            print("\n🔗 Step 3: Testing download redirect...")
            
            headers = {"Range": "bytes=0-1023"}  # 只下载前1KB
            
            async with client.stream("GET", download_url, headers=headers) as stream_response:
                print(f"✓ Response status: {stream_response.status_code}")
                print(f"✓ Final URL: {stream_response.url}")
                print(f"✓ Content-Length: {stream_response.headers.get('content-length', 'Unknown')}")
                print(f"✓ Content-Range: {stream_response.headers.get('content-range', 'Not set')}")
                
                # 读取一小部分数据来验证
                chunk_count = 0
                async for chunk in stream_response.aiter_bytes(chunk_size=1024):
                    chunk_count += 1
                    if chunk_count >= 1:  # 只读取第一个chunk
                        break
                
                print(f"✓ Successfully read {len(chunk)} bytes")
                
            print("\n🎉 Download redirect test PASSED!")
            print("The download should work correctly now.")
            
    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP Error: {e}")
        print(f"   Status: {e.response.status_code}")
        print(f"   URL: {e.request.url}")
        if hasattr(e.response, 'headers'):
            location = e.response.headers.get('location')
            if location:
                print(f"   Redirect to: {location}")
                
    except Exception as e:
        print(f"❌ Error: {e}")
        logger.exception("Test failed")

async def main():
    """主函数"""
    await test_github_download()

if __name__ == "__main__":
    asyncio.run(main()) 