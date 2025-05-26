#!/usr/bin/env python3
"""
快速构建脚本 - 优化构建速度
支持增量构建、缓存机制和智能依赖检测
"""

import os
import sys
import shutil
import subprocess
import argparse
import time
import hashlib
import json
from pathlib import Path

# 构建缓存配置
CACHE_DIR = ".build_cache"
CACHE_FILE = os.path.join(CACHE_DIR, "build_cache.json")

def get_file_hash(filepath):
    """获取文件的MD5哈希值"""
    if not os.path.exists(filepath):
        return None
    
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def get_directory_hash(directory, extensions=None):
    """获取目录中所有文件的哈希值"""
    if extensions is None:
        extensions = ['.py', '.ui', '.qrc', '.ico', '.png', '.jpg', '.txt', '.md']
    
    all_hashes = []
    for root, dirs, files in os.walk(directory):
        # 跳过缓存目录和其他不需要的目录
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'build', 'dist']]
        
        for file in sorted(files):
            if any(file.endswith(ext) for ext in extensions):
                filepath = os.path.join(root, file)
                file_hash = get_file_hash(filepath)
                if file_hash:
                    all_hashes.append(f"{filepath}:{file_hash}")
    
    # 计算所有文件哈希的总哈希
    combined = "|".join(all_hashes)
    return hashlib.md5(combined.encode()).hexdigest()

