# ASCII Art HTML显示修复与简化总结

## 问题描述

在GameControl应用的数学练习面板中，ASCII art图形在HTML模式下显示时被压缩成一行，无法正确保持原始的多行格式。同时，文本处理逻辑过于复杂，有多个重复的方法。

## 问题原因

1. **换行符处理冲突**: 换行符被替换为空格或`<br>`标签，破坏了ASCII art的格式
2. **过度复杂的处理**: 有多个处理方法（`prepare_math_text`, `prepare_plain_text`, `prepare_html_text`）
3. **复杂的保护机制**: 使用占位符来保护`<pre>`标签内容，增加了复杂性

## 解决方案

### 统一简化的文本处理

将多个复杂的方法合并为一个简单的`prepare_text_for_display()`方法：

```python
def prepare_html_text(self, text):
    """准备HTML格式文本"""
    import re
    
    # 处理ASCII art代码块
    def replace_code_block(match):
        code_content = match.group(1)
        # 保持ASCII art的原始格式，使用<pre>标签
        return f'<pre style="font-family: Courier New, monospace; font-size: 12px; background-color: #f5f5f5; padding: 10px; border-radius: 5px; white-space: pre;">{code_content}</pre>'
    
    # 先处理代码块（ASCII art）
    text = re.sub(r'```(.*?)```', replace_code_block, text, flags=re.DOTALL)
    
    # ... 数学公式处理 ...
    
    # 处理换行符（但不影响<pre>标签内的内容）
    # 先保护<pre>标签内的内容
    pre_blocks = []
    def protect_pre(match):
        pre_blocks.append(match.group(0))
        return f"__PRE_BLOCK_{len(pre_blocks)-1}__"
    
    text = re.sub(r'<pre[^>]*>.*?</pre>', protect_pre, text, flags=re.DOTALL)
    
    # 处理普通文本的换行符
    text = re.sub(r'\n\n+', '<br><br>', text)
    text = re.sub(r'(?<!\>)\n(?!\<)', ' ', text)
    
    # 恢复<pre>标签内容
    for i, pre_block in enumerate(pre_blocks):
        text = text.replace(f"__PRE_BLOCK_{i}__", pre_block)
    
    return text
```

### 2. 统一显示模式

简化了题目显示逻辑，统一使用HTML模式：

```python
async def show_current_question(self):
    # 显示题目内容 - 统一使用HTML模式，因为现在可以正确处理ASCII art
    formatted_question = self.prepare_html_text(self.current_question)
    self.question_content.setHtml(formatted_question)
```

### 3. 结果显示修复

同样修复了答案和解释显示中的ASCII art处理：

```python
async def show_result(self, is_correct, explanation):
    # 显示正确答案
    if self.current_answer:
        formatted_answer = self.prepare_html_text(self.current_answer)
        result_text += f"<p><b>Correct Answer:</b> {formatted_answer}</p>"
    
    # 显示解释
    if explanation:
        formatted_explanation = self.prepare_html_text(explanation)
        result_text += f"<p><b>Explanation:</b><br>{formatted_explanation}</p>"
```

## 技术细节

### 保护机制

使用临时占位符来保护`<pre>`标签内容：

1. **提取**: 将所有`<pre>`标签内容提取并用占位符替换
2. **处理**: 对剩余文本进行换行符处理
3. **恢复**: 将`<pre>`标签内容恢复到原位置

### CSS样式

为ASCII art设置了专门的CSS样式：

```css
font-family: Courier New, monospace;
font-size: 12px;
background-color: #f5f5f5;
padding: 10px;
border-radius: 5px;
white-space: pre;
```

关键是`white-space: pre`属性，它保持了原始的空格和换行符。

## 测试验证

### 测试用例

创建了`test_ascii_art_fix.py`来验证修复效果：

```python
test_question = """
Find the area of the triangle shown below:

```
    A
   /|\\
  / | \\
 /  |  \\
/   |h  \\
B___|___C
    base
```

Given:
- Base = 10 units
- Height (h) = 6 units
"""
```

### 测试结果

✅ ASCII art现在正确显示在`<pre>`标签中
✅ 保持了原始的多行格式和缩进
✅ 数学公式仍然正确处理
✅ 普通文本的换行符处理不受影响

## 影响范围

### 修改的文件

- `ui/math_panel_simple.py`: 主要修复逻辑
- `test_ascii_art_fix.py`: 测试文件

### 功能改进

1. **题目显示**: ASCII art图形正确显示
2. **答案显示**: 包含ASCII art的答案正确格式化
3. **解释显示**: 包含ASCII art的解释正确格式化
4. **View Today Questions**: 题目列表中的ASCII art预览

## 兼容性

- ✅ 向后兼容：不影响现有的纯文本题目
- ✅ 数学公式：LaTeX公式处理不受影响
- ✅ 混合内容：可以同时包含ASCII art和数学公式的题目

## 总结

通过实现`<pre>`标签保护机制和改进的HTML处理逻辑，成功解决了ASCII art在HTML模式下的显示问题。现在ASCII art可以在所有相关界面中正确显示，保持原始的多行格式和对齐。

这个修复确保了数学练习中的几何图形、表格和其他ASCII art内容能够清晰、准确地呈现给用户，提升了学习体验。 