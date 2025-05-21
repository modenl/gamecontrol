import sys
import os
import re
import logging
import asyncio
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, 
    QLabel, QPushButton, QLineEdit, QTextEdit,
    QFrame, QProgressBar, QMessageBox,
    QScrollArea, QGridLayout, QSpacerItem, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QPixmap

from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
import io
from PIL import Image

from logic.constants import (
    PADDING_SMALL, PADDING_MEDIUM, PADDING_LARGE,
    THEME_PRIMARY, THEME_SUCCESS, THEME_DANGER, THEME_WARNING,
    MAX_DAILY_MATH_QUESTIONS, MATH_REWARD_PER_QUESTION
)
from logic.math_exercises import MathExercises
from ui.base import ToolTip, ShakeEffect

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
        
        # 设置窗口
        self.setWindowTitle("数学练习")
        self.resize(1000, 800)
        self.setMinimumSize(800, 600)
        self.setModal(True)
        
        # 初始化UI
        self.setup_ui()
        
        # 加载题目
        asyncio.create_task(self.load_or_generate_questions())
        
    def setup_ui(self):
        """设置UI组件"""
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(PADDING_MEDIUM, PADDING_MEDIUM, PADDING_MEDIUM, PADDING_MEDIUM)
        main_layout.setSpacing(PADDING_MEDIUM)
        
        # 顶部信息框架
        info_frame = QFrame()
        info_frame.setFrameShape(QFrame.Shape.StyledPanel)
        info_frame.setFrameShadow(QFrame.Shadow.Raised)
        info_layout = QHBoxLayout(info_frame)
        
        # 标题
        title_label = QLabel("数学练习")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        info_layout.addWidget(title_label)
        
        # 今日奖励分钟数标签
        self.reward_label = QLabel("今日已奖励：0 分钟")
        info_layout.addWidget(self.reward_label, 1)
        
        # 完成计数
        self.done_label = QLabel(f"已完成: 0/{MAX_DAILY_MATH_QUESTIONS}")
        info_layout.addWidget(self.done_label)
        
        # 每题奖励信息
        reward_info = QLabel(f"每题奖励{MATH_REWARD_PER_QUESTION}分钟")
        info_layout.addWidget(reward_info)
        
        main_layout.addWidget(info_frame)
        
        # 题目显示区域
        question_frame = QFrame()
        question_frame.setFrameShape(QFrame.Shape.StyledPanel)
        question_frame.setFrameShadow(QFrame.Shadow.Raised)
        question_layout = QVBoxLayout(question_frame)
        
        # 题目文本框
        self.question_text = QTextEdit()
        self.question_text.setReadOnly(True)
        self.question_text.setMinimumHeight(200)
        question_layout.addWidget(self.question_text)
        
        main_layout.addWidget(question_frame)
        
        # 答案输入框架
        answer_frame = QFrame()
        answer_frame.setFrameShape(QFrame.Shape.StyledPanel)
        answer_frame.setFrameShadow(QFrame.Shadow.Raised)
        answer_layout = QHBoxLayout(answer_frame)
        
        # 答案标签
        answer_label = QLabel("你的答案:")
        answer_layout.addWidget(answer_label)
        
        # 答案输入框
        self.answer_entry = QLineEdit()
        self.answer_entry.setMinimumWidth(200)
        answer_layout.addWidget(self.answer_entry)
        
        # 提交按钮
        self.submit_button = QPushButton("提交答案")
        self.submit_button.clicked.connect(lambda: asyncio.create_task(self.submit_answer()))
        self.submit_button.setEnabled(False)
        answer_layout.addWidget(self.submit_button)
        
        main_layout.addWidget(answer_frame)
        
        # 结果显示区域
        result_frame = QFrame()
        result_frame.setFrameShape(QFrame.Shape.StyledPanel)
        result_frame.setFrameShadow(QFrame.Shadow.Raised)
        result_layout = QVBoxLayout(result_frame)
        
        # 结果文本框
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setMinimumHeight(150)
        result_layout.addWidget(self.result_text)
        
        main_layout.addWidget(result_frame)
        
        # 进度条 - 仅在加载时显示
        self.progress_frame = QFrame()
        progress_layout = QVBoxLayout(self.progress_frame)
        
        self.progress_label = QLabel("正在加载题目，请稍候...")
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
        
        # 调试按钮 - 查看/重新生成今日题目
        self.debug_button = QPushButton("查看/重新生成今日题目")
        self.debug_button.clicked.connect(self.show_today_questions)
        button_layout.addWidget(self.debug_button)
        
        # 下一题按钮
        self.next_button = QPushButton("下一题")
        self.next_button.clicked.connect(self.next_question)
        self.next_button.setEnabled(False)
        button_layout.addWidget(self.next_button)
        
        # 空白
        button_layout.addStretch()
        
        # 关闭按钮
        self.close_button = QPushButton("关闭")
        self.close_button.clicked.connect(self.close)
        button_layout.addWidget(self.close_button)
        
        main_layout.addWidget(button_frame)
        
        # 设置工具提示
        ToolTip(self.next_button, "前往下一道题目")
        ToolTip(self.submit_button, "提交你的答案")
        ToolTip(self.done_label, f"每天最多可以完成{MAX_DAILY_MATH_QUESTIONS}道题目")
    
    async def load_or_generate_questions(self):
        """自动加载或生成题目"""
        if self.loading:
            return
            
        self.loading = True
        self.show_progress("正在加载题目，请稍候...")
        
        try:
            # 直接在异步函数中执行，无需线程
            questions = await asyncio.to_thread(self.math.get_daily_questions)
            # 查看已完成的题目数量
            done_count = await asyncio.to_thread(self.math.get_completed_count)
            
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
        
        # 更新完成数
        self.update_done_count()
        
        # 显示第一个未完成的题目
        if self.questions and len(self.questions) > self.done_count:
            self.current_index = self.done_count
            await self.show_current_question()
        else:
            self.question_text.setHtml("<p>今日题目已全部完成！</p>")
            self.submit_button.setEnabled(False)
    
    async def on_load_error(self, error_msg):
        """题目加载错误回调"""
        self.hide_progress()
        
        QMessageBox.critical(self, "加载错误", f"加载题目时出错: {error_msg}")
        self.close()
    
    async def show_current_question(self):
        """显示当前题目"""
        if not self.questions or self.current_index >= len(self.questions):
            return
            
        question_data = self.questions[self.current_index]
        self.current_question = question_data['question']
        self.current_answer = question_data['answer']
        self.current_explanation = question_data.get('explanation', '')
        self.answer_checked = False
        
        # 清空之前的答案和结果
        self.answer_entry.clear()
        self.result_text.clear()
        
        # 创建题目标题
        title = f"题目 {self.current_index + 1}/{len(self.questions)}"
        
        # 检查是否是最后一题（竞赛级题目）
        is_competition = (self.current_index == len(self.questions) - 1)
        
        if is_competition:
            # 竞赛级题目使用特殊样式
            title_html = f'<h2 style="color: #ff6600;">竞赛题: {title} <span style="font-size: 14px;">(高级难度)</span></h2>'
        else:
            title_html = f'<h2>{title}</h2>'
        
        # 显示题目文本
        self.question_text.clear()
        self.question_text.setHtml(title_html)
        self.insert_question_content()
        
        # 启用提交按钮
        self.submit_button.setEnabled(True)
        
        # 禁用下一题按钮，直到回答后再启用
        self.next_button.setEnabled(False)
        
        # 聚焦到答案输入框
        self.answer_entry.setFocus()
    
    def next_question(self):
        """前往下一题"""
        if self.current_index < len(self.questions) - 1:
            self.current_index += 1
            asyncio.create_task(self.show_current_question())
        else:
            QMessageBox.information(self, "完成", "所有题目已完成！")
    
    def update_done_count(self):
        """更新完成计数"""
        # 更新完成数量显示
        self.done_label.setText(f"已完成: {self.done_count}/{MAX_DAILY_MATH_QUESTIONS}")
        
        # 更新奖励分钟数
        reward_minutes = self.done_count * MATH_REWARD_PER_QUESTION
        self.reward_label.setText(f"今日已奖励：{reward_minutes} 分钟")
    
    async def submit_answer(self):
        """提交答案"""
        if self.answer_checked:
            self.next_question()
            return
            
        user_answer = self.answer_entry.text().strip()
        if not user_answer:
            QMessageBox.warning(self, "提示", "请输入答案")
            return
            
        # 显示进度
        self.show_progress("正在检查答案，请稍候...")
        self.submit_button.setEnabled(False)
        
        try:
            # 直接在异步函数中执行，无需线程
            is_correct = await asyncio.to_thread(
                self.math.check_answer,
                self.current_index, 
                user_answer
            )
            
            # 处理结果
            await self.on_check_complete(True, is_correct, self.current_explanation)
            
        except Exception as e:
            logger.error(f"检查答案出错: {e}")
            await self.on_check_complete(False, False, None, str(e))
        finally:
            self.submit_button.setEnabled(True)
    
    async def on_check_complete(self, success, is_correct, explanation, error_msg=None):
        """检查完成回调"""
        self.hide_progress()
        
        if not success:
            QMessageBox.critical(self, "错误", f"检查答案时出错: {error_msg}")
            return
            
        self.answer_checked = True
        
        # 显示结果
        if is_correct:
            # 答案正确，更新计数
            self.done_count += 1
            self.update_done_count()
            
            # 如果是最后一个完成的题目，发送信号
            if self.done_count == MAX_DAILY_MATH_QUESTIONS:
                # 计算奖励分钟数
                reward_minutes = MAX_DAILY_MATH_QUESTIONS * MATH_REWARD_PER_QUESTION
                self.on_complete_signal.emit(reward_minutes)
                
                # 弹出祝贺消息
                QMessageBox.information(
                    self, 
                    "完成所有题目", 
                    f"恭喜你完成了今天所有的题目！\n获得了{reward_minutes}分钟的额外游戏时间。"
                )
            
            # 更改按钮文字
            self.submit_button.setText("下一题")
            self.next_button.setEnabled(True)
        
        # 显示结果
        await self.show_result(is_correct, explanation)
    
    async def show_result(self, is_correct, explanation):
        """显示结果"""
        # 显示正确或错误
        if is_correct:
            result_html = '<div style="color: #28a745; font-weight: bold;">正确！</div>'
        else:
            result_html = '<div style="color: #dc3545; font-weight: bold;">错误！</div>'
            
            # 显示正确答案
            result_html += f'<div>正确答案: {self.current_answer}</div>'
            await ShakeEffect.shake(self.answer_entry)
        
        # 添加解释
        if explanation:
            result_html += '<div style="margin-top: 10px;">'
            result_html += '<h3>解释:</h3>'
            result_html += explanation
            result_html += '</div>'
        
        self.result_text.setHtml(result_html)
    
    def close(self):
        """关闭窗口"""
        # 如果有需要清理的资源，在这里处理
        super().close()
    
    def show_today_questions(self):
        """显示/重新生成今日题目"""
        dialog = QDialog(self)
        dialog.setWindowTitle("今日题目")
        dialog.resize(800, 600)
        
        layout = QVBoxLayout(dialog)
        
        # 当前题目信息
        info_text = QTextEdit()
        info_text.setReadOnly(True)
        info_html = "<h2>今日题目</h2>"
        
        completed = self.math.get_completed_count()
        info_html += f"<p>已完成: {completed}/{MAX_DAILY_MATH_QUESTIONS}</p>"
        
        if self.questions:
            for i, q in enumerate(self.questions):
                status = "已完成" if i < completed else "未完成"
                color = "#28a745" if i < completed else "#6c757d"
                
                # 检查是否是竞赛级题目（最后一题）
                is_competition = (i == len(self.questions) - 1)
                
                info_html += f'<div style="margin-bottom: 15px; padding: 10px; border: 1px solid #ddd; border-radius: 5px;'
                
                # 为竞赛级题目添加特殊样式
                if is_competition:
                    info_html += ' background-color: #fff8f0; border-color: #ff6600;">'
                    info_html += f'<h3 style="color: #ff6600;">竞赛题 {i+1} <span style="color: {color};">({status})</span> <span style="font-size: 14px;">(高级难度)</span></h3>'
                else:
                    info_html += '">'
                    info_html += f'<h3>题目 {i+1} <span style="color: {color};">({status})</span></h3>'
                
                info_html += f'<p><strong>问题:</strong> {q["question"]}</p>'
                info_html += f'<p><strong>答案:</strong> {q["answer"]}</p>'
                if "explanation" in q and q["explanation"]:
                    info_html += f'<p><strong>解释:</strong> {q["explanation"]}</p>'
                info_html += '</div>'
        else:
            info_html += "<p>没有找到今日题目数据</p>"
            
        info_text.setHtml(info_html)
        layout.addWidget(info_text)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        regen_button = QPushButton("重新生成题目")
        regen_button.clicked.connect(lambda: asyncio.create_task(self.regenerate_questions(dialog)))
        button_layout.addWidget(regen_button)
        
        close_button = QPushButton("关闭")
        close_button.clicked.connect(dialog.close)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
        
        dialog.setLayout(layout)
        dialog.exec()
    
    async def regenerate_questions(self, parent_dialog=None):
        """重新生成题目"""
        msg = "确定要重新生成今日题目吗？\n这将重置你今天的所有进度！"
        confirm = QMessageBox.question(
            self, 
            "确认重新生成", 
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirm != QMessageBox.StandardButton.Yes:
            return
            
        # 显示进度
        self.show_progress("正在重新生成题目，请稍候...")
        
        try:
            # 直接在异步函数中执行，无需线程
            # 删除旧的数据并重新生成
            await asyncio.to_thread(self.math.regenerate_daily_questions)
            
            # 获取新的题目
            questions = await asyncio.to_thread(self.math.get_daily_questions)
            done_count = 0
            
            # 处理结果
            await self.on_regen_complete(questions, done_count, parent_dialog)
            
        except Exception as e:
            logger.error(f"重新生成题目出错: {e}")
            await self.on_load_error(str(e))
    
    async def on_regen_complete(self, questions, done_count, parent_dialog=None):
        """重新生成完成回调"""
        self.hide_progress()
        
        # 更新题目数据
        self.questions = questions
        self.done_count = done_count
        self.current_index = 0
        
        # 更新UI
        self.update_done_count()
        await self.show_current_question()
        
        # 成功消息
        QMessageBox.information(self, "成功", "题目已重新生成！")
        
        # 如果是从对话框调用的，关闭并重新打开
        if parent_dialog:
            parent_dialog.close()
            self.show_today_questions()
    
    def show_progress(self, message="正在处理，请稍候..."):
        """显示进度条"""
        self.progress_label.setText(message)
        self.progress_frame.show()
        
    def hide_progress(self):
        """隐藏进度条"""
        self.progress_frame.hide()
    
    def insert_question_content(self):
        """插入题目内容"""
        question_text = self.current_question
        
        # 创建一个HTML容器
        content_html = ''
        
        # 检查是否是竞赛级题目（最后一题）
        is_competition = (self.current_index == len(self.questions) - 1)
        
        # 竞赛题目的特殊样式
        if is_competition:
            content_html += '<div style="padding: 10px; background-color: #fff8f0; border-left: 3px solid #ff6600; margin-bottom: 10px;">'
        else:
            content_html += '<div>'
        
        # 检查是否有公式
        if "![formula]" in question_text:
            # 替换公式为图像
            parts = question_text.split("![formula]")
            html_content = parts[0]
            
            for i in range(1, len(parts)):
                formula_end = parts[i].find("]")
                if formula_end != -1:
                    formula = parts[i][:formula_end]
                    
                    # 生成公式图像
                    img_data = self.render_math_formula(formula)
                    if img_data:
                        html_content += f'<img src="{img_data}" alt="{formula}" style="vertical-align: middle;" />'
                    else:
                        html_content += formula
                        
                    # 添加剩余文本
                    html_content += parts[i][formula_end+1:]
                else:
                    html_content += parts[i]
            
            content_html += html_content
        else:
            # 处理纯文本，支持基本格式化
            # 替换换行符为HTML换行
            formatted_text = question_text.replace("\n", "<br>")
            
            # 尝试检测数学符号，添加行内公式格式 (如 *x^2* 转换为 $x^2$)
            import re
            math_pattern = r'\*([^*]+)\*'
            formatted_text = re.sub(math_pattern, lambda m: self.format_math_inline(m.group(1)), formatted_text)
            
            content_html += formatted_text
        
        # 关闭div容器
        content_html += '</div>'
        
        # 获取当前HTML内容
        current_html = self.question_text.toHtml()
        
        # 在标题后添加内容
        title_end = current_html.find('</h2>') + 5
        if title_end > 4:  # 如果找到了标题结束标签
            new_html = current_html[:title_end] + content_html + current_html[title_end:]
            self.question_text.setHtml(new_html)
        else:
            # 如果没有找到标题，直接设置内容
            self.question_text.setHtml(content_html)
    
    def format_math_inline(self, math_text):
        """将内联数学公式转换为图像"""
        img_data = self.render_math_formula(math_text, is_multiline=False)
        if img_data:
            return f'<img src="{img_data}" alt="{math_text}" style="vertical-align: middle; height: 1.2em;" />'
        else:
            return f'${math_text}$'
    
    def render_math_formula(self, formula, is_multiline=False):
        """渲染数学公式为图像"""
        try:
            # 创建图形
            fig = Figure(figsize=(6, 0.5 if not is_multiline else 1.5))
            fig.patch.set_facecolor('none')  # 透明背景
            ax = fig.add_subplot(111)
            ax.axis('off')
            
            # 渲染公式
            if is_multiline:
                ax.text(0.5, 0.5, f"${formula}$", 
                        fontsize=14, 
                        ha='center', va='center', 
                        transform=ax.transAxes)
            else:
                ax.text(0.5, 0.5, f"${formula}$", 
                        fontsize=14, 
                        ha='center', va='center', 
                        transform=ax.transAxes)
            
            # 保存为内存中的图像
            buffer = io.BytesIO()
            fig.savefig(buffer, format='png', bbox_inches='tight', pad_inches=0.1, transparent=True)
            buffer.seek(0)
            
            # 转换为base64
            import base64
            img_str = base64.b64encode(buffer.getvalue()).decode()
            return f"data:image/png;base64,{img_str}"
            
        except Exception as e:
            logger.error(f"渲染公式出错: {e}")
            return None 