def load_build_cache():
    """加载构建缓存"""
    if not os.path.exists(CACHE_FILE):
        return {}
    
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_build_cache(cache_data):
    """保存构建缓存"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache_data, f, indent=2)

def check_if_rebuild_needed():
    """检查是否需要重新构建"""
    print("🔍 检查是否需要重新构建...")
    
    # 加载缓存
    cache = load_build_cache()
    
    # 检查关键文件
    key_files = [
        'main.py',
        'version.py',
        'requirements.txt',
        'app.ico'
    ]
    
    # 检查关键目录
    key_dirs = ['logic', 'ui']
    
    current_hashes = {}
    
    # 检查关键文件
    for file in key_files:
        if os.path.exists(file):
            current_hashes[file] = get_file_hash(file)
    
    # 检查关键目录
    for dir in key_dirs:
        if os.path.exists(dir):
            current_hashes[dir] = get_directory_hash(dir)
    
    # 检查可执行文件是否存在
    exe_exists = (
        os.path.exists('dist/GameTimeLimiter.exe') or 
        os.path.exists('dist/GameTimeLimiter/GameTimeLimiter.exe')
    )
    
    # 比较哈希值
    cached_hashes = cache.get('file_hashes', {})
    
    if not exe_exists:
        print("❌ 可执行文件不存在，需要完整构建")
        return True, current_hashes
    
    for key, current_hash in current_hashes.items():
        cached_hash = cached_hashes.get(key)
        if cached_hash != current_hash:
            print(f"📝 文件/目录已更改: {key}")
            return True, current_hashes
    
    print("✅ 无需重新构建，使用现有可执行文件")
    return False, current_hashes

def quick_clean():
    """快速清理 - 只清理必要的文件"""
    print("🧹 快速清理构建文件...")
    
    # 只清理spec文件和部分构建文件
    files_to_remove = [
        'GameTimeLimiter.spec',
        'main.spec'
    ]
    
    for file in files_to_remove:
        if os.path.exists(file):
            os.remove(file)
            print(f"   删除: {file}")

def fast_build(force_rebuild=False, use_cache=True):
    """快速构建"""
    start_time = time.time()
    print("🚀 开始快速构建...")
    
    # 检查是否需要重新构建
    if use_cache and not force_rebuild:
        needs_rebuild, current_hashes = check_if_rebuild_needed()
        if not needs_rebuild:
            print(f"⚡ 构建跳过，耗时: {time.time() - start_time:.2f} 秒")
            return True
    else:
        # 强制重建时获取当前哈希
        current_hashes = {}
        key_files = ['main.py', 'version.py', 'requirements.txt', 'app.ico']
        key_dirs = ['logic', 'ui']
        
        for file in key_files:
            if os.path.exists(file):
                current_hashes[file] = get_file_hash(file)
        
        for dir in key_dirs:
            if os.path.exists(dir):
                current_hashes[dir] = get_directory_hash(dir)
    
    # 快速清理
    quick_clean()
    
    # 构建命令 - 优化版本
    cmd = [
        'pyinstaller',
        '--name=GameTimeLimiter',
        '--windowed',
        '--icon=app.ico',
        '--add-data=.env.example;.',
        '--noconfirm',  # 不询问覆盖
        '--clean',      # 清理临时文件
        '--onefile',    # 单文件模式，启动稍慢但分发方便
        
        # 关键优化：减少不必要的模块
        '--exclude-module=matplotlib.tests',
        '--exclude-module=numpy.testing',
        '--exclude-module=scipy',
        '--exclude-module=pandas',
        '--exclude-module=tkinter',
        '--exclude-module=PyQt5',
        '--exclude-module=PySide2',
        '--exclude-module=pytest',
        '--exclude-module=jupyter',
        '--exclude-module=IPython',
        '--exclude-module=sphinx',
        '--exclude-module=bokeh',
        '--exclude-module=seaborn',
        
        # 必要的隐藏导入
        '--hidden-import=win32security',
        '--hidden-import=psutil',
        '--hidden-import=requests',
        '--hidden-import=urllib3',
        '--hidden-import=certifi',
        
        # 减少日志输出
        '--log-level=WARN',
        
        # 入口点
        'main.py'
    ]
    
    print("🔨 执行PyInstaller构建...")
    try:
        # 使用较少的输出来加速
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print("❌ 构建失败:")
            print(result.stderr)
            return False
        else:
            print("✅ PyInstaller构建完成")
    except subprocess.CalledProcessError as e:
        print(f"❌ 构建失败: {e}")
        return False
    
    # 更新缓存
    if use_cache:
        cache = load_build_cache()
        cache['file_hashes'] = current_hashes
        cache['last_build_time'] = time.time()
        save_build_cache(cache)
        print("💾 构建缓存已更新")
    
    build_time = time.time() - start_time
    print(f"🎉 快速构建完成! 耗时: {build_time:.2f} 秒")
    
    # 显示可执行文件位置
    if os.path.exists('dist/GameTimeLimiter.exe'):
        print("📁 可执行文件: dist/GameTimeLimiter.exe")
    else:
        print("⚠️ 警告: 未找到预期的可执行文件")
    
    return True

def clean_all():
    """完全清理所有构建文件和缓存"""
    print("🧹 完全清理构建文件和缓存...")
    
    dirs_to_remove = ['build', 'dist', CACHE_DIR]
    files_to_remove = ['GameTimeLimiter.spec', 'main.spec']
    
    for dir_name in dirs_to_remove:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"   删除目录: {dir_name}")
    
    for file_name in files_to_remove:
        if os.path.exists(file_name):
            os.remove(file_name)
            print(f"   删除文件: {file_name}")
    
    print("✅ 清理完成")

def show_cache_info():
    """显示缓存信息"""
    cache = load_build_cache()
    
    if not cache:
        print("📋 无构建缓存")
        return
    
    print("📋 构建缓存信息:")
    
    if 'last_build_time' in cache:
        last_build = time.ctime(cache['last_build_time'])
        print(f"   上次构建: {last_build}")
    
    if 'file_hashes' in cache:
        print(f"   缓存文件数: {len(cache['file_hashes'])}")
        for file, hash_val in cache['file_hashes'].items():
            print(f"     {file}: {hash_val[:8]}...")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='GameTimeLimiter 快速构建工具')
    parser.add_argument('--force', action='store_true', help='强制重新构建，忽略缓存')
    parser.add_argument('--no-cache', action='store_true', help='不使用缓存机制')
    parser.add_argument('--clean', action='store_true', help='完全清理所有构建文件和缓存')
    parser.add_argument('--cache-info', action='store_true', help='显示缓存信息')
    
    args = parser.parse_args()
    
    if args.cache_info:
        show_cache_info()
        return
    
    if args.clean:
        clean_all()
        return
    
    # 执行快速构建
    success = fast_build(
        force_rebuild=args.force,
        use_cache=not args.no_cache
    )
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main() 