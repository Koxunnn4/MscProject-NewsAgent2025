"""
统一新闻数据接口
整合虚拟币和港股新闻源，提供统一的数据访问接口
"""
import os
import sys
from typing import List, Dict, Optional, Union
from datetime import datetime
from abc import ABC, abstractmethod

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.database.db_manager import get_db_manager
from src.crypto_analysis.crypto_analyzer import get_crypto_analyzer


class NewsSource(ABC):
    """新闻源抽象基类"""
    
    @abstractmethod
    def fetch_news(self, limit: int = 100) -> List[Dict]:
        """获取新闻"""
        pass
    
    @abstractmethod
    def extract_keywords(self, text: str) -> List[tuple]:
        """提取关键词"""
        pass
    
    @abstractmethod
    def save_to_db(self, news_data: Dict) -> int:
        """保存到数据库"""
        pass


class CryptoNewsSource(NewsSource):
    """虚拟币新闻源"""
    
    def __init__(self):
        self.db = get_db_manager()
        self.analyzer = get_crypto_analyzer()
        self.source_type = 'crypto'
    
    def fetch_news(self, limit: int = 100, db_path: str = None) -> List[Dict]:
        """
        从虚拟币数据库获取新闻
        
        Args:
            limit: 最多返回数量
            db_path: 数据库路径
            
        Returns:
            新闻列表
        """
        db_path = db_path or self.db.history_db_path
        query = """
        SELECT id, channel_id, message_id, text, date, keywords, industry
        FROM messages
        ORDER BY date DESC
        LIMIT ?
        """
        results = self.db.execute_query(query, (limit,), db_path)
        
        # 标准化格式
        return [self._standardize_format(news) for news in results]
    
    def extract_keywords(self, text: str, top_n: int = 10) -> List[tuple]:
        """提取关键词"""
        return self.analyzer.extract_keywords(text, top_n=top_n)
    
    def identify_currency(self, text: str) -> List[str]:
        """识别币种"""
        return self.analyzer.identify_currency(text)
    
    def save_to_db(self, news_data: Dict, db_path: str = None) -> int:
        """
        保存虚拟币新闻到数据库
        
        Args:
            news_data: 新闻数据字典
            db_path: 数据库路径
            
        Returns:
            新闻ID
        """
        db_path = db_path or self.db.history_db_path
        
        # 提取关键词和币种
        keywords = self.extract_keywords(news_data['text'])
        coins = self.identify_currency(news_data['text'])
        
        keywords_str = ','.join([kw[0] for kw in keywords]) if keywords else ''
        coins_str = ','.join(coins) if coins else ''
        
        # 插入或更新
        query = """
        INSERT OR REPLACE INTO messages 
        (id, channel_id, message_id, text, date, keywords, industry)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        
        self.db.execute_update(
            query,
            (
                news_data.get('id'),
                news_data.get('channel_id'),
                news_data.get('message_id'),
                news_data['text'],
                news_data['date'],
                keywords_str,
                coins_str
            ),
            db_path
        )
        
        return news_data.get('id') or self.db.get_last_insert_id(db_path)
    
    def _standardize_format(self, news: Dict) -> Dict:
        """标准化新闻格式"""
        return {
            'id': news['id'],
            'source_type': 'crypto',
            'channel_id': news['channel_id'],
            'message_id': news.get('message_id'),
            'text': news['text'],
            'title': news['text'][:100] + '...' if len(news['text']) > 100 else news['text'],
            'date': news['date'],
            'keywords': news.get('keywords', '').split(',') if news.get('keywords') else [],
            'industry': news.get('industry', '').split(',') if news.get('industry') else [],
            'url': None
        }


class HKStockNewsSource(NewsSource):
    """港股新闻源"""
    
    def __init__(self):
        self.db = get_db_manager()
        self.analyzer = get_crypto_analyzer()  # 复用关键词提取
        self.source_type = 'hkstock'
    
    def fetch_news(self, limit: int = 100, db_path: str = None) -> List[Dict]:
        """
        从港股数据库获取新闻
        
        Args:
            limit: 最多返回数量
            db_path: 数据库路径
            
        Returns:
            新闻列表
        """
        db_path = db_path or self.db.history_db_path
        query = """
        SELECT id, title, url, content, publish_date, source, category
        FROM hkstocks_news
        ORDER BY publish_date DESC
        LIMIT ?
        """
        results = self.db.execute_query(query, (limit,), db_path)
        
        # 标准化格式
        return [self._standardize_format(news) for news in results]
    
    def extract_keywords(self, text: str, top_n: int = 10) -> List[tuple]:
        """提取关键词"""
        return self.analyzer.extract_keywords(text, top_n=top_n)
    
    def save_to_db(self, news_data: Dict, db_path: str = None) -> int:
        """
        保存港股新闻到数据库
        
        Args:
            news_data: 新闻数据字典（HKStockNews.to_dict()格式）
            db_path: 数据库路径
            
        Returns:
            新闻ID
        """
        db_path = db_path or self.db.history_db_path
        
        # 提取关键词
        text = news_data.get('text', '')
        keywords = self.extract_keywords(text)
        keywords_str = ','.join([kw[0] for kw in keywords]) if keywords else ''
        
        # 插入或忽略（按URL去重）
        query = """
        INSERT OR IGNORE INTO hkstocks_news 
        (title, url, content, publish_date, source, category, keywords)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        
        self.db.execute_update(
            query,
            (
                news_data.get('title'),
                news_data.get('url'),
                news_data.get('text'),
                news_data.get('date'),
                news_data.get('source', 'AAStocks'),
                news_data.get('category', ''),
                keywords_str
            ),
            db_path
        )
        
        return self.db.get_last_insert_id(db_path)
    
    def _standardize_format(self, news: Dict) -> Dict:
        """标准化新闻格式"""
        # 提取关键词（如果数据库中有）
        keywords = news.get('keywords', '').split(',') if news.get('keywords') else []
        
        return {
            'id': news['id'],
            'source_type': 'hkstock',
            'channel_id': 'aastocks',
            'message_id': news['id'],
            'text': news['content'],
            'title': news['title'],
            'date': news['publish_date'],
            'keywords': keywords,
            'industry': [],
            'url': news.get('url'),
            'category': news.get('category', '')
        }


