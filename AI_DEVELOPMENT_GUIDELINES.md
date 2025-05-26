# AI Development Guidelines

## 🤖 AI开发规范

本文档规定了AI助手在协助开发此项目时必须遵循的规则和最佳实践。

## 📋 核心规则

### ✅ 允许的操作

#### 1. **可重复执行的集成测试**
- ✅ 添加可以多次运行的集成测试文件
- ✅ 测试文件应该能够在任何时候运行并产生一致的结果
- ✅ 测试应该有清理机制，不会留下副作用
- ✅ 文件命名格式：`test_integration_*.py`

**示例**：
```python
# test_integration_session_flow.py
def test_complete_session_flow():
    """测试完整的游戏会话流程"""
    # 可重复执行的测试逻辑
    pass

def teardown():
    """清理测试环境"""
    # 确保测试后环境干净
    pass
```

#### 2. **永久性功能文件**
- ✅ 核心功能模块
- ✅ UI组件
- ✅ 配置文件
- ✅ 文档更新

### ❌ 禁止的操作

#### 1. **临时性测试文件**
- ❌ 只运行一次的测试脚本
- ❌ 调试用的临时测试
- ❌ 验证特定问题的一次性测试
- ❌ 文件命名如：`test_fix_*.py`, `test_debug_*.py`, `temp_test_*.py`

#### 2. **一次性修复和清理文件**
- ❌ `fix_*.py` - 修复脚本
- ❌ `cleanup_*.py` - 清理脚本  
- ❌ `repair_*.py` - 修复工具
- ❌ `migrate_*.py` - 迁移脚本（除非是永久的数据库迁移）
- ❌ `patch_*.py` - 补丁文件

#### 3. **临时性文档**
- ❌ `*_FIX.md` - 修复说明
- ❌ `*_SOLUTION.md` - 解决方案文档
- ❌ `*_IMPLEMENTATION.md` - 实现说明（除非是永久架构文档）
- ❌ `TEMP_*.md` - 临时文档
- ❌ `DEBUG_*.md` - 调试文档

#### 4. **调试和诊断工具**
- ❌ `debug_*.py` - 调试脚本
- ❌ `check_*.py` - 检查工具（除非是永久的健康检查）
- ❌ `diagnose_*.py` - 诊断工具

## 🔄 替代方案

### 代替临时测试文件
```python
# 在现有测试文件中添加测试方法
# tests/test_integration_core.py

class TestCoreIntegration:
    def test_new_feature(self):
        """测试新功能 - 可重复执行"""
        pass
```

### 代替修复脚本
```python
# 在核心代码中添加自修复逻辑
# logic/self_repair.py

class SelfRepair:
    def auto_fix_common_issues(self):
        """自动修复常见问题 - 作为永久功能"""
        pass
```

### 代替临时文档
```markdown
<!-- 在 README.md 或相关文档中添加章节 -->
## 故障排除

### 常见问题及解决方案
1. 问题描述
2. 解决步骤
3. 预防措施
```

## 📁 推荐的文件结构

```
gamecontrol/
├── tests/
│   ├── integration/
│   │   ├── test_integration_session.py     ✅ 可重复集成测试
│   │   ├── test_integration_monitoring.py  ✅ 可重复集成测试
│   │   └── test_integration_updates.py     ✅ 可重复集成测试
│   └── unit/
│       ├── test_game_limiter.py            ✅ 单元测试
│       └── test_window_monitor.py          ✅ 单元测试
├── logic/
│   ├── self_repair.py                      ✅ 永久自修复功能
│   └── health_check.py                     ✅ 永久健康检查
└── docs/
    ├── TROUBLESHOOTING.md                  ✅ 永久故障排除指南
    └── ARCHITECTURE.md                     ✅ 永久架构文档
```

## 🚫 避免的文件模式

```
❌ test_fix_dll_issue.py
❌ test_debug_qasync.py  
❌ cleanup_old_files.py
❌ fix_monitor_bug.py
❌ repair_database.py
❌ DLL_FIX_SOLUTION.md
❌ QASYNC_DEBUG_NOTES.md
❌ TEMP_MONITOR_FIX.md
```

## 🎯 最佳实践

### 1. **测试文件**
- 使用描述性名称：`test_integration_complete_workflow.py`
- 包含setup和teardown方法
- 确保测试的幂等性（多次运行结果一致）
- 添加详细的文档字符串

### 2. **功能文件**
- 优先扩展现有文件而不是创建新文件
- 新功能应该是永久性的，不是临时修复
- 包含适当的错误处理和日志记录

### 3. **文档**
- 更新现有文档而不是创建新的修复说明
- 在README.md中添加故障排除章节
- 保持文档的时效性和准确性

## 🔍 代码审查检查清单

在添加任何文件之前，请检查：

- [ ] 这个文件是否可以重复执行？
- [ ] 这个文件是否解决永久性需求？
- [ ] 是否可以通过修改现有文件来实现？
- [ ] 文件名是否遵循命名规范？
- [ ] 是否包含适当的文档和注释？

## 📞 违规处理

如果AI助手违反了这些规则：

1. **立即停止** 创建违规文件
2. **解释** 为什么该文件违反规则
3. **提供** 符合规范的替代方案
4. **更新** 现有文件而不是创建新文件

## 🎉 总结

遵循这些规则将确保：
- 项目保持整洁和可维护
- 避免临时文件的积累
- 提高代码质量和一致性
- 减少技术债务

**记住：每个添加的文件都应该是项目的永久组成部分，而不是临时解决方案。** 