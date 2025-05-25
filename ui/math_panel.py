import sys
import os
import re
import logging
import asyncio
import json
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QLabel,
    QPushButton,
    QLineEdit,
    QTextEdit,
    QFrame,
    QProgressBar,
    QMessageBox,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize, QUrl
from PyQt6.QtGui import QFont
from PyQt6.QtWebEngineWidgets import QWebEngineView

from logic.constants import (
    PADDING_SMALL,
    PADDING_MEDIUM,
    PADDING_LARGE,
    THEME_PRIMARY,
    THEME_SUCCESS,
    THEME_DANGER,
    THEME_WARNING,
    MAX_DAILY_MATH_QUESTIONS,
    MATH_REWARD_PER_QUESTION,
)
from logic.math_exercises import MathExercises
from logic.database import get_week_start
from ui.base import ToolTip, ShakeEffect
from qasync import asyncSlot
from datetime import date, datetime

logger = logging.getLogger(__name__)


class MathPanel(QDialog):
    """数学练习面板 - 使用KaTeX渲染数学公式"""

    # 定义信号
    on_complete_signal = pyqtSignal(int)  # 参数:奖励分钟数

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.math = MathExercises()
        self.loading = False
        self.answer_checked = False
        self.current_question = None
        self.current_answer = None
        self.current_explanation = None
        self.current_index = 0
        self.questions = []

        # 设置窗口
        self.setWindowTitle("Math Exercise - Enhanced Formula Display")
        self.resize(1200, 900)
        self.setMinimumSize(900, 700)
        self.setModal(True)

        # 初始化UI
        self.setup_ui()

        # 检查session状态后再加载题目
        if self.check_session_status():
            # 加载题目
            asyncio.create_task(self.load_or_generate_questions())
        else:
            # 显示禁用状态
            self.show_session_active_warning()

    def get_katex_html_template(self):
        """获取KaTeX HTML模板"""
        return """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Math Exercise</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css">
    <script src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/contrib/auto-render.min.js"></script>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f8f9fa;
            color: #333;
            line-height: 1.6;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background-color: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            padding: 30px;
        }
        .question-header {
            border-bottom: 2px solid #e9ecef;
            padding-bottom: 15px;
            margin-bottom: 25px;
        }
        .question-title {
            font-size: 24px;
            color: #2c3e50;
            margin: 0 0 10px 0;
            font-weight: 600;
        }
        .question-meta {
            display: flex;
            gap: 20px;
            font-size: 14px;
            margin-bottom: 10px;
        }
        .difficulty {
            padding: 4px 12px;
            border-radius: 20px;
            font-weight: bold;
            color: white;
        }
        .difficulty.easy { background-color: #28a745; }
        .difficulty.medium { background-color: #ffc107; color: #333; }
        .difficulty.hard { background-color: #dc3545; }
        .difficulty.contest { background-color: #ff6600; }
        .reward {
            color: #17a2b8;
            font-weight: bold;
        }
        .question-content {
            font-size: 18px;
            line-height: 1.8;
            margin: 25px 0;
            padding: 20px;
            background-color: #f8f9fa;
            border-left: 4px solid #007bff;
            border-radius: 0 8px 8px 0;
        }
        .result-section {
            margin-top: 30px;
            padding: 20px;
            border-radius: 8px;
            border: 2px solid #e9ecef;
            background-color: #f8f9fa;
        }
        .result-correct {
            border-color: #28a745;
            background-color: #d4edda;
            color: #155724;
        }
        .result-incorrect {
            border-color: #dc3545;
            background-color: #f8d7da;
            color: #721c24;
        }
        .result-title {
            font-size: 20px;
            font-weight: bold;
            margin-bottom: 15px;
        }
        .correct-answer {
            font-size: 18px;
            margin: 15px 0;
            padding: 15px;
            background-color: rgba(255,255,255,0.7);
            border-radius: 5px;
            border-left: 4px solid #007bff;
        }
        .explanation {
            margin-top: 20px;
            padding: 20px;
            background-color: rgba(255,255,255,0.7);
            border-radius: 5px;
            border-left: 4px solid #17a2b8;
        }
        .explanation-title {
            font-weight: bold;
            color: #17a2b8;
            margin-bottom: 10px;
        }
        .katex { font-size: 1.1em; }
        .katex-display { margin: 20px 0; }
        .hint {
            font-style: italic;
            color: #6c757d;
            font-size: 14px;
            margin-bottom: 15px;
        }
        /* ASCII art diagram styles */
        .ascii-art-container {
            margin: 20px 0;
            border-radius: 8px;
            background-color: #1e1e1e;
            border: 1px solid #444;
            overflow: hidden;
        }
        .ascii-art {
            font-family: 'Courier New', 'Liberation Mono', Consolas, Monaco, monospace;
            font-size: 14px;
            line-height: 1.3;
            background-color: #1e1e1e;
            color: #d4d4d4;
            border: none;
            border-radius: 0;
            padding: 20px;
            margin: 0;
            white-space: pre;
            overflow-x: auto;
            text-align: left;
        }
        .ascii-diagram {
            font-family: 'Courier New', Consolas, Monaco, monospace;
            font-size: 14px;
            line-height: 1.2;
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 6px;
            padding: 15px;
            margin: 15px 0;
            text-align: center;
            white-space: pre;
            overflow-x: auto;
        }
        pre {
            font-family: 'Courier New', Consolas, Monaco, monospace;
            font-size: 14px;
            line-height: 1.2;
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 6px;
            padding: 15px;
            margin: 15px 0;
            white-space: pre;
            overflow-x: auto;
        }
        code {
            font-family: 'Courier New', Consolas, Monaco, monospace;
            background-color: #f8f9fa;
            padding: 2px 4px;
            border-radius: 4px;
            border: 1px solid #dee2e6;
        }
    </style>
</head>
<body>
    <div class="container">
        <div id="content">
            <!-- Content will be inserted here -->
        </div>
    </div>
    
    <script>
        // 渲染所有数学公式
        function renderMath() {
            renderMathInElement(document.body, {
                delimiters: [
                    {left: '$$', right: '$$', display: true},
                    {left: '$', right: '$', display: false},
                    {left: '\\[', right: '\\]', display: true},
                    {left: '\\(', right: '\\)', display: false}
                ],
                throwOnError: false,
                errorColor: '#cc0000',
                strict: false
            });
        }
        
        // 页面加载完成后渲染数学公式
        document.addEventListener('DOMContentLoaded', renderMath);
        
        // 提供外部调用的方法来重新渲染数学公式
        window.renderMath = renderMath;
    </script>
</body>
</html>
        """

    def setup_ui(self):
        """设置UI组件"""
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(
            PADDING_MEDIUM, PADDING_MEDIUM, PADDING_MEDIUM, PADDING_MEDIUM
        )
        main_layout.setSpacing(PADDING_MEDIUM)

        # 顶部信息框架
        info_frame = QFrame()
        info_frame.setFrameShape(QFrame.Shape.StyledPanel)
        info_frame.setFrameShadow(QFrame.Shadow.Raised)
        info_layout = QHBoxLayout(info_frame)

        # 标题
        title_label = QLabel("Math Exercise")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        info_layout.addWidget(title_label)

        # 今日奖励分钟数标签
        self.reward_label = QLabel("Today's Reward: 0 minutes")
        info_layout.addWidget(self.reward_label, 1)

        # 完成计数
        self.done_label = QLabel(f"Completed: 0/{MAX_DAILY_MATH_QUESTIONS}")
        info_layout.addWidget(self.done_label)

        # 奖励说明按钮
        reward_info_btn = QPushButton("Reward Information")
        reward_info_btn.setToolTip("View the reward minutes for different difficulty levels")
        reward_info_btn.clicked.connect(self.show_reward_info)
        reward_info_btn.setAutoDefault(False)
        reward_info_btn.setDefault(False)
        info_layout.addWidget(reward_info_btn)

        main_layout.addWidget(info_frame)

        # 题目显示区域 - 使用WebEngineView
        question_frame = QFrame()
        question_frame.setFrameShape(QFrame.Shape.StyledPanel)
        question_frame.setFrameShadow(QFrame.Shadow.Raised)
        question_layout = QVBoxLayout(question_frame)

        # 创建WebEngineView来显示数学公式
        self.question_web = QWebEngineView()
        self.question_web.setMinimumHeight(400)
        self.question_web.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        
        # 设置初始HTML
        self.question_web.setHtml(self.get_katex_html_template())
        
        question_layout.addWidget(self.question_web)
        main_layout.addWidget(question_frame)

        # 答案输入框架
        answer_frame = QFrame()
        answer_frame.setFrameShape(QFrame.Shape.StyledPanel)
        answer_frame.setFrameShadow(QFrame.Shadow.Raised)
        answer_layout = QHBoxLayout(answer_frame)

        # 答案标签
        answer_label = QLabel("Your Answer:")
        answer_layout.addWidget(answer_label)

        # 答案输入框
        self.answer_entry = QLineEdit()
        self.answer_entry.setMinimumWidth(200)
        self.answer_entry.returnPressed.connect(
            lambda: asyncio.create_task(self.submit_answer())
        )
        answer_layout.addWidget(self.answer_entry)

        # 提交按钮
        self.submit_button = QPushButton("Submit Answer")
        self.submit_button.clicked.connect(
            lambda: asyncio.create_task(self.submit_answer())
        )
        self.submit_button.setEnabled(False)
        self.submit_button.setDefault(True)
        self.submit_button.setAutoDefault(False)
        answer_layout.addWidget(self.submit_button)

        main_layout.addWidget(answer_frame)

        # 进度条 - 仅在加载时显示
        self.progress_frame = QFrame()
        progress_layout = QVBoxLayout(self.progress_frame)

        self.progress_label = QLabel("Loading questions, please wait...")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        progress_layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        progress_layout.addWidget(self.progress_bar)

        self.progress_frame.hide()
        main_layout.addWidget(self.progress_frame)

        # 底部按钮框架
        button_frame = QFrame()
        button_layout = QHBoxLayout(button_frame)

        # 查看题目按钮
        self.debug_button = QPushButton("View Today's Questions")
        self.debug_button.clicked.connect(self.show_today_questions)
        self.debug_button.setAutoDefault(False)
        button_layout.addWidget(self.debug_button)

        # 下一题按钮
        self.next_button = QPushButton("Next Question")
        self.next_button.clicked.connect(self.next_question)
        self.next_button.setEnabled(False)
        self.next_button.setAutoDefault(False)
        button_layout.addWidget(self.next_button)

        # 空白
        button_layout.addStretch()

        # 关闭按钮
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        self.close_button.setAutoDefault(False)
        button_layout.addWidget(self.close_button)

        main_layout.addWidget(button_frame)

        # 设置工具提示
        ToolTip(self.next_button, "Go to the next question")
        ToolTip(self.submit_button, "Submit your answer")
        ToolTip(self.done_label, f"You can complete up to {MAX_DAILY_MATH_QUESTIONS} questions per day")

    def check_session_status(self):
        """检查游戏session状态，返回是否允许做数学练习"""
        if self.parent and hasattr(self.parent, 'session_active'):
            if self.parent.session_active:
                logger.info("检测到活动的游戏session，禁用数学练习")
                return False
        return True

    def show_session_active_warning(self):
        """显示session活跃时的警告信息"""
        warning_html = """
        <div style="text-align: center; padding: 40px;">
            <h2 style="color: #dc3545; margin-bottom: 20px;">Math Exercise Temporarily Unavailable</h2>
            <p style="font-size: 18px; color: #6c757d; margin: 20px 0;">
                A game session is currently in progress.
            </p>
            <p style="font-size: 16px; color: #6c757d;">
                To ensure fair game time management, math exercises cannot be performed during active game sessions.
            </p>
            <p style="font-size: 16px; color: #28a745; margin-top: 30px; font-weight: bold;">
                Please return after the game session ends!
            </p>
        </div>
        """
        
        self.update_web_content(warning_html)
        
        # 禁用所有交互组件
        self.answer_entry.setEnabled(False)
        self.submit_button.setEnabled(False)
        self.next_button.setEnabled(False)
        self.debug_button.setEnabled(False)
        
        # 隐藏进度条
        self.hide_progress()

    async def load_or_generate_questions(self):
        """自动加载或生成题目"""
        if self.loading:
            logger.warning("已有加载任务在运行，忽略此次请求")
            return

        self.loading = True
        try:
            self.show_progress("Loading questions, please wait...")

            # 先初始化MathExercises
            await self.math.initialize()

            # 直接使用异步方法
            questions = await self.math.get_daily_questions()
            logger.info(
                f"获取到{len(questions)}道题目，检查难度：{[q.get('difficulty', 'unknown') for q in questions]}"
            )

            # 查看已完成的题目数量
            done_count = await self.math.get_completed_count()

            # 直接调用加载完成回调
            await self.on_questions_loaded(questions, done_count)

        except Exception as e:
            logger.error(f"加载题目出错: {e}")
            await self.on_load_error(str(e))
        finally:
            self.loading = False

    async def on_questions_loaded(self, questions, done_count):
        """题目加载完成回调"""
        self.hide_progress()
        self.questions = questions
        self.done_count = done_count
        logger.info(
            f"[DEBUG] on_questions_loaded: done_count={self.done_count}, total={len(self.questions)}"
        )
        self.update_done_count()
        # 只在全部完成时才显示"已完成"
        if self.questions and self.done_count < len(self.questions):
            self.current_index = self.done_count
            await self.show_current_question()
        else:
            self.question_web.setHtml("<p>All questions for today have been completed!</p>")
            self.submit_button.setEnabled(False)

    async def on_load_error(self, error_msg):
        """题目加载错误回调"""
        self.hide_progress()

        QMessageBox.critical(self, "Loading Error", f"Error loading questions: {error_msg}")
        self.close()

    def prepare_math_text(self, text):
        """准备数学文本，将LaTeX格式转换为KaTeX可识别的格式，并处理ASCII art"""
        if not text:
            return ""
        
        # 处理ASCII art代码块，使其更像ChatGPT的显示效果
        import re
        
        # 查找```代码块并转换为独立的ASCII art显示块
        def replace_code_block(match):
            code_content = match.group(1).strip()
            # 为ASCII art添加特殊样式
            return f'''
            <div class="ascii-art-container">
                <pre class="ascii-art">{code_content}</pre>
            </div>
            '''
        
        # 替换```代码块
        text = re.sub(r'```\n?(.*?)\n?```', replace_code_block, text, flags=re.DOTALL)
        
        # 首先保护所有明显的货币表达式，避免被数学公式处理误伤
        # 匹配模式：$数字 或 $数字.数字 (货币)
        currency_placeholders = {}
        placeholder_counter = 0
        
        def protect_currency(match):
            nonlocal placeholder_counter
            currency_text = match.group(0)
            placeholder = f"__CURRENCY_PLACEHOLDER_{placeholder_counter}__"
            currency_placeholders[placeholder] = currency_text
            placeholder_counter += 1
            return placeholder
        
        # 保护货币符号（$数字 或 $数字.数字）
        text = re.sub(r'\$\d+(?:\.\d+)?', protect_currency, text)
        
        # 数学公式处理 - 修复常见的LaTeX格式问题
        
        # 1. 处理 \[ ... \] 块级公式 (修复正则表达式)
        text = re.sub(r'\\{1,2}\[(.*?)\\{1,2}\]', r'$$\1$$', text, flags=re.DOTALL)
        
        # 2. 处理 \( ... \) 内联公式 (修复正则表达式)
        text = re.sub(r'\\{1,2}\((.*?)\\{1,2}\)', r'$\1$', text, flags=re.DOTALL)
        
        # 3. 处理非标准的 \$$ ... \$$ 格式（转为标准的 $$ ... $$）
        text = re.sub(r'\\{1,2}\$\$(.*?)\\{1,2}\$\$', r'$$\1$$', text, flags=re.DOTALL)
        
        # 4. 清理空的数学标记
        text = re.sub(r'\$\s*\$', '', text)
        
        # 5. 清理重复的数学标记
        text = re.sub(r'\$\$\$\$', '$$', text)
        text = re.sub(r'\$\$\$', '$$', text)
        
        # 最后恢复被保护的货币符号
        for placeholder, currency_text in currency_placeholders.items():
            text = text.replace(placeholder, currency_text)
        
        return text

    def get_question_html(self):
        """生成题目的HTML内容"""
        if not self.current_question:
            return "<div>No question available</div>"
        
        # 获取题目信息
        title = f"Question {self.current_index + 1}/{len(self.questions)}"
        question_text = self.prepare_math_text(self.current_question)
        
        # 获取难度和奖励信息
        difficulty = self.questions[self.current_index].get("difficulty", 2)
        reward_mins = self.questions[self.current_index].get("reward_minutes", 2)  # 使用实际奖励时间
        
        # 难度标签
        difficulty_classes = {
            1: "easy",
            2: "medium", 
            3: "hard",
            4: "contest"
        }
        difficulty_names = {
            1: "Easy",
            2: "Medium",
            3: "Hard", 
            4: "Contest"
        }
        
        difficulty_class = difficulty_classes.get(difficulty, "medium")
        difficulty_name = difficulty_names.get(difficulty, "Medium")
        
        # 生成HTML
        html_content = f"""
        <div class="question-header">
            <h1 class="question-title">{title}</h1>
            <div class="question-meta">
                <span class="difficulty {difficulty_class}">{difficulty_name}</span>
                <span class="reward">Reward: {reward_mins} minutes</span>
            </div>
        </div>
        <div class="question-content">
            {question_text}
        </div>
        """
        
        return html_content

    def get_result_html(self, is_correct, explanation=None):
        """生成结果显示的HTML内容"""
        result_class = "result-correct" if is_correct else "result-incorrect"
        result_title = "Correct!" if is_correct else "Incorrect!"
        
        html_content = f"""
        <div class="result-section {result_class}">
            <div class="result-title">{result_title}</div>
        """
        
        if not is_correct:
            # 显示正确答案
            formatted_answer = self.prepare_math_text(self.current_answer)
            html_content += f"""
            <div class="correct-answer">
                <strong>Correct Answer:</strong><br>
                {formatted_answer}
            </div>
            """
        
        if explanation and not is_correct:
            # 显示解释 - 处理换行符和LaTeX公式
            formatted_explanation = self.prepare_math_text(explanation)
            # 将换行符转换为HTML换行
            formatted_explanation = formatted_explanation.replace('\n', '<br>')
            html_content += f"""
            <div class="explanation">
                <div class="explanation-title">Explanation:</div>
                {formatted_explanation}
            </div>
            """
        
        html_content += "</div>"
        return html_content

    def update_web_content(self, content_html):
        """更新WebEngineView的内容"""
        # 获取完整的HTML模板
        full_html = self.get_katex_html_template()
        
        # 替换内容
        updated_html = full_html.replace(
            '<!-- Content will be inserted here -->', 
            content_html
        )
        
        # 设置HTML并触发KaTeX渲染
        self.question_web.setHtml(updated_html)
        
        # 等待页面加载完成后执行JavaScript来渲染数学公式
        def on_load_finished(ok):
            if ok:
                self.question_web.page().runJavaScript("window.renderMath();")
        
        self.question_web.loadFinished.connect(on_load_finished)

    async def show_current_question(self):
        """显示当前题目"""
        if not self.questions or self.current_index >= len(self.questions):
            return

        question_data = self.questions[self.current_index]
        self.current_question = question_data["question"]
        self.current_answer = question_data["answer"]
        self.current_explanation = question_data.get("explanation", "")
        self.answer_checked = False

        # 清空之前的答案
        self.answer_entry.clear()

        # 生成并显示题目HTML
        question_html = self.get_question_html()
        self.update_web_content(question_html)

        # 启用提交按钮并恢复文字
        self.submit_button.setEnabled(True)
        self.submit_button.setText("Submit Answer")

        # 禁用下一题按钮，直到回答后再启用
        self.next_button.setEnabled(False)

        # 聚焦到答案输入框
        self.answer_entry.setFocus()
        
        # 记录当前题目
        logger.info(f"显示题目 {self.current_index+1}, 难度: {question_data.get('difficulty', 2)}")

    async def show_result(self, is_correct, explanation):
        """显示结果"""
        if not is_correct:
            await ShakeEffect.shake(self.answer_entry)
        
        # 生成结果HTML
        result_html = self.get_result_html(is_correct, explanation)
        
        # 组合题目和结果HTML
        question_html = self.get_question_html()
        combined_html = question_html + result_html
        
        # 更新显示
        self.update_web_content(combined_html)

    def next_question(self):
        """前往下一题"""
        # 防止重复调用
        if hasattr(self, '_moving_to_next') and self._moving_to_next:
            logger.warning("已有下一题任务在运行，忽略此次请求")
            return
            
        self._moving_to_next = True
        
        try:
            if self.current_index < len(self.questions) - 1:
                self.current_index += 1
                # 重置状态
                self.answer_checked = False
                self.answer_entry.clear()
                # 立即更新按钮状态
                self.submit_button.setText("Submit Answer")
                self.submit_button.setEnabled(True)
                self.next_button.setEnabled(False)
                # 显示下一题
                asyncio.create_task(self.show_current_question())
            else:
                QMessageBox.information(self, "Completed", "All questions completed!")
        finally:
            self._moving_to_next = False

    def update_done_count(self):
        """更新已完成题目数量"""
        self.done_label.setText(f"Completed: {self.done_count}/{MAX_DAILY_MATH_QUESTIONS}")

        # 计算实际奖励分钟数：遍历已完成的题目，累加其奖励时间
        actual_reward = 0
        for i in range(min(self.done_count, len(self.questions))):
            if i < len(self.questions):
                reward_mins = self.questions[i].get("reward_minutes", 2)  # 使用实际奖励时间
                actual_reward += reward_mins
                
        self.reward_label.setText(f"Today's Reward: {actual_reward} minutes")

    async def submit_answer(self):
        """提交答案"""
        # 检查是否已经在检查答案
        if hasattr(self, '_checking_answer') and self._checking_answer:
            logger.warning("已有答案检查任务在运行，忽略此次请求")
            return
            
        if self.answer_checked:
            # 如果答案已检查，这个按钮点击应该进入下一题
            self.next_question()
            return
        
        # 检查是否有有效题目
        if not self.questions or self.current_index >= len(self.questions):
            QMessageBox.warning(self, "Error", "No valid question available")
            return
            
        user_answer = self.answer_entry.text().strip()
        if not user_answer:
            QMessageBox.warning(self, "Hint", "Please enter your answer")
            return
            
        self._checking_answer = True
        self.show_progress("Checking answer, please wait...")
        self.submit_button.setEnabled(False)
        self.submit_button.setText("Checking...")
        
        try:
            # 使用异步检查答案方法，获取 is_correct, explanation
            logger.info(f"检查答案: 题目索引={self.current_index}, 用户答案={user_answer}")
            is_correct, explanation = await self.math.check_answer_async(
                self.current_index, user_answer
            )
            logger.info(f"答案检查结果: is_correct={is_correct}")
            
            # 处理检查完成
            await self.on_check_complete(True, is_correct, explanation)
            
        except Exception as e:
            logger.error(f"检查答案出错: {e} (type={type(e)})")
            logger.exception("详细错误堆栈:")
            await self.on_check_complete(False, False, None, str(e))
            
        finally:
            self.hide_progress()
            self._checking_answer = False

    async def on_check_complete(self, success, is_correct, explanation, error_msg=None):
        """检查完成回调"""
        self.hide_progress()
        if not success:
            QMessageBox.critical(self, "Error", f"Error checking answer: {error_msg}")
            # 恢复按钮状态
            self.submit_button.setEnabled(True)
            self.submit_button.setText("Submit Answer")
            return
            
        self.answer_checked = True
        
        # 显示结果
        await self.show_result(is_correct, explanation)
        
        if is_correct:
            self.done_count += 1
            self.update_done_count()
            
            # 答对了，立即发送信号更新主窗口（单题奖励）
            if self.questions and self.current_index < len(self.questions):
                reward_minutes = self.questions[self.current_index].get("reward_minutes", 2)  # 使用实际奖励时间
                logger.info(f"单题答对，发送信号更新主窗口，奖励: {reward_minutes}minutes")
                self.on_complete_signal.emit(reward_minutes)
                
        # 检查是否完成所有题目
        if self.done_count == MAX_DAILY_MATH_QUESTIONS:
            # 计算实际总奖励
            total_reward = sum(q.get("reward_minutes", 2) for q in self.questions[:MAX_DAILY_MATH_QUESTIONS])
            QMessageBox.information(
                self,
                "All Questions Completed",
                f"Congratulations! You've completed all questions for today!\nTotal {total_reward} minutes of extra game time earned.",
            )
            
        # 设置按钮状态：答案已检查，显示"Next Question"按钮
        self.submit_button.setText("Next Question")
        self.submit_button.setEnabled(True)
        self.next_button.setEnabled(False)  # 禁用独立的下一题按钮，避免冲突

    def format_explanation_text(self, text):
        """最基础的换行处理，不做任何渲染"""
        if not text:
            return ""
        return text.replace("\n", "\n")

    def close(self):
        """关闭窗口"""
        # 如果有需要清理的资源，在这里处理
        super().close()

    @asyncSlot()
    async def show_today_questions(self):
        """显示今日题目 (异步槽) - 使用KaTeX渲染"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Today's Questions")
        dialog.resize(1000, 700)

        layout = QVBoxLayout(dialog)

        # 创建WebEngineView来显示题目
        questions_web = QWebEngineView()
        questions_web.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        # 生成今日题目的HTML内容
        completed = await self.math.get_completed_count()
        
        questions_html = f"""
        <div class="question-header">
            <h1 class="question-title">Today's Questions</h1>
            <div class="question-meta">
                <span class="reward">Completed: {completed}/{MAX_DAILY_MATH_QUESTIONS}</span>
            </div>
        </div>
        """

        if self.questions:
            for i, q in enumerate(self.questions):
                status = "Completed" if i < completed else "Pending"
                status_class = "result-correct" if i < completed else "result-section"
                
                # 获取难度和奖励信息
                difficulty = q.get("difficulty", 2)
                reward_mins = q.get("reward_minutes", 2)  # 使用实际奖励时间
                
                difficulty_classes = {1: "easy", 2: "medium", 3: "hard", 4: "contest"}
                difficulty_names = {1: "Easy", 2: "Medium", 3: "Hard", 4: "Contest"}
                
                difficulty_class = difficulty_classes.get(difficulty, "medium")
                difficulty_name = difficulty_names.get(difficulty, "Medium")
                
                # 准备题目、答案和解释的数学文本
                question_text = self.prepare_math_text(q["question"])
                answer_text = self.prepare_math_text(q["answer"])
                explanation_text = self.prepare_math_text(q.get("explanation", "")) if q.get("explanation") else ""
                
                questions_html += f"""
                <div class="result-section {status_class}" style="margin-bottom: 20px;">
                    <div class="question-header">
                        <h2 class="question-title">Question {i+1} 
                            <span style="color: {'#28a745' if i < completed else '#6c757d'};">({status})</span>
                        </h2>
                        <div class="question-meta">
                            <span class="difficulty {difficulty_class}">{difficulty_name}</span>
                            <span class="reward">Reward: {reward_mins} minutes</span>
                        </div>
                    </div>
                    <div class="question-content">
                        <strong>Question:</strong><br>
                        {question_text}
                    </div>
                """
                
                # 只对已完成的题目显示答案和解释
                if i < completed:
                    questions_html += f"""
                    <div class="correct-answer">
                        <strong>Answer:</strong><br>
                        {answer_text}
                    </div>
                    """
                    
                    if explanation_text:
                        questions_html += f"""
                        <div class="explanation">
                            <div class="explanation-title">Explanation:</div>
                            {explanation_text}
                        </div>
                        """
                else:
                    # 对未完成的题目显示提示
                    questions_html += f"""
                    <div class="hint">
                        <em>Complete this question to see the answer and explanation</em>
                    </div>
                    """
                
                questions_html += "</div>"
        else:
            questions_html += """
            <div class="result-section">
                <p>No questions found for today</p>
            </div>
            """

        # 使用相同的HTML模板
        full_html = self.get_katex_html_template()
        updated_html = full_html.replace('<!-- Content will be inserted here -->', questions_html)
        
        # 设置HTML
        questions_web.setHtml(updated_html)
        
        # 等待加载完成后渲染数学公式
        def on_load_finished(ok):
            if ok:
                questions_web.page().runJavaScript("window.renderMath();")
        
        questions_web.loadFinished.connect(on_load_finished)
        
        layout.addWidget(questions_web)
        
        # 只保留关闭按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.close)
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)
        
        dialog.setLayout(layout)
        dialog.show()

    def show_progress(self, message="Processing, please wait..."):
        """显示进度条"""
        self.progress_label.setText(message)
        self.progress_frame.show()

    def hide_progress(self):
        """隐藏进度条"""
        self.progress_frame.hide()

    def show_reward_info(self):
        """显示GPT动态奖励机制的说明"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Reward Information")
        dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout(dialog)
        
        # 说明文本
        info_label = QLabel("New GPT-Based Reward System:")
        info_label.setStyleSheet("font-weight: bold; margin-bottom: 10px; font-size: 14px;")
        layout.addWidget(info_label)
        
        # 详细说明
        explanation_text = QLabel("""
The reward system now uses GPT to intelligently assign 1-5 minutes for each question based on:

• Actual problem complexity and time required
• Mathematical reasoning involved
• Number of steps needed to solve

Reward Distribution:
• 1 minute: Very simple calculations, basic arithmetic
• 2 minutes: Straightforward problems (1-2 steps)
• 3 minutes: Moderate complexity, some reasoning
• 4 minutes: Complex multi-step problems
• 5 minutes: Most challenging, competition-level

This replaces the old fixed difficulty-based system and provides more fair and accurate rewards based on actual effort required.
        """)
        explanation_text.setWordWrap(True)
        explanation_text.setStyleSheet("padding: 10px; background-color: #f0f0f0; border-radius: 5px;")
        layout.addWidget(explanation_text)
        
        # 如果有当前题目，显示实际奖励分布
        if hasattr(self, 'questions') and self.questions:
            actual_label = QLabel("Today's Actual Rewards:")
            actual_label.setStyleSheet("font-weight: bold; margin-top: 15px; margin-bottom: 5px;")
            layout.addWidget(actual_label)
            
            rewards_text = ""
            total_reward = 0
            for i, q in enumerate(self.questions):
                reward = q.get("reward_minutes", 2)
                difficulty = q.get("difficulty", 2)
                rewards_text += f"Question {i+1}: {reward} minutes (Level {difficulty})\n"
                total_reward += reward
            
            rewards_text += f"\nTotal Possible Reward: {total_reward} minutes"
            
            rewards_display = QLabel(rewards_text)
            rewards_display.setStyleSheet("font-family: monospace; background-color: #e8f4f8; padding: 10px; border-radius: 5px;")
            layout.addWidget(rewards_display)
        
        # 关闭按钮
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.close)
        layout.addWidget(close_button)
        
        dialog.setLayout(layout)
        dialog.exec()

    def setup_buttons_state(self):
        """根据当前状态设置按钮的启用/禁用"""
        # 题目加载中，所有操作按钮禁用
        if getattr(self, 'loading', False):
            self.submit_button.setEnabled(False)
            self.next_button.setEnabled(False)
            return
        # 没有题目，禁用按钮
        if not getattr(self, 'current_question', None):
            self.submit_button.setEnabled(False)
            self.next_button.setEnabled(False)
            return
        # 答案已检查，允许下一题，禁用提交
        if getattr(self, 'answer_checked', False):
            self.submit_button.setEnabled(False)
            self.next_button.setEnabled(True)
        else:
            # 未检查答案，允许提交，禁用下一题
            self.submit_button.setEnabled(True)
            self.next_button.setEnabled(False)
