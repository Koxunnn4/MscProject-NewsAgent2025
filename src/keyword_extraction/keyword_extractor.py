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


class KeywordExtractor:
    """关键词提取器"""

    def __init__(self, model_name: str = None):
        """
        初始化关键词提取器

        Args:
            model_name: KeyBERT 模型名称
        """
        self.model_name = model_name or KEYBERT_MODEL
        self.model = None
        self.stopwords = set()

        if KEYBERT_AVAILABLE:
            try:
                print(f"正在加载 KeyBERT 模型: {self.model_name}...")
                print("（首次运行会自动下载模型，使用国内镜像加速）")
                self.model = KeyBERT(model=self.model_name)
                print("✓ KeyBERT 模型加载完成")
            except Exception as e:
                print(f"❌ KeyBERT 模型加载失败: {e}")
                self.model = None

    def extract_keywords(self, text: str, top_n: int = None) -> List[Tuple[str, float]]:
        """
        提取文本关键词

        Args:
            text: 输入文本
            top_n: 返回前N个关键词

        Returns:
            [(keyword, weight), ...] 关键词和权重列表
        """
        if not self.model:
            return []

        if not text or len(text.strip()) == 0:
            return []

        self._load_stopwords()
        vectorizer = CountVectorizer(tokenizer=self.tokenize_and_filter)

        top_n = top_n or TOP_N_KEYWORDS

        try:
            keywords = self.model.extract_keywords(
                text,
                vectorizer=vectorizer,
                keyphrase_ngram_range=(1, 3),
                top_n=top_n,
                diversity=0.3
            )
            return keywords if keywords else []
        except Exception as e:
            print(f"关键词提取失败: {e}")
            return []

    def extract_keywords_batch(self, texts: List[str], top_n: int = None) -> List[List[Tuple[str, float]]]:
        """
        批量提取关键词

        Args:
            texts: 文本列表
            top_n: 每个文本返回前N个关键词

        Returns:
            关键词列表的列表
        """
        results = []
        for text in texts:
            keywords = self.extract_keywords(text, top_n)
            results.append(keywords)
        return results

    def _load_stopwords(self, path: str = "stopwords.txt"):
        """加载停用词"""
        if not self.stopwords:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.stopwords = set(line.strip() for line in f if line.strip())
            except Exception as e:
                print(f"停用词加载失败: {e}")
                self.stopwords = set()

    def tokenize_and_filter(self, text):
        """分词+过滤"""
        tokens = jieba.lcut(text)
        # 去除停用词
        tokens = [tok for tok in tokens if tok not in self.stopwords]
        # 过滤规则
        allowed_pattern = re.compile(r'^[A-Za-z0-9\u4e00-\u9fff]+$')

        def is_valid_keyword(w):
            if not w:
                return False
            w = w.strip()
            # 只要一个汉字
            if re.fullmatch(r'[\u4e00-\u9fff]', w):
                return False
            # 只要一个英文字母
            if re.fullmatch(r'[A-Za-z]', w):
                return False
            # 除表示年份的数字，其他纯数字不通过
            if re.fullmatch(r'\d+', w):
                if not (1950 <= int(w) <= 2050):
                    return False
            # 特殊字符
            if not allowed_pattern.match(w):
                return False
            return True

        filtered_tokens = [tok.strip() for tok in tokens if is_valid_keyword(tok)]
        return filtered_tokens


    def calculate_relevance(self, user_keyword: str, news_keywords: List[str],
                          news_weights: List[float]) -> float:
        """
        计算用户关键词与新闻关键词的相关性

        Args:
            user_keyword: 用户输入的关键词
            news_keywords: 新闻的关键词列表
            news_weights: 新闻关键词的权重列表

        Returns:
            相关性得分
        """
        if not news_keywords:
            return 0.0

        try:
            # 使用词袋模型计算余弦相似度
            all_keywords = [user_keyword] + news_keywords
            vectorizer = CountVectorizer().fit(all_keywords)
            user_vector = vectorizer.transform([user_keyword]).toarray()
            news_vector = vectorizer.transform([' '.join(news_keywords)]).toarray()

            # 余弦相似度
            similarity = cosine_similarity(user_vector, news_vector)[0][0]

            # 计算关键词匹配加权
            weight_sum = sum(
                news_weights[i] for i, kw in enumerate(news_keywords)
                if user_keyword.lower() in kw.lower()
            )

            # 综合得分
            relevance = similarity * (1 + weight_sum)
            return relevance

        except Exception as e:
            print(f"相关性计算失败: {e}")
            return 0.0

    def get_top_relevant_news(self, user_keyword: str,
                             news_list: List[Dict],
                             top_k: int = 10) -> List[Dict]:
        """
        获取与用户关键词最相关的新闻

        Args:
            user_keyword: 用户关键词
            news_list: 新闻列表，每个新闻包含 keywords 和 weights
            top_k: 返回前K条

        Returns:
            相关性最高的新闻列表
        """
        # 计算每条新闻的相关性
        for news in news_list:
            if 'keywords' in news and 'weights' in news:
                news['relevance_score'] = self.calculate_relevance(
                    user_keyword,
                    news['keywords'],
                    news['weights']
                )
            else:
                news['relevance_score'] = 0.0

        # 按相关性排序
        sorted_news = sorted(news_list,
                           key=lambda x: (x.get('relevance_score', 0), x.get('date', '')),
                           reverse=True)

        return sorted_news[:top_k]


# 单例模式
_keyword_extractor = None

def get_keyword_extractor() -> KeywordExtractor:
    """获取关键词提取器单例"""
    global _keyword_extractor
    if _keyword_extractor is None:
        _keyword_extractor = KeywordExtractor()
    return _keyword_extractor


if __name__ == "__main__":
    # 测试
    extractor = get_keyword_extractor()

    test_text = """
    比特币价格今日突破 $65,000，创下近期新高。
    分析师认为这与美联储降息预期有关，投资者情绪乐观。
    """

    keywords = extractor.extract_keywords(test_text)
    print("提取的关键词:")
    for kw, weight in keywords:
        print(f"  {kw}: {weight:.4f}")

