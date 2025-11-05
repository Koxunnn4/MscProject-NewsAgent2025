import json
import asyncio
import redis
import logging
import sqlite3
from sklearn.feature_extraction.text import CountVectorizer
import jieba
from keybert import KeyBERT
import spacy
from spacy.matcher import PhraseMatcher
import os
import sys
import re
import torch

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

        self._kw_model = KeyBERT(model="paraphrase-multilingual-MiniLM-L12-v2")
        # self.stopwords_path = "stopwords.txt"
        self.stopwords = set()
        # self.coin_dict_path = "coin_dict.json"

        # 加载spacy中文模型和币种词典
        self.nlp = spacy.load("zh_core_web_sm")
        # self.coin_dict = self._load_coin_dict()
        # self.matcher = self._build_matcher()

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

    # def run_keywords_extraction(self, text):
    #     """对新闻文本提取前k个关键词,返回逗号分隔字符串"""
    #     self._load_stopwords()
    #     vectorizer = CountVectorizer(tokenizer=self.tokenize_and_filter)
    #     top_n = 10 if len(text) > 50 else 5
    #     keywords = self._kw_model.extract_keywords(
    #         text,
    #         vectorizer=vectorizer,
    #         keyphrase_ngram_range=(1, 3),
    #         top_n=top_n,
    #     )
    #     keywords_str = ",".join([kw[0] for kw in keywords])
    #     return keywords_str

    # def tokenize_and_filter(self, text):
    #     # 1. jieba分词
    #     tokens = jieba.lcut(text)
    #     # 2. 去除停用词
    #     if self.stopwords:
    #         tokens = [tok for tok in tokens if tok not in self.stopwords]
    #     # 3. 过滤不符合规则的词
    #     allowed_pattern = re.compile(r'^[A-Za-z0-9\u4e00-\u9fff]+$')
    #     def is_valid_keyword(w):
    #         if not w:
    #             return False
    #         w = w.strip()
    #         # 规则1: 单独的汉字
    #         if re.fullmatch(r'[\u4e00-\u9fff]', w):
    #             return False
    #         # 规则2: 单独的英文字母
    #         if re.fullmatch(r'[A-Za-z]', w):
    #             return False
    #         # 规则3: 除了表示年份的数字以外,其他纯数字不通过
    #         if re.fullmatch(r'\d+', w):
    #             if not (1950 <= int(w) <= 2050):
    #                 return False
    #         # 规则4: 包含特殊字符
    #         if not allowed_pattern.match(w):
    #             return False

    #         return True

    #     # 应用过滤规则
    #     filtered_tokens = [tok.strip() for tok in tokens if is_valid_keyword(tok)]

    #     return filtered_tokens

    # def _load_stopwords(self):
    #     """加载停用词列表"""
    #     try:
    #         with open(self.stopwords_path, 'r', encoding='utf-8') as f:
    #             for line in f:
    #                 self.stopwords.add(line.strip())
    #     except Exception as e:
    #         logger.error(f"Failed to load stopwords: {e}")

    # def _load_coin_dict(self):
    #     """从JSON文件加载币种词典"""
    #     try:
    #         with open(self.coin_dict_path, 'r', encoding='utf-8') as f:
    #             return json.load(f)
    #     except Exception as e:
    #         logger.error(f"Failed to load coin_dict.json: {e}")
    #         return {}

    # def _build_matcher(self):
    #     """构建币种匹配器(英文不区分大小写)"""
    #     patterns = []
    #     for synonyms in self.coin_dict.values():
    #         for name in synonyms:
    #             name_lower = name.lower()
    #             patterns.append(self.nlp.make_doc(name_lower))

    #     matcher = PhraseMatcher(self.nlp.vocab, attr="LOWER")
    #     matcher.add("COIN", patterns)
    #     return matcher

    # def identify_currency(self, text):
    #     doc = self.nlp(text)
    #     matches = self.matcher(doc)
    #     mentioned_coins = set()

    #     for _, start, end in matches:
    #         span_text = doc[start:end].text
    #         # 查找所属币种
    #         for coin_id, synonyms in self.coin_dict.items():
    #             if span_text in synonyms:
    #                 mentioned_coins.add(coin_id)
    #                 break

    #     return list(mentioned_coins)

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
