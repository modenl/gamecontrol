# 集成测试指南

## 概述

本项目采用集成测试驱动的发布流程，确保所有主要功能场景在每次发布前都经过验证。

## 测试架构

### 测试模式
- **环境变量**: `GAMECONTROL_TEST_MODE=true`
- **测试数据库**: 使用独立的测试数据库 `test_game_sessions.db`
- **Mock服务**: 数学练习使用Mock模块，避免GPT API调用
- **禁用锁屏**: 测试模式下不执行锁屏操作
- **测试密码**: 管理员密码为 `test_admin_123`

### 目录结构
```
tests/
├── integration/
│   ├── test_framework.py      # 测试框架基类
│   └── test_main_scenarios.py # 主要场景测试
└── __init__.py

run_integration_tests.py          # 测试运行器
.githooks/
├── pre-push                   # Unix/Linux/Mac Git hook
└── pre-push.bat              # Windows Git hook
scripts/
└── install_git_hooks.py      # Git hook安装脚本
```

## 运行测试

### 手动运行
```bash
# 设置测试模式
export GAMECONTROL_TEST_MODE=true  # Linux/Mac
set GAMECONTROL_TEST_MODE=true     # Windows

# 运行所有集成测试
python run_integration_tests.py
```

### 自动运行（Git Hook）
```bash
# 安装Git hooks
python scripts/install_git_hooks.py install

# 现在每次git push前会自动运行测试
git push origin main
```

## 测试场景

### 当前覆盖的场景
1. **会话开始和停止流程**
   - 验证UI状态变化
   - 验证计时器功能
   - 验证按钮启用/禁用状态

2. **数学练习流程**
   - 验证数学面板打开
   - 验证答题功能
   - 验证奖励时间增加

3. **周状态显示**
   - 验证数据完整性
   - 验证UI显示正确性

4. **管理员面板访问**
   - 验证管理员按钮功能

5. **历史记录面板访问**
   - 验证历史面板打开

6. **更新检查功能**
   - 验证更新按钮状态变化

7. **会话时间验证**
   - 验证无效输入处理
   - 验证有效输入接受

## 添加新测试

### 1. 扩展现有测试
在 `tests/integration/test_main_scenarios.py` 中添加新的测试方法：

```python
async def test_new_feature(self):
    """测试新功能"""
    # 设置测试条件
    await self.framework.simulate_text_input(...)
    
    # 执行操作
    await self.framework.simulate_button_click(...)
    
    # 验证结果
    await self.framework.assert_ui_state({...}, "验证消息")
```

### 2. 创建新测试文件
在 `tests/integration/` 目录下创建新的 `test_*.py` 文件：

```python
from test_framework import IntegrationTestFramework

class NewFeatureTest:
    def __init__(self):
        self.framework = IntegrationTestFramework()
    
    async def test_scenario(self):
        # 测试逻辑
        pass
    
    async def run_all_tests(self):
        # 运行所有测试
        pass

# 主函数
async def main():
    test_runner = NewFeatureTest()
    await test_runner.framework.setup()
    try:
        results = await test_runner.run_all_tests()
        return all(result[1] for result in results)
    finally:
        await test_runner.framework.teardown()
```

## 测试工具

### IntegrationTestFramework 提供的方法

#### UI操作
- `simulate_button_click(button, wait_ms=100)` - 模拟按钮点击
- `simulate_text_input(line_edit, text, wait_ms=100)` - 模拟文本输入
- `simulate_admin_login(password=None)` - 模拟管理员登录

#### 状态检查
- `get_ui_state()` - 获取当前UI状态
- `assert_ui_state(expected_state, message="")` - 断言UI状态
- `get_weekly_status()` - 获取周状态数据

#### 测试管理
- `setup()` - 设置测试环境
- `teardown()` - 清理测试环境
- `wait_for_ui_update(timeout_ms=1000)` - 等待UI更新

## 发布流程

### 1. 开发阶段
- 编写功能代码
- 添加或更新相应的集成测试
- 本地运行测试确保通过

### 2. 提交前检查
```bash
# 手动运行测试
python run_integration_tests.py

# 如果测试通过，提交代码
git add .
git commit -m "功能描述"
```

### 3. 推送前验证
```bash
# Git hook会自动运行测试
git push origin main

# 如果测试失败，修复问题后重新推送
# 紧急情况下可以跳过测试（不推荐）
git push --no-verify origin main
```

### 4. 重大更新前
对于重大功能更新或版本发布：
1. 确保所有集成测试通过
2. 手动验证关键功能
3. 更新版本号
4. 创建发布标签

## 故障排除

### 常见问题

#### 1. 测试环境问题
```bash
# 检查虚拟环境
source venv/Scripts/activate  # Windows
source venv/bin/activate      # Linux/Mac

# 检查依赖
pip install -r requirements.txt
```

#### 2. 测试数据库问题
```bash
# 清理测试数据库
rm test_game_sessions.db
```

#### 3. UI测试失败
- 确保在测试模式下运行 (`GAMECONTROL_TEST_MODE=true`)
- 检查是否有其他应用程序实例在运行
- 增加等待时间 (`wait_ms` 参数)

#### 4. Git Hook问题
```bash
# 检查Git hook状态
python scripts/install_git_hooks.py check

# 重新安装Git hooks
python scripts/install_git_hooks.py uninstall
python scripts/install_git_hooks.py install
```

### 调试技巧

#### 1. 增加日志输出
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

#### 2. 单独运行测试文件
```bash
cd tests/integration
python test_main_scenarios.py
```

#### 3. 查看测试报告
测试运行后会生成 `integration_test_report.txt` 文件，包含详细的测试结果。

## 最佳实践

### 1. 测试设计原则
- **独立性**: 每个测试应该独立运行，不依赖其他测试
- **可重复性**: 测试应该可以多次运行并产生相同结果
- **快速性**: 测试应该尽快完成，避免长时间等待
- **清晰性**: 测试意图应该清晰，易于理解和维护

### 2. 测试数据管理
- 使用临时数据库和文件
- 在测试结束后清理所有测试数据
- 使用Mock服务避免外部依赖

### 3. 错误处理
- 提供清晰的错误消息
- 在测试失败时保留足够的调试信息
- 优雅地处理异常情况

### 4. 维护建议
- 定期审查和更新测试用例
- 删除过时或重复的测试
- 保持测试代码的简洁和可读性 