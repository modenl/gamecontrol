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
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QFont

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
    MATH_DIFFICULTY_REWARDS,
)
from logic.math_exercises import MathExercises
from logic.database import get_week_start
from ui.base import ToolTip, ShakeEffect
from qasync import asyncSlot
from datetime import date, datetime

logger = logging.getLogger(__name__)


class MathPanel(QDialog):
    """数学练习面板"""

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
        self.questions = []  # Initialize the questions attribute

        # 设置窗口
        self.setWindowTitle("Math Exercise")
        self.resize(1000, 800)
        self.setMinimumSize(800, 600)
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
        # 确保不是默认按钮，防止回车键误触发
        reward_info_btn.setAutoDefault(False)
        reward_info_btn.setDefault(False)
        info_layout.addWidget(reward_info_btn)

        main_layout.addWidget(info_frame)

        # 题目显示区域
        question_frame = QFrame()
        question_frame.setFrameShape(QFrame.Shape.StyledPanel)
        question_frame.setFrameShadow(QFrame.Shadow.Raised)
        question_layout = QVBoxLayout(question_frame)

        # 题目文本框
        self.question_text = QTextEdit()
        self.question_text.setReadOnly(True)
        self.question_text.setMinimumHeight(120)
        question_layout.addWidget(self.question_text)

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
        # 连接回车键事件到提交答案方法
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
        # 设置为默认按钮，但不是自动默认
        self.submit_button.setDefault(True)
        self.submit_button.setAutoDefault(False)
        answer_layout.addWidget(self.submit_button)

        main_layout.addWidget(answer_frame)

        # 结果显示区域
        result_frame = QFrame()
        result_frame.setFrameShape(QFrame.Shape.StyledPanel)
        result_frame.setFrameShadow(QFrame.Shadow.Raised)
        result_layout = QVBoxLayout(result_frame)

        # 结果显示区改为 QTextEdit
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setMinimumHeight(220)
        self.result_text.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        result_layout.addWidget(self.result_text)

        main_layout.addWidget(result_frame)

        # 进度条 - 仅在加载时显示
        self.progress_frame = QFrame()
        progress_layout = QVBoxLayout(self.progress_frame)

        self.progress_label = QLabel("Loading questions, please wait...")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        progress_layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # 设置为不确定模式
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
        self.question_text.setHtml("""
            <div style="text-align: center; padding: 20px;">
                <h2 style="color: #dc3545;">Math Exercise temporarily unavailable</h2>
                <p style="font-size: 16px; color: #6c757d; margin: 20px 0;">
                    Detected current game Session is in progress.
                </p>
                <p style="font-size: 14px; color: #6c757d;">
                    To ensure fair game time management, math exercise cannot be performed during game Session.
                </p>
                <p style="font-size: 14px; color: #28a745; margin-top: 20px;">
                    Please come back after the game Session ends!
                </p>
            </div>
        """)
        
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
            self.question_text.setHtml("<p>All questions for today have been completed!</p>")
            self.submit_button.setEnabled(False)

    async def on_load_error(self, error_msg):
        """题目加载错误回调"""
        self.hide_progress()

        QMessageBox.critical(self, "Loading Error", f"Error loading questions: {error_msg}")
        self.close()

    async def show_current_question(self):
        """显示当前题目"""
        if not self.questions or self.current_index >= len(self.questions):
            return

        question_data = self.questions[self.current_index]
        self.current_question = question_data["question"]
        self.current_answer = question_data["answer"]
        self.current_explanation = question_data.get("explanation", "")
        self.answer_checked = False

        # 清空之前的答案和结果
        self.answer_entry.clear()
        self.result_text.setPlainText("")

        # 创建题目标题
        title = f"Question {self.current_index + 1}/{len(self.questions)}"

        title_html = f"<h2>{title}</h2>"

        # 显示题目文本
        self.question_text.clear()
        self.question_text.setHtml(title_html)
        self.insert_question_content()

        # 启用提交按钮并恢复文字
        self.submit_button.setEnabled(True)
        self.submit_button.setText("Submit Answer")

        # 禁用下一题按钮，直到回答后再启用
        self.next_button.setEnabled(False)

        # 聚焦到答案输入框
        self.answer_entry.setFocus()
        
        # 记录当前题目，便于调试
        logger.info(f"当前显示题目: '{self.current_question[:50]}...'，索引: {self.current_index}")

    def next_question(self):
        """前往下一题"""
        if self.current_index < len(self.questions) - 1:
            self.current_index += 1
            asyncio.create_task(self.show_current_question())
        else:
            QMessageBox.information(self, "Completed", "All questions completed!")

    def update_done_count(self):
        """更新完成计数"""
        # 更新完成数量显示
        self.done_label.setText(f"Completed: {self.done_count}/{MAX_DAILY_MATH_QUESTIONS}")

        # 更新奖励分钟数
        reward_minutes = self.done_count * MATH_REWARD_PER_QUESTION
        self.reward_label.setText(f"Today's Reward: {reward_minutes} minutes")

    async def submit_answer(self):
        """提交答案"""
        # 检查是否已经在检查答案
        if hasattr(self, '_checking_answer') and self._checking_answer:
            logger.warning("已有答案检查任务在运行，忽略此次请求")
            return
            
        if self.answer_checked:
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
        self.submit_button.setText("Submit Answer")  # 保持为提交答案，防止提前变成下一题
        
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
            self.submit_button.setEnabled(True)
            self._checking_answer = False

    async def on_check_complete(self, success, is_correct, explanation, error_msg=None):
        """检查完成回调"""
        self.hide_progress()
        if not success:
            QMessageBox.critical(self, "Error", f"Error checking answer: {error_msg}")
            return
        self.answer_checked = True
        # 显示结果
        await self.show_result(is_correct, explanation)
        if is_correct:
            self.done_count += 1
            self.update_done_count()
            
            # 答对了，立即发送信号更新主窗口（单题奖励）
            if self.questions and self.current_index < len(self.questions):
                difficulty = self.questions[self.current_index].get("difficulty", 2)
                reward_minutes = MATH_DIFFICULTY_REWARDS.get(difficulty, MATH_REWARD_PER_QUESTION)
                logger.info(f"单题答对，发送信号更新主窗口，奖励: {reward_minutes}minutes")
                self.on_complete_signal.emit(reward_minutes)
                
        if self.done_count == MAX_DAILY_MATH_QUESTIONS:
            # 完成所有题目的额外提示（不再发送信号，因为每题都已发送过了）
            total_reward = MAX_DAILY_MATH_QUESTIONS * MATH_REWARD_PER_QUESTION
            QMessageBox.information(
                self,
                "All Questions Completed",
                f"Congratulations! You've completed all questions for today!\nTotal {total_reward} minutes of extra game time earned.",
            )
        if is_correct:
            # 答对时，自动跳到下一题，禁用"下一题"按钮
            self.submit_button.setText("Next Question")
            self.next_button.setEnabled(False)
            from PyQt6.QtCore import QTimer

            QTimer.singleShot(1500, self.next_question)
        else:
            # 答错时，允许手动点击"下一题"
            self.submit_button.setText("Next Question")
            self.next_button.setEnabled(True)

    def format_explanation_text(self, text):
        """最基础的换行处理，不做任何渲染"""
        if not text:
            return ""
        return text.replace("\n", "\n")

    async def show_result(self, is_correct, explanation):
        """显示结果，纯文本/简单HTML，支持简化的数学公式"""
        if is_correct:
            result_text = "Correct!"
        else:
            # 使用简化的公式显示答案
            formatted_answer = self.simplify_math_formula(self.current_answer)
            result_text = f"Incorrect!\nCorrect answer: {formatted_answer}"
            await ShakeEffect.shake(self.answer_entry)
            
        if not is_correct and explanation:
            # 简化解释中的数学公式
            simplified_explanation = self.simplify_math_formula(explanation)
            result_text += "\n\nExplanation:\n" + self.format_explanation_text(simplified_explanation)
            
        self.result_text.setPlainText(result_text)

    def close(self):
        """关闭窗口"""
        # 如果有需要清理的资源，在这里处理
        super().close()

    @asyncSlot()
    async def show_today_questions(self):
        """显示今日题目 (异步槽)"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Today's Questions")
        dialog.resize(800, 600)

        layout = QVBoxLayout(dialog)

        # 当前题目信息
        info_text = QTextEdit()
        info_text.setReadOnly(True)
        info_html = "<h2>Today's Questions</h2>"

        completed = await self.math.get_completed_count()
        info_html += f"<p>Completed: {completed}/{MAX_DAILY_MATH_QUESTIONS}</p>"

        if self.questions:
            for i, q in enumerate(self.questions):
                status = "Completed" if i < completed else "Pending"
                color = "#28a745" if i < completed else "#6c757d"
                info_html += f'<div style="margin-bottom: 15px; padding: 10px; border: 1px solid #ddd; border-radius: 5px;">'
                info_html += f'<h3>Question {i+1} <span style="color: {color};">({status})</span></h3>'

                # 显示难度和奖励信息
                difficulty = q.get("difficulty", 2)
                reward_mins = MATH_DIFFICULTY_REWARDS.get(
                    difficulty, MATH_REWARD_PER_QUESTION
                )

                difficulty_text = ""
                if difficulty == 1:
                    difficulty_text = '<span style="color: #28a745;">Easy</span>'
                elif difficulty == 2:
                    difficulty_text = '<span style="color: #ffc107;">Medium</span>'
                elif difficulty == 3:
                    difficulty_text = '<span style="color: #dc3545;">Hard</span>'
                elif difficulty == 4:
                    difficulty_text = (
                        '<span style="color: #ff6600; font-weight: bold;">Contest</span>'
                    )

                info_html += f'<p>{difficulty_text} | <span style="color: #17a2b8;">Reward: {reward_mins} minutes</span></p>'

                info_html += f'<p><strong>Question:</strong> {q["question"]}</p>'
                info_html += f'<p><strong>Answer:</strong> {q["answer"]}</p>'
                if "explanation" in q and q["explanation"]:
                    info_html += f'<p><strong>Explanation:</strong> {q["explanation"]}</p>'
                info_html += "</div>"
        else:
            info_html += "<p>No questions found for today</p>"
        info_text.setHtml(info_html)
        layout.addWidget(info_text)
        
        # 只保留关闭按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()  # 居中关闭按钮
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.close)
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)
        dialog.setLayout(layout)
        dialog.show()  # 不要用 exec()

    def show_progress(self, message="Processing, please wait..."):
        """显示进度条"""
        self.progress_label.setText(message)
        self.progress_frame.show()

    def hide_progress(self):
        """隐藏进度条"""
        self.progress_frame.hide()

    def simplify_math_formula(self, text):
        """将 LaTeX 格式的数学公式转换为更易于理解的形式"""
        if not text or '$' not in text:
            return text
            
        # 查找所有 $...$ 格式的公式
        import re
        formulas = re.findall(r'\$(.*?)\$', text)
        result = text
        
        for formula in formulas:
            original = f"${formula}$"
            simplified = formula
            
            # 替换常见的数学符号
            simplified = simplified.replace("\\times", "×")
            simplified = simplified.replace("\\div", "÷")
            simplified = simplified.replace("\\cdot", "·")
            
            # 分数处理
            simplified = re.sub(r'\\frac\{([^{}]+)\}\{([^{}]+)\}', r'\1/\2', simplified)
            
            # 嵌套分数处理
            while '\\frac{' in simplified:
                simplified = re.sub(r'\\frac\{([^{}]+)\}\{([^{}]+)\}', r'\1/\2', simplified)
            
            # 处理根号
            simplified = re.sub(r'\\sqrt\{([^{}]+)\}', r'√(\1)', simplified)
            
            # 常见数学符号
            simplified = simplified.replace("\\pi", "π")
            simplified = simplified.replace("\\leq", "≤")
            simplified = simplified.replace("\\geq", "≥")
            simplified = simplified.replace("\\neq", "≠")
            simplified = simplified.replace("\\approx", "≈")
            simplified = simplified.replace("\\pm", "±")
            simplified = simplified.replace("\\infty", "∞")
            simplified = simplified.replace("\\in", "∈")
            simplified = simplified.replace("\\sum", "∑")
            simplified = simplified.replace("\\prod", "∏")
            simplified = simplified.replace("\\alpha", "α")
            simplified = simplified.replace("\\beta", "β")
            simplified = simplified.replace("\\gamma", "γ")
            simplified = simplified.replace("\\delta", "δ")
            simplified = simplified.replace("\\theta", "θ")
            
            # 处理上标和下标
            simplified = re.sub(r'\^(\d+|\{\d+\})', lambda m: "^" + m.group(1).strip('{}'), simplified)
            simplified = re.sub(r'_(\d+|\{\d+\})', lambda m: "_" + m.group(1).strip('{}'), simplified)
            
            # 最后清理多余的花括号
            simplified = simplified.replace("{", "").replace("}", "")
            
            # 用更柔和的颜色替换原始公式
            formatted = f"<span style='color:#2d8659; font-weight:bold;'>{simplified}</span>"
            result = result.replace(original, formatted)
            
        return result

    def insert_question_content(self):
        """插入题目内容，支持简化的数学公式渲染"""
        question_text = self.current_question
        import re

        # 替换 [ ... ] 为 $$...$$
        question_text = re.sub(r"\[([^\[\]]+)\]", r"$$\1$$", question_text)
        
        # 简化数学公式
        question_text = self.simplify_math_formula(question_text)
        
        content_html = ""
        current_difficulty = 2
        if self.questions and self.current_index < len(self.questions):
            if "difficulty" in self.questions[self.current_index]:
                current_difficulty = self.questions[self.current_index]["difficulty"]
                logger.info(
                    f"显示题目 {self.current_index+1}, 难度: {current_difficulty}"
                )
        reward_mins = MATH_DIFFICULTY_REWARDS.get(
            current_difficulty, MATH_REWARD_PER_QUESTION
        )
        difficulty_text = ""
        if current_difficulty == 1:
            difficulty_text = '<span style="color: #28a745;">Easy</span>'
        elif current_difficulty == 2:
            difficulty_text = '<span style="color: #ffc107;">Medium</span>'
        elif current_difficulty == 3:
            difficulty_text = '<span style="color: #dc3545;">Hard</span>'
        elif current_difficulty == 4:
            difficulty_text = (
                '<span style="color: #ff6600; font-weight: bold;">Contest</span>'
            )
        reward_text = f'<span style="color: #17a2b8;">Reward: {reward_mins} minutes</span>'
        content_html += "<div>"
        content_html += (
            f'<div style="margin-bottom: 8px;">{difficulty_text} | {reward_text}</div>'
        )
        
        # 添加一个提示，说明绿色文字是数学公式
        if '$' in question_text:
            content_html += '<div style="margin-bottom: 10px; font-style: italic; color: #666;">Hint: Green text represents mathematical formulas</div>'
            
        # 直接输出题目内容，保留简化后的公式
        formatted_text = question_text.replace("\n", "<br>")
        content_html += formatted_text
        content_html += "</div>"
        current_html = self.question_text.toHtml()
        title_end = current_html.find("</h2>") + 5
        if title_end > 4:
            new_html = (
                current_html[:title_end] + content_html + current_html[title_end:]
            )
            self.question_text.setHtml(new_html)
        else:
            self.question_text.setHtml(content_html)

    def format_math_inline(self, math_text):
        """将内联数学公式转换为图像"""
        img_data = self.render_math_formula(math_text, is_multiline=False)
        if img_data:
            return f'<img src="{img_data}" alt="{math_text}" style="vertical-align: middle; height: 3em; margin:0;" />'
        else:
            return f"${math_text}$"

    def render_math_formula(self, formula, is_multiline=False):
        """渲染数学公式为图像"""
        try:
            # 创建图形
            fig = Figure(figsize=(14, 3 if not is_multiline else 5))
            fig.patch.set_facecolor("none")  # 透明背景
            fig.tight_layout(pad=0.0)  # 减少边距
            ax = fig.add_subplot(111)
            ax.axis("off")

            # 渲染公式
            if is_multiline:
                ax.text(
                    0.5,
                    0.5,
                    f"${formula}$",
                    fontsize=26,
                    ha="center",
                    va="center",
                    transform=ax.transAxes,
                )
            else:
                ax.text(
                    0.5,
                    0.5,
                    f"${formula}$",
                    fontsize=26,
                    ha="center",
                    va="center",
                    transform=ax.transAxes,
                )

            # 保存为内存中的图像
            buffer = io.BytesIO()
            fig.savefig(
                buffer,
                format="png",
                bbox_inches="tight",
                pad_inches=0.0,
                transparent=True,
                dpi=180,
            )
            buffer.seek(0)

            # 转换为base64
            import base64

            img_str = base64.b64encode(buffer.getvalue()).decode()
            return f"data:image/png;base64,{img_str}"

        except Exception as e:
            logger.error(f"渲染公式出错: {e}")
            return None

    def show_reward_info(self):
        """显示难度与奖励的对照表"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Reward Information")
        dialog.setMinimumWidth(300)
        
        layout = QVBoxLayout(dialog)
        
        # 说明文本
        info_label = QLabel("Reward minutes for different difficulty levels:")
        info_label.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(info_label)
        
        # 创建表格
        table = QTableWidget(4, 2)
        table.setHorizontalHeaderLabels(["Difficulty", "Reward Minutes"])
        
        # 填充数据
        for i, difficulty in enumerate([1, 2, 3, 4]):
            # 难度项
            if difficulty == 1:
                difficulty_item = QTableWidgetItem("Easy")
            elif difficulty == 2:
                difficulty_item = QTableWidgetItem("Medium")
            elif difficulty == 3:
                difficulty_item = QTableWidgetItem("Hard")
            elif difficulty == 4:
                difficulty_item = QTableWidgetItem("Contest")
            table.setItem(i, 0, difficulty_item)
            
            # 奖励项
            reward = MATH_DIFFICULTY_REWARDS.get(difficulty, MATH_REWARD_PER_QUESTION)
            reward_item = QTableWidgetItem(f"{reward} minutes")
            table.setItem(i, 1, reward_item)
            
        # 调整表格
        table.resizeColumnsToContents()
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(table)
        
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
