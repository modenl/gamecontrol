#!/usr/bin/env python3
"""
简单的下载测试脚本
"""

import asyncio
import httpx

async def test_simple_download():
    """简单测试下载"""
    
    print("🧪 Testing GitHub download with improved configuration...")
    
    # 使用改进的配置
    async with httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=True,
        limits=httpx.Limits(max_redirects=10)
    ) as client:
        
        # 获取发布信息
        api_url = "https://api.github.com/repos/modenl/gamecontrol/releases/latest"
        response = await client.get(api_url)
        release_data = response.json()
        
        # 找到exe文件
        exe_asset = None
        for asset in release_data["assets"]:
            if asset["name"].lower().endswith(".exe"):
                exe_asset = asset
                break
        
        if not exe_asset:
            print("❌ No exe file found")
            return
            
        download_url = exe_asset["browser_download_url"]
        print(f"📦 Found: {exe_asset['name']}")
        print(f"🔗 URL: {download_url}")
        
        # 测试下载前1KB
        print("🔄 Testing download (first 1KB)...")
        
        headers = {"Range": "bytes=0-1023"}
        async with client.stream("GET", download_url, headers=headers) as stream:
            print(f"✅ Status: {stream.status_code}")
            print(f"🎯 Final URL: {stream.url}")
            
            data = b""
            async for chunk in stream.aiter_bytes(1024):
                data += chunk
                break
                
            print(f"📊 Downloaded: {len(data)} bytes")
            print("🎉 Download test successful!")

if __name__ == "__main__":
    asyncio.run(test_simple_download()) 