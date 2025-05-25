import sys
import os
import re
import logging
import asyncio
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
    QScrollArea,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QPixmap, QPainter, QColor

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


class SimpleMathPanel(QDialog):
    """轻量级数学练习面板 - 不使用WebEngine"""

    # 定义信号
    on_complete_signal = pyqtSignal(float)  # 参数:奖励分钟数

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
        
        # 防止暴力尝试的状态跟踪
        self.checking_answer = False  # 是否正在检查答案
        self.submitted_answers = set()  # 已提交的答案（题目索引）

        # 设置窗口
        self.setWindowTitle("Math Exercise - Simple Display")
        self.resize(1200, 900)
        self.setMinimumSize(1000, 700)
        self.setModal(True)

        # 初始化UI
        self.setup_ui()

        # 延迟加载题目，等窗口显示后再执行
        QTimer.singleShot(100, self.delayed_load_questions)

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

        # 题目显示区域 - 使用原生Qt组件
        question_frame = QFrame()
        question_frame.setFrameShape(QFrame.Shape.StyledPanel)
        question_frame.setFrameShadow(QFrame.Shadow.Raised)
        question_layout = QVBoxLayout(question_frame)

        # 题目标题
        self.question_title = QLabel("Question 1/10")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        self.question_title.setFont(title_font)
        self.question_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        question_layout.addWidget(self.question_title)

        # 难度和奖励信息
        self.meta_info = QLabel("Difficulty: Medium | Reward: 2 minutes")
        meta_font = QFont()
        meta_font.setPointSize(12)
        self.meta_info.setFont(meta_font)
        self.meta_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.meta_info.setStyleSheet("color: #adb5bd; margin: 5px;")
        question_layout.addWidget(self.meta_info)

        # 题目内容显示 - 使用QTextEdit以更好支持等宽字体
        self.question_content = QTextEdit()
        self.question_content.setReadOnly(True)
        self.question_content.setMinimumHeight(300)
        self.question_content.setHtml("Loading question...")
        
        # 设置题目内容的字体和样式
        content_font = QFont()
        content_font.setPointSize(14)
        self.question_content.setFont(content_font)
        self.question_content.setStyleSheet("""
            QTextEdit {
                background-color: #3d3d3d;
                color: #ffffff;
                border: 1px solid #6c757d;
                border-radius: 8px;
                padding: 20px;
                line-height: 1.6;
            }
        """)
        
        question_layout.addWidget(self.question_content)

        # 结果显示区域（初始隐藏）- 使用QTextEdit以支持滚动
        self.result_frame = QFrame()
        self.result_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.result_frame.setFrameShadow(QFrame.Shadow.Raised)
        result_layout = QVBoxLayout(self.result_frame)
        
        self.result_display = QTextEdit()
        self.result_display.setReadOnly(True)
        self.result_display.setMinimumHeight(150)
        self.result_display.setMaximumHeight(300)
        result_font = QFont()
        result_font.setPointSize(12)
        self.result_display.setFont(result_font)
        result_layout.addWidget(self.result_display)
        
        self.result_frame.hide()
        question_layout.addWidget(self.result_frame)

        main_layout.addWidget(question_frame)

        # 答案输入框架
        answer_frame = QFrame()
        answer_frame.setFrameShape(QFrame.Shape.StyledPanel)
        answer_frame.setFrameShadow(QFrame.Shadow.Raised)
        answer_layout = QHBoxLayout(answer_frame)

        # 答案标签
        answer_label = QLabel("Your Answer:")
        answer_font = QFont()
        answer_font.setPointSize(12)
        answer_label.setFont(answer_font)
        answer_layout.addWidget(answer_label)

        # 答案输入框
        self.answer_entry = QLineEdit()
        self.answer_entry.setMinimumWidth(200)
        self.answer_entry.setFont(answer_font)
        self.answer_entry.returnPressed.connect(
            lambda: self.safe_async_call(self.submit_answer())
        )
        answer_layout.addWidget(self.answer_entry)

        # 提交按钮
        self.submit_button = QPushButton("Submit Answer")
        self.submit_button.clicked.connect(
            lambda: self.safe_async_call(self.submit_answer())
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

    def safe_async_call(self, coro):
        """安全地调用异步函数"""
        try:
            # 获取当前事件循环
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(coro)
            else:
                # 如果没有运行的循环，创建一个任务
                loop.create_task(coro)
        except RuntimeError:
            # 如果没有事件循环，记录错误
            logger.error("没有可用的事件循环，无法执行异步操作")
            QMessageBox.warning(self, "Error", "No event loop available. Please restart the application.")

    def check_session_status(self):
        """检查游戏session状态，返回是否允许做数学练习"""
        if self.parent and hasattr(self.parent, 'session_active'):
            if self.parent.session_active:
                logger.info("检测到活动的游戏session，禁用数学练习")
                return False
        return True

    def show_session_active_warning(self):
        """显示session活跃时的警告信息"""
        self.question_title.setText("Math Exercise Temporarily Unavailable")
        self.meta_info.setText("")
        self.question_content.setText("""
        <div style="text-align: center; padding: 40px; color: #ffffff;">
            <h2 style="color: #dc3545; margin-bottom: 20px;">Math Exercise Temporarily Unavailable</h2>
            <p style="font-size: 18px; color: #adb5bd; margin: 20px 0;">
                A game session is currently in progress.
            </p>
            <p style="font-size: 16px; color: #adb5bd;">
                To ensure fair game time management, math exercises cannot be performed during active game sessions.
            </p>
            <p style="font-size: 16px; color: #adb5bd;">
                Please come back after the session ends.
            </p>
        </div>
        """)
        self.submit_button.setEnabled(False)
        self.next_button.setEnabled(False)

    def show_progress(self, message="Loading..."):
        """显示进度条"""
        self.progress_label.setText(message)
        self.progress_frame.show()

    def hide_progress(self):
        """隐藏进度条"""
        self.progress_frame.hide()

    def delayed_load_questions(self):
        """延迟加载题目，等窗口显示后再执行"""
        if self.check_session_status():
            # 加载题目 - 使用QTimer来启动异步任务
            def start_loading():
                try:
                    # 获取当前事件循环
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.ensure_future(self.load_or_generate_questions())
                    else:
                        # 如果没有运行的循环，创建一个任务
                        loop.create_task(self.load_or_generate_questions())
                except RuntimeError:
                    # 如果没有事件循环，显示错误
                    logger.error("没有可用的事件循环，无法加载题目")
                    self.on_load_error("No event loop available. Please restart the application.")
            
            QTimer.singleShot(100, start_loading)
        else:
            # 显示禁用状态
            self.show_session_active_warning()

    async def load_or_generate_questions(self):
        """加载或生成题目"""
        if self.loading:
            logger.warning("已有加载任务在运行，忽略此次请求")
            return

        self.loading = True
        self.show_progress("Loading today's math questions...")

        try:
            # 初始化数学练习模块 - 确保正确等待异步初始化
            logger.info("初始化数学练习模块...")
            self.math = await MathExercises().initialize()
            logger.info("数学练习模块初始化完成")

            # 获取今日题目
            logger.info("获取今日题目...")
            questions = await self.math.get_daily_questions()
            logger.info(f"[DEBUG] 获取到题目数量: {len(questions)}")

            # 获取今日完成数量
            done_count = await self.math.get_completed_count()
            logger.info(f"[DEBUG] 今日完成数量: {done_count}")

            # 更新今日奖励分钟数
            reward_minutes = await self.math.get_today_reward_minutes()
            if reward_minutes == int(reward_minutes):
                reward_display = f"{int(reward_minutes)}"
            else:
                reward_display = f"{reward_minutes:.1f}"
            self.reward_label.setText(f"Today's Reward: {reward_display} minutes")

            # 隐藏进度条
            self.hide_progress()

            await self.on_questions_loaded(questions, done_count)

        except Exception as e:
            logger.error(f"加载题目出错: {e}")
            logger.exception("详细错误信息:")
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
        
        # 检查题目是否为空
        if not self.questions:
            logger.error("题目列表为空！")
            self.question_content.setText("""
            <div style="text-align: center; padding: 40px; color: #ffffff;">
                <h2 style="color: #dc3545; margin-bottom: 20px;">No Questions Available</h2>
                <p style="font-size: 18px; color: #adb5bd; margin: 20px 0;">
                    Failed to load or generate math questions.
                </p>
                <p style="font-size: 16px; color: #adb5bd;">
                    Please check your internet connection and OpenAI API key configuration.
                </p>
                <p style="font-size: 16px; color: #adb5bd;">
                    You can try closing and reopening the math panel.
                </p>
            </div>
            """)
            self.submit_button.setEnabled(False)
            self.next_button.setEnabled(False)
            return
        
        self.update_done_count()
        # 只在全部完成时才显示"已完成"
        if self.questions and self.done_count < len(self.questions):
            self.current_index = self.done_count
            await self.show_current_question()
        else:
            self.question_content.setText("All questions for today have been completed!")
            self.submit_button.setEnabled(False)

    async def on_load_error(self, error_msg):
        """题目加载错误回调"""
        self.hide_progress()
        
        # 检查是否是API密钥问题
        if "API密钥" in error_msg or "API key" in error_msg or "OPENAI_API_KEY" in error_msg:
            self.question_content.setText("""
            <div style="text-align: center; padding: 40px; color: #ffffff;">
                <h2 style="color: #dc3545; margin-bottom: 20px;">OpenAI API Key Required</h2>
                <p style="font-size: 18px; color: #adb5bd; margin: 20px 0;">
                    Math exercises require an OpenAI API key to generate questions.
                </p>
                <p style="font-size: 16px; color: #adb5bd;">
                    Please follow these steps:
                </p>
                <ol style="text-align: left; max-width: 500px; margin: 20px auto; color: #adb5bd;">
                    <li>Get an API key from <a href="https://platform.openai.com/api-keys" target="_blank" style="color: #4fc3f7;">OpenAI Platform</a></li>
                    <li>Create a <code style="background: #2d2d2d; color: #ffffff; padding: 2px 4px; border-radius: 3px;">.env</code> file in the project root</li>
                    <li>Add: <code style="background: #2d2d2d; color: #ffffff; padding: 2px 4px; border-radius: 3px;">OPENAI_API_KEY=your_api_key_here</code></li>
                    <li>Restart the application</li>
                </ol>
            </div>
            """)
        else:
            self.question_content.setText(f"""
            <div style="text-align: center; padding: 40px; color: #ffffff;">
                <h2 style="color: #dc3545; margin-bottom: 20px;">Loading Error</h2>
                <p style="font-size: 18px; color: #adb5bd; margin: 20px 0;">
                    Failed to load math questions.
                </p>
                <p style="font-size: 14px; color: #adb5bd; font-family: monospace; background: #2d2d2d; padding: 10px; border-radius: 4px; border: 1px solid #6c757d;">
                    {error_msg}
                </p>
                <p style="font-size: 16px; color: #adb5bd;">
                    Please check your internet connection and try again.
                </p>
            </div>
            """)
        
        self.submit_button.setEnabled(False)
        self.next_button.setEnabled(False)

    def prepare_math_text(self, text):
        """准备数学文本，使用混合模式：HTML+纯文本"""
        if not text:
            return ""
        
        # 注意：这里不需要JSON转义处理，因为数据已经是Python字符串对象
        # 之前的JSON转义处理是不必要的，还会破坏LaTeX命令
        
        # 检查是否包含ASCII art（代码块）
        import re
        has_ascii_art = bool(re.search(r'```.*?```', text, re.DOTALL))
        
        if has_ascii_art:
            # 如果包含ASCII art，使用纯文本模式
            return self.prepare_plain_text(text)
        else:
            # 如果没有ASCII art，使用HTML模式
            return self.prepare_html_text(text)
    
    def prepare_plain_text(self, text):
        """准备纯文本格式，保持ASCII art的原始格式"""
        import re
        
        # 移除代码块标记，但保留内容
        text = re.sub(r'```\n?(.*?)\n?```', r'\1', text, flags=re.DOTALL)
        
        # 简单的数学符号替换
        text = text.replace('\\pi', 'π')
        text = text.replace('\\theta', 'θ')
        text = text.replace('\\alpha', 'α')
        text = text.replace('\\beta', 'β')
        text = text.replace('\\gamma', 'γ')
        text = text.replace('\\cdot', '·')
        text = text.replace('\\times', '×')
        text = text.replace('\\div', '÷')
        text = text.replace('\\leq', '≤')
        text = text.replace('\\geq', '≥')
        text = text.replace('\\neq', '≠')
        text = text.replace('\\approx', '≈')
        text = text.replace('\\infty', '∞')
        
        # 移除$$标记
        text = re.sub(r'\$\$(.*?)\$\$', r'\1', text, flags=re.DOTALL)
        text = re.sub(r'\$([^$]+)\$', r'\1', text)
        
        return text.strip()
    
    def prepare_html_text(self, text):
        """准备HTML格式文本"""
        import re
        
        # 简化数学公式处理
        def replace_math(match):
            math_content = match.group(1).strip()
            # 简单的数学符号替换
            math_content = math_content.replace('\\frac', 'fraction')
            math_content = math_content.replace('\\sqrt', 'sqrt')
            math_content = math_content.replace('\\pi', 'π')
            math_content = math_content.replace('\\theta', 'θ')
            math_content = math_content.replace('\\alpha', 'α')
            math_content = math_content.replace('\\beta', 'β')
            math_content = math_content.replace('\\gamma', 'γ')
            math_content = math_content.replace('\\cdot', '·')
            math_content = math_content.replace('\\times', '×')
            math_content = math_content.replace('\\div', '÷')
            math_content = math_content.replace('\\leq', '≤')
            math_content = math_content.replace('\\geq', '≥')
            math_content = math_content.replace('\\neq', '≠')
            math_content = math_content.replace('\\approx', '≈')
            math_content = math_content.replace('\\infty', '∞')
            return f'<b style="color: #4fc3f7;">{math_content}</b>'
        
        # 替换$$...$$数学公式
        text = re.sub(r'\$\$(.*?)\$\$', replace_math, text, flags=re.DOTALL)
        
        # 替换$...$数学公式
        text = re.sub(r'\$([^$]+)\$', replace_math, text)
        
        # 处理换行符
        text = re.sub(r'\n\n+', '<br><br>', text)
        text = re.sub(r'(?<!\>)\n(?!\<)', ' ', text)
        
        return text

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

        # 更新题目标题
        self.question_title.setText(f"Question {self.current_index + 1}/{len(self.questions)}")

        # 更新难度和奖励信息
        difficulty = question_data.get("difficulty", 2)
        reward_mins = question_data.get("reward_minutes", 1.0)
        
        difficulty_names = {1: "Easy", 2: "Medium", 3: "Hard", 4: "Contest"}
        difficulty_name = difficulty_names.get(difficulty, "Medium")
        
        # 格式化奖励时间显示，如果是整数则不显示小数点
        if reward_mins == int(reward_mins):
            reward_display = f"{int(reward_mins)}"
        else:
            reward_display = f"{reward_mins:.1f}"
        self.meta_info.setText(f"Difficulty: {difficulty_name} | Reward: {reward_display} minutes")

        # 显示题目内容
        formatted_question = self.prepare_math_text(self.current_question)
        
        # 检查是否包含ASCII art来决定显示方式
        import re
        has_ascii_art = bool(re.search(r'```.*?```', self.current_question, re.DOTALL))
        
        if has_ascii_art:
            # 对于ASCII art，使用纯文本模式并设置等宽字体
            self.question_content.setPlainText(formatted_question)
            # 设置等宽字体
            mono_font = QFont("Courier New", 12)
            mono_font.setStyleHint(QFont.StyleHint.Monospace)
            self.question_content.setFont(mono_font)
        else:
            # 对于普通文本，使用HTML模式
            self.question_content.setHtml(formatted_question)
            # 恢复普通字体
            content_font = QFont()
            content_font.setPointSize(14)
            self.question_content.setFont(content_font)

        # 隐藏结果区域
        self.result_frame.hide()

        # 检查这题是否已经回答过
        if self.current_index in self.submitted_answers:
            # 已经回答过，禁用提交按钮，启用下一题按钮
            self.submit_button.setEnabled(False)
            self.submit_button.setText("Already Answered")
            if self.current_index < len(self.questions) - 1:
                self.next_button.setEnabled(True)
                self.next_button.setText("Next Question")
            else:
                self.next_button.setText("All Done!")
                self.next_button.setEnabled(False)
        else:
            # 未回答过，启用提交按钮
            self.submit_button.setEnabled(True)
            self.submit_button.setText("Submit Answer")
            # 禁用下一题按钮，直到回答后再启用
            self.next_button.setEnabled(False)

        # 聚焦到答案输入框
        self.answer_entry.setFocus()
        
        # 记录当前题目
        logger.info(f"显示题目 {self.current_index+1}, 难度: {difficulty}")

    async def submit_answer(self):
        """提交答案"""
        # 防止重复检查同一题目
        if self.answer_checked or self.current_index in self.submitted_answers:
            logger.warning(f"题目 {self.current_index} 答案已检查过，忽略重复提交")
            return

        # 防止在检查过程中重复提交
        if self.checking_answer:
            logger.warning("正在检查答案中，忽略重复提交")
            return

        user_answer = self.answer_entry.text().strip()
        if not user_answer:
            await ShakeEffect.shake(self.answer_entry)
            return

        # 设置检查状态
        self.checking_answer = True
        self.submitted_answers.add(self.current_index)
        
        # 显示进度条
        self.show_progress("Checking answer with AI, please wait...")
        
        # 禁用提交按钮和关闭按钮，防止重复提交和中途关闭
        self.submit_button.setEnabled(False)
        self.submit_button.setText("Checking...")
        self.close_button.setEnabled(False)
        self.close_button.setText("Checking...")

        try:
            logger.info(f"开始检查题目 {self.current_index} 的答案: {user_answer}")
            
            # 检查答案
            is_correct, explanation = await self.math.check_answer_async(
                self.current_index, user_answer
            )

            logger.info(f"题目 {self.current_index} 答案检查完成: {'正确' if is_correct else '错误'}")
            
            self.answer_checked = True

            # 显示结果
            await self.show_result(is_correct, explanation)

            # 更新完成计数
            self.done_count += 1
            self.update_done_count()

            # 更新今日奖励分钟数
            reward_minutes = await self.math.get_today_reward_minutes()
            if reward_minutes == int(reward_minutes):
                reward_display = f"{int(reward_minutes)}"
            else:
                reward_display = f"{reward_minutes:.1f}"
            self.reward_label.setText(f"Today's Reward: {reward_display} minutes")

            # 重置提交按钮状态并启用下一题按钮
            self.submit_button.setText("Submit Answer")
            self.submit_button.setEnabled(False)  # 禁用提交按钮，直到下一题
            
            if self.current_index < len(self.questions) - 1:
                self.next_button.setEnabled(True)
                self.next_button.setText("Next Question")
            else:
                # 最后一题，显示完成信息
                self.next_button.setText("All Done!")
                self.next_button.setEnabled(False)

        except Exception as e:
            logger.error(f"检查答案时出错: {e}")
            # 如果检查失败，移除已提交标记，允许重试
            self.submitted_answers.discard(self.current_index)
            QMessageBox.critical(self, "Error", f"Error checking answer: {str(e)}")
            # 重新启用提交按钮
            self.submit_button.setEnabled(True)
            self.submit_button.setText("Submit Answer")
        finally:
            # 隐藏进度条
            self.hide_progress()
            # 恢复检查状态和关闭按钮
            self.checking_answer = False
            self.close_button.setEnabled(True)
            self.close_button.setText("Close")

    async def show_result(self, is_correct, explanation):
        """显示结果"""
        if not is_correct:
            await ShakeEffect.shake(self.answer_entry)
        
        # 设置结果样式和内容
        if is_correct:
            result_style = """
                QTextEdit {
                    background-color: #d4edda;
                    border: 2px solid #28a745;
                    border-radius: 8px;
                    padding: 15px;
                    color: #155724;
                }
            """
            result_text = "<h3 style='color: #155724; margin-top: 0;'>✓ Correct!</h3>"
        else:
            result_style = """
                QTextEdit {
                    background-color: #f8d7da;
                    border: 2px solid #dc3545;
                    border-radius: 8px;
                    padding: 15px;
                    color: #721c24;
                }
            """
            result_text = "<h3 style='color: #721c24; margin-top: 0;'>✗ Incorrect!</h3>"
            
            # 显示正确答案
            if self.current_answer:
                # 检查是否包含ASCII art来决定显示方式
                import re
                has_ascii_art = bool(re.search(r'```.*?```', self.current_answer, re.DOTALL))
                
                if has_ascii_art:
                    formatted_answer = self.prepare_plain_text(self.current_answer)
                    result_text += f"<p><b>Correct Answer:</b></p><pre style='font-family: monospace; background-color: #f0f0f0; padding: 10px; border-radius: 4px; color: #333;'>{formatted_answer}</pre>"
                else:
                    formatted_answer = self.prepare_html_text(self.current_answer)
                    result_text += f"<p><b>Correct Answer:</b> {formatted_answer}</p>"
            
            # 显示解释
            if explanation:
                # 检查解释是否包含ASCII art
                import re
                has_ascii_art = bool(re.search(r'```.*?```', explanation, re.DOTALL))
                
                if has_ascii_art:
                    formatted_explanation = self.prepare_plain_text(explanation)
                    result_text += f"<p><b>Explanation:</b></p><pre style='font-family: monospace; background-color: #f0f0f0; padding: 10px; border-radius: 4px; color: #333; white-space: pre-wrap;'>{formatted_explanation}</pre>"
                else:
                    formatted_explanation = self.prepare_html_text(explanation)
                    result_text += f"<p><b>Explanation:</b><br>{formatted_explanation}</p>"
        
        self.result_display.setStyleSheet(result_style)
        self.result_display.setHtml(result_text)
        self.result_frame.show()

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
                # 异步显示下一题
                self.safe_async_call(self.show_current_question())
            else:
                # 已经是最后一题
                logger.info("已经是最后一题")
                self.next_button.setText("All Done!")
                self.next_button.setEnabled(False)
                
                # 发送完成信号
                total_reward = 0
                for q in self.questions:
                    if q.get("is_correct"):
                        total_reward += q.get("reward_minutes", 1.0)
                
                self.on_complete_signal.emit(total_reward)
                
        finally:
            self._moving_to_next = False

    def update_done_count(self):
        """更新完成计数显示"""
        self.done_label.setText(f"Completed: {self.done_count}/{MAX_DAILY_MATH_QUESTIONS}")

    def show_reward_info(self):
        """显示奖励信息"""
        info_text = """
        <h3>Math Exercise Reward System</h3>
        <p>Each question has a reward time based on its actual complexity and solving time (approximately half of solving time):</p>
        <ul>
            <li><b>Very Simple:</b> 0.5 minutes (1-2 min solving time)</li>
            <li><b>Simple:</b> 1 minute (2-3 min solving time)</li>
            <li><b>Straightforward:</b> 1.5 minutes (3-4 min solving time)</li>
            <li><b>Moderate:</b> 2 minutes (4-5 min solving time)</li>
            <li><b>Multi-step:</b> 2.5 minutes (5-6 min solving time)</li>
            <li><b>Complex:</b> 3 minutes (6-7 min solving time)</li>
            <li><b>Very Challenging:</b> 4 minutes (8-9 min solving time)</li>
            <li><b>Competition Level:</b> 5 minutes (10+ min solving time)</li>
        </ul>
        <p>The exact reward time for each question is determined by AI based on the actual complexity and time required.</p>
        <p>You can earn up to {MAX_DAILY_MATH_QUESTIONS} questions worth of rewards per day.</p>
        """.format(MAX_DAILY_MATH_QUESTIONS=MAX_DAILY_MATH_QUESTIONS)
        
        QMessageBox.information(self, "Reward Information", info_text)

    def show_today_questions(self):
        """显示今日题目列表"""
        if not self.questions:
            QMessageBox.information(self, "No Questions", "No questions available for today.")
            return

        # 创建题目列表对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("Today's Math Questions")
        dialog.resize(800, 600)
        
        layout = QVBoxLayout(dialog)
        
        # 创建表格
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["#", "Difficulty", "Reward", "Status", "Question Preview"])
        table.setRowCount(len(self.questions))
        
        for i, q in enumerate(self.questions):
            # 题目编号
            table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            
            # 难度
            difficulty = q.get("difficulty", 2)
            difficulty_names = {1: "Easy", 2: "Medium", 3: "Hard", 4: "Contest"}
            table.setItem(i, 1, QTableWidgetItem(difficulty_names.get(difficulty, "Medium")))
            
            # 奖励 - 格式化显示
            reward = q.get("reward_minutes", 1.0)
            if reward == int(reward):
                reward_display = f"{int(reward)} min"
            else:
                reward_display = f"{reward:.1f} min"
            table.setItem(i, 2, QTableWidgetItem(reward_display))
            
            # 状态 - 基于已完成数量判断
            if i < self.done_count:
                # 已完成的题目，检查是否正确
                is_correct = q.get("is_correct")
                if is_correct:
                    status = "Correct ✓"
                else:
                    status = "Incorrect ✗"
            else:
                # 未完成的题目
                status = "Not answered"
            table.setItem(i, 3, QTableWidgetItem(status))
            
            # 题目预览
            question_text = q.get("question", "")
            preview = question_text[:100] + "..." if len(question_text) > 100 else question_text
            # 移除HTML标签用于预览
            import re
            preview = re.sub(r'<[^>]+>', '', preview)
            table.setItem(i, 4, QTableWidgetItem(preview))
        
        # 调整列宽
        table.resizeColumnsToContents()
        layout.addWidget(table)
        
        # 关闭按钮
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn)
        
        dialog.exec()

    def close(self):
        """关闭窗口"""
        # 如果正在检查答案，阻止关闭
        if hasattr(self, 'checking_answer') and self.checking_answer:
            logger.warning("正在检查答案中，无法关闭窗口")
            QMessageBox.warning(
                self, 
                "Cannot Close", 
                "Answer is being checked. Please wait for the check to complete before closing."
            )
            return
        
        try:
            logger.info("关闭简单数学面板...")
            
            # 清理数学练习对象
            if hasattr(self, 'math') and self.math:
                self.math.close()
                self.math = None
            
            logger.info("简单数学面板资源清理完成")
        except Exception as e:
            logger.error(f"清理简单数学面板资源时出错: {e}")
        
        # 调用父类关闭方法
        super().close()
    
    def closeEvent(self, event):
        """处理窗口关闭事件"""
        # 如果正在检查答案，阻止关闭
        if hasattr(self, 'checking_answer') and self.checking_answer:
            logger.warning("正在检查答案中，无法关闭窗口")
            QMessageBox.warning(
                self, 
                "Cannot Close", 
                "Answer is being checked. Please wait for the check to complete before closing."
            )
            event.ignore()  # 忽略关闭事件
            return
        
        # 允许关闭
        event.accept()
        super().closeEvent(event) 