class UnifiedNewsInterface:
    """统一新闻接口"""
    
    def __init__(self):
        self.crypto_source = CryptoNewsSource()
        self.hkstock_source = HKStockNewsSource()
        self.db = get_db_manager()
    
    def fetch_all_news(self, limit: int = 100, source_type: str = 'all',
                       db_path: str = None) -> List[Dict]:
        """
        获取所有新闻（虚拟币+港股）
        
        Args:
            limit: 最多返回数量（每个源）
            source_type: 'all', 'crypto', 'hkstock'
            db_path: 数据库路径
            
        Returns:
            新闻列表（按日期倒序）
        """
        news_list = []
        
        if source_type in ['all', 'crypto']:
            crypto_news = self.crypto_source.fetch_news(limit, db_path)
            news_list.extend(crypto_news)
        
        if source_type in ['all', 'hkstock']:
            hkstock_news = self.hkstock_source.fetch_news(limit, db_path)
            news_list.extend(hkstock_news)
        
        # 按日期排序
        news_list.sort(key=lambda x: x['date'], reverse=True)
        
        return news_list[:limit] if source_type == 'all' else news_list
    
    def fetch_news_by_keyword(self, keyword: str, limit: int = 100,
                              source_type: str = 'all',
                              db_path: str = None) -> List[Dict]:
        """
        按关键词搜索新闻
        
        Args:
            keyword: 关键词
            limit: 最多返回数量
            source_type: 新闻源类型
            db_path: 数据库路径
            
        Returns:
            新闻列表
        """
        db_path = db_path or self.db.history_db_path
        news_list = []
        
        # 搜索虚拟币新闻
        if source_type in ['all', 'crypto']:
            crypto_query = """
            SELECT id, channel_id, message_id, text, date, keywords, industry
            FROM messages
            WHERE text LIKE ? OR keywords LIKE ? OR industry LIKE ?
            ORDER BY date DESC
            LIMIT ?
            """
            crypto_results = self.db.execute_query(
                crypto_query,
                (f'%{keyword}%', f'%{keyword}%', f'%{keyword}%', limit),
                db_path
            )
            news_list.extend([self.crypto_source._standardize_format(n) for n in crypto_results])
        
        # 搜索港股新闻
        if source_type in ['all', 'hkstock']:
            hkstock_query = """
            SELECT id, title, url, content, publish_date, source, category, keywords
            FROM hkstocks_news
            WHERE title LIKE ? OR content LIKE ? OR keywords LIKE ?
            ORDER BY publish_date DESC
            LIMIT ?
            """
            hkstock_results = self.db.execute_query(
                hkstock_query,
                (f'%{keyword}%', f'%{keyword}%', f'%{keyword}%', limit),
                db_path
            )
            news_list.extend([self.hkstock_source._standardize_format(n) for n in hkstock_results])
        
        # 按日期排序
        news_list.sort(key=lambda x: x['date'], reverse=True)
        
        return news_list[:limit]
    
    def extract_keywords(self, text: str, top_n: int = 10) -> List[tuple]:
        """统一关键词提取接口"""
        return self.crypto_source.extract_keywords(text, top_n)
    
    def save_news(self, news_data: Dict, source_type: str = 'crypto',
                  db_path: str = None) -> int:
        """
        保存新闻（自动识别类型）
        
        Args:
            news_data: 新闻数据
            source_type: 'crypto' 或 'hkstock'
            db_path: 数据库路径
            
        Returns:
            新闻ID
        """
        if source_type == 'crypto':
            return self.crypto_source.save_to_db(news_data, db_path)
        elif source_type == 'hkstock':
            return self.hkstock_source.save_to_db(news_data, db_path)
        else:
            raise ValueError(f"Unknown source_type: {source_type}")


# 单例模式
_unified_interface = None

def get_unified_news_interface() -> UnifiedNewsInterface:
    """获取统一新闻接口单例"""
    global _unified_interface
    if _unified_interface is None:
        _unified_interface = UnifiedNewsInterface()
    return _unified_interface


if __name__ == "__main__":
    # 测试统一接口
    interface = get_unified_news_interface()
    
    print("=" * 70)
    print("测试统一新闻接口")
    print("=" * 70)
    
    # 测试1: 获取所有新闻
    print("\n【测试1】获取所有新闻（前10条）")
    all_news = interface.fetch_all_news(limit=10)
    print(f"  共获取 {len(all_news)} 条新闻")
    for news in all_news[:3]:
        print(f"  - [{news['source_type']}] {news['title'][:50]}...")
    
    # 测试2: 按关键词搜索
    print("\n【测试2】搜索关键词'比特币'")
    bitcoin_news = interface.fetch_news_by_keyword('比特币', limit=5)
    print(f"  找到 {len(bitcoin_news)} 条相关新闻")
    
    # 测试3: 提取关键词
    print("\n【测试3】提取关键词")
    if all_news:
        keywords = interface.extract_keywords(all_news[0]['text'])
        print(f"  提取到 {len(keywords)} 个关键词")
        for kw, weight in keywords[:5]:
            print(f"    - {kw}: {weight:.4f}")
    
    print("\n✓ 测试完成")

