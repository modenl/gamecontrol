# 版本管理
# 这个文件定义了应用程序的版本信息

# 当前版本 - 遵循语义化版本控制 (Semantic Versioning)
# 格式: MAJOR.MINOR.PATCH
# MAJOR: 不兼容的API修改
# MINOR: 向下兼容的功能性新增
# PATCH: 向下兼容的问题修正
__version__ = "1.0.14"

# 版本信息
VERSION_INFO = {
    "major": 1,
    "minor": 0,
    "patch": 14,
    "pre_release": None,  # 例如: "alpha", "beta", "rc1"
    "build": None         # 构建号
}

# 应用程序信息
APP_NAME = "GameTimeLimiter"
APP_DISPLAY_NAME = "Game Time Limiter"
APP_DESCRIPTION = "A comprehensive game time management application with math exercises and reward system"
APP_AUTHOR = "GameControl Team"
APP_URL = "https://github.com/yourusername/gamecontrol"  # 替换为实际的GitHub仓库地址

# GitHub相关配置
GITHUB_REPO_OWNER = "modenl"        # 实际的GitHub用户名
GITHUB_REPO_NAME = "gamecontrol"    # 实际的仓库名
GITHUB_API_BASE = "https://api.github.com"
GITHUB_RELEASES_URL = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/releases"

# 升级相关配置
UPDATE_CHECK_INTERVAL = 24 * 60 * 60  # 24小时检查一次更新（秒）
UPDATE_DOWNLOAD_TIMEOUT = 300         # 下载超时时间（秒）
UPDATE_BACKUP_ENABLED = True          # 是否在升级前备份当前版本

def get_version_string():
    """获取完整的版本字符串"""
    version = __version__
    if VERSION_INFO["pre_release"]:
        version += f"-{VERSION_INFO['pre_release']}"
    if VERSION_INFO["build"]:
        version += f"+{VERSION_INFO['build']}"
    return version

def get_version_tuple():
    """获取版本元组，用于版本比较"""
    return (VERSION_INFO["major"], VERSION_INFO["minor"], VERSION_INFO["patch"])

def compare_versions(version1, version2):
    """比较两个版本
    
    Args:
        version1 (str): 版本1，格式如 "1.0.0"
        version2 (str): 版本2，格式如 "1.0.0"
    
    Returns:
        int: -1 if version1 < version2, 0 if equal, 1 if version1 > version2
    """
    def parse_version(version_str):
        # 移除预发布和构建信息，只比较主版本号
        clean_version = version_str.split('-')[0].split('+')[0]
        return tuple(map(int, clean_version.split('.')))
    
    v1 = parse_version(version1)
    v2 = parse_version(version2)
    
    if v1 < v2:
        return -1
    elif v1 > v2:
        return 1
    else:
        return 0

def is_newer_version(current_version, new_version):
    """检查新版本是否比当前版本更新
    
    Args:
        current_version (str): 当前版本
        new_version (str): 新版本
    
    Returns:
        bool: 如果新版本更新则返回True
    """
    return compare_versions(current_version, new_version) < 0 

# 测试版本覆盖功能 - 用于快速测试自动更新
def get_test_version():
    """获取测试版本，支持命令行参数覆盖"""
    import sys
    
    # 检查命令行参数中是否有版本覆盖
    for i, arg in enumerate(sys.argv):
        if arg == "--test-version" and i + 1 < len(sys.argv):
            test_version = sys.argv[i + 1]
            print(f"🧪 测试模式：版本覆盖为 {test_version}")
            return test_version
        elif arg.startswith("--test-version="):
            test_version = arg.split("=", 1)[1]
            print(f"🧪 测试模式：版本覆盖为 {test_version}")
            return test_version
    
    return __version__

# 获取当前有效版本（可能被测试参数覆盖）
def get_current_version():
    """获取当前有效版本"""
    return get_test_version()