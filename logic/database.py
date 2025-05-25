import sqlite3
import datetime
import hashlib
import logging
import asyncio
from logic.constants import (
    DB_FILE, 
    MAX_WEEKLY_LIMIT, 
    MATH_REWARD_PER_QUESTION, 
    MAX_DAILY_MATH_QUESTIONS
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # 输出到控制台
        logging.FileHandler('game_limiter.log', encoding='utf-8')  # 同时保存到文件
    ]
)
logger = logging.getLogger('database')

def sha256(s): 
    return hashlib.sha256(s.encode('utf-8')).hexdigest()

def get_week_start(date=None):
    """获取周日的日期（每周从周日凌晨0点开始）"""
    d = date or datetime.date.today()
    # weekday(): 周一=0, 周二=1, ..., 周日=6
    # 我们希望周日为一周的开始，所以需要调整计算
    days_since_sunday = (d.weekday() + 1) % 7
    return d - datetime.timedelta(days=days_since_sunday)

class Database:
    def __init__(self):
        """初始化数据库连接"""
        self.conn = None
        self.cache = {}
        self.cache_timeout = {}
        self.cache_max_age = 60  # 缓存过期时间(秒)
        self._lock = asyncio.Lock()
        self.connect()
        self.create_tables()
        self.check_db_version()

    def connect(self):
        """连接到数据库"""
        try:
            # 设置超时和重试
            self.conn = sqlite3.connect(
                DB_FILE,
                timeout=20,  # 设置超时时间为20秒
                check_same_thread=False  # 允许多线程访问
            )
            self.conn.row_factory = sqlite3.Row
        except sqlite3.Error as e:
            logger.error(f"连接数据库失败: {e}")
            raise Exception(f"连接数据库失败: {e}")
            
    def create_tables(self):
        """创建数据库表"""
        try:
            c = self.conn.cursor()
            
            # 创建游戏Session表
            c.execute('''
                CREATE TABLE IF NOT EXISTS game_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    duration REAL,
                    game TEXT,
                    note TEXT
                )
            ''')
            
            # 创建每周额外时间表
            c.execute('''
                CREATE TABLE IF NOT EXISTS weekly_extra_time (
                    week_start TEXT PRIMARY KEY,
                    extra_minutes INTEGER DEFAULT 0
                )
            ''')
            
            # 创建数据库版本表
            c.execute('''
                CREATE TABLE IF NOT EXISTS db_version (
                    version INTEGER PRIMARY KEY
                )
            ''')
            
            # 如果数据库版本表为空，初始化为版本0
            c.execute("SELECT count(*) FROM db_version")
            if c.fetchone()[0] == 0:
                try:
                    c.execute("INSERT INTO db_version VALUES (0)")
                    self.conn.commit()
                except sqlite3.IntegrityError:
                    # 如果插入失败，可能是并发操作，忽略错误
                    self.conn.rollback()
                    logger.info("db_version表已被其他进程初始化")
            
            # 创建数学练习表
            c.execute('''
                CREATE TABLE IF NOT EXISTS math_exercises (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    question TEXT NOT NULL,
                    answer TEXT,
                    is_correct INTEGER,
                    reward_minutes INTEGER,
                    explanation TEXT,
                    is_gpt INTEGER DEFAULT 0
                )
            ''')
            
            # 创建数学练习解释缓存表
            c.execute('''
                CREATE TABLE IF NOT EXISTS math_explanations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    explanation TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            ''')
            
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"创建数据库表失败: {e}")
            # 尝试重新连接
            try:
                self.conn.close()
                time.sleep(1)  # 等待1秒
                self.connect()
                self.create_tables()
            except Exception as retry_error:
                raise Exception(f"创建数据库表失败: {e}")

    def check_db_version(self):
        """检查数据库版本并执行必要的升级"""
        try:
            c = self.conn.cursor()
            
            # 获取当前版本
            try:
                c.execute("SELECT version FROM db_version")
                result = c.fetchone()
                current_version = result[0] if result else 0
            except sqlite3.Error:
                # 可能表不存在或有结构问题
                logger.warning("db_version表可能存在问题，尝试重建")
                try:
                    c.execute("DROP TABLE IF EXISTS db_version")
                    c.execute("CREATE TABLE db_version (version INTEGER PRIMARY KEY)")
                    c.execute("INSERT INTO db_version VALUES (0)")
                    self.conn.commit()
                    current_version = 0
                except sqlite3.Error as e:
                    logger.error(f"重建版本表失败: {e}")
                    return
            
            # 定义升级脚本
            upgrades = {
                0: self._upgrade_to_v1,
                1: self._upgrade_to_v2,
                2: self._upgrade_to_v3,
                3: self._upgrade_to_v4,
                4: self._upgrade_to_v5,
                5: self._upgrade_to_v6,
                # 添加新的升级版本
            }
            
            # 执行所有需要的升级
            while current_version in upgrades:
                try:
                    logger.info(f"正在升级数据库到版本 {current_version + 1}")
                    
                    # 开始事务
                    self.conn.execute("BEGIN TRANSACTION")
                    
                    # 执行升级
                    upgrades[current_version]()
                    next_version = current_version + 1
                    
                    # 更新版本号 - 使用REPLACE INTO来避免UNIQUE约束错误
                    c.execute("REPLACE INTO db_version (version) VALUES (?)", (next_version,))
                    
                    # 提交事务
                    self.conn.commit()
                    logger.info(f"成功升级到版本 {next_version}")
                    
                    # 更新当前版本
                    current_version = next_version
                    
                except sqlite3.Error as e:
                    logger.error(f"数据库升级SQL错误: 升级到版本 {current_version + 1} 时出错：{str(e)}")
                    self.conn.rollback()
                    break
                except Exception as e:
                    logger.error(f"数据库升级错误: 升级到版本 {current_version + 1} 时出错：{str(e)}")
                    self.conn.rollback()
                    break
        except sqlite3.Error as e:
            logger.error(f"检查数据库版本错误: {e}")
            raise Exception(f"检查数据库版本失败: {e}")

    def _upgrade_to_v1(self):
        """升级到版本1：添加游戏名称字段"""
        c = self.conn.cursor()
        # 检查game列是否存在
        c.execute("PRAGMA table_info(game_sessions)")
        columns = [column[1] for column in c.fetchall()]
        
        if 'game' not in columns:
            # 添加game列
            c.execute("ALTER TABLE game_sessions ADD COLUMN game TEXT DEFAULT 'Minecraft'")
            self.conn.commit()

    def _upgrade_to_v2(self):
        """升级到版本2：添加备注字段"""
        c = self.conn.cursor()
        # 检查note列是否存在
        c.execute("PRAGMA table_info(game_sessions)")
        columns = [column[1] for column in c.fetchall()]
        
        if 'note' not in columns:
            # 添加note列
            c.execute("ALTER TABLE game_sessions ADD COLUMN note TEXT")
            self.conn.commit()

    def _upgrade_to_v3(self):
        """升级到版本3：确保数学习题表有答案和解释字段"""
        c = self.conn.cursor()
        
        # 检查math_exercises表的字段
        c.execute("PRAGMA table_info(math_exercises)")
        columns = {column[1]: column for column in c.fetchall()}
        
        # 检查并添加缺失的字段
        if 'answer' not in columns:
            c.execute("ALTER TABLE math_exercises ADD COLUMN answer TEXT")
            
        if 'explanation' not in columns:
            c.execute("ALTER TABLE math_exercises ADD COLUMN explanation TEXT")
            
        # 修改现有的GPT题目记录，确保是_gpt标记正确
        c.execute("UPDATE math_exercises SET is_gpt = 1 WHERE is_gpt IS NULL AND is_correct IS NULL")
        
        self.conn.commit()
        logger.info("成功升级数据库到版本3：添加数学习题答案和解释字段")

    def _upgrade_to_v4(self):
        """升级到版本4：添加难度字段，用于计算奖励分钟数"""
        c = self.conn.cursor()
        
        # 检查math_exercises表的字段
        c.execute("PRAGMA table_info(math_exercises)")
        columns = {column[1]: column for column in c.fetchall()}
        
        # 检查并添加难度字段
        if 'difficulty' not in columns:
            c.execute("ALTER TABLE math_exercises ADD COLUMN difficulty INTEGER DEFAULT 2")
            
        # 为已有记录设置默认难度级别，前5题默认难度2，最后一题(竞赛题)难度4
        c.execute("""
            UPDATE math_exercises 
            SET difficulty = 
                CASE 
                    WHEN id % 6 = 0 OR id = (
                        SELECT MAX(id) FROM math_exercises WHERE date = math_exercises.date
                    ) THEN 4
                    ELSE 2
                END
            WHERE difficulty IS NULL
        """)
        
        self.conn.commit()
        logger.info("成功升级数据库到版本4：添加难度字段，用于计算奖励分钟数")

    def _upgrade_to_v5(self):
        """升级到版本5：添加std_question字段，用于标准化比较"""
        c = self.conn.cursor()
        
        # 检查是否已有std_question列
        c.execute("PRAGMA table_info(math_exercises)")
        columns = {column[1]: column for column in c.fetchall()}
        
        if 'std_question' not in columns:
            # 添加std_question列
            c.execute("ALTER TABLE math_exercises ADD COLUMN std_question TEXT")
            
            # 填充标准化题目数据
            c.execute("SELECT id, question FROM math_exercises")
            for row in c.fetchall():
                id, question = row
                std_question = question.strip().replace('\n', '').replace(' ', '')
                c.execute("UPDATE math_exercises SET std_question = ? WHERE id = ?", (std_question, id))
                
        self.conn.commit()
        logger.info("成功升级数据库到版本5：添加std_question字段，用于标准化比较")

    def _upgrade_to_v6(self):
        """升级到版本6：修改reward_minutes字段支持小数"""
        c = self.conn.cursor()
        
        # 检查当前reward_minutes字段类型
        c.execute("PRAGMA table_info(math_exercises)")
        columns = {column[1]: column for column in c.fetchall()}
        
        if 'reward_minutes' in columns:
            # SQLite中，我们需要重建表来改变字段类型
            # 首先备份数据
            c.execute("""
                CREATE TABLE math_exercises_backup AS 
                SELECT id, date, question, answer, is_correct, 
                       CAST(reward_minutes AS REAL) as reward_minutes, 
                       explanation, is_gpt, difficulty, std_question 
                FROM math_exercises
            """)
            
            # 删除原表
            c.execute("DROP TABLE math_exercises")
            
            # 重新创建表，reward_minutes使用REAL类型
            c.execute('''
                CREATE TABLE math_exercises (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    question TEXT NOT NULL,
                    answer TEXT,
                    is_correct INTEGER,
                    reward_minutes REAL,
                    explanation TEXT,
                    is_gpt INTEGER DEFAULT 0,
                    difficulty INTEGER DEFAULT 2,
                    std_question TEXT
                )
            ''')
            
            # 恢复数据
            c.execute("""
                INSERT INTO math_exercises 
                (id, date, question, answer, is_correct, reward_minutes, explanation, is_gpt, difficulty, std_question)
                SELECT id, date, question, answer, is_correct, reward_minutes, explanation, is_gpt, difficulty, std_question
                FROM math_exercises_backup
            """)
            
            # 删除备份表
            c.execute("DROP TABLE math_exercises_backup")
        
        self.conn.commit()
        logger.info("成功升级数据库到版本6：修改reward_minutes字段支持小数")

    def _get_cache_key(self, func_name, *args):
        """生成缓存键"""
        return f"{func_name}:{':'.join(str(arg) for arg in args)}"

    def _cache_result(self, cache_key, result):
        """缓存结果"""
        self.cache[cache_key] = result
        self.cache_timeout[cache_key] = datetime.datetime.now()

    def _get_cached_result(self, cache_key):
        """获取缓存结果，如果过期返回None"""
        if cache_key in self.cache:
            if (datetime.datetime.now() - self.cache_timeout[cache_key]).total_seconds() < self.cache_max_age:
                return self.cache[cache_key]
            else:
                # 清除过期缓存
                del self.cache[cache_key]
                del self.cache_timeout[cache_key]
        return None

    def _invalidate_cache(self, pattern=None):
        """清除缓存
        Args:
            pattern: 缓存键的部分字符串匹配，如果为None则清除所有缓存
        """
        if pattern is None:
            self.cache.clear()
            self.cache_timeout.clear()
        else:
            keys_to_delete = [k for k in self.cache.keys() if pattern in k]
            for k in keys_to_delete:
                del self.cache[k]
                del self.cache_timeout[k]

    async def execute_query(self, query, params=(), fetchone=False, commit=False):
        """异步执行SQL查询"""
        # 确保数据库连接有效
        if self.conn is None:
            self.reconnect()
            
        async with self._lock:
            try:
                # 在异步环境中使用同步API，使用to_thread
                result = await asyncio.to_thread(self._execute_query_sync, query, params, fetchone, commit)
                return result
            except sqlite3.Error as e:
                if commit:
                    await asyncio.to_thread(self.conn.rollback)
                logger.error(f"执行查询失败: {query}, 错误: {e}")
                raise

    def _execute_query_sync(self, query, params=(), fetchone=False, commit=False):
        """同步执行SQL查询(内部使用)"""
        c = self.conn.cursor()
        c.execute(query, params)
        
        if commit:
            self.conn.commit()
            
        if fetchone:
            return c.fetchone()
        else:
            return c.fetchall()

    async def add_session(self, start, end, duration, game_name="Minecraft", note=None):
        """添加游戏Session记录"""
        try:
            query = "INSERT INTO game_sessions (start_time, end_time, duration, game, note) VALUES (?, ?, ?, ?, ?)"
            params = (start, end, duration, game_name, note)
            result = await self.execute_query(query, params, commit=True)
            
            # 清除相关缓存
            self._invalidate_cache("get_sessions")
            self._invalidate_cache("get_week_total")
            
            return result
        except Exception as e:
            logger.error(f"添加Session记录错误: {e}")
            raise

    async def get_sessions(self, week_start=None):
        """获取Session记录"""
        cache_key = self._get_cache_key("get_sessions", week_start)
        cached = self._get_cached_result(cache_key)
        if cached:
            return cached
            
        try:
            if week_start:
                week_end = (datetime.datetime.strptime(week_start, "%Y-%m-%d") + datetime.timedelta(days=7)).strftime("%Y-%m-%d")
                query = "SELECT * FROM game_sessions WHERE start_time>=? AND start_time<? ORDER BY start_time DESC"
                params = (week_start, week_end)
            else:
                query = "SELECT * FROM game_sessions ORDER BY start_time DESC"
                params = ()
                
            result = await self.execute_query(query, params)
            self._cache_result(cache_key, result)
            return result
        except Exception as e:
            logger.error(f"获取Session记录错误: {e}")
            raise

    async def delete_session(self, session_id):
        """删除一个游戏Session记录
        
        Args:
            session_id: 要删除的Session ID
        
        Returns:
            True表示删除成功，False表示失败
        """
        try:
            query = "DELETE FROM game_sessions WHERE id = ?"
            await self.execute_query(query, (session_id,), commit=True)
            
            # 清除相关缓存
            self._invalidate_cache("get_sessions")
            self._invalidate_cache("get_week_total")
            
            logger.info(f"已删除Session记录: id={session_id}")
            return True
        except Exception as e:
            logger.error(f"删除Session记录错误: {e}")
            raise

    async def get_week_total(self, week_start):
        """获取每周总时长和额外时间"""
        cache_key = self._get_cache_key("get_week_total", week_start)
        cached = self._get_cached_result(cache_key)
        if cached:
            return cached
            
        try:
            week_end = (datetime.datetime.strptime(week_start, "%Y-%m-%d") + datetime.timedelta(days=7)).strftime("%Y-%m-%d")
            
            # 获取总时长
            query1 = "SELECT SUM(duration) FROM game_sessions WHERE start_time>=? AND start_time<?"
            sum_result = await self.execute_query(query1, (week_start, week_end), fetchone=True)
            sum_value = sum_result[0] if sum_result and sum_result[0] else 0
            
            # 获取额外时间
            query2 = "SELECT extra_minutes FROM weekly_extra_time WHERE week_start=?"
            extra_result = await self.execute_query(query2, (week_start,), fetchone=True)
            extra_value = extra_result[0] if extra_result else 0
            
            result = (sum_value, extra_value)
            self._cache_result(cache_key, result)
            return result
        except Exception as e:
            logger.error(f"获取每周总计错误: {e}")
            raise

    async def add_weekly_extra_time(self, week_start, minutes):
        """添加每周额外游戏时间"""
        try:
            query = "INSERT OR REPLACE INTO weekly_extra_time (week_start, extra_minutes) VALUES (?, ?)"
            await self.execute_query(query, (week_start, minutes), commit=True)
            
            # 清除相关缓存
            self._invalidate_cache("get_week_total")
        except Exception as e:
            logger.error(f"添加每周额外时间错误: {e}")
            raise

    async def get_today_math_exercises(self):
        """获取今天的数学练习记录"""
        try:
            today = datetime.date.today().strftime("%Y-%m-%d")
            query = "SELECT * FROM math_exercises WHERE date=? ORDER BY id"
            result = await self.execute_query(query, (today,))
            # 打印每条记录的详细信息
            for row in result:
                logger.info(f"[DEBUG] 数学练习记录: id={row[0]}, date={row[1]}, question={row[2]}, answer={row[3]}, is_correct={row[4]}, reward={row[5]}, is_gpt={row[7]}")
            return result
        except Exception as e:
            logger.error(f"获取今天数学练习错误: {e}")
            raise

    def add_math_exercise(self, question, answer, is_correct, reward_minutes, explanation, is_gpt=0, difficulty=None):
        """添加数学练习记录
        
        Args:
            question: 题目文本
            answer: 回答文本
            is_correct: 是否正确 (1/0)
            reward_minutes: 奖励分钟数
            explanation: 解释文本
            is_gpt: 是否GPT生成 (1/0)
            difficulty: 难度 (1-4，默认2)
        
        Returns:
            添加的记录ID
        """
        try:
            today = datetime.date.today().strftime("%Y-%m-%d")
            # 标准化题目文本，防止重复
            std_question = question.strip().replace('\n', '').replace(' ', '').replace('\r', '')
            # 原始题目，只去除前后空白
            original_question = question.strip()
            
            # 记录操作日志
            logger.debug(f"添加数学练习记录：原始题目={original_question[:30]}..., 标准化后={std_question[:30]}...")
            
            # 如果未提供难度，使用默认值2
            if difficulty is None:
                difficulty = 2
            # 确保难度为整数
            try:
                difficulty = int(difficulty)
            except (ValueError, TypeError):
                logger.warning(f"难度值转换整数失败 '{difficulty}'，使用默认值2")
                difficulty = 2
                
            logger.debug(f"添加数学练习记录：problem={original_question[:30]}..., 难度={difficulty}")
            
            # 首先检查今天是否已有相同的题目记录（使用标准化后的题目进行比较）
            c = self.conn.cursor()
            c.execute(
                "SELECT id FROM math_exercises WHERE date=date('now') AND std_question=? AND is_gpt=?",
                (std_question, is_gpt)
            )
            result = c.fetchone()
            
            if result:
                # 如果题目已存在，更新记录
                exercise_id = result[0]
                logger.info(f"题目已存在，更新记录ID {exercise_id}（标准化后: {std_question[:30]}...）")
                c.execute(
                    """UPDATE math_exercises
                        SET question=?, std_question=?, answer=?, is_correct=?, reward_minutes=?, explanation=?, difficulty=?
                        WHERE id=?""",
                    (original_question, std_question, answer, is_correct, reward_minutes, explanation, difficulty, exercise_id)
                )
                logger.debug(f"更新题目ID {exercise_id} 的难度为 {difficulty}")
            else:
                # 否则插入新记录，使用原始题目和标准化题目
                logger.info(f"插入新题目（标准化后: {std_question[:30]}...）")
                c.execute(
                    """INSERT INTO math_exercises 
                        (date, question, std_question, answer, is_correct, reward_minutes, explanation, is_gpt, difficulty) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (today, original_question, std_question, answer, is_correct, reward_minutes, explanation, is_gpt, difficulty)
                )
                exercise_id = c.lastrowid
                logger.debug(f"插入新题目ID {exercise_id} 的难度为 {difficulty}")
                
            self.conn.commit()
            
            # 清除缓存
            self._invalidate_cache("get_today_math_exercises")
            self._invalidate_cache("get_today_math_reward")
            self._invalidate_cache("get_today_gpt_questions")
            
            return exercise_id
        except Exception as e:
            self.conn.rollback()
            logger.error(f"添加数学练习记录失败: {e}")
            raise

    async def get_today_math_reward(self):
        """获取今天通过数学练习获得的奖励分钟数"""
        try:
            today = datetime.date.today().strftime("%Y-%m-%d")
            query = "SELECT SUM(reward_minutes) FROM math_exercises WHERE date=? AND is_correct=1"
            result = await self.execute_query(query, (today,), fetchone=True)
            
            reward = result[0] if result and result[0] else 0
            logger.info(f"[DEBUG] 从数据库获取数学奖励: {reward}")
            
            # 打印所有正确答题的记录
            check_query = "SELECT id, question, answer, is_correct, reward_minutes FROM math_exercises WHERE date=? AND is_correct=1"
            correct_records = await self.execute_query(check_query, (today,))
            for record in correct_records:
                logger.info(f"[DEBUG] 正确答题记录: id={record[0]}, question={record[1]}, answer={record[2]}, is_correct={record[3]}, reward={record[4]}")
            
            return reward
        except Exception as e:
            logger.error(f"获取今天数学奖励错误: {e}")
            raise

    async def get_today_gpt_questions(self):
        """获取今天的GPT生成题目"""
        cache_key = self._get_cache_key("get_today_gpt_questions")
        cached = self._get_cached_result(cache_key)
        if cached:
            return cached
            
        try:
            today = datetime.date.today().strftime("%Y-%m-%d")
            query = "SELECT * FROM math_exercises WHERE date=? AND is_gpt=1 ORDER BY id"
            result = await self.execute_query(query, (today,))
            
            # 记录所有题目的难度和标准化处理
            if result:
                difficulties = []
                for i, row in enumerate(result):
                    # difficulty在索引8
                    diff = row[8] if len(row) > 8 and row[8] is not None else None
                    difficulties.append(diff)
                    
                    # 记录原始题目和标准化题目
                    raw_question = row[2]
                    std_question = raw_question.strip().replace('\n', '').replace(' ', '').replace('\r', '')
                    logger.debug(f"题目 {i+1}: ID={row[0]}, 难度={diff}, 标准化前={raw_question[:30]}..., 标准化后={std_question[:30]}...")
                
                logger.info(f"从数据库加载的题目难度: {difficulties}")
            
            self._cache_result(cache_key, result)
            return result
        except Exception as e:
            logger.error(f"获取今天GPT题目错误: {e}")
            raise

    def cache_today_gpt_questions(self, questions, answers=None, explanations=None):
        """缓存GPT生成的题目
        
        Args:
            questions: 问题列表
            answers: 可选的答案列表
            explanations: 可选的解释列表
        """
        try:
            today = datetime.date.today().strftime("%Y-%m-%d")
            
            # 在一个事务中执行多个操作
            with self.conn:
                # 首先清除旧的缓存
                self.conn.execute("DELETE FROM math_exercises WHERE date=? AND is_gpt=1", (today,))
                
                # 插入新的缓存
                for i, q in enumerate(questions):
                    # 获取对应的答案和解释（如果有）
                    answer = answers[i] if answers and i < len(answers) else None
                    explanation = explanations[i] if explanations and i < len(explanations) else None
                    
                    self.conn.execute(
                        "INSERT INTO math_exercises (date, question, answer, is_correct, reward_minutes, explanation, is_gpt, difficulty) VALUES (?, ?, ?, ?, ?, ?, 1, 2)",
                        (today, q, answer, None, 1.0, explanation)
                    )
            
            # 清除相关缓存
            self._invalidate_cache("get_today_gpt_questions")
        except Exception as e:
            logger.error(f"缓存GPT题目错误: {e}")
            raise

    async def clear_today_gpt_questions(self):
        """清除今天的GPT题目"""
        today = datetime.date.today().strftime("%Y-%m-%d")
        try:
            await self.execute_query(
                "DELETE FROM math_exercises WHERE date = ? AND is_gpt = 1",
                (today,),
                commit=True
            )
            logger.info(f"已清除今天的GPT题目: {today}")
        except Exception as e:
            logger.error(f"清除今天的GPT题目失败: {e}")
            raise

    async def get_recent_gpt_questions(self, days=30):
        """获取最近几天的GPT题目用于避免重复"""
        cutoff_date = (datetime.date.today() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
        try:
            result = await self.execute_query(
                """SELECT id, date, question, answer, is_correct, reward_minutes, 
                          explanation, is_gpt, difficulty 
                   FROM math_exercises 
                   WHERE date >= ? AND is_gpt = 1 
                   ORDER BY date DESC""",
                (cutoff_date,)
            )
            logger.info(f"获取最近{days}天的GPT题目，共{len(result)}道")
            return result
        except Exception as e:
            logger.error(f"获取最近GPT题目失败: {e}")
            return []

    async def get_cached_explanation(self, question, wrong_answer):
        """从缓存中获取解释"""
        try:
            query = "SELECT explanation FROM math_explanations WHERE question=? AND answer=?"
            result = await self.execute_query(query, (question, wrong_answer), fetchone=True)
            return result[0] if result else None
        except Exception as e:
            logger.error(f"获取缓存解释错误: {e}")
            return None  # 即使出错也返回None，让调用者能继续工作

    async def cache_explanation(self, question, wrong_answer, explanation):
        """缓存解释"""
        try:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            query = "INSERT INTO math_explanations (question, answer, explanation, created_at) VALUES (?, ?, ?, ?)"
            await self.execute_query(query, (question, wrong_answer, explanation, now), commit=True)
        except Exception as e:
            logger.error(f"缓存解释错误: {e}")
            # 这个错误不是致命的，所以不需要抛出异常

    async def clear_old_explanations(self, days=7):
        """清除旧的解释缓存"""
        try:
            cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
            query = "DELETE FROM math_explanations WHERE created_at < ?"
            await self.execute_query(query, (cutoff,), commit=True)
        except Exception as e:
            logger.error(f"清除旧解释错误: {e}")
            # 这个错误不是致命的，所以不需要抛出异常

    def optimize_database(self):
        """优化数据库性能和修复问题"""
        try:
            c = self.conn.cursor()
            # 修复潜在的NULL问题
            c.execute("UPDATE math_exercises SET is_gpt = 0 WHERE is_gpt IS NULL AND is_correct IS NOT NULL")
            c.execute("UPDATE math_exercises SET is_gpt = 1 WHERE is_gpt IS NULL AND is_correct IS NULL")
            # 清理没有题目内容的记录
            c.execute("DELETE FROM math_exercises WHERE question IS NULL OR question = ''")
            # 为缺失的字段设置默认值
            c.execute("UPDATE math_exercises SET answer = '（无标准答案）' WHERE answer IS NULL AND is_gpt = 1")
            c.execute("UPDATE math_exercises SET explanation = '（无解释）' WHERE explanation IS NULL AND is_gpt = 1")
            self.conn.commit()
            # 清除所有解释缓存 - 创建异步任务但不等待它
            asyncio.create_task(self.clear_old_explanations(0))
            # 运行VACUUM来压缩数据库
            c.execute("VACUUM")
            # 分析数据库以优化查询
            c.execute("ANALYZE")
            # 清除所有缓存
            self._invalidate_cache()
            logger.info("数据库优化完成")
            return True
        except Exception as e:
            logger.error(f"数据库优化错误: {e}")
            return False

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            try:
                # 清理缓存
                self.cache.clear()
                self.cache_timeout.clear()
                
                # 提交任何未提交的事务
                try:
                    self.conn.commit()
                except sqlite3.Error:
                    pass  # 忽略提交错误
                
                # 关闭连接
                self.conn.close()
                self.conn = None
                logger.info("数据库连接已关闭")
            except Exception as e:
                logger.error(f"关闭数据库连接失败: {e}")
                # 强制设置为None，确保不会重复关闭
                self.conn = None

    def reconnect(self):
        """重新连接数据库（如果已关闭）"""
        if self.conn is None:
            logger.info("重新连接数据库...")
            self.connect()
            return True
        return False

    async def get_setting(self, key, default=None):
        """获取设置值"""
        try:
            # 首先检查settings表是否存在
            c = self.conn.cursor()
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='settings'")
            if not c.fetchone():
                # 如果表不存在，创建它
                c.execute('''
                    CREATE TABLE settings (
                        key TEXT PRIMARY KEY,
                        value TEXT,
                        updated_at TEXT
                    )
                ''')
                self.conn.commit()
                
            # 获取设置值
            query = "SELECT value FROM settings WHERE key=?"
            result = await self.execute_query(query, (key,), fetchone=True)
            
            if result:
                return result[0]
            return default
        except Exception as e:
            logger.error(f"获取设置值错误: {e}")
            return default
            
    async def set_setting(self, key, value):
        """设置值"""
        try:
            # 首先检查settings表是否存在
            c = self.conn.cursor()
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='settings'")
            if not c.fetchone():
                # 如果表不存在，创建它
                c.execute('''
                    CREATE TABLE settings (
                        key TEXT PRIMARY KEY,
                        value TEXT,
                        updated_at TEXT
                    )
                ''')
            
            # 更新或插入设置
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            query = "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)"
            await self.execute_query(query, (key, value, now), commit=True)
            
            return True
        except Exception as e:
            logger.error(f"设置值错误: {e}")
            return False

     