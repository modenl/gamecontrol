import os
import json
import asyncio
import datetime
import logging
import openai
import re
from dotenv import load_dotenv
from logic.database import Database, get_week_start
from logic.constants import MATH_REWARD_PER_QUESTION, MAX_DAILY_MATH_QUESTIONS, MATH_DIFFICULTY_REWARDS

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
        # 使用单一数据结构存储题目
        self.questions = []
        self.current_index = 0
        self.api_error = None
        
    async def initialize(self):
        """Async initialization to be called after construction"""
        await self.load_cached_questions()
        return self
        
    async def load_cached_questions(self):
        """从数据库加载缓存的问题"""
        try:
            cached_questions = await self.db.get_today_gpt_questions()
            # 记录加载到的题目数量
            logger.info(f"从数据库加载题目，共{len(cached_questions)}条记录")
            
            # 只保留每道题的最新一条（按question分组，取id最大）
            latest_questions = {}
            seen_questions = set()  # 跟踪已处理的题目，防止重复
            
            for q in cached_questions:
                try:
                    # 确保question是标准化比较的
                    if q[2] is None:  # 检查question是否为None
                        logger.warning(f"跳过无效题目记录ID={q[0]}")
                        continue
                        
                    std_question = q[2].strip().replace('\n', '').replace(' ', '').replace('\r', '')
                    
                    # 检查是否有重复题目（即使标准化后也相同）
                    if std_question in seen_questions:
                        logger.debug(f"跳过重复题目ID={q[0]}, 标准化后={std_question[:20]}...")
                        continue
                        
                    # 使用标准化后的题目作为键，避免重复
                    if std_question not in latest_questions or q[0] > latest_questions[std_question][0]:
                        latest_questions[std_question] = q
                        seen_questions.add(std_question)
                except Exception as e:
                    logger.error(f"处理题目记录出错 ID={q[0] if len(q) > 0 else 'unknown'}: {e}")
                    continue
                    
            if latest_questions:
                logger.info(f"去重后加载的题目，共{len(latest_questions)}道")
                self.questions = []
                
                for q in latest_questions.values():
                    try:
                        difficulty = None
                        if len(q) > 8:
                            difficulty = q[8]  # difficulty在索引8
                            logger.debug(f"从数据库加载题目，ID={q[0]}，难度={difficulty}")
                        
                        # 添加到题目列表，确保所有字段都有有效值
                        question_obj = {
                            "question": q[2] if q[2] else "（无题目内容）",  # 使用原始格式
                            "answer": q[3] if len(q) > 3 and q[3] else "（无答案）",
                            "explanation": q[6] if len(q) > 6 and q[6] else "（无解释）",
                            "difficulty": difficulty if difficulty is not None else 2,  # 默认难度2
                            "is_correct": q[4] if len(q) > 4 else None
                        }
                        self.questions.append(question_obj)
                    except Exception as e:
                        logger.error(f"添加题目到列表出错 ID={q[0] if len(q) > 0 else 'unknown'}: {e}")
                        continue
                    
                # 确保至少有6道题
                if len(self.questions) < 6:
                    logger.warning(f"加载题目数量不足，只有{len(self.questions)}道，应为6道")
                    
                # 设置当前索引为第一个未回答的问题
                self.current_index = 0
                for i, q in enumerate(self.questions):
                    if q["is_correct"] is None:
                        self.current_index = i
                        break
                logger.info(f"成功加载缓存题目: {len(self.questions)}道")
                logger.info(f"加载的题目难度: {[q.get('difficulty') for q in self.questions]}")
            else:
                logger.info("没有找到缓存的题目")
        except Exception as e:
            logger.error(f"加载缓存题目出错: {str(e)}")
            logger.exception("详细错误信息:")
            
    async def _handle_api_error(self, operation_name, func, *args, **kwargs):
        """通用错误处理，简化API操作"""
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            error_msg = f"{operation_name}失败: {str(e)}"
            logger.error(error_msg)
            self.api_error = error_msg
            raise
            
    async def generate_questions_async(self):
        """异步生成数学问题"""
        return await self._handle_api_error("异步生成题目", self._generate_questions_async, False)
            
    # 保留兼容性方法，但内部使用异步实现
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
                today_questions = await self.db.get_today_gpt_questions()
                if today_questions:
                    logger.info("今天已有题目，直接加载")
                    self.questions = []
                    for q in today_questions:
                        # 详细记录从数据库加载的题目难度
                        difficulty = q[8] if len(q) > 8 and q[8] is not None else None
                        logger.debug(f"从数据库加载题目ID={q[0]}，难度={difficulty}")
                        
                        question_obj = {
                            "question": q[2],  # question在索引2
                            "answer": q[3] if len(q) > 3 and q[3] else "（无答案）",
                            "explanation": q[6] if len(q) > 6 and q[6] else "",
                            "difficulty": difficulty,
                            "is_correct": q[4]
                        }
                        self.questions.append(question_obj)
                    
                    logger.info(f"从数据库加载题目，难度: {[q.get('difficulty') for q in self.questions]}")
                    
                    # 设置当前索引为第一个未回答的问题
                    self.current_index = 0
                    for i, q in enumerate(self.questions):
                        if q["is_correct"] is None:
                            self.current_index = i
                            break
                    return True
                    
            # 如果没有今天的题目或强制重新生成，生成新题目
            logger.info("开始生成新题目")
            self.questions = []
            
            if not openai.api_key:
                self.api_error = "未设置OpenAI API密钥，请在.env文件中设置OPENAI_API_KEY"
                logger.error(self.api_error)
                raise ValueError(self.api_error)
                
            # 使用单一prompt生成全部6道题目（5道常规+1道竞赛级）
            # 添加时间戳以确保每次生成的题目不同
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
            all_questions_prompt = f"""
Generate 6 NEW and UNIQUE math questions with the following requirements:

1. Each question should be in English.
2. Each question should be clear and concise.
3. The answer should be a number.
4. All questions must be in the style and difficulty of the AMC8 math competition in the United States.
5. The first 5 questions should cover a range of AMC8 difficulty from easy to hard.
6. Include a mix of AMC8 topics, such as arithmetic, fractions, decimals, percentages, basic algebra, geometry, combinatorics, and word problems.
7. Assign a difficulty level from 1-4 for each question, where:
   - 1: AMC8 easy (comparable to AMC8 Q1-5)
   - 2: AMC8 medium (comparable to AMC8 Q6-15)
   - 3: AMC8 hard (comparable to AMC8 Q16-20)
   - 4: AMC8 very hard/competition level (comparable to AMC8 Q21-25)
8. The 6th question MUST be AMC8 competition-level difficulty (level 4), similar to the hardest AMC8 questions.
9. Use authentic AMC8 style and wording, and avoid non-competition or classroom-style questions.
10. IMPORTANT: Generate COMPLETELY DIFFERENT questions each time. Do not repeat similar patterns or question formats.
11. IMPORTANT: Keep math notation simple! Use simple notation like x^2 for x squared, x/y for fractions. 
12. If you must use LaTeX-style notation with $ symbols, use very basic symbols.
13. AVOID complex LaTeX expressions that children might find difficult to understand.

Return ONLY a valid JSON object in the following format (do not include any explanation or markdown):

{{
  "questions": [
    {{
      "question": "string",
      "answer": "number",
      "difficulty": 1
    }},
    ...
  ]
}}

Current timestamp: {now_str}
"""

            # 使用直接格式化的f-string，避免使用.format()方法
            # 这样已经把now_str嵌入字符串中，不需要额外的格式化
            formatted_prompt = all_questions_prompt

            # 发送单一请求
            logger.info("发送单一请求生成全部6道题目")
            response = await asyncio.to_thread(
                openai.chat.completions.create,
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": "You are a math teacher creating questions for 6th grade students in an Advanced Learning Program, with the final question being competition level. Please return results in JSON format."},
                    {"role": "user", "content": formatted_prompt}
                ],
                temperature=1.2
            )
            
            # 解析题目
            logger.info(f"[DEBUG] OpenAI response: {response.choices[0].message.content}")
            try:
                result = json.loads(response.choices[0].message.content)
            except json.JSONDecodeError as e:
                logger.error(f"OpenAI返回内容无法解析为JSON: {response.choices[0].message.content}")
                raise ValueError("OpenAI返回内容不是严格的JSON格式，请检查prompt或网络响应。原始内容已写入日志。")
            all_questions = result.get("questions", [])
            logger.info(f"[DEBUG] Generated questions count: {len(all_questions)}")
            
            # 确保生成了足够的题目
            if len(all_questions) < 6:
                error_msg = f"只生成了{len(all_questions)}题，少于要求的6题"
                logger.error(error_msg)
                raise ValueError(error_msg)
                
            # 转换为我们的数据结构
            for q in all_questions:
                difficulty = q.get("difficulty")
                logger.debug(f"从GPT获取题目：问题={q['question'][:30]}...，难度={difficulty}")
                
                question_obj = {
                    "question": q["question"],
                    "answer": q["answer"],
                    "explanation": "",  # 不生成解释
                    "difficulty": difficulty,  # 直接使用GPT返回的难度，不设默认值
                    "is_correct": None
                }
                self.questions.append(question_obj)
                
            logger.info(f"[DEBUG] total questions to insert: {len(self.questions)}")
            
            # 缓存生成的题目
            today = datetime.date.today().strftime("%Y-%m-%d")
            await self.db.clear_today_gpt_questions()
            c = self.db.conn.cursor()
            self.db.conn.execute("BEGIN TRANSACTION")
            
            # 只插入前6道题
            for q in self.questions[:6]:                
                # 确保difficulty是整数值
                difficulty = q["difficulty"]
                if difficulty is None:
                    logger.warning(f"题目缺少难度值，设为默认值2: {q['question'][:30]}...")
                    difficulty = 2
                try:
                    difficulty = int(difficulty)
                except (ValueError, TypeError):
                    logger.warning(f"难度值转换整数失败，使用默认值2: {difficulty}")
                    difficulty = 2
                # 标准化题目文本，防止后续查找不一致
                # 同时保留原始题目文本以便显示
                std_question = q["question"].strip().replace('\n', '').replace(' ', '')
                original_question = q["question"].strip()  # 保留原始格式，只去除前后空白
                logger.info(f"[DEBUG] 写入题目: {q['question'][:30]}..., 答案: {q['answer']}, 难度: {difficulty}")
                
                # 同时保存原始题目和标准化题目到数据库
                # 使用question字段存储原始题目，使用std_question字段进行查重
                c.execute(
                    """INSERT INTO math_exercises 
                        (date, question, std_question, answer, is_correct, reward_minutes, explanation, is_gpt, difficulty) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (today, original_question, std_question, q["answer"], None, None, "", 1, difficulty)
                )
            self.db.conn.commit()
            # 检查并清理多余题目，只保留最新6道
            c.execute("SELECT id FROM math_exercises WHERE date=? AND is_gpt=1 ORDER BY id DESC", (today,))
            rows = c.fetchall()
            if len(rows) > 6:
                for row in rows[6:]:
                    c.execute("DELETE FROM math_exercises WHERE id=?", (row[0],))
                self.db.conn.commit()
            
            logger.info(f"[DEBUG] 已写入数据库题目数: {len(self.questions)}")
            self.current_index = 0
            return True
            
        except Exception as e:
            logger.error(f"生成题目时出错: {e}")
            self.api_error = f"生成题目时出错: {str(e)}"
            raise
    
    def get_current_question(self):
        """获取当前问题"""
        if not self.questions or self.current_index >= len(self.questions):
            return None
        return self.questions[self.current_index]["question"]
    
    def get_current_answer(self):
        """获取当前问题的标准答案"""
        if not self.questions or self.current_index >= len(self.questions):
            return "（无标准答案）"
        return self.questions[self.current_index]["answer"]
    
    def get_current_explanation(self):
        """获取当前问题的解释"""
        if not self.questions or self.current_index >= len(self.questions):
            return "（无解释）"
        return self.questions[self.current_index]["explanation"]
        
    def next_question(self):
        """移动到下一个问题"""
        if self.current_index < len(self.questions) - 1:
            self.current_index += 1
            return self.get_current_question()
        return None
        
    async def get_completed_count(self):
        """获取今天已完成的题目数量"""
        exercises = await self.db.get_today_math_exercises()
        # 只计算 is_correct 不为 NULL 的记录
        completed = sum(1 for ex in exercises if ex[4] is not None)  # ex[4] 是 is_correct 字段
        return completed
    
    async def check_answer_async(self, question_index, user_answer):
        """异步检查答案 - 简化版"""
        if question_index >= len(self.questions):
            raise ValueError("问题索引超出范围")
        
        question_obj = self.questions[question_index]
        question = question_obj["question"]
        standard_answer = question_obj["answer"]
        difficulty = question_obj["difficulty"]
        
        if not standard_answer:
            raise ValueError("无法获取标准答案")
        
        # 清理答案中的空格
        user_answer = str(user_answer)
        standard_answer = str(standard_answer)
        user_answer = re.sub(r'\s+', '', user_answer)
        standard_answer = re.sub(r'\s+', '', standard_answer)
        
        # 尝试直接数值比较
        try:
            user_num = float(user_answer)
            standard_num = float(standard_answer)
            is_correct = abs(user_num - standard_num) < 0.01
            
            # 根据难度确定奖励分钟数
            reward = MATH_DIFFICULTY_REWARDS.get(difficulty, MATH_REWARD_PER_QUESTION) if is_correct else 0
            logger.info(f"答案检查：难度={difficulty}, 奖励={reward}分钟")
            
            # 更新当前问题对象
            question_obj["is_correct"] = is_correct
            
            # 添加到数据库
            await self._add_exercise_result(question, user_answer, is_correct, reward)
            
            # 如果答案错误，获取解释
            explanation = ""
            if not is_correct:
                explanation = await self._get_explanation(question, user_answer, standard_answer)
                question_obj["explanation"] = explanation
                
            return is_correct, explanation
        
        except ValueError:
            # 数值比较失败，使用GPT检查
            return await self._check_with_gpt(question_obj, user_answer)

    async def _check_with_gpt(self, question_obj, user_answer):
        """使用GPT检查答案 - 分离出的辅助方法"""
        question = question_obj["question"]
        standard_answer = question_obj["answer"]
        difficulty = question_obj["difficulty"]
        
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
            temperature=1.2
        )
        
        try:
            result = json.loads(response.choices[0].message.content)
            is_correct = result.get("is_correct", False)
            explanation = result.get("explanation", "")
            
            # 根据难度确定奖励分钟数
            reward = MATH_DIFFICULTY_REWARDS.get(difficulty, MATH_REWARD_PER_QUESTION) if is_correct else 0
            
            # 更新当前问题对象
            question_obj["is_correct"] = is_correct
            
            # 添加到数据库
            await self._add_exercise_result(question, user_answer, is_correct, reward)
            
            # 如果答案错误，更新解释
            if not is_correct:
                question_obj["explanation"] = explanation
                
            return is_correct, explanation
        except json.JSONDecodeError:
            logger.error(f"GPT返回的不是有效的JSON格式: {response.choices[0].message.content}")
            raise ValueError("无法解析GPT的响应")

    async def _add_exercise_result(self, question, answer, is_correct, reward_minutes):
        """添加练习结果到数据库 - 简化数据库操作，并同步奖励到本周extra_minutes"""
        # 获取当前问题的难度和解释
        difficulty = None
        explanation = ""
        for q in self.questions:
            if q["question"] == question:
                difficulty = q["difficulty"]
                explanation = q.get("explanation", "")
                logger.debug(f"提交答案记录，题目难度为 {difficulty}")
                break
        await asyncio.to_thread(
            self.db.add_math_exercise,
            question,
            answer,
            is_correct,
            reward_minutes,
            explanation,
            1,  # is_gpt=1
            difficulty
        )
        # 如果答对且有奖励，自动同步到本周extra_minutes
        if is_correct and reward_minutes > 0:
            today = datetime.date.today()
            week_start = get_week_start(today).strftime("%Y-%m-%d")
            # 获取当前extra_minutes
            _, current_extra = await self.db.get_week_total(week_start)
            new_extra = current_extra + reward_minutes
            await self.db.add_weekly_extra_time(week_start, new_extra)
        
    # 兼容方法 - 调用异步版本
    def check_answer(self, question_index, user_answer, callback=None):
        if callback:
            async def _run_and_callback():
                try:
                    is_correct, explanation = await self.check_answer_async(question_index, user_answer)
                    callback(True, is_correct, explanation, None)
                except Exception as e:
                    callback(False, False, None, str(e))
            return asyncio.create_task(_run_and_callback())

    async def _get_explanation(self, question, user_answer, standard_answer):
        """获取解释 - 简化版"""
        # 检查缓存
        cached = await self.db.get_cached_explanation(question, user_answer)
        if cached:
            return cached
        try:
            # 使用OpenAI API获取解释
            response = await asyncio.to_thread(
                openai.chat.completions.create,
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": "You are a math teacher. Please explain the student's answer and give a complete correct solution process. All in English."},
                    {"role": "user", "content": f"Question: {question}\n\nStudent's answer: {user_answer}\n\nCorrect answer: {standard_answer}\n\nPlease explain why the student's answer is wrong and provide a complete correct solution process."}
                ],
                temperature=1.2
            )
            
            explanation = response.choices[0].message.content
            await self.db.cache_explanation(question, user_answer, explanation)
            return explanation
        except Exception as e:
            logger.error(f"获取解释时出错: {str(e)}")
            return f"无法获取解释: {str(e)}"
    
    # 兼容方法 - 获取错误答案的解释
    def get_explanation(self, question, user_answer, callback=None):
        """兼容性方法 - 获取错误答案的解释"""
        if callback:
            async def _run_and_callback():
                try:
                    explanation = await self._get_explanation(question, user_answer, "")
                    callback(True, explanation, None)
                except Exception as e:
                    callback(False, None, str(e))
                    
            return asyncio.create_task(_run_and_callback())
    
    async def get_today_reward_minutes(self):
        """获取今天通过数学练习获得的奖励分钟数"""
        exercises = await self.db.get_today_math_exercises()
        return sum(ex[5] or 0 for ex in exercises if ex[4] == 1)
    
    async def get_daily_questions(self):
        """获取今日题目 - 简化版"""
        # 检查是否已有缓存题目
        if not self.questions:
            # 如果没有题目，生成新题目
            try:
                logger.info("没有找到缓存题目，准备生成新题目")
                await self._generate_questions_async(force_regenerate=False)
            except Exception as e:
                logger.error(f"异步生成题目失败: {str(e)}")
                logger.exception("详细错误信息:")
                return []
        
        # 确保题目数量正确
        if len(self.questions) < 6:
            logger.warning(f"题目数量不足，只有{len(self.questions)}道，尝试重新生成")
            try:
                # 尝试清空并重新生成
                await self.clear_today_questions()
                await self._generate_questions_async(force_regenerate=True)
            except Exception as e:
                logger.error(f"重新生成题目失败: {str(e)}")
                logger.exception("详细错误信息:")
                
        # 记录题目难度，使用GPT返回的原始难度
        if self.questions:
            logger.info(f"GPT返回的题目难度: {[q.get('difficulty', '?') for q in self.questions]}")
            
            # 确保最后一题是难度4（竞赛级）
            if len(self.questions) >= 6 and self.questions[5]['difficulty'] != 4:
                logger.info(f"确保最后一题是竞赛级难度4")
                self.questions[5]['difficulty'] = 4
                
                # 更新数据库中最后一题的难度
                try:
                    today = datetime.date.today().strftime("%Y-%m-%d")
                    questions = await self.db.get_today_gpt_questions()
                    
                    if len(questions) >= 6:
                        question_id = questions[5][0]  # 获取最后一题的ID
                        logger.info(f"更新竞赛题ID {question_id} 的难度为4")
                        self.db.conn.execute(
                            "UPDATE math_exercises SET difficulty=? WHERE id=?",
                            (4, question_id)
                        )
                        self.db.conn.commit()
                except Exception as e:
                    logger.error(f"更新竞赛题难度时出错: {e}")
                    if hasattr(self.db, 'conn') and self.db.conn:
                        self.db.conn.rollback()
        
        # 构造返回结果 (保持与原接口兼容)
        result = []
        for q in self.questions:
            question_data = {
                'question': q['question'],
                'answer': q['answer'],
                'explanation': q.get('explanation', ''),
                'difficulty': q.get('difficulty', 2)  # 默认难度2
            }
            result.append(question_data)
            
        if not result:
            logger.error("无法获取有效题目！")
            
        return result
    
    async def clear_today_questions(self):
        """清除今天的问题缓存 - 简化版"""
        self.questions = []
        self.current_index = 0
        await self.db.clear_today_gpt_questions()
        
    def close(self):
        """关闭数据库连接"""
        self.db.close()

    async def regenerate_daily_questions_async(self):
        """异步重新生成今天的题目 - 简化版"""
        # 清除今天的题目
        await self.clear_today_questions()
        
        # 重新生成题目，强制重新生成
        return await self._generate_questions_async(force_regenerate=True)

    async def regenerate_daily_questions(self):
        """重新生成今天的题目 (兼容版本)"""
        return await self.regenerate_daily_questions_async() 