"""
关键词提取模块
test git
"""
import os
import sys
from typing import List, Tuple, Dict
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import CountVectorizer
import jieba
import re
import spacy
from spacy.matcher import PhraseMatcher
import json
import sqlite3
from collections import Counter
import itertools

# 分隔关键词的正则（英文/中文逗号）
SPLIT_RE = re.compile(r"[,，]+")

# 添加项目根目录到路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from config import KEYBERT_MODEL, TOP_N_KEYWORDS, KEYWORD_NGRAM_RANGE

try:
    from keybert import KeyBERT
    KEYBERT_AVAILABLE = True
except ImportError:
    KEYBERT_AVAILABLE = False
    print("⚠️  KeyBERT 未安装，请运行: pip install keybert sentence-transformers")


class CryptoAnalyzer:
    def __init__(self, model_name: str = None):
        self.model_name = model_name or KEYBERT_MODEL
        self.model = None
        self.stopwords = set()
        self.coin_dict = self._load_coin_dict()

        # 加载KeyBERT模型
        if KEYBERT_AVAILABLE:
            try:
                self.model = KeyBERT(model=self.model_name)
            except Exception as e:
                print(f"KeyBERT模型加载失败: {e}")
                self.model = None

        # 加载spaCy中文NER模型
        try:
            self.nlp = spacy.load("zh_core_web_sm")
        except Exception as e:
            print(f"spaCy中文模型加载失败: {e}")
            self.nlp = None

        # 构建币种匹配器
        if self.nlp:
            self.matcher = self._build_matcher()

    def _load_stopwords(self, path: str = "stopwords.txt"):
        if not self.stopwords:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.stopwords = set(line.strip() for line in f if line.strip())
            except Exception as e:
                print(f"停用词加载失败: {e}")
                self.stopwords = set()

    def spacy_ner_keywords(self, text: str) -> List[str]:
        if not self.nlp:
            return []
        doc = self.nlp(text)
        entities = set()
        for token in doc:
            # print(f"识别到词性: {token.text} ({token.pos_})")
            # 过滤停用词和长度小的实体
            token_text = token.text.strip()
            # 仅保留名词、动词和专有名词等作为关键词
            if token.pos_ in {"PROPN", "NOUN", "VERB", "ORG", "GPE", "LOC"}:
                if token_text not in self.stopwords and len(token_text) > 1 and self.is_valid_keyword(token_text):
                    entities.add(token_text)
            # if token_text not in self.stopwords and len(token_text) > 1 and self.is_valid_keyword(token_text):
            #     entities.add(token_text)
        print(f"识别到合规实体: {entities}")
        return list(entities)

    def extract_keywords(self, text: str, top_n: int = 10) -> List[Tuple[str, float]]:
        if not self.model or not text or len(text.strip()) == 0:
            return []

        self._load_stopwords()
        # 指定 token_pattern=None 可以避免 sklearn 关于 token_pattern 被忽略的警告
        vectorizer = CountVectorizer(tokenizer=self.tokenize_and_filter, token_pattern=None)
        top_n = top_n or TOP_N_KEYWORDS

        kw_results: List[Tuple[str, float]] = []
        try:
            kw_results = self.model.extract_keywords(
                text,
                vectorizer=vectorizer,
                keyphrase_ngram_range=(1, 3),
                top_n=top_n,
                diversity=0.3
            )
        except Exception as e:
            # 常见错误：empty vocabulary（文档可能全是停用词）等
            print(f"关键词提取失败: {e}")

        return kw_results

    def is_valid_keyword(self, w):
            allowed_pattern = re.compile(r'^[A-Za-z0-9\u4e00-\u9fff]+$')
            if not w:
                return False
            w = w.strip()
            if re.fullmatch(r'[\u4e00-\u9fff]', w):
                return False
            if re.fullmatch(r'[A-Za-z]', w):
                return False
            if re.fullmatch(r'\d+', w):
                if not (1950 <= int(w) <= 2050):
                    return False
            if not allowed_pattern.match(w):
                return False
            return True

    def tokenize_and_filter(self, text):
        # 这是你的分词和过滤函数定义，应确保在类中
        tokens = jieba.lcut(text)
        if self.stopwords:
            tokens = [tok for tok in tokens if tok not in self.stopwords]
        filtered_tokens = [tok.strip() for tok in tokens if self.is_valid_keyword(tok)]
        return filtered_tokens

    def extract_keywords_batch(self, db_path: str):
        # 读取.db数据库中的数据，其中包含新闻文本text字段，分别提取关键词和identify_currency，将关键词和币种更新回数据库的keywords和industry字段,如果db没有keywords和industry字段则新增后再存入

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, text FROM news")
        rows = cursor.fetchall()
        for row in rows:
            news_id = row[0]
            text = row[1]
            keywords = self.extract_keywords(text)
            keyword_list = [kw[0] for kw in keywords]
            coins = self.identify_currency(text)
            # 更新回数据库
            cursor.execute("UPDATE news SET keywords = ?, industry = ? WHERE id = ?", (",".join(keyword_list), ",".join(coins), news_id))
        conn.commit()
        conn.close()

    def _load_coin_dict(self):
        """从JSON文件加载币种词典"""
        try:
            with open("coin_dict.json", 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load coin_dict.json: {e}")
            return {}

    def _build_matcher(self):
        """构建币种匹配器(英文不区分大小写)"""
        patterns = []
        for synonyms in self.coin_dict.values():
            for name in synonyms:
                patterns.append(self.nlp.make_doc(name.lower()))
        matcher = PhraseMatcher(self.nlp.vocab, attr="LOWER")
        matcher.add("COIN", patterns)
        return matcher

    def identify_currency(self, text: str) -> List[str]:
        """识别文本中的币种，返回币种ID列表"""
        if not self.matcher or not self.nlp:
            return []
        doc = self.nlp(text)
        matches = self.matcher(doc)
        mentioned_coins = set()
        for _, start, end in matches:
            span_text = doc[start:end].text
            for coin_id, synonyms in self.coin_dict.items():
                # 这里忽略大小写比较
                if span_text.lower() in [s.lower() for s in synonyms]:
                    mentioned_coins.add(coin_id)
                    break
        return list(mentioned_coins)



# 单例模式
_crypto_analyzer = None

def get_crypto_analyzer() -> CryptoAnalyzer:
    """获取加密分析器单例"""
    global _crypto_analyzer
    if _crypto_analyzer is None:
        _crypto_analyzer = CryptoAnalyzer()
    return _crypto_analyzer


if __name__ == "__main__":
    pass
    # DB_PATH = r"E:\msc_proj\MscProject-NewsAgent2025\src\crawler\crpyto_news\history.db"
    # TABLE = "messages"
    # KEYWORD_COLUMN = "keywords"
    # # 测试
    # extractor = get_crypto_analyzer()
    # nlp = extractor.load_spacy_similarity_model()
    # keyword_rows = extractor.fetch_column_data(DB_PATH, TABLE, KEYWORD_COLUMN)
    # keyword_counter, keyword_occurrence = extractor.count_items_with_occurrence(keyword_rows, case_insensitive=True)
    # # 测试 calculate_similarity
    # pairs = extractor.calculate_similarity(nlp, keyword_counter)

    # test_text = """
    # **“胜率100%巨鲸”凌晨加仓173.6枚BTC，总持仓价值超2.96亿美元** 10月26日，据链上分析师Ai姨（@ai_9684xtpa）监测，胜率100%的巨鲸在今日凌晨加仓173.6枚BTC。该巨鲸当前BTC多单持仓达1,482.9枚，价值1.65亿美元，开仓价为110,680.1美元。 此外，该巨鲸还持有33,270.78枚ETH多单，价值1.32亿美元，开仓价为3,897.59美元。其整体仓位超过2.96亿美元，目前浮盈270万美元。
    # """

    # keywords = extractor.extract_keywords(test_text)
    # print("提取的关键词:")
    # for kw, weight in keywords:
    #     print(f"  {kw}: {weight:.4f}")

    # coins = extractor.identify_currency(test_text)
    # print("提取的币种:")
    # for coin in coins:
    #     print(f"  {coin}")
