import os
import json
import asyncio
import datetime
import logging
import openai
import re
from dotenv import load_dotenv
from logic.database import Database, get_week_start
from logic.constants import MATH_REWARD_PER_QUESTION, MAX_DAILY_MATH_QUESTIONS

# 配置日志
logger = logging.getLogger('math_exercises')
logger.setLevel(logging.INFO)

# 添加控制台处理器
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(console_handler)

# 添加文件处理器
file_handler = logging.FileHandler('game_limiter.log', encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

# 加载环境变量
load_dotenv()

# 设置OpenAI API密钥
openai.api_key = os.getenv("OPENAI_API_KEY")

class MathExercises:
    def __init__(self):
        self.db = Database()
        self.current_questions = []
        self.current_answers = []
        self.current_explanations = []
        self.current_question_index = 0
        self.api_error = None
        self.load_cached_questions()
        
    def load_cached_questions(self):
        """从数据库加载缓存的问题"""
        try:
            # cached_questions = self.db.get_today_gpt_questions() # Fetches records for today where is_gpt=1, regardless of is_correct status.
            cached_questions = self.db.get_today_gpt_questions()
            if cached_questions and len(cached_questions) > 0:
                logger.info(f"加载缓存的题目，共{len(cached_questions)}道")
                
                # 重置现有数据
                self.current_questions = []
                self.current_answers = []
                self.current_explanations = []
                
                # 从缓存中提取数据
                for q in cached_questions:
                    self.current_questions.append(q[2])  # question在索引2
                    
                    # 如果有答案和解释也提取
                    if len(q) > 3 and q[3]:
                        self.current_answers.append(q[3])
                    else:
                        self.current_answers.append("（无答案）")
                        
                    if len(q) > 6 and q[6]:
                        self.current_explanations.append(q[6])
                    else:
                        self.current_explanations.append("（无解释）")
                        
                self.current_question_index = 0
                logger.info(f"成功加载缓存题目: {len(self.current_questions)}道")
            else:
                logger.info("没有找到缓存的题目")
        except Exception as e:
            logger.error(f"加载缓存题目出错: {str(e)}")
            
    async def generate_questions_async(self):
        """异步生成数学问题"""
        try:
            return await self._generate_questions_async(force_regenerate=False)
        except Exception as e:
            logger.error(f"异步生成题目失败: {str(e)}")
            raise
            
    def generate_questions(self, callback=None):
        """生成数学问题 (保留兼容性)"""
        if callback:
            # 创建任务并设置回调
            async def _run_and_callback():
                try:
                    result = await self._generate_questions_async(force_regenerate=False)
                    callback(True, None)
                except Exception as e:
                    logger.error(f"生成题目出错: {str(e)}")
                    callback(False, str(e))
                    
            return asyncio.create_task(_run_and_callback())
        else:
            # 简单创建任务
            return asyncio.create_task(self._generate_questions_async(force_regenerate=False))
        
    async def _generate_questions_async(self, force_regenerate=False):
        """异步生成题目"""
        try:
            # 检查是否已经有今天的题目，且不强制重新生成
            if not force_regenerate:
                today_questions = self.db.get_today_gpt_questions()
                if today_questions:
                    logger.info("今天已有题目，直接加载")
                    self.current_questions = [q[2] for q in today_questions]  # question在索引2
                    self.current_answers = [q[3] for q in today_questions]    # answer在索引3
                    self.current_explanations = [q[6] for q in today_questions]  # explanation在索引6
                    self.current_question_index = 0
                    
                    # 找到第一个未完成的题目
                    for i, q in enumerate(today_questions):
                        if q[4] is None:  # is_correct在索引4
                            self.current_question_index = i
                            break
                    else:
                        # 如果所有题目都已完成，跳转到最后一题
                        self.current_question_index = len(today_questions) - 1
                    
                    return True
            
            # 如果没有今天的题目或强制重新生成，生成新题目
            logger.info("开始生成新题目")
            self.current_questions = []
            self.current_answers = []
            self.current_explanations = []
            
            if not openai.api_key:
                self.api_error = "未设置OpenAI API密钥，请在.env文件中设置OPENAI_API_KEY"
                logger.error(self.api_error)
                raise ValueError(self.api_error)
                
            # 使用GPT生成5个常规题目
            regular_prompt = """Generate 5 math questions with the following requirements:
1. Each question should be in English
2. Each question should be clear and concise
3. The answer should be a number
4. The questions should represent a range of difficulty from mid difficulty to high difficulty
5. The questions should be suitable for 6th grade Advanced Learning Program (ALP) students
6. Include a mix of different math topics, such as arithmetic, fractions, decimals, percentages, basic algebra, and geometry

Return the result in JSON format as follows:
{
    "questions": [
        {
            "question": "the math question",
            "answer": "the numerical answer",
            "explanation": "step-by-step solution explanation"
        },
        ... (5 questions total)
    ]
}

Please ensure the response is in valid JSON format."""

            # 使用GPT生成1个竞赛级难度题目
            competition_prompt = """Generate 1 competition-level math question with the following requirements:
1. The question should be in English
2. It should be challenging and suitable for a talented 6th grade student in an Advanced Learning Program (ALP)
3. The question should be at the level of math competitions (such as Math Olympiad or MathCounts)
4. Topics can include advanced problem-solving, creative applications of algebra, advanced geometry, number theory, or combinatorics
5. The question should require deeper thinking and possibly multiple steps to solve
6. The answer should be a number
7. Include a detailed step-by-step solution explanation

Return the result in JSON format as follows:
{
    "question": "the competition-level math question",
    "answer": "the numerical answer",
    "explanation": "detailed step-by-step solution explanation"
}

Please ensure the response is in valid JSON format."""

            # 并行发送两个请求以提高效率
            regular_task = asyncio.create_task(asyncio.to_thread(
                openai.chat.completions.create,
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": "You are a math teacher creating questions for 6th grade students in an Advanced Learning Program. Please return results in JSON format."},
                    {"role": "user", "content": regular_prompt}
                ],
                temperature=0.7
            ))
            
            competition_task = asyncio.create_task(asyncio.to_thread(
                openai.chat.completions.create,
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": "You are an expert math competition coach creating challenging problems for talented 6th grade students. Please return results in JSON format."},
                    {"role": "user", "content": competition_prompt}
                ],
                temperature=0.7
            ))
            
            # 等待两个任务完成
            regular_response, competition_response = await asyncio.gather(regular_task, competition_task)
            
            # 解析常规题目
            regular_result = json.loads(regular_response.choices[0].message.content)
            regular_questions = regular_result.get("questions", [])
            
            # 解析竞赛级题目
            competition_result = json.loads(competition_response.choices[0].message.content)
            competition_question = {
                "question": competition_result.get("question", ""),
                "answer": competition_result.get("answer", ""),
                "explanation": competition_result.get("explanation", "")
            }
            
            # 确保生成了足够的常规题目
            if len(regular_questions) < 5:
                error_msg = f"只生成了{len(regular_questions)}题常规题目，少于要求的5题"
                logger.error(error_msg)
                raise ValueError(error_msg)
                
            # 提取题目、答案和解释
            for q in regular_questions:
                self.current_questions.append(q["question"])
                self.current_answers.append(q["answer"])
                # 如果提供了解释，使用提供的解释，否则使用空字符串
                self.current_explanations.append(q.get("explanation", ""))
            
            # 添加竞赛级题目作为最后一题
            self.current_questions.append(competition_question["question"])
            self.current_answers.append(competition_question["answer"])
            self.current_explanations.append(competition_question["explanation"])
            
            # 缓存生成的题目
            today = datetime.date.today().strftime("%Y-%m-%d")
            await asyncio.to_thread(self.db.clear_all_today_math_exercises)
            c = self.db.conn.cursor()
            self.db.conn.execute("BEGIN TRANSACTION")
            for i in range(len(self.current_questions)):
                logger.info(f"[DEBUG] 写入题目: {self.current_questions[i]}, 答案: {self.current_answers[i]}")
                c.execute(
                    "INSERT INTO math_exercises (date, question, answer, explanation, is_gpt) VALUES (?, ?, ?, ?, 1)",
                    (today, self.current_questions[i], self.current_answers[i], self.current_explanations[i])
                )
            self.db.conn.commit()
            logger.info("已成功保存题目到数据库")
            
            # 更新状态
            self.current_question_index = 0
            
            return True
                
        except Exception as e:
            logger.error(f"生成题目时出错: {e}")
            self.api_error = f"生成题目时出错: {str(e)}"
            raise
    
    def get_current_question(self):
        """获取当前问题"""
        if not self.current_questions:
            return None
        if self.current_question_index >= len(self.current_questions):
            return None
        return self.current_questions[self.current_question_index]
    
    def get_current_answer(self):
        """获取当前问题的标准答案"""
        if not self.current_answers or self.current_question_index >= len(self.current_answers):
            return "（无标准答案）"
        return self.current_answers[self.current_question_index]
    
    def get_current_explanation(self):
        """获取当前问题的解释"""
        if not self.current_explanations or self.current_question_index >= len(self.current_explanations):
            return "（无解释）"
        return self.current_explanations[self.current_question_index]
        
    def next_question(self):
        """移动到下一个问题"""
        if self.current_question_index < len(self.current_questions) - 1:
            self.current_question_index += 1
            return self.get_current_question()
        return None
        
    def get_completed_count(self):
        """获取今天已完成的题目数量"""
        exercises = self.db.get_today_math_exercises()
        # 只计算 is_correct 不为 NULL 的记录
        completed = 0
        for ex in exercises:
            if ex[4] is not None: # ex[4] 是 is_correct 字段
                logger.info(f"Record ID {ex[0]} with is_correct={ex[4]} is counted as completed.")
                completed += 1
        logger.info(f"Total completed math exercises for today: {completed}")
        return completed
    
    async def check_answer_async(self, question_index, user_answer):
        """异步检查答案"""
        if question_index >= len(self.current_questions):
            raise ValueError("问题索引超出范围")
            
        question = self.current_questions[question_index]
        try:
            # 获取标准答案
            standard_answer = self.current_answers[question_index]
            if not standard_answer:
                raise ValueError("无法获取标准答案")
                
            # 清理答案中的空格
            user_answer = re.sub(r'\s+', '', user_answer)
            standard_answer = re.sub(r'\s+', '', standard_answer)
            
            # 尝试直接比较
            try:
                # 尝试转换为数值进行比较
                user_num = float(user_answer)
                standard_num = float(standard_answer)
                # 允许0.01的误差
                is_correct = abs(user_num - standard_num) < 0.01
                reward = MATH_REWARD_PER_QUESTION if is_correct else 0
                
                # 记录到数据库
                await asyncio.to_thread(
                    self.db.add_math_exercise,
                    question=question,
                    answer=user_answer,
                    is_correct=is_correct,
                    reward_minutes=reward,
                    is_gpt=0
                )
                
                return is_correct
            except ValueError:
                # 如果无法转换为数值，使用GPT检查
                pass
                
            # 使用GPT检查答案
            prompt = f"""Please check if the following math answer is correct. Return the result in JSON format as follows:
{{
    "is_correct": true/false,  // whether the answer is correct
    "explanation": "detailed explanation",  // explain why it's correct or wrong
    "standard_answer": "standard answer"  // the standard answer
}}

Question: {question}
Student's answer: {user_answer}
Standard answer: {standard_answer}

Please ensure the response is in valid JSON format."""

            response = await asyncio.to_thread(
                openai.chat.completions.create,
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": "You are a math teacher responsible for checking student answers. Please return results in JSON format."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            # 解析GPT的响应
            try:
                result = json.loads(response.choices[0].message.content)
                is_correct = result.get("is_correct", False)
                explanation = result.get("explanation", "")
                reward = MATH_REWARD_PER_QUESTION if is_correct else 0
                
                # 记录到数据库
                await asyncio.to_thread(
                    self.db.add_math_exercise,
                    question=question,
                    answer=user_answer,
                    is_correct=is_correct,
                    reward_minutes=reward,
                    is_gpt=1
                )
                
                # 更新解释
                if explanation and question_index < len(self.current_explanations):
                    self.current_explanations[question_index] = explanation
                
                return is_correct
            except json.JSONDecodeError:
                logger.error(f"GPT返回的不是有效的JSON格式: {response.choices[0].message.content}")
                raise ValueError("无法解析GPT的响应")
                
        except Exception as e:
            logger.error(f"检查答案时出错: {str(e)}")
            raise
        
    def check_answer(self, question_index, user_answer):
        """检查答案（同步版本，保留兼容性）"""
        if question_index >= len(self.current_questions):
            raise ValueError("问题索引超出范围")
            
        question = self.current_questions[question_index]
        
        # 获取标准答案
        standard_answer = self.current_answers[question_index]
        if not standard_answer:
            raise ValueError("无法获取标准答案")
            
        # 清理答案中的空格
        user_answer = re.sub(r'\s+', '', user_answer)
        standard_answer = re.sub(r'\s+', '', standard_answer)
        
        # 尝试直接比较
        try:
            # 尝试转换为数值进行比较
            user_num = float(user_answer)
            standard_num = float(standard_answer)
            # 允许0.01的误差
            is_correct = abs(user_num - standard_num) < 0.01
            reward = MATH_REWARD_PER_QUESTION if is_correct else 0
            
            # 记录到数据库
            self.db.add_math_exercise(
                question=question,
                answer=user_answer,
                is_correct=is_correct,
                reward_minutes=reward,
                is_gpt=0
            )
            
            return is_correct
        except ValueError:
            # 如果无法简单比较，尝试正则表达式或其他模式匹配
            # 这里使用简单的相等比较作为fallback
            is_correct = user_answer.lower() == standard_answer.lower()
            reward = MATH_REWARD_PER_QUESTION if is_correct else 0
            
            # 记录到数据库
            self.db.add_math_exercise(
                question=question,
                answer=user_answer,
                is_correct=is_correct,
                reward_minutes=reward,
                is_gpt=0
            )
            
            return is_correct
    
    async def get_explanation_async(self, question, user_answer):
        """异步获取错误答案的解释"""
        # 检查缓存
        cached = self.db.get_cached_explanation(question, user_answer)
        if cached:
            return cached
            
        try:
            if not openai.api_key:
                raise ValueError("未设置OpenAI API密钥，请在.env文件中设置OPENAI_API_KEY")

            # 使用OpenAI API获取解释
            response = await asyncio.to_thread(
                openai.chat.completions.create,
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": "You are a math teacher. Please explain the student's answer and give a complete correct solution process. All in English."},
                    {"role": "user", "content": f"Question: {question}\n\nStudent's answer: {user_answer}\n\nPlease explain the student's answer and give a complete correct solution process."}
                ],
                temperature=0.5
            )
            
            explanation = response.choices[0].message.content
            await asyncio.to_thread(self.db.cache_explanation, question, user_answer, explanation)
            return explanation
        except Exception as e:
            error_msg = f"获取解释时出错: {str(e)}"
            logger.error(error_msg)
            raise
    
    def get_explanation(self, question, user_answer, callback=None):
        """兼容性方法 - 获取错误答案的解释"""
        if callback:
            async def _run_and_callback():
                try:
                    explanation = await self.get_explanation_async(question, user_answer)
                    callback(True, explanation, None)
                except Exception as e:
                    callback(False, None, str(e))
                    
            return asyncio.create_task(_run_and_callback())
    
    def get_today_math_reward(self):
        """获取今天通过数学练习获得的奖励分钟数"""
        return self.db.get_today_math_reward()
    
    def get_daily_questions(self):
        """获取今日题目 (供UI调用)"""
        # 检查是否已有缓存题目
        if not self.current_questions:
            # 尝试从数据库加载
            self.load_cached_questions()
            
            # 如果仍然没有题目，生成新题目 (同步调用)
            if not self.current_questions:
                # 创建event loop确保可以调用异步函数
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    # 创建新的event loop
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                # 同步等待异步函数完成
                try:
                    loop.run_until_complete(self._generate_questions_async(force_regenerate=False))
                except Exception as e:
                    logger.error(f"同步生成题目失败: {str(e)}")
        
        # 构造返回结果
        result = []
        for i in range(len(self.current_questions)):
            question_data = {
                'question': self.current_questions[i],
                'answer': self.current_answers[i] if i < len(self.current_answers) else "（无答案）",
                'explanation': self.current_explanations[i] if i < len(self.current_explanations) else ""
            }
            result.append(question_data)
            
        return result
    
    def clear_today_questions(self):
        """清除今天的问题缓存"""
        self.current_questions = []
        self.current_answers = []
        self.current_explanations = []
        self.current_question_index = 0
        self.db.clear_all_today_math_exercises()
        
    def close(self):
        """关闭数据库连接"""
        self.db.close()

    async def regenerate_daily_questions_async(self):
        """异步重新生成今天的题目"""
        # 清除今天的题目
        await asyncio.to_thread(self.db.clear_all_today_math_exercises)
        self.current_questions = []
        self.current_answers = []
        self.current_explanations = []
        self.current_question_index = 0
        
        # 重新生成题目，强制重新生成
        return await self._generate_questions_async(force_regenerate=True)

    def regenerate_daily_questions(self):
        """重新生成今天的题目 (同步版本保留兼容性)"""
        # 清除今天的题目
        self.db.clear_all_today_math_exercises()
        self.current_questions = []
        self.current_answers = []
        self.current_explanations = []
        self.current_question_index = 0
        
        # 使用同步方式生成题目
        self._generate_questions_thread(force_regenerate=True)
        
    def _generate_questions_thread(self, on_complete=None, force_regenerate=False):
        """在后台线程中生成题目 (保留兼容性，不建议使用)"""
        try:
            # 检查是否已经有今天的题目，且不强制重新生成
            if not force_regenerate:
                today_questions = self.db.get_today_gpt_questions()
                if today_questions:
                    logger.info("今天已有题目，直接加载")
                    self.current_questions = [q[2] for q in today_questions]  # question在索引2
                    self.current_answers = [q[3] for q in today_questions]    # answer在索引3
                    self.current_explanations = [q[6] for q in today_questions]  # explanation在索引6
                    self.current_question_index = 0
                    
                    # 找到第一个未完成的题目
                    for i, q in enumerate(today_questions):
                        if q[4] is None:  # is_correct在索引4
                            self.current_question_index = i
                            break
                    else:
                        # 如果所有题目都已完成，跳转到最后一题
                        self.current_question_index = len(today_questions) - 1
                    
                    if on_complete:
                        on_complete(True, None)
                    return True
                
            # 启动异步任务
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                # 如果没有事件循环，创建一个
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
            # 创建异步任务
            task = loop.create_task(self._generate_questions_async(force_regenerate))
            
            # 设置回调
            if on_complete:
                def done_callback(task):
                    try:
                        result = task.result()
                        on_complete(True, None)
                    except Exception as e:
                        on_complete(False, str(e))
                        
                task.add_done_callback(done_callback)
                
            return task
            
        except Exception as e:
            logger.error(f"生成题目错误: {e}")
            if on_complete:
                on_complete(False, str(e))
            return False 