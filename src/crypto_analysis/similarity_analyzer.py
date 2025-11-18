"""
相似度分析器（核心逻辑）
纯粹的分析函数，不包含 UI 交互代码
"""
import sqlite3
import re
import logging
from collections import Counter
from typing import List, Tuple, Optional, Dict
import os
import sys

# 添加项目根目录到路径
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.crypto_analysis.model_loader import get_spacy_model

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

SPLIT_RE = re.compile(r"[,，]+")  # 分隔符正则


class SimilarityAnalyzer:
    """
    相似度分析器 - 纯分析逻辑（不包含 UI 交互）
    """

    def __init__(self,
                 db_path: str = "stream.db",
                 table: str = "messages",
                 keyword_column: str = "keywords",
                 currency_column: str = "industry",
                 min_count: int = 5,
                 top_n: int = 100):
        """
        初始化分析器

        Args:
            db_path: 数据库路径
            table: 表名
            keyword_column: 关键词列名
            currency_column: 币种列名
            min_count: 最小词频阈值
            top_n: 输出前 N 对结果
        """
        self.db_path = db_path
        self.table = table
        self.keyword_column = keyword_column
        self.currency_column = currency_column
        self.min_count = min_count
        self.top_n = top_n

        # 延迟加载 spaCy 模型
        self.nlp = None

    def _load_spacy_model(self):
        """延迟加载 spaCy 模型"""
        if self.nlp is None:
            try:
                self.nlp = get_spacy_model("zh_core_web_sm")
            except Exception as e:
                logger.error(f"spaCy 模型加载失败: {e}")
                raise

    def get_total_rows(self, channel_ids: List[str] = None, time_range: Tuple[str, str] = None) -> int:
        """
        获取数据库总行数

        Args:
            channel_ids: 频道 ID 列表
            time_range: 时间范围 (start_time, end_time)

        Returns:
            总行数
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            where_clauses = []
            params = []

            if channel_ids:
                placeholders = ",".join("?" for _ in channel_ids)
                where_clauses.append(f"channel_id IN ({placeholders})")
                params.extend(channel_ids)

            if time_range:
                start_time, end_time = time_range
                where_clauses.append("date BETWEEN ? AND ?")
                params.extend([start_time, end_time])

            where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
            sql = f"SELECT COUNT(*) FROM {self.table} {where_sql}"

            cur.execute(sql, params)
            total = cur.fetchone()[0]
        finally:
            conn.close()
        return total

    def fetch_column_data(self,
                         column: str,
                         channel_ids: List[str] = None,
                         time_range: Tuple[str, str] = None) -> List[Tuple]:
        """
        从数据库读取指定列数据

        Args:
            column: 列名
            channel_ids: 频道 ID 列表（可选）
            time_range: 时间范围（可选）

        Returns:
            查询结果列表
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            where_clauses = []
            params = []

            if channel_ids:
                placeholders = ",".join("?" for _ in channel_ids)
                where_clauses.append(f"channel_id IN ({placeholders})")
                params.extend(channel_ids)

            if time_range:
                start_time, end_time = time_range
                where_clauses.append("date BETWEEN ? AND ?")
                params.extend([start_time, end_time])

            where_sql = ""
            if where_clauses:
                where_sql = " WHERE " + " AND ".join(where_clauses)

            # ✅ 修复 SQL 拼接错误
            if where_sql:
                sql = f"SELECT {column} FROM {self.table} {where_sql} AND {column} IS NOT NULL"
            else:
                sql = f"SELECT {column} FROM {self.table} WHERE {column} IS NOT NULL"

            cur.execute(sql, params)
            rows = cur.fetchall()
        finally:
            conn.close()

        return rows

    def count_items_with_occurrence(self,
                                   rows: List[Tuple],
                                   case_insensitive: bool = True) -> Tuple[Counter, Counter]:
        """
        统计分隔字符串中各项的出现次数

        Args:
            rows: 数据行列表
            case_insensitive: 是否不区分大小写

        Returns:
            (item_counter, occurrence_counter) 元组
        """
        item_counter = Counter()
        occurrence_counter = Counter()

        for (item_str,) in rows:
            if not item_str:
                continue
            parts = [p.strip() for p in SPLIT_RE.split(item_str) if p and p.strip()]
            if case_insensitive:
                parts = [p.lower() for p in parts]
            item_counter.update(parts)
            occurrence_counter.update(set(parts))

        return item_counter, occurrence_counter

    def calculate_similarity(self, keyword_counter: Counter) -> List[Tuple]:
        """
        计算关键词相似度

        Args:
            keyword_counter: 关键词计数器

        Returns:
            相似度结果列表 [(word1, count1, word2, count2, similarity), ...]
        """
        self._load_spacy_model()

        # 过滤低频词
        terms = [t for t, c in keyword_counter.items() if c >= self.min_count]

        if len(terms) < 2:
            logger.warning("关键词数量不足（< 2），无法计算相似度")
            return []

        # 构建词向量
        term_docs = {}
        skipped = []
        for t in terms:
            try:
                doc = self.nlp(t)
                if hasattr(doc, "vector_norm") and doc.vector_norm > 0:
                    term_docs[t] = doc
                else:
                    skipped.append(t)
            except Exception as e:
                logger.debug(f"跳过词 '{t}': {e}")
                skipped.append(t)

        if len(term_docs) < 2:
            logger.warning("有效关键词数量不足（< 2），无法计算相似度")
            return []

        # 计算相似度对
        pairs = []
        keys = list(term_docs.keys())

        import itertools
        for a, b in itertools.combinations(keys, 2):
            try:
                sim = term_docs[a].similarity(term_docs[b])
                pairs.append((a, keyword_counter[a], b, keyword_counter[b], float(sim)))
            except Exception as e:
                logger.debug(f"计算 '{a}' 和 '{b}' 的相似度失败: {e}")
                continue

        pairs.sort(key=lambda x: x[4], reverse=True)
        return pairs

    def query_keyword_similarity(self,
                               input_keyword: str,
                               keyword_counter: Counter,
                               top_n: int = 10) -> Tuple[bool, List[Tuple]]:
        """
        查询关键词相似度

        Args:
            input_keyword: 输入的关键词
            keyword_counter: 关键词计数器
            top_n: 返回前 N 个相似词

        Returns:
            (exists, similar_words) 元组
            - exists: 关键词是否存在
            - similar_words: [(word, count, similarity), ...] 列表
        """
        self._load_spacy_model()

        input_norm = input_keyword.lower().strip()

        # 判断是否存在
        exists = input_norm in (k.lower() for k in keyword_counter.keys())

        # 过滤高频词
        high_freq_terms = [t for t, c in keyword_counter.items() if c >= self.min_count]

        # 构建词向量
        term_docs = {}
        for t in high_freq_terms:
            try:
                doc = self.nlp(t)
                if hasattr(doc, "vector_norm") and doc.vector_norm > 0:
                    term_docs[t] = doc
            except Exception as e:
                logger.debug(f"跳过词 '{t}': {e}")
                continue

        # 计算输入词向量
        try:
            input_doc = self.nlp(input_norm)
            if not (hasattr(input_doc, "vector_norm") and input_doc.vector_norm > 0):
                return exists, []
        except Exception as e:
            logger.error(f"处理输入关键词失败: {e}")
            return exists, []

        # 计算相似度
        similarities = []
        for term, doc in term_docs.items():
            try:
                sim = input_doc.similarity(doc)
                similarities.append((term, keyword_counter[term], float(sim)))
            except Exception as e:
                logger.debug(f"计算相似度失败: {e}")
                continue

        similarities.sort(key=lambda x: x[2], reverse=True)
        top_similar = similarities[:top_n]

        return exists, top_similar


if __name__ == "__main__":
    # 基本测试
    analyzer = SimilarityAnalyzer()
    print("✓ SimilarityAnalyzer 初始化成功")
