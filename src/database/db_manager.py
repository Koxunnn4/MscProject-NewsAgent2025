"""
数据库管理模块
"""
import sqlite3
from contextlib import contextmanager
from typing import List, Dict, Any, Optional
import os
import sys

# 添加项目根目录到路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from config import DATABASE_PATH, HISTORY_DB_PATH
from src.database.schema import ALL_TABLES


class DatabaseManager:
    """数据库管理类"""
    
    def __init__(self, db_path: str = None):
        """
        初始化数据库管理器
        
        Args:
            db_path: 数据库文件路径，默认使用配置文件中的路径
        """
        self.db_path = db_path or HISTORY_DB_PATH
        self.history_db_path = HISTORY_DB_PATH
        self._init_database()
    
    def _init_database(self):
        """初始化数据库，创建所有表"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for sql in ALL_TABLES:
                try:
                    cursor.execute(sql)
                except sqlite3.OperationalError as e:
                    # 忽略"表已存在"错误
                    if 'already exists' not in str(e):
                        print(f"Warning: Failed to execute SQL: {e}")
                except sqlite3.DatabaseError as e:
                    # 数据库损坏错误
                    print(f"Database error: {e}")
                    raise
            conn.commit()
    
    @contextmanager
    def get_connection(self, db_path: str = None):
        """
        获取数据库连接（上下文管理器）
        
        Args:
            db_path: 数据库路径，默认使用主数据库
            
        Yields:
            sqlite3.Connection: 数据库连接对象
        """
        path = db_path or self.db_path
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row  # 返回字典格式
        try:
            yield conn
        finally:
            conn.close()
    
    def execute_query(self, query: str, params: tuple = None, 
                     db_path: str = None) -> List[Dict[str, Any]]:
        """
        执行查询SQL
        
        Args:
            query: SQL查询语句
            params: 查询参数
            db_path: 数据库路径
            
        Returns:
            List[Dict]: 查询结果列表
        """
        with self.get_connection(db_path) as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            columns = [col[0] for col in cursor.description] if cursor.description else []
            results = []
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
            return results
    
    def execute_update(self, query: str, params: tuple = None,
                      db_path: str = None) -> int:
        """
        执行更新SQL（INSERT/UPDATE/DELETE）
        
        Args:
            query: SQL语句
            params: 参数
            db_path: 数据库路径
            
        Returns:
            int: 影响的行数
        """
        with self.get_connection(db_path) as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            conn.commit()
            return cursor.rowcount
    
    def execute_many(self, query: str, params_list: List[tuple],
                    db_path: str = None) -> int:
        """
        批量执行SQL
        
        Args:
            query: SQL语句
            params_list: 参数列表
            db_path: 数据库路径
            
        Returns:
            int: 影响的行数
        """
        with self.get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.executemany(query, params_list)
            conn.commit()
            return cursor.rowcount
    
    def get_last_insert_id(self, db_path: str = None) -> int:
        """获取最后插入的ID"""
        with self.get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT last_insert_rowid()")
            return cursor.fetchone()[0]
    
    # ==================== 新闻相关操作 ====================
    
    def get_news_by_date_range(self, start_date: str, end_date: str,
                               db_path: str = None) -> List[Dict]:
        """获取指定日期范围的新闻"""
        query = """
        SELECT id, channel_id, message_id, text, date
        FROM messages
        WHERE date >= ? AND date <= ?
        ORDER BY date
        """
        return self.execute_query(query, (start_date, end_date), 
                                 db_path or self.history_db_path)
    
    def get_news_by_keyword(self, keyword: str, limit: int = 100,
                           db_path: str = None) -> List[Dict]:
        """获取包含关键词的新闻"""
        query = """
        SELECT id, channel_id, message_id, text, date
        FROM messages
        WHERE text LIKE ?
        ORDER BY date DESC
        LIMIT ?
        """
        return self.execute_query(query, (f'%{keyword}%', limit),
                                 db_path or self.history_db_path)
    
    # ==================== 关键词相关操作 ====================
    
    def save_news_keywords(self, news_id: int, keywords: List[tuple]):
        """
        保存新闻关键词
        
        Args:
            news_id: 新闻ID
            keywords: [(keyword, weight), ...]
        """
        query = """
        INSERT OR REPLACE INTO news_keywords (news_id, keyword, weight)
        VALUES (?, ?, ?)
        """
        params = [(news_id, kw, weight) for kw, weight in keywords]
        return self.execute_many(query, params)
    
    def get_news_keywords(self, news_id: int) -> List[Dict]:
        """获取新闻的关键词"""
        query = """
        SELECT keyword, weight
        FROM news_keywords
        WHERE news_id = ?
        ORDER BY weight DESC
        """
        return self.execute_query(query, (news_id,))
    
    def check_keywords_exist(self, news_ids: List[int]) -> Dict[int, bool]:
        """检查哪些新闻已经提取过关键词"""
        if not news_ids:
            return {}
        
        placeholders = ','.join('?' * len(news_ids))
        query = f"""
        SELECT DISTINCT news_id
        FROM news_keywords
        WHERE news_id IN ({placeholders})
        """
        results = self.execute_query(query, tuple(news_ids))
        existing_ids = {row['news_id'] for row in results}
        return {nid: nid in existing_ids for nid in news_ids}
    
    # ==================== 热度趋势相关操作 ====================
    
    def save_keyword_trend(self, keyword: str, date: str, 
                          count: int, total_weight: float):
        """保存关键词热度数据"""
        query = """
        INSERT OR REPLACE INTO keyword_trends 
        (keyword, date, count, total_weight, updated_at)
        VALUES (?, ?, ?, ?, datetime('now'))
        """
        return self.execute_update(query, (keyword, date, count, total_weight))
    
    def get_keyword_trend(self, keyword: str, start_date: str = None,
                         end_date: str = None) -> List[Dict]:
        """获取关键词热度趋势"""
        if start_date and end_date:
            query = """
            SELECT date, count, total_weight
            FROM keyword_trends
            WHERE keyword = ? AND date >= ? AND date <= ?
            ORDER BY date
            """
            return self.execute_query(query, (keyword, start_date, end_date))
        else:
            query = """
            SELECT date, count, total_weight
            FROM keyword_trends
            WHERE keyword = ?
            ORDER BY date
            """
            return self.execute_query(query, (keyword,))
    
    # ==================== 同义词相关操作 ====================
    
    def save_keyword_synonym(self, keyword: str, representative: str, 
                            similarity: float):
        """保存关键词同义词映射"""
        query = """
        INSERT OR REPLACE INTO keyword_synonyms 
        (keyword, representative_keyword, similarity)
        VALUES (?, ?, ?)
        """
        return self.execute_update(query, (keyword, representative, similarity))
    
    def get_representative_keyword(self, keyword: str) -> Optional[str]:
        """获取关键词的代表词"""
        query = """
        SELECT representative_keyword
        FROM keyword_synonyms
        WHERE keyword = ?
        """
        results = self.execute_query(query, (keyword,))
        return results[0]['representative_keyword'] if results else keyword
    
    # ==================== 订阅相关操作（Task 4）====================
    
    def create_subscription(self, user_id: str, keyword: str,
                           telegram_chat_id: str = None) -> int:
        """创建订阅"""
        query = """
        INSERT OR REPLACE INTO subscriptions 
        (user_id, keyword, telegram_chat_id, is_active)
        VALUES (?, ?, ?, 1)
        """
        self.execute_update(query, (user_id, keyword, telegram_chat_id))
        return self.get_last_insert_id()
    
    def get_user_subscriptions(self, user_id: str) -> List[Dict]:
        """获取用户的订阅列表"""
        query = """
        SELECT id, keyword, telegram_chat_id, is_active, created_at
        FROM subscriptions
        WHERE user_id = ?
        ORDER BY created_at DESC
        """
        return self.execute_query(query, (user_id,))
    
    def get_keyword_subscribers(self, keyword: str) -> List[Dict]:
        """获取订阅某个关键词的用户"""
        query = """
        SELECT id, user_id, telegram_chat_id
        FROM subscriptions
        WHERE keyword = ? AND is_active = 1
        """
        return self.execute_query(query, (keyword,))
    
    def deactivate_subscription(self, subscription_id: int) -> int:
        """取消订阅"""
        query = """
        UPDATE subscriptions
        SET is_active = 0
        WHERE id = ?
        """
        return self.execute_update(query, (subscription_id,))
    
    def save_push_history(self, subscription_id: int, news_id: int, 
                         status: str = 'success') -> int:
        """保存推送历史"""
        query = """
        INSERT INTO push_history (subscription_id, news_id, status)
        VALUES (?, ?, ?)
        """
        self.execute_update(query, (subscription_id, news_id, status))
        return self.get_last_insert_id()
    
    def check_news_pushed(self, subscription_id: int, news_id: int) -> bool:
        """检查新闻是否已推送"""
        query = """
        SELECT COUNT(*) as count
        FROM push_history
        WHERE subscription_id = ? AND news_id = ?
        """
        results = self.execute_query(query, (subscription_id, news_id))
        return results[0]['count'] > 0 if results else False


# 单例模式
_db_manager = None

def get_db_manager() -> DatabaseManager:
    """获取数据库管理器单例"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


if __name__ == "__main__":
    # 测试数据库初始化
    db = get_db_manager()
    print("✓ 数据库初始化成功")
    
    # 测试查询
    news = db.get_news_by_keyword("比特币", limit=5)
    print(f"✓ 找到 {len(news)} 条包含'比特币'的新闻")

