import json
import asyncio
import redis
import logging
import sqlite3
import os
import sys
import re

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
from crypto_analysis.crypto_analyzer import CryptoAnalyzer

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class NewsConsumer:
    def __init__(self, redis_config, db_path="history.db"):
        self.redis_client = redis.Redis(host=redis_config["host"], port=redis_config["port"], decode_responses=True)
        self.list_key = redis_config["stream_key"]
        # 新增:连接数据库
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.db_path = db_path
        # 新增:创建表(如不存在)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY,
            channel_id TEXT,
            message_id INTEGER,
            text TEXT,
            date TEXT,
            keywords TEXT,
            industry TEXT
            )
        """)
        self.conn.commit()

        self.analyzer = CryptoAnalyzer()
        # ✅ CryptoAnalyzer 已包含 KeyBERT、spaCy、币种识别等所有分析功能
        
    async def process_message(self, message):
        """处理单条消息，打印并写入数据库，既识别币种，也提取关键词"""
        data = json.loads(message)
        logger.info(f"Channel: {data['channel']}")
        logger.info(f"Time: {data['timestamp']}")
        logger.info(f"Content: {data['content']}")
        logger.info("-" * 50)
        data = self.news_preprocess(data)

        # 识别币种
        # mentioned_coins = self.identify_currency(data['content'])
        mentioned_coins = self.analyzer.identify_currency(data['content'])
        coins_str = ",".join(mentioned_coins)
        print("Mentioned Currencies: ", coins_str)

        # 提取关键词
        # keywords_str = self.run_keywords_extraction(data['content'])
        keywords = self.analyzer.extract_keywords(
            data['content'],
            top_n=10
        )
        print("Keywords: ", keywords)
        if keywords:
            keywords_str = ",".join([kw[0] for kw in keywords])
            # keywords_str = self.capitalize_english(keywords_str)  # 英文部分转大写
        else:
            keywords_str = ""

        try:
            self.cursor.execute("SELECT MAX(message_id) FROM messages")
            result = self.cursor.fetchone()
            next_message_id = (result[0] or 0) + 1
            self.cursor.execute(
                "INSERT OR IGNORE INTO messages (id, channel_id, message_id, text, date, keywords, industry) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (data['id'], data['channel'], next_message_id, data['content'], data['timestamp'], keywords_str, coins_str)
            )
            self.conn.commit()
        except Exception as e:
            logger.error(f"DB insert error: {e}")

    def capitalize_english(self, text: str) -> str:
        """将字符串中的英文部分转为大写，保留中文和其他字符不变"""
        result = []
        for char in text:
            if char.isalpha() and ord(char) < 128:  # ASCII 英文字符
                result.append(char.upper())
            else:
                result.append(char)
        return ''.join(result)

    def news_preprocess(self, data):
        content = data['content']
        def clean_text(text):
            # 删除除了字母之间以外的所有空格
            text = re.sub(r'(?<![a-zA-Z]) | (?![a-zA-Z])', '', text)
            # 去掉所有空行,添加一个空格
            text = re.sub(r'\n+', ' ', text).strip()
            return text
        content = clean_text(content)

        if data['channel'] == '-1001387109317':# @theblockbeats
            content = re.sub(r'BlockBeats消息，', '', content)
            content = re.sub(r'^原文链接\s*\[.*?\]\(.*?\)\s*$', '', content, count=0, flags=re.M)

        if data['channel'] == '-1001735732363':# @TechFlowDaily
            content = re.sub(r'https?://\S+', '', content)
            content = re.sub(r'深潮TechFlow消息，', '', content)

        if data['channel'] == '-1002395608815':# @news6551
            pattern = r'----------.*|📢'
            content = re.sub(pattern, '', content, flags=re.DOTALL)

        if data['channel'] == '-1002117032512':# @MMSnews
            pattern = r'https://[^\s]+|📎'
            content = re.sub(pattern, '', content)

        data['content'] = content
        return data

    def __del__(self):
        self.conn.close()

    async def run_history_mode(self):
        """历史模式：从头开始读取所有消息"""
        # 获取所有消息
        messages = self.redis_client.lrange(self.list_key, 0, -1)
        for message in messages:
            await self.process_message(message)
        # 运行分析
        await self.analyzer.run_analysis(self.db_path)

    async def run_stream_mode(self):
        """实时模式：持续监听新消息"""
        last_id = 0  # 用于记录上次处理的位置

        while True:
            try:
                # 获取新消息（使用阻塞操作）
                result = self.redis_client.brpop(self.list_key, timeout=1)

                if result:
                    _, message = result
                    await self.process_message(message)
                else:
                    # 无新消息，等待一下
                    await asyncio.sleep(1)

            except Exception as e:
                logger.info(f"Error processing message: {e}")
                await asyncio.sleep(1)  # 出错时暂停一下
