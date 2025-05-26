#!/usr/bin/env python3
"""
检查GitHub Actions构建状态的脚本
"""

import requests
import json
import sys
from datetime import datetime

def check_build_status():
    """检查GitHub Actions构建状态"""
    
    # GitHub API配置
    owner = "modenl"
    repo = "gamecontrol"
    api_url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs"
    
    try:
        print("🔍 检查GitHub Actions构建状态...")
        print(f"API URL: {api_url}")
        print("=" * 60)
        
        # 获取最近的workflow runs
        response = requests.get(api_url, params={"per_page": 5})
        response.raise_for_status()
        
        data = response.json()
        workflow_runs = data.get("workflow_runs", [])
        
        if not workflow_runs:
            print("❌ 没有找到任何workflow runs")
            return
        
        print(f"📋 找到 {len(workflow_runs)} 个最近的workflow runs:")
        print()
        
        for i, run in enumerate(workflow_runs, 1):
            status = run.get("status", "unknown")
            conclusion = run.get("conclusion", "unknown")
            created_at = run.get("created_at", "")
            head_branch = run.get("head_branch", "unknown")
            head_sha = run.get("head_sha", "unknown")[:7]
            workflow_name = run.get("name", "unknown")
            
            # 格式化时间
            try:
                created_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                time_str = created_time.strftime("%Y-%m-%d %H:%M:%S UTC")
            except:
                time_str = created_at
            
            # 状态图标
            if status == "completed":
                if conclusion == "success":
                    status_icon = "✅"
                elif conclusion == "failure":
                    status_icon = "❌"
                elif conclusion == "cancelled":
                    status_icon = "🚫"
                else:
                    status_icon = "❓"
            elif status == "in_progress":
                status_icon = "🔄"
            elif status == "queued":
                status_icon = "⏳"
            else:
                status_icon = "❓"
            
            print(f"{i}. {status_icon} {workflow_name}")
            print(f"   状态: {status}")
            if conclusion and conclusion != "null":
                print(f"   结果: {conclusion}")
            print(f"   分支: {head_branch}")
            print(f"   提交: {head_sha}")
            print(f"   时间: {time_str}")
            print(f"   URL: {run.get('html_url', 'N/A')}")
            print()
        
        # 检查最新的release
        print("🏷️ 检查最新release...")
        release_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
        release_response = requests.get(release_url)
        
        if release_response.status_code == 200:
            release_data = release_response.json()
            tag_name = release_data.get("tag_name", "unknown")
            published_at = release_data.get("published_at", "")
            
            try:
                pub_time = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                pub_time_str = pub_time.strftime("%Y-%m-%d %H:%M:%S UTC")
            except:
                pub_time_str = published_at
            
            print(f"📦 最新release: {tag_name}")
            print(f"📅 发布时间: {pub_time_str}")
        else:
            print("❌ 无法获取release信息")
        
    except requests.RequestException as e:
        print(f"❌ 请求失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 发生错误: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = check_build_status()
    sys.exit(0 if success else 1) 