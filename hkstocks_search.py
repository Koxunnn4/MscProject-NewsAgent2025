import logging
import sqlite3
from collections import Counter
from typing import Dict, List

from config import HISTORY_DB_PATH
from news_search import NewsSearchEngine

logger = logging.getLogger(__name__)


class HKStocksSearchEngine(NewsSearchEngine):
    """新闻搜索引擎的港股版本，读取 hkstocks_news 表"""

    def __init__(self, db_path: str = HISTORY_DB_PATH):
        super().__init__(db_path=db_path)

    def _load_news_data(self):
        """从港股新闻表加载数据"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, title, content, keywords, publish_date, url, source, category
                FROM hkstocks_news
                WHERE content IS NOT NULL AND content != ''
                ORDER BY publish_date DESC
                """
            )
            rows = cursor.fetchall()
            self.news_data = []

            for row in rows:
                news_id, title, content, keywords, publish_date, url, source, category = row
                title = title or self._derive_title(content)
                cleaned_text = self._clean_text(f"{title} {content}")
                if not cleaned_text:
                    continue
                original_text = f"{title}\n{content}" if content else title
                self.news_data.append({
                    'id': news_id,
                    'channel_id': 'hkstocks',
                    'title': title,
                    'text': cleaned_text,
                    'original_text': original_text,
                    'keywords': keywords or '',
                    'currency': category or '',
                    'date': publish_date,
                    'url': url or '',
                    'source': source or 'AAStocks',
                    'source_type': 'hkstocks'
                })

            conn.close()
        except Exception as e:
            logger.error(f"加载港股新闻数据失败: {e}")
            self.news_data = []

    def get_top_keywords_with_counts(self, limit: int = 20) -> List[Dict]:
        """港股关键词统计"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT keywords FROM hkstocks_news
                WHERE keywords IS NOT NULL AND keywords != ''
                """
            )
            rows = cursor.fetchall()
            conn.close()
            keyword_counter = Counter()
            for row in rows:
                kws = [k.strip() for k in str(row[0]).split(',') if k.strip()]
                for k in kws:
                    keyword_counter[k] += 1
            return [{"keyword": k, "count": c} for k, c in keyword_counter.most_common(limit)]
        except Exception as e:
            logger.error(f"获取港股关键词失败: {e}")
            return []
