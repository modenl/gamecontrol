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
from logic.event_logger import get_event_logger

# 配置日志
logger = logging.getLogger('math_exercises')
logger.setLevel(logging.INFO)

# 只在没有处理器时添加处理器，避免重复配置
if not logger.handlers:
    # 添加控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(console_handler)

    # 添加文件处理器
    file_handler = logging.FileHandler('game_limiter.log', encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)
    
    # 防止消息传播到父logger，避免重复输出
    logger.propagate = False

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
        # 初始化事件日志记录器
        self.event_logger = get_event_logger()
        
    async def initialize(self):
        """Async initialization to be called after construction"""
        # 不在初始化时加载题目，让get_daily_questions()来处理
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
                        reward_minutes = 1.0  # 默认奖励时间
                        if len(q) > 8:
                            difficulty = q[8]  # difficulty在索引8
                        if len(q) > 5:
                            reward_minutes = q[5] if q[5] is not None else 1.0  # reward_minutes在索引5
                        
                        # 添加到题目列表，确保所有字段都有有效值
                        question_obj = {
                            "question": q[2] if q[2] else "（无题目内容）",  # 使用原始格式
                            "answer": q[3] if len(q) > 3 and q[3] else "（无答案）",
                            "explanation": q[6] if len(q) > 6 and q[6] else "（无解释）",
                            "difficulty": difficulty if difficulty is not None else 2,  # 默认难度2
                            "reward_minutes": reward_minutes,  # 添加奖励时间字段
                            "is_correct": q[4] if len(q) > 4 else None
                        }
                        self.questions.append(question_obj)
                    except Exception as e:
                        logger.error(f"添加题目到列表出错 ID={q[0] if len(q) > 0 else 'unknown'}: {e}")
                        continue
                    
                # 确保至少有10道题
                if len(self.questions) < MAX_DAILY_MATH_QUESTIONS:
                    logger.warning(f"加载题目数量不足，只有{len(self.questions)}道，应为{MAX_DAILY_MATH_QUESTIONS}道")
                    
                # 设置当前索引为第一个未回答的问题
                self.current_index = 0
                for i, q in enumerate(self.questions):
                    if q["is_correct"] is None:
                        self.current_index = i
                        break
                logger.info(f"成功加载缓存题目: {len(self.questions)}道")
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
            # 如果强制重新生成，先清理
            if force_regenerate:
                logger.info("重新生成今日数学题目")
                await self.clear_today_questions()
            
            # 直接生成新题目
            logger.info("开始生成数学题目")
            self.questions = []
            
            if not openai.api_key:
                self.api_error = "未设置OpenAI API密钥，请在.env文件中设置OPENAI_API_KEY"
                logger.error(self.api_error)
                raise ValueError(self.api_error)
                
            # 使用单一prompt生成全部10道题目
            # 添加时间戳和随机种子以确保每次生成的题目不同
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
            import random
            random_seed = random.randint(1000, 9999)
            
            # 获取已有题目用于避免重复
            existing_questions = await self.db.get_recent_gpt_questions(days=30)
            existing_topics = []
            if existing_questions:
                for q in existing_questions:
                    # 提取题目的主要关键词
                    question_text = q[2] if q[2] else ""
                    if any(keyword in question_text.lower() for keyword in 
                          ["triangle", "circle", "rectangle", "square", "polygon"]):
                        existing_topics.append("geometry")
                    elif any(keyword in question_text.lower() for keyword in 
                            ["probability", "chance", "dice", "coin", "random"]):
                        existing_topics.append("probability")
                    elif any(keyword in question_text.lower() for keyword in 
                            ["permutation", "combination", "arrange", "choose"]):
                        existing_topics.append("combinatorics")
                    elif any(keyword in question_text.lower() for keyword in 
                            ["prime", "factor", "divisible", "remainder"]):
                        existing_topics.append("number_theory")
            
            # 根据最近题目类型调整prompt以避免重复
            avoid_topics = ""
            if len(existing_topics) > 0:
                topic_counts = {topic: existing_topics.count(topic) for topic in set(existing_topics)}
                frequent_topics = [topic for topic, count in topic_counts.items() if count >= 2]
                if frequent_topics:
                    avoid_topics = f"\n- AVOID these recently used topics: {', '.join(frequent_topics)}"

            all_questions_prompt = fr"""
You are to generate 10 COMPLETELY NEW and UNIQUE AMC 8 style math questions, strictly following these requirements:

1. STYLE & CONTENT
- Authentic AMC 8 style: clear, concise, clever.
- Focus on mathematical reasoning, not mere computation.
- Use diverse problem-solving methods (e.g., working backwards, logic, pattern recognition).
- Each question tests a distinct mathematical concept—NO topic or approach repetition.
- Include AT LEAST 3 geometry questions using DIFFERENT geometric concepts.
- Geometry questions must include simple, accurate ASCII art diagrams WRAPPED IN CODE BLOCKS using ``` syntax.
- ASCII art MUST be in the format: ```\n[diagram]\n``` to ensure proper display.
- ASCII art must be GEOMETRICALLY ACCURATE and PROPERLY ALIGNED.

2. DIFFICULTY & TOPICS
- Q1-2: Level 1 (AMC8 Q1-5 style) — basic arithmetic, simple geometry, or word problems; topics must differ.
- Q3-4: Level 1 — different topics and methods from Q1-2.
- Q5-6: Level 2 (AMC8 Q6-15 style) — intermediate algebra, geometry, number theory; differ from previous questions.
- Q7-8: Level 2 — different approaches and topics than Q5-6.
- Q9: Level 3 (AMC8 Q16-20 style) — advanced multi-step reasoning.
- Q10: Level 4 (AMC8 Q21-25 style) — challenging competition-level problem.

- Topics must cover 10 different areas, including (but not limited to):
  arithmetic sequences, various geometry (triangles, circles, rectangles, angles, coordinate geometry, Pythagorean theorem),
  number theory (divisibility, primes, factors),
  probability and counting,
  algebraic thinking,
  logic puzzles,
  percentages and ratios,
  combinatorics,
  time and rate,
  statistics and data interpretation.

3. ANSWERS
- Prefer positive integers or simple fractions (e.g. 5, 12, 3/4, 7/8).
- For geometry measurements, round to 2 decimal places if necessary.
- For probability, use fractions.
- Avoid complex decimals or overly long answers.

4. REWARD MINUTES
- Assign reward minutes (0.5-5) based on actual question complexity and time needed (approximately half of solving time):
  * 0.5 minutes: Very simple calculations, basic arithmetic (1-2 min solving time)
  * 1 minute: Simple problems requiring one step (2-3 min solving time)
  * 1.5 minutes: Straightforward problems requiring two steps (3-4 min solving time)
  * 2 minutes: Moderate complexity, some reasoning (4-5 min solving time)
  * 2.5 minutes: Multi-step problems with moderate thinking (5-6 min solving time)
  * 3 minutes: Complex problems requiring significant reasoning (6-7 min solving time)
  * 4 minutes: Very challenging multi-step problems (8-9 min solving time)
  * 5 minutes: Most challenging competition-level problems (10+ min solving time)
- Consider both conceptual difficulty and actual time investment required
- Reward should be approximately half of the expected solving time
- Use decimal values (0.5, 1.5, 2.5, etc.) for more precise reward allocation

5. FORMATTING
- IMPORTANT: Please wrap ALL math expressions using $$...$$ (even inline) to ensure consistent LaTeX rendering.
- Do NOT use \\( ... \\) or \\[ ... \\] formats - use ONLY $$...$$ for all math.
- Plain text expressions allowed for simple cases (e.g., x^2, x/y) when no special symbols needed.
- Questions limited to 1-3 sentences, with concrete numbers and realistic scenarios.
- Geometry ASCII art must:
  * Use ONLY these characters: |, -, /, \\, +, spaces (no other symbols).
  * Label vertices logically (A, B, C, D clockwise or counterclockwise).
  * Show points on edges accurately (e.g., A+---E---+B).
  * Keep diagrams simple but GEOMETRICALLY ACCURATE.
  * MUST be wrapped in ``` code blocks within the question text.
  * For rectangles: ALL sides must be EQUAL LENGTH in ASCII (same number of - and | characters).
  * For triangles: Use proper angles and proportions, vertices should align correctly.
  * For circles: Use simple representation like O or describe as "circle with center O".
  * CRITICAL: Count characters carefully to ensure symmetry and accuracy.
  * RECTANGLE EXAMPLES (must be symmetric):
    - Small: "```\\nA+----+B\\n|    |\\n|    |\\nD+----+C\\n```" (4 chars wide, 2 tall)
    - Medium: "```\\nA+--------+B\\n|        |\\n|        |\\n|        |\\nD+--------+C\\n```" (8 chars wide, 3 tall)
  * TRIANGLE EXAMPLES (vertices must align):
    - Isosceles: "```\\n    A\\n   / \\\\\\n  /   \\\\\\n /     \\\\\\nB+-----+C\\n```"
    - Right triangle: "```\\nA+\\n|\\\\\\n| \\\\\\n|  \\\\\\nB+--+C\\n```"
    - With height: "```\\n    A\\n   /|\\\\\\n  / | \\\\\\n /  |  \\\\\\nB+--D--+C\\n```" (D is foot of altitude)
  * SPECIAL SHAPES:
    - Square: "```\\nA+----+B\\n|    |\\n|    |\\n|    |\\nD+----+C\\n```" (equal width and height)
    - Parallelogram: "```\\n  A+----+B\\n /    /\\n/    /\\nD+----+C\\n```"
  * MEASUREMENT RULES:
    - If problem states "AB = 8 cm, BC = 3 cm", make ASCII reflect this ratio
    - Use proportional character counts: 8:3 ratio ≈ 8 chars : 3 chars
    - Always count characters to ensure accuracy

CRITICAL JSON OUTPUT RULES:
- Return ONLY a single valid JSON object, no markdown, no code block, no explanation, no comments.
- Each question object MUST have ALL of these fields: "question", "answer", "difficulty", "reward_minutes".
- All string values MUST be strictly JSON-escaped (e.g. newlines as \\n, quotes as \", backslashes as \\\\).
- DO NOT use any markdown formatting, DO NOT wrap the output in ``` or ```json.
- DO NOT add any extra text before or after the JSON.
- DO NOT use extra or missing commas, or trailing commas.
- DO NOT use extra quotes around the question object or any field.
- DO NOT omit any field, even if empty.
- DO NOT use markdown or LaTeX code block syntax.
- Example of a valid output (note: this is the ONLY thing you should return):

{{
  "questions": [
    {{
      "question": "A farmer has 8 chickens and 12 cows. How many animals does he have in total?",
      "answer": "20",
      "difficulty": 1,
      "reward_minutes": 1
    }},
    {{
      "question": "In triangle PQR, angle P is 40° and angle Q is 75°. What is the measure of angle R in degrees?\\n\\n```\\nP+---+Q\\n|   /|\\n|  / |\\n| /  |\\nR----+\\n```",
      "answer": "65",
      "difficulty": 1,
                                  "reward_minutes": 1.0
    }}
    // ...8 more
  ]
}}

REMEMBER: Output ONLY the JSON, nothing else. If you are unsure, output nothing.

Randomization seed: {random_seed}
Timestamp: {now_str}
"""

            # 使用直接格式化的f-string，避免使用.format()方法
            formatted_prompt = all_questions_prompt

            # 发送请求生成题目
            logger.info("正在生成10道AMC8风格数学题目")
            try:
                # 添加超时设置，防止请求挂起
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                openai.chat.completions.create,
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": "You are an expert AMC8 mathematics competition problem writer. Create diverse, engaging problems that test mathematical reasoning and problem-solving skills. Ensure maximum variety in topics and approaches."},
                    {"role": "user", "content": formatted_prompt}
                ],
                temperature=1.3,  # 增加随机性
                top_p=0.9,       # 增加创造性
                frequency_penalty=0.3,  # 减少重复
                        presence_penalty=0.2,   # 鼓励新颖性
                        response_format={"type": "json_object"},  # 强制返回JSON格式
                        timeout=60  # 设置60秒超时
                    ),
                    timeout=90  # 总超时时间90秒
                )
                logger.info("OpenAI API请求成功完成")
            except asyncio.TimeoutError:
                logger.error("OpenAI API请求超时")
                raise ValueError("OpenAI API请求超时，请检查网络连接")
            except Exception as api_error:
                logger.error(f"OpenAI API请求失败: {str(api_error)}")
                logger.exception("详细API错误信息:")
                raise ValueError(f"OpenAI API请求失败: {str(api_error)}")
            
            # 解析题目
            raw_content = response.choices[0].message.content
            
            try:
                # 解析JSON响应
                result = json.loads(raw_content)
            except json.JSONDecodeError as e:
                logger.error(f"JSON解析失败: {e}")
                logger.error(f"响应内容: {raw_content}")
                
                # 记录详细的JSON解析错误信息
                json_error_details = {
                    "error_type": "JSONDecodeError",
                    "error_message": str(e),
                    "response_length": len(raw_content),
                    "response_preview": raw_content[:500] if raw_content else "Empty response",
                    "timestamp": datetime.datetime.now().isoformat()
                }
                logger.error(f"JSON解析失败详情: {json_error_details}")
                
                # 抛出JSON解析错误
                raise ValueError(f"OpenAI返回的不是有效的JSON格式: {str(e)}")
            all_questions = result.get("questions", [])
            
            # 确保生成了足够的题目
            if len(all_questions) < 10:
                error_msg = f"只生成了{len(all_questions)}题，少于要求的10题"
                logger.error(error_msg)
                raise ValueError(error_msg)
                
            # 转换为我们的数据结构
            for q in all_questions:
                difficulty = q.get("difficulty")
                reward_minutes = q.get("reward_minutes", 1.0)  # 默认1分钟
                
                # 后处理题目文本，转换LaTeX格式
                processed_question = self._postprocess_question_text(q["question"])
                processed_answer = self._postprocess_question_text(q["answer"])
                
                question_obj = {
                    "question": processed_question,
                    "answer": processed_answer,
                    "explanation": "",  # 不生成解释
                    "difficulty": difficulty,  # 直接使用GPT返回的难度，不设默认值
                    "reward_minutes": reward_minutes,  # 使用GPT指定的奖励时间
                    "is_correct": None
                }
                self.questions.append(question_obj)
            
            # 缓存生成的题目
            today = datetime.date.today().strftime("%Y-%m-%d")
            await self.db.clear_today_gpt_questions()
            c = self.db.conn.cursor()
            self.db.conn.execute("BEGIN TRANSACTION")
            
            # 只插入前10道题
            for q in self.questions[:10]:                
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
                
                # 同时保存原始题目和标准化题目到数据库
                # 使用question字段存储原始题目，使用std_question字段进行查重
                c.execute(
                    """INSERT INTO math_exercises 
                        (date, question, std_question, answer, is_correct, reward_minutes, explanation, is_gpt, difficulty) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (today, original_question, std_question, q["answer"], None, q.get("reward_minutes", 1.0), "", 1, difficulty)
                )
            self.db.conn.commit()
            # 检查并清理多余题目，只保留最新10道
            c.execute("SELECT id FROM math_exercises WHERE date=? AND is_gpt=1 ORDER BY id DESC", (today,))
            rows = c.fetchall()
            if len(rows) > 10:
                for row in rows[10:]:
                    c.execute("DELETE FROM math_exercises WHERE id=?", (row[0],))
                self.db.conn.commit()
            
            logger.info(f"成功生成并保存{len(self.questions)}道数学题目")
            self.current_index = 0
            return True
            
        except Exception as e:
            logger.error(f"生成题目时出错: {e}")
            logger.exception("详细错误信息:")
            
            # 记录错误信息
            logger.error(f"题目生成失败: {type(e).__name__}: {str(e)}")
            
            # 不使用备用题目，直接抛出错误让调用者处理
            self.api_error = f"生成题目时出错: {str(e)}"
            raise
        finally:
            pass  # 不再需要锁管理
    
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
        reward_minutes = question_obj.get("reward_minutes", 1.0)  # 使用GPT指定的奖励时间，默认1分钟
        
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
            
            # 根据答案大小确定容差
            if standard_num == 0:
                tolerance = 0.01
            elif abs(standard_num) < 1:
                tolerance = 0.01  # 小数用固定小容差
            elif abs(standard_num) < 100:
                tolerance = max(0.01, abs(standard_num) * 0.02)  # 2%相对误差，但至少0.01
            else:
                tolerance = abs(standard_num) * 0.01  # 大数用1%相对误差
            
            is_correct = abs(user_num - standard_num) <= tolerance
            
            # 使用GPT指定的奖励时间
            reward = reward_minutes if is_correct else 0
            
            # 更新当前问题对象
            question_obj["is_correct"] = is_correct
            
            # 记录题目回答事件
            self.event_logger.log_question_answered(
                question_type="数学",
                user_answer=user_answer,
                correct_answer=standard_answer,
                is_correct=is_correct,
                attempt_count=1
            )
            
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
        """使用GPT检查答案 - 改进错误处理"""
        question = question_obj["question"]
        standard_answer = question_obj["answer"]
        reward_minutes = question_obj.get("reward_minutes", 1.0)
        
        prompt = f"""Please check if the student's answer is correct.

Question: {question}
Standard Answer: {standard_answer}
Student's Answer: {user_answer}

Please return the result in this exact JSON format:
{{
    "is_correct": true/false,
    "explanation": "explanation text here"
}}

If the answer is correct, set is_correct to true.
If the answer is incorrect, set is_correct to false and provide a detailed explanation of why it's wrong and show the correct solution process.

IMPORTANT: Please wrap ALL math expressions using $$...$$ (even inline) to ensure consistent LaTeX rendering.
"""

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                openai.chat.completions.create,
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": "You are a math teacher responsible for checking student answers. Please return results in JSON format."},
                    {"role": "user", "content": prompt}
                ],
                    temperature=1.2,
                    response_format={"type": "json_object"},  # 强制返回JSON格式
                    timeout=30  # 设置30秒超时
                ),
                timeout=45  # 总超时时间45秒
            )
            
            # 检查响应是否有效
            if not response or not response.choices or not response.choices[0].message:
                logger.error("GPT API返回了无效的响应结构")
                raise ValueError("GPT API响应无效")
                
            content = response.choices[0].message.content
            if not content or content.strip() == "":
                logger.error("GPT API返回了空内容")
                raise ValueError("GPT API返回空内容")
            
            logger.debug(f"GPT原始响应: {content}")
            
            # 由于使用了response_format={"type": "json_object"}，应该直接是有效的JSON
            try:
                result = json.loads(content)
                is_correct = result.get("is_correct", False)
                explanation = result.get("explanation", "")
                
                # 使用GPT指定的奖励时间
                reward = reward_minutes if is_correct else 0
                
                # 更新当前问题对象
                question_obj["is_correct"] = is_correct
                
                # 记录题目回答事件
                self.event_logger.log_question_answered(
                    question_type="数学",
                    user_answer=user_answer,
                    correct_answer=standard_answer,
                    is_correct=is_correct,
                    attempt_count=1
                )
                
                # 添加到数据库
                await self._add_exercise_result(question, user_answer, is_correct, reward)
                
                # 如果答案错误，更新解释
                if not is_correct:
                    question_obj["explanation"] = explanation
                    
                return is_correct, explanation
                
            except json.JSONDecodeError as e:
                logger.error(f"GPT返回的不是有效的JSON格式: {content}")
                logger.error(f"JSON解析错误: {str(e)}")
                
                # 尝试提取有用信息作为备用方案
                content_lower = content.lower()
                if "is_correct\": true" in content_lower or "correct" in content_lower:
                    # 可能是正确答案
                    is_correct = True
                    explanation = "答案正确，但GPT响应格式异常"
                else:
                    # 可能是错误答案
                    is_correct = False
                    explanation = f"GPT响应格式异常，无法解析答案正确性。原始响应: {content[:200]}..."
                
                # 使用备用方案记录结果
                reward = reward_minutes if is_correct else 0
                question_obj["is_correct"] = is_correct
                await self._add_exercise_result(question, user_answer, is_correct, reward)
                
                if not is_correct:
                    question_obj["explanation"] = explanation
                    
                return is_correct, explanation
                
        except Exception as e:
            logger.error(f"调用GPT API时出错: {str(e)}")
            logger.exception("详细错误信息:")
            
            # 网络错误或其他API错误的备用方案
            # 简单的字符串比较作为备用
            try:
                user_answer_clean = str(user_answer).strip().lower()
                standard_answer_clean = str(standard_answer).strip().lower()
                
                # 简单的答案比较
                is_correct = user_answer_clean == standard_answer_clean
                explanation = f"由于网络问题无法使用AI检查，采用简单字符串匹配。标准答案: {standard_answer}"
                
                reward = reward_minutes if is_correct else 0
                question_obj["is_correct"] = is_correct
                await self._add_exercise_result(question, user_answer, is_correct, reward)
                
                if not is_correct:
                    question_obj["explanation"] = explanation
                    
                return is_correct, explanation
                
            except Exception as fallback_error:
                logger.error(f"备用方案也失败了: {str(fallback_error)}")
                # 最后的备用方案：标记为错误，不给奖励
                is_correct = False
                explanation = f"检查答案时发生错误: {str(e)}"
                
                question_obj["is_correct"] = is_correct
                await self._add_exercise_result(question, user_answer, is_correct, 0)
                question_obj["explanation"] = explanation
                
                return is_correct, explanation

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
            response = await asyncio.wait_for(
                asyncio.to_thread(
                openai.chat.completions.create,
                model="gpt-4.1-mini",
                messages=[
                        {"role": "system", "content": "You are a math teacher. Please explain the student's answer and give a complete correct solution process. All in English. Return your response as a JSON object with an 'explanation' field. IMPORTANT: Please wrap ALL math expressions using $$...$$ (even inline) to ensure consistent LaTeX rendering."},
                    {"role": "user", "content": f"Question: {question}\n\nStudent's answer: {user_answer}\n\nCorrect answer: {standard_answer}\n\nPlease explain why the student's answer is wrong and provide a complete correct solution process."}
                ],
                    temperature=1.2,
                    response_format={"type": "json_object"},  # 强制返回JSON格式
                    timeout=30  # 设置30秒超时
                ),
                timeout=45  # 总超时时间45秒
            )
            
            content = response.choices[0].message.content
            try:
                # 解析JSON响应
                result = json.loads(content)
                explanation = result.get("explanation", content)  # 如果没有explanation字段，使用原始内容
            except json.JSONDecodeError:
                # 如果JSON解析失败，使用原始内容
                explanation = content
            
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
            # 如果没有题目，先尝试从数据库加载
            try:
                logger.info("检查数据库中是否已有今天的题目")
                today_questions = await self.db.get_today_gpt_questions()
                if today_questions and len(today_questions) >= 10:
                    logger.info(f"从数据库加载到{len(today_questions)}道题目")
                    self.questions = []
                    for q in today_questions:
                        difficulty = q[8] if len(q) > 8 and q[8] is not None else None
                        reward_minutes = q[5] if len(q) > 5 and q[5] is not None else 1.0
                        question_obj = {
                            "question": q[2],
                            "answer": q[3] if len(q) > 3 and q[3] else "（无答案）",
                            "explanation": q[6] if len(q) > 6 and q[6] else "",
                            "difficulty": difficulty,
                            "reward_minutes": reward_minutes,
                            "is_correct": q[4]
                        }
                        self.questions.append(question_obj)
                    self.current_index = 0
                    for i, q in enumerate(self.questions):
                        if q["is_correct"] is None:
                            self.current_index = i
                            break
                    logger.info(f"成功从数据库加载{len(self.questions)}道题目")
                else:
                    # 数据库中没有足够的题目，需要生成新题目
                    logger.info("数据库中没有足够题目，开始生成新题目")
                    await self._generate_questions_async(force_regenerate=True)
            except Exception as e:
                logger.error(f"加载或生成题目失败: {str(e)}")
                logger.exception("详细错误信息:")
                return []
                
        # 确保题目难度设置正确
        if self.questions:
            # 确保最后一题是难度4（竞赛级）
            if len(self.questions) >= 10 and self.questions[9]['difficulty'] != 4:
                self.questions[9]['difficulty'] = 4
                
                # 更新数据库中最后一题的难度
                try:
                    today = datetime.date.today().strftime("%Y-%m-%d")
                    questions = await self.db.get_today_gpt_questions()
                    
                    if len(questions) >= 10:
                        question_id = questions[9][0]  # 获取最后一题的ID
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
                'difficulty': q.get('difficulty', 2),  # 默认难度2
                'reward_minutes': q.get('reward_minutes', 1.0)  # 添加奖励分钟数字段
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
        """异步重新生成今天的题目"""
        logger.info("开始重新生成今日数学题目")
        return await self._generate_questions_async(force_regenerate=True)

    async def regenerate_daily_questions(self):
        """重新生成今天的题目 (兼容版本)"""
        return await self.regenerate_daily_questions_async()


    
    def _postprocess_question_text(self, question_text):
        """后处理题目文本，转换LaTeX格式为KaTeX支持的格式"""
        if not question_text:
            return question_text
        
        # 将LaTeX格式转换为KaTeX支持的格式
        text = question_text
        # 将 \( ... \) 转换为 $ ... $
        text = re.sub(r'\\?\\\(([^)]+)\\?\\\)', r'$\1$', text)
        # 将 \[ ... \] 转换为 $$ ... $$
        text = re.sub(r'\\?\\\[([^\]]+)\\?\\\]', r'$$\1$$', text)
        
        return text




    


 