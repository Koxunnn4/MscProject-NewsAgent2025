import sqlite3
import jieba
import re
from collections import Counter
from typing import List, Dict, Tuple
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NewsSearchEngine:
    def __init__(self, db_path: str = "data/history.db"):
        """
        初始化新闻搜索引擎
        
        Args:
            db_path: 数据库路径
        """
        self.db_path = db_path
        self.vectorizer = TfidfVectorizer(max_features=5000, stop_words=None)
        self.news_data = []
        self.tfidf_matrix = None
        

        
        self._load_news_data()
        self._build_tfidf_matrix()
        
        # 摘要模型配置与加载（中文摘要微调：XL-Sum）
        self.summary_min_len = 16
        self.summary_max_len = 84
        try:
            model_id = "csebuetnlp/mT5_multilingual_XLSum"
            self.t5_tokenizer = AutoTokenizer.from_pretrained(model_id)
            self.t5_model = AutoModelForSeq2SeqLM.from_pretrained(model_id)
        except Exception as e:
            logger.error(f"加载中文摘要模型失败: {e}")
            self.t5_tokenizer = None
            self.t5_model = None
        
    

    
    def _load_news_data(self):
        """从数据库加载新闻数据"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            # 优先尝试读取包含 url 列
            has_url = False
            try:
                cursor.execute(
                    """
                    SELECT id, channel_id, text, keywords, currency, date, url 
                    FROM messages 
                    WHERE text IS NOT NULL AND text != ''
                    ORDER BY date DESC
                    """
                )
                has_url = True
            except Exception:
                cursor.execute(
                    """
                    SELECT id, channel_id, text, keywords, currency, date 
                    FROM messages 
                    WHERE text IS NOT NULL AND text != ''
                    ORDER BY date DESC
                    """
                )
            rows = cursor.fetchall()
            self.news_data = []

            for row in rows:
                if has_url:
                    news_id, channel_id, text, keywords, currency, date, url = row
                else:
                    news_id, channel_id, text, keywords, currency, date = row
                    url = ""
                # 清理文本
                cleaned_text = self._clean_text(text)
                if cleaned_text:  # 只保留有效文本
                    title = self._derive_title(text)
                    self.news_data.append({
                        'id': news_id,
                        'channel_id': channel_id or '',
                        'title': title,
                        'text': cleaned_text,
                        'original_text': text,
                        'keywords': keywords or '',
                        'currency': currency or '',
                        'date': date,
                        'url': url or '',
                        'source': channel_id or 'Telegram',
                        'source_type': 'crypto'
                    })
            
            conn.close()
            logger.info(f"加载了 {len(self.news_data)} 条新闻数据")
            
        except Exception as e:
            logger.error(f"加载新闻数据失败: {e}")
            self.news_data = []

    def _derive_title(self, text: str) -> str:
        """根据新闻正文生成一个简短标题"""
        if not text:
            return "即时快讯"
        try:
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            candidate = lines[0] if lines else text.strip()
            return candidate[:80]
        except Exception:
            return str(text)[:80]
    
    def _clean_text(self, text: str) -> str:
        """清理文本数据"""
        if not text:
            return ""
        
        # 移除特殊字符，保留中文、英文、数字
        text = re.sub(r'[^\u4e00-\u9fff\w\s]', ' ', text)
        # 移除多余空格
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def _build_tfidf_matrix(self):
        """构建TF-IDF矩阵"""
        if not self.news_data:
            logger.warning("没有新闻数据，无法构建TF-IDF矩阵")
            return
        
        try:
            # 准备文本数据，使用jieba分词
            texts = []
            for news in self.news_data:
                # 结合新闻文本和关键词
                combined_text = f"{news['text']} {news['keywords']}"
                # 使用jieba分词
                words = jieba.cut(combined_text)
                segmented_text = ' '.join(words)
                texts.append(segmented_text)
            
            # 构建TF-IDF矩阵
            self.tfidf_matrix = self.vectorizer.fit_transform(texts)
            logger.info(f"TF-IDF矩阵构建完成，形状: {self.tfidf_matrix.shape}")
            
        except Exception as e:
            logger.error(f"构建TF-IDF矩阵失败: {e}")
            self.tfidf_matrix = None
    
    def search_by_keyword(self, keyword: str, top_k: int = 10) -> List[Dict]:
        """
        根据关键词搜索相关新闻
        
        Args:
            keyword: 搜索关键词
            top_k: 返回前k条结果
            
        Returns:
            相关新闻列表，按相关性排序
        """
        if not self.news_data or self.tfidf_matrix is None:
            logger.warning("没有可用的新闻数据或TF-IDF矩阵")
            return []
        
        try:
            # 对关键词进行分词
            keyword_words = jieba.cut(keyword)
            keyword_text = ' '.join(keyword_words)
            
            # 将关键词转换为TF-IDF向量
            keyword_vector = self.vectorizer.transform([keyword_text])
            
            # 计算余弦相似度
            similarities = cosine_similarity(keyword_vector, self.tfidf_matrix).flatten()
            
            # 获取相似度最高的top_k个新闻
            top_indices = similarities.argsort()[-top_k:][::-1]
            
            results = []
            for idx in top_indices:
                if similarities[idx] > 0:  # 只返回有相关性的结果
                    news = self.news_data[idx].copy()
                    news['similarity_score'] = float(similarities[idx])
                    results.append(news)
            
            logger.info(f"找到 {len(results)} 条与关键词 '{keyword}' 相关的新闻")
            return results
            
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return []

    def get_recent_news(self, limit: int = 20) -> List[Dict]:
        """获取最新的新闻数据，用于无关键词的默认展示"""
        if not self.news_data:
            return []
        try:
            safe_limit = max(1, int(limit))
        except Exception:
            safe_limit = 20
        recent_slice = self.news_data[:safe_limit]
        results = []
        for item in recent_slice:
            news_copy = item.copy()
            news_copy.setdefault('similarity_score', None)
            results.append(news_copy)
        return results

    

    



    

    
    
    def get_top_keywords(self, limit: int = 20) -> List[str]:
        """
        获取数据库中最常见的关键词
        
        Args:
            limit: 返回的关键词数量
            
        Returns:
            关键词列表
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT keywords FROM messages WHERE keywords IS NOT NULL AND keywords != ''")
            rows = cursor.fetchall()
            conn.close()
            
            # 统计关键词频率
            keyword_counter = Counter()
            for row in rows:
                keywords = row[0].split(',')
                for keyword in keywords:
                    keyword = keyword.strip()
                    if keyword:
                        keyword_counter[keyword] += 1
            
            # 返回最常见的关键词
            return [keyword for keyword, count in keyword_counter.most_common(limit)]
            
        except Exception as e:
            logger.error(f"获取关键词失败: {e}")
            return []

    # 新增：返回含计数的热门关键词
    def get_top_keywords_with_counts(self, limit: int = 20) -> List[Dict]:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT keywords FROM messages WHERE keywords IS NOT NULL AND keywords != ''")
            rows = cursor.fetchall()
            conn.close()
            keyword_counter = Counter()
            for row in rows:
                kws = [k.strip() for k in str(row[0]).split(",") if k.strip()]
                for k in kws:
                    keyword_counter[k] += 1
            return [{"keyword": k, "count": c} for k, c in keyword_counter.most_common(limit)]
        except Exception as e:
            logger.error(f"获取带计数的关键词失败: {e}")
            return []

    def generate_summary(self, text: str) -> str:
        try:
            if not text:
                return ""
            if getattr(self, "t5_tokenizer", None) is None or getattr(self, "t5_model", None) is None:
                return "模型不可用"
            clean_text = re.sub(r"\s+", " ", re.sub(r"\n+", " ", text.strip()))
            inputs = self.t5_tokenizer(
                clean_text,
                return_tensors="pt",
                padding="max_length",
                truncation=True,
                max_length=512,
            )
            summary_ids = self.t5_model.generate(
                inputs["input_ids"],
                max_length=self.summary_max_len,
                min_length=self.summary_min_len,
                num_beams=4,
                no_repeat_ngram_size=2,
                early_stopping=True,
            )
            return self.t5_tokenizer.decode(
                summary_ids[0],
                skip_special_tokens=True,
                clean_up_tokenization_spaces=False,
            )
        except Exception as e:
            logger.error(f"生成摘要失败: {e}")
            return "模型不可用"

    def _parse_date_str(self, date_str: str):
        try:
            if not date_str:
                return None
        except Exception:
            return None
        # Try common formats
        for fmt in ("%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(str(date_str), fmt)
            except Exception:
                pass
        # ISO 8601 (including 'Z')
        try:
            s = str(date_str).replace("Z", "+00:00")
            return datetime.fromisoformat(s)
        except Exception:
            pass
        # Fallback: extract YYYY-MM-DD
        try:
            import re as _re
            m = _re.search(r"(\d{4}-\d{2}-\d{2})", str(date_str))
            if m:
                return datetime.strptime(m.group(1), "%Y-%m-%d")
        except Exception:
            pass
        return None

    def get_keyword_trend(self, keyword: str, granularity: str = "day", start_date: str | None = None, end_date: str | None = None):
        key = (keyword or "").strip()
        if not key:
            return []
        data = getattr(self, "news_data", []) or []
        start_dt = self._parse_date_str(start_date) if start_date else None
        end_dt = self._parse_date_str(end_date) if end_date else None
        counts = {}
        for item in data:
            kw_str = str(item.get("keywords", ""))
            kws = [k.strip() for k in kw_str.split(",") if k.strip()]
            if key not in kws:
                continue
            dt = self._parse_date_str(item.get("date", ""))
            if dt is None:
                continue
            if start_dt and dt < start_dt:
                continue
            if end_dt and dt > end_dt:
                continue
            if granularity == "hour":
                label = dt.strftime("%Y-%m-%d %H:00")
            elif granularity == "week":
                # ISO week label
                label = f"{dt.strftime('%Y')}-W{dt.isocalendar().week:02d}"
            else:
                label = dt.strftime("%Y-%m-%d")
            counts[label] = counts.get(label, 0) + 1
        def _label_to_dt(lbl: str):
            try:
                if granularity == "hour":
                    return datetime.strptime(lbl, "%Y-%m-%d %H:00")
                elif granularity == "week":
                    y, w = lbl.split("-W")
                    return datetime.fromisocalendar(int(y), int(w), 1)
                else:
                    return datetime.strptime(lbl, "%Y-%m-%d")
            except Exception:
                return datetime.min
        return [{"time": t, "count": counts[t]} for t in sorted(counts.keys(), key=_label_to_dt)]


def main():
    """测试函数"""
    # 创建搜索引擎实例
    search_engine = NewsSearchEngine()
    
    # 获取一些常见关键词用于测试
    top_keywords = search_engine.get_top_keywords(10)
    print("数据库中最常见的关键词:")
    for i, keyword in enumerate(top_keywords, 1):
        print(f"{i}. {keyword}")
    
    if top_keywords:
        # 使用第一个关键词进行测试
        test_keyword = top_keywords[0]
        print(f"\n使用关键词 '{test_keyword}' 进行搜索测试:")
        
        # 搜索相关新闻
        results = search_engine.search_by_keyword(test_keyword, top_k=5)
        
        for i, news in enumerate(results, 1):
            print(f"\n--- 新闻 {i} (相关性: {news['similarity_score']:.4f}) ---")
            print(f"日期: {news['date']}")
            print(f"原文: {news['original_text'][:100]}...")
            summary = search_engine.generate_summary(news['original_text'])
            print(f"摘要: {summary}")
            print("-" * 50)

        # 关键词热度趋势输出（按日粒度）
        trend = search_engine.get_keyword_trend(test_keyword, granularity="day")
        if trend:
            print("\n关键词热度趋势（按日）:")
            for point in trend[-15:]:
                print(f"{point['time']}: {point['count']}")
        else:
            print("\n没有可用的热度趋势数据。")



if __name__ == "__main__":
    main()