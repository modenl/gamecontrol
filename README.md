# GameControl - 游戏时间管理器

一个用于管理和控制游戏时间的桌面应用程序，特别适合需要限制孩子游戏时间的家长使用。

## 功能特点

- 游戏时间限制：设置每周游戏时间上限
- 实时监控：自动检测和关闭未授权的游戏进程
- 数学练习奖励：通过完成数学练习获得额外游戏时间
- 详细统计：记录和展示游戏时间使用情况
- 家长控制：管理员密码保护，确保设置安全
- 自动锁屏：会话结束时自动锁定屏幕

## 安装要求

- Windows 10 或更高版本
- Python 3.8 或更高版本
- 依赖包（见 requirements.txt）

## 快速开始

1. 克隆仓库：
   ```bash
   git clone https://github.com/yourusername/gamecontrol.git
   cd gamecontrol
   ```

2. 创建并激活虚拟环境：
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

3. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

4. 配置环境变量：
   - 复制 `.env.example` 到 `.env`
   - 在 `.env` 中设置必要的配置项

5. 运行应用：
   ```bash
   python main.py
   ```

## 构建可执行文件

使用以下命令构建独立的可执行文件：

```bash
python build.py --optimize 1
```

构建完成后，可执行文件将位于 `dist` 目录中。

## 使用说明

1. 基本使用：
   - 启动应用程序
   - 输入游戏时长
   - 点击"开始游戏"按钮

2. 获取额外时间：
   - 点击"赢取奖励"按钮
   - 完成数学练习题
   - 每道题可获得额外游戏时间

3. 管理员功能：
   - 点击"管理"按钮
   - 输入管理员密码（默认：password）
   - 可以修改时间限制、查看历史记录等

## 安全说明

- 默认管理员密码为 'password'，请在首次使用时修改
- 所有敏感操作都需要管理员密码验证
- 会话数据存储在本地SQLite数据库中

## 配置选项

主要配置项（在 `.env` 文件中）：
- `OPENAI_API_KEY`：用于生成数学练习题（可选）

系统常量（在 `logic/constants.py` 中）：
- `DEFAULT_WEEKLY_LIMIT`：默认每周游戏时间限制（分钟）
- `MAX_WEEKLY_LIMIT`：最大每周游戏时间限制（分钟）
- `MATH_REWARD_PER_QUESTION`：每道数学题奖励时间（分钟）
- `MAX_DAILY_MATH_QUESTIONS`：每日最大数学题数量

## 贡献指南

欢迎提交 Pull Requests！请确保：
1. 代码符合项目的编码规范
2. 添加必要的测试
3. 更新相关文档

## 许可证

MIT License - 详见 LICENSE 文件

## 作者

[Your Name] - [your@email.com]

## Project Structure

```
gamecontrol/
├── logic/               # Business logic
│   ├── constants.py     # Application constants
│   ├── database.py      # Database operations
│   ├── game_limiter.py  # Game time limiting logic
│   └── math_exercises.py # Math exercises generator
├── ui/                  # User interface
│   ├── base.py          # Base UI components
│   ├── main_window.py   # Main application window
│   ├── admin_panel.py   # Admin control panel
│   ├── math_panel.py    # Math exercises panel
│   └── history_panel.py # Session history panel
├── main.py              # Application entry point
├── requirements.txt     # Dependencies
└── README.md            # This file
```

## Implementation Details

This application uses:
- PyQt6 for the user interface
- qasync for asyncio integration with PyQt6
- SQLite for data storage
- Threading for non-blocking operations

## License

This project is licensed under the MIT License - see the LICENSE file for details. 