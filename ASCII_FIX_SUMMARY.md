# ASCII Art 显示修复方案

## 问题描述
用户反馈："ascii art对齐有问题" - ASCII图形在数学面板中显示错乱，无法正确对齐。

## 根本原因
1. **HTML渲染限制**：QLabel的HTML渲染对等宽字体支持有限
2. **字体不一致**：不同字符宽度不统一导致对齐问题
3. **样式冲突**：CSS样式与ASCII art的格式要求冲突

## 解决方案

### 1. 混合显示模式
- **检测内容类型**：自动检测题目是否包含ASCII art（```代码块```）
- **智能切换**：
  - 包含ASCII art → 使用纯文本模式 + 等宽字体
  - 普通文本 → 使用HTML模式 + 数学公式渲染

### 2. 技术实现

#### 内容检测
```python
import re
has_ascii_art = bool(re.search(r'```.*?```', text, re.DOTALL))
```

#### 显示方式切换
```python
if has_ascii_art:
    # 纯文本模式 - 完美保持ASCII art格式
    self.question_content.setPlainText(formatted_question)
    mono_font = QFont("Courier New", 12)
    mono_font.setStyleHint(QFont.StyleHint.Monospace)
    self.question_content.setFont(mono_font)
else:
    # HTML模式 - 支持数学公式和格式化
    self.question_content.setHtml(formatted_question)
    content_font = QFont()
    content_font.setPointSize(14)
    self.question_content.setFont(content_font)
```

#### 文本处理
```python
def prepare_plain_text(self, text):
    """纯文本模式：移除标记，保持原始格式"""
    # 移除代码块标记，保留内容
    text = re.sub(r'```\n?(.*?)\n?```', r'\1', text, flags=re.DOTALL)
    
    # 简单符号替换
    text = text.replace('\\pi', 'π')
    text = text.replace('\\theta', 'θ')
    # ... 更多符号
    
    return text.strip()
```

### 3. 优势

#### 显示效果
- ✅ ASCII art完美对齐
- ✅ 等宽字体确保字符宽度一致
- ✅ 保持原始格式不变形

#### 兼容性
- ✅ 普通文本仍支持HTML格式化
- ✅ 数学公式正常显示
- ✅ 深色主题兼容

#### 性能
- ✅ 无需复杂CSS处理
- ✅ 原生Qt组件，稳定可靠
- ✅ 自动检测，无需手动配置

### 4. 测试验证

#### 三角形测试
```
      A
     /|\
    / | \
   /  |  \
  /   |h  \
 /    |    \
/     |     \
B-----+-----C
    base
```

#### 坐标系测试
```
        Y
        ^
        |
        |    * (3,4)
        |   /|
        |  / |
        | /  |
        |/   |
        +----+-----> X
        |    |
        |    |
        |    * (3,-4)
        |
```

### 5. 使用方法

#### 自动检测
系统会自动检测题目内容：
- 发现```代码块``` → 自动切换到等宽字体模式
- 普通文本 → 保持HTML渲染模式

#### 手动测试
```bash
# 测试ASCII art修复效果
python test_ascii_fix.py
```

## 总结

这个解决方案通过智能检测和模式切换，完美解决了ASCII art对齐问题：

1. **保持功能完整性**：普通文本和数学公式仍然正常显示
2. **修复对齐问题**：ASCII art使用等宽字体，确保完美对齐
3. **自动化处理**：无需手动配置，系统自动选择最佳显示方式
4. **向后兼容**：不影响现有功能，只是改进显示效果

现在ASCII art应该能够正确对齐显示了！ 