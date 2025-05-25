# 自动更新功能实现说明

## 🚀 功能概述

GameTimeLimiter现在支持完整的自动更新功能，包括：

- ✅ **自动版本检测**：每24小时自动检查GitHub releases
- ✅ **手动更新检查**：用户可以随时点击"Check Updates"按钮
- ✅ **智能更新时机**：只在没有游戏会话和数学练习时允许更新
- ✅ **GitHub Actions自动构建**：推送标签时自动构建和发布
- ✅ **进度显示**：下载过程中显示详细进度
- ✅ **自动备份**：更新前自动备份当前版本
- ✅ **安全更新**：使用批处理脚本确保更新过程的可靠性

## 📁 文件结构

```
gamecontrol/
├── version.py                           # 版本管理文件
├── logic/
│   └── auto_updater.py                 # 自动更新核心模块
├── .github/
│   └── workflows/
│       └── build-release.yml           # GitHub Actions构建工作流
├── test_auto_updater.py               # 更新功能测试脚本
├── requirements.txt                    # 新增httpx依赖
└── AUTO_UPDATE_IMPLEMENTATION.md      # 本文档
```

## 🔧 核心组件

### 1. 版本管理 (`version.py`)

```python
__version__ = "1.0.0"  # 当前版本
VERSION_INFO = {
    "major": 1,
    "minor": 0, 
    "patch": 0
}
```

**功能**：
- 定义应用程序版本信息
- 提供版本比较函数
- 配置GitHub仓库信息

### 2. 自动更新器 (`logic/auto_updater.py`)

**主要类**：
- `UpdateChecker`: 检查GitHub releases获取最新版本
- `UpdateDownloader`: 下载更新文件并显示进度
- `AutoUpdater`: 统一管理更新流程
- `UpdateInfo`: 更新信息数据类

**核心功能**：
- 异步检查GitHub releases API
- 智能判断是否有新版本可用
- 检查当前状态是否允许更新
- 下载更新文件并显示进度
- 创建更新脚本并自动重启

### 3. GitHub Actions (`build-release.yml`)

**触发条件**：
- 推送版本标签 (如 `v1.0.1`)
- 手动触发工作流

**构建产物**：
- `GameTimeLimiter.exe`: 标准单文件版本
- `GameTimeLimiter-Portable-v{version}.zip`: 便携版本

## 🎯 使用方法

### 开发者发布新版本

1. **更新版本号**：
   ```bash
   # 编辑 version.py
   __version__ = "1.0.1"
   VERSION_INFO = {"major": 1, "minor": 0, "patch": 1}
   ```

2. **提交并推送标签**：
   ```bash
   git add version.py
   git commit -m "Bump version to 1.0.1"
   git tag v1.0.1
   git push origin main
   git push origin v1.0.1
   ```

3. **GitHub Actions自动构建**：
   - 自动更新代码中的版本号
   - 构建两个版本的可执行文件
   - 创建GitHub Release
   - 上传构建产物

### 用户更新体验

1. **自动检查**：
   - 程序启动5秒后自动检查更新
   - 每24小时自动检查一次

2. **手动检查**：
   - 点击主界面的"Check Updates"按钮
   - 立即检查是否有新版本

3. **更新流程**：
   - 发现新版本时显示更新对话框
   - 用户确认后开始下载
   - 显示下载进度
   - 下载完成后自动安装并重启

## ⚙️ 配置说明

### GitHub仓库配置

在 `version.py` 中配置你的GitHub仓库信息：

```python
GITHUB_REPO_OWNER = "yourusername"  # 替换为你的GitHub用户名
GITHUB_REPO_NAME = "gamecontrol"    # 替换为你的仓库名
```

### 更新检查间隔

```python
UPDATE_CHECK_INTERVAL = 24 * 60 * 60  # 24小时（秒）
```

### 备份设置

```python
UPDATE_BACKUP_ENABLED = True  # 是否在更新前备份当前版本
```

## 🔒 安全机制

### 1. 状态检查

更新只能在以下条件下进行：
- ✅ 没有活动的游戏会话
- ✅ 没有正在进行的数学练习
- ✅ 用户明确确认更新

### 2. 备份机制

- 更新前自动备份当前版本到 `backup/` 目录
- 备份文件命名：`GameTimeLimiter_v{version}_{timestamp}.exe`
- 更新失败时可以手动恢复

### 3. 更新脚本

使用Windows批处理脚本执行更新：
- 等待主程序完全退出
- 支持ZIP和EXE两种更新格式
- 更新失败时自动恢复备份
- 更新成功后自动启动新版本

## 🧪 测试方法

### 1. 运行测试脚本

```bash
# UI测试
python test_auto_updater.py

# 无UI测试
python test_auto_updater.py --no-ui
```

### 2. 测试功能

- **版本比较测试**：验证版本比较逻辑
- **更新检查测试**：实际连接GitHub API检查更新
- **模拟更新测试**：模拟发现新版本的用户体验

### 3. 手动测试流程

1. 修改 `version.py` 中的版本号为较低版本
2. 运行程序，点击"Check Updates"
3. 验证是否正确检测到更新
4. 测试下载和安装流程

## 📋 依赖要求

新增依赖：
```
httpx  # 用于HTTP请求
```

现有依赖保持不变：
```
PyQt6
qasync
openai
python-dotenv
numpy
python-markdown==3.4.3
psutil==5.9.5
python-markdown-math
```

## 🚨 注意事项

### 1. 首次设置

- 确保在 `version.py` 中正确配置GitHub仓库信息
- 确保GitHub仓库已启用Actions功能
- 确保有正确的release权限

### 2. 网络要求

- 更新检查需要访问 `api.github.com`
- 下载更新需要访问 `github.com`
- 建议在网络良好的环境下进行更新

### 3. 权限要求

- 更新过程需要写入程序目录的权限
- 可能需要管理员权限（取决于安装位置）

## 🔄 更新流程图

```
启动程序
    ↓
延迟5秒检查更新
    ↓
每24小时自动检查 ←→ 用户手动检查
    ↓
发现新版本？
    ↓ 是
检查当前状态
    ↓ 可以更新
显示更新对话框
    ↓ 用户确认
开始下载更新
    ↓
显示下载进度
    ↓
下载完成
    ↓
备份当前版本
    ↓
创建更新脚本
    ↓
退出程序
    ↓
执行更新脚本
    ↓
重启新版本
```

## 📈 版本发布最佳实践

1. **版本号规范**：遵循语义化版本控制 (Semantic Versioning)
   - `MAJOR.MINOR.PATCH`
   - 不兼容的API修改：增加MAJOR
   - 向下兼容的功能新增：增加MINOR  
   - 向下兼容的问题修正：增加PATCH

2. **发布说明**：在GitHub Release中提供详细的更新说明
   - 新功能列表
   - 修复的问题
   - 已知问题
   - 升级注意事项

3. **测试流程**：
   - 本地测试更新功能
   - 验证构建产物
   - 测试自动更新流程

## 🎉 总结

自动更新功能为GameTimeLimiter提供了：

- **用户友好**：自动检查和一键更新
- **开发高效**：自动化构建和发布流程  
- **安全可靠**：多重检查和备份机制
- **易于维护**：清晰的代码结构和文档

这个实现确保了用户始终能够使用最新版本的功能和修复，同时为开发者提供了便捷的发布流程。 