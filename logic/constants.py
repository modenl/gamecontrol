import os
from hashlib import sha256

# 应用名称
APP_NAME = "GameControl"

# 数据库文件
DB_FILE = os.getenv('GAMECONTROL_DB_PATH', "game_sessions.db")

# 管理员密码（SHA256哈希）
ADMIN_PASS_HASH = "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8"  # 'password' 的sha256

# 游戏时间限制
DEFAULT_WEEKLY_LIMIT = 120  # 2小时（分钟）
MAX_WEEKLY_LIMIT = 240  # 4小时（分钟）

# 数学练习奖励
MATH_REWARD_PER_QUESTION = 1.0  # 每道题奖励分钟数（默认，实际由GPT指定0.5-5分钟）
MAX_DAILY_MATH_QUESTIONS = 10  # 每日最大题目数

# 数学题难度系数对应的奖励分钟数（已弃用，现由GPT为每题指定1-5分钟奖励）
MATH_DIFFICULTY_REWARDS = {
    1: 1,  # 简单：1分钟
    2: 2,  # 一般：2分钟
    3: 3,  # 困难：3分钟
    4: 4   # 竞赛级：4分钟
}

# UI相关
UI_TITLE = "游戏时间管理器"
UI_WIDTH = 800
UI_HEIGHT = 750
UI_MIN_WIDTH = 700
UI_MIN_HEIGHT = 650

# 颜色主题
THEME_BG = "#f0f0f0"
THEME_PRIMARY = "#4a6fa5"
THEME_SECONDARY = "#6c757d"
THEME_SUCCESS = "#28a745"
THEME_DANGER = "#dc3545"
THEME_WARNING = "#ffc107"
THEME_INFO = "#17a2b8"
THEME_LIGHT = "#f8f9fa"
THEME_DARK = "#343a40"

# 字体
FONT_FAMILY = "Microsoft YaHei UI"  # 中文友好字体
FONT_SIZE_SMALL = 9
FONT_SIZE_NORMAL = 10
FONT_SIZE_LARGE = 12
FONT_SIZE_XLARGE = 14
FONT_SIZE_XXLARGE = 18

# 按钮尺寸
BUTTON_HEIGHT = 28
BUTTON_WIDTH = 100
BUTTON_PADX = 10
BUTTON_PADY = 5

# 间距
PADDING_SMALL = 5
PADDING_MEDIUM = 10
PADDING_LARGE = 15
PADDING_XLARGE = 20

# 测试模式配置
TEST_MODE = os.getenv('GAMECONTROL_TEST_MODE', 'false').lower() == 'true'
TEST_ADMIN_PASSWORD = "test_admin_123"  # 测试专用管理员密码
TEST_ADMIN_PASS_HASH = sha256(TEST_ADMIN_PASSWORD.encode()).hexdigest()

# 测试数据库配置
TEST_DB_FILE = "test_game_sessions.db"

# 锁屏功能开关
ENABLE_LOCK_SCREEN = True

# 测试模式下的配置覆盖
if TEST_MODE:
    # 使用测试数据库
    DB_FILE = TEST_DB_FILE
    # 禁用锁屏
    ENABLE_LOCK_SCREEN = False
    # 使用测试管理员密码
    ADMIN_PASS_HASH = TEST_ADMIN_PASS_HASH
    # 禁用对话框
    ENABLE_DIALOGS = False
else:
    ENABLE_DIALOGS = True 