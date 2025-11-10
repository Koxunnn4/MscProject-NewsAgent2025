"""
数据库同步管理器
实现新老数据库分离策略：
- testdb_realtime.db: 实时数据库（最近30天）
- testdb_history.db: 历史数据库（所有数据）

每月1号凌晨自动合并
"""
import os
import sys
import sqlite3
from datetime import datetime, timedelta
from typing import Optional
import logging
import schedule
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from config import PROJECT_ROOT as CONFIG_ROOT
from src.database.schema import ALL_TABLES

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DatabaseSyncManager:
    """数据库同步管理器"""
    
    def __init__(self, 
                 realtime_db_path: str = None,
                 history_db_path: str = None,
                 retention_days: int = 30):
        """
        初始化数据库同步管理器
        
        Args:
            realtime_db_path: 实时数据库路径
            history_db_path: 历史数据库路径
            retention_days: 实时库保留天数
        """
        self.realtime_db_path = realtime_db_path or os.path.join(
            CONFIG_ROOT, 'testdb_realtime.db'
        )
        self.history_db_path = history_db_path or os.path.join(
            CONFIG_ROOT, 'testdb_history.db'
        )
        self.retention_days = retention_days
        
        # 初始化数据库
        self._init_databases()
        
        logger.info(f"数据库同步管理器初始化完成")
        logger.info(f"  实时库: {self.realtime_db_path}")
        logger.info(f"  历史库: {self.history_db_path}")
        logger.info(f"  保留天数: {self.retention_days}天")
    
    def _init_databases(self):
        """初始化两个数据库（创建表结构）"""
        for db_path in [self.realtime_db_path, self.history_db_path]:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            for sql in ALL_TABLES:
                try:
                    cursor.execute(sql)
                except Exception as e:
                    logger.warning(f"创建表失败: {e}")
            
            conn.commit()
            conn.close()
        
        logger.info("✓ 数据库表结构初始化完成")
    
    def insert_realtime_news(self, news_data: dict, source_type: str = 'crypto'):
        """
        插入新闻到实时数据库
        
        Args:
            news_data: 新闻数据
            source_type: 'crypto' 或 'hkstock'
        """
        conn = sqlite3.connect(self.realtime_db_path)
        cursor = conn.cursor()
        
        try:
            if source_type == 'crypto':
                # 虚拟币新闻
                cursor.execute("""
                    INSERT OR REPLACE INTO messages 
                    (id, channel_id, message_id, text, date, keywords, industry)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    news_data.get('id'),
                    news_data.get('channel_id'),
                    news_data.get('message_id'),
                    news_data['text'],
                    news_data['date'],
                    news_data.get('keywords', ''),
                    news_data.get('industry', '')
                ))
            
            elif source_type == 'hkstock':
                # 港股新闻
                cursor.execute("""
                    INSERT OR IGNORE INTO hkstocks_news 
                    (title, url, content, publish_date, source, category, keywords)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    news_data.get('title'),
                    news_data.get('url'),
                    news_data['text'],
                    news_data['date'],
                    news_data.get('source', 'AAStocks'),
                    news_data.get('category', ''),
                    news_data.get('keywords', '')
                ))
            
            conn.commit()
            logger.debug(f"新闻已插入实时库 [类型: {source_type}]")
            
        except Exception as e:
            logger.error(f"插入实时库失败: {e}", exc_info=True)
            conn.rollback()
        finally:
            conn.close()
    
    def merge_to_history(self, cutoff_date: Optional[str] = None):
        """
        将旧数据从实时库迁移到历史库
        
        Args:
            cutoff_date: 截止日期（YYYY-MM-DD），默认为30天前
        """
        if cutoff_date is None:
            cutoff_date = (datetime.now() - timedelta(days=self.retention_days)
                          ).strftime('%Y-%m-%d')
        
        logger.info(f"开始数据迁移（截止日期: {cutoff_date}）...")
        
        realtime_conn = sqlite3.connect(self.realtime_db_path)
        history_conn = sqlite3.connect(self.history_db_path)
        
        try:
            # 1. 迁移虚拟币新闻（messages表）
            moved_crypto = self._merge_table(
                realtime_conn, history_conn,
                table_name='messages',
                date_column='date',
                cutoff_date=cutoff_date
            )
            
            # 2. 迁移港股新闻（hkstocks_news表）
            moved_hk = self._merge_table(
                realtime_conn, history_conn,
                table_name='hkstocks_news',
                date_column='publish_date',
                cutoff_date=cutoff_date,
                unique_column='url'
            )
            
            # 3. 迁移关键词数据
            moved_keywords = self._merge_related_keywords(
                realtime_conn, history_conn, cutoff_date
            )
            
            # 4. 迁移推送历史
            moved_push = self._merge_push_history(
                realtime_conn, history_conn, cutoff_date
            )
            
            logger.info("=" * 60)
            logger.info("数据迁移完成统计：")
            logger.info(f"  虚拟币新闻: {moved_crypto} 条")
            logger.info(f"  港股新闻: {moved_hk} 条")
            logger.info(f"  关键词记录: {moved_keywords} 条")
            logger.info(f"  推送历史: {moved_push} 条")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"数据迁移失败: {e}", exc_info=True)
        finally:
            realtime_conn.close()
            history_conn.close()
    
    def _merge_table(self, realtime_conn, history_conn,
                    table_name: str, date_column: str,
                    cutoff_date: str, unique_column: str = None) -> int:
        """
        迁移单个表的数据
        
        Args:
            realtime_conn: 实时库连接
            history_conn: 历史库连接
            table_name: 表名
            date_column: 日期列名
            cutoff_date: 截止日期
            unique_column: 唯一列名（用于去重）
            
        Returns:
            迁移的记录数
        """
        try:
            # 查询需要迁移的数据
            query = f"""
            SELECT * FROM {table_name}
            WHERE {date_column} < ?
            """
            
            realtime_cursor = realtime_conn.cursor()
            realtime_cursor.execute(query, (cutoff_date,))
            rows = realtime_cursor.fetchall()
            
            if not rows:
                logger.debug(f"表 {table_name} 无数据需要迁移")
                return 0
            
            # 获取列名
            columns = [desc[0] for desc in realtime_cursor.description]
            
            # 插入到历史库
            history_cursor = history_conn.cursor()
            
            placeholders = ','.join(['?' for _ in columns])
            if unique_column:
                # 使用 INSERT OR IGNORE 避免重复
                insert_sql = f"""
                INSERT OR IGNORE INTO {table_name} ({','.join(columns)})
                VALUES ({placeholders})
                """
            else:
                insert_sql = f"""
                INSERT OR REPLACE INTO {table_name} ({','.join(columns)})
                VALUES ({placeholders})
                """
            
            history_cursor.executemany(insert_sql, rows)
            history_conn.commit()
            
            moved_count = len(rows)
            
            # 从实时库删除
            delete_sql = f"""
            DELETE FROM {table_name}
            WHERE {date_column} < ?
            """
            realtime_cursor.execute(delete_sql, (cutoff_date,))
            realtime_conn.commit()
            
            logger.info(f"✓ 表 {table_name} 迁移 {moved_count} 条记录")
            
            return moved_count
            
        except Exception as e:
            logger.error(f"迁移表 {table_name} 失败: {e}", exc_info=True)
            return 0
    
    def _merge_related_keywords(self, realtime_conn, history_conn,
                                cutoff_date: str) -> int:
        """迁移关键词相关表"""
        moved = 0
        
        # 迁移 news_keywords 表
        try:
            realtime_cursor = realtime_conn.cursor()
            
            # 找出需要迁移的新闻ID
            realtime_cursor.execute("""
                SELECT id FROM messages WHERE date < ?
            """, (cutoff_date,))
            old_news_ids = [row[0] for row in realtime_cursor.fetchall()]
            
            if old_news_ids:
                # 查询关键词数据
                placeholders = ','.join(['?' for _ in old_news_ids])
                realtime_cursor.execute(f"""
                    SELECT * FROM news_keywords
                    WHERE news_id IN ({placeholders})
                """, old_news_ids)
                rows = realtime_cursor.fetchall()
                
                if rows:
                    # 插入历史库
                    history_cursor = history_conn.cursor()
                    history_cursor.executemany("""
                        INSERT OR IGNORE INTO news_keywords 
                        (id, news_id, keyword, weight, created_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, rows)
                    history_conn.commit()
                    
                    # 从实时库删除
                    realtime_cursor.execute(f"""
                        DELETE FROM news_keywords
                        WHERE news_id IN ({placeholders})
                    """, old_news_ids)
                    realtime_conn.commit()
                    
                    moved = len(rows)
                    logger.info(f"✓ news_keywords 迁移 {moved} 条记录")
        
        except Exception as e:
            logger.error(f"迁移 news_keywords 失败: {e}", exc_info=True)
        
        return moved
    
    def _merge_push_history(self, realtime_conn, history_conn,
                           cutoff_date: str) -> int:
        """迁移推送历史"""
        try:
            realtime_cursor = realtime_conn.cursor()
            
            # 查询旧推送记录
            realtime_cursor.execute("""
                SELECT * FROM push_history
                WHERE pushed_at < ?
            """, (cutoff_date,))
            rows = realtime_cursor.fetchall()
            
            if not rows:
                return 0
            
            # 插入历史库
            history_cursor = history_conn.cursor()
            history_cursor.executemany("""
                INSERT OR IGNORE INTO push_history 
                (id, subscription_id, news_id, pushed_at, status)
                VALUES (?, ?, ?, ?, ?)
            """, rows)
            history_conn.commit()
            
            # 从实时库删除
            realtime_cursor.execute("""
                DELETE FROM push_history
                WHERE pushed_at < ?
            """, (cutoff_date,))
            realtime_conn.commit()
            
            moved = len(rows)
            logger.info(f"✓ push_history 迁移 {moved} 条记录")
            
            return moved
            
        except Exception as e:
            logger.error(f"迁移 push_history 失败: {e}", exc_info=True)
            return 0
    
    def cleanup_old_data(self):
        """清理实时库中的旧数据（安全删除已迁移的数据）"""
        cutoff_date = (datetime.now() - timedelta(days=self.retention_days)
                      ).strftime('%Y-%m-%d')
        
        logger.info(f"清理实时库旧数据（{cutoff_date} 之前）...")
        
        conn = sqlite3.connect(self.realtime_db_path)
        cursor = conn.cursor()
        
        try:
            # 删除旧新闻
            cursor.execute("DELETE FROM messages WHERE date < ?", (cutoff_date,))
            deleted_crypto = cursor.rowcount
            
            cursor.execute("DELETE FROM hkstocks_news WHERE publish_date < ?", (cutoff_date,))
            deleted_hk = cursor.rowcount
            
            conn.commit()
            
            logger.info(f"✓ 清理完成: 虚拟币 {deleted_crypto} 条, 港股 {deleted_hk} 条")
            
        except Exception as e:
            logger.error(f"清理失败: {e}", exc_info=True)
        finally:
            conn.close()
    
    def schedule_monthly_merge(self):
        """定时任务：每月1号凌晨3点执行合并"""
        schedule.every().month.at("03:00").do(self.merge_to_history)
        
        logger.info("已设置定时任务：每月1号凌晨3点执行数据合并")
        
        while True:
            schedule.run_pending()
            time.sleep(3600)  # 每小时检查一次
    
    def get_database_stats(self) -> dict:
        """获取数据库统计信息"""
        stats = {
            'realtime': {},
            'history': {}
        }
        
        for db_type, db_path in [
            ('realtime', self.realtime_db_path),
            ('history', self.history_db_path)
        ]:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            try:
                # 统计各表记录数
                cursor.execute("SELECT COUNT(*) FROM messages")
                stats[db_type]['crypto_news'] = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM hkstocks_news")
                stats[db_type]['hk_news'] = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE is_active = 1")
                stats[db_type]['active_subscriptions'] = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM push_history")
                stats[db_type]['push_history'] = cursor.fetchone()[0]
                
                # 数据库文件大小
                stats[db_type]['file_size_mb'] = os.path.getsize(db_path) / (1024 * 1024)
                
            except Exception as e:
                logger.error(f"获取 {db_type} 统计失败: {e}")
            finally:
                conn.close()
        
        return stats


# 单例模式
_sync_manager = None

def get_db_sync_manager() -> DatabaseSyncManager:
    """获取数据库同步管理器单例"""
    global _sync_manager
    if _sync_manager is None:
        _sync_manager = DatabaseSyncManager()
    return _sync_manager


if __name__ == "__main__":
    # 测试数据库同步
    manager = get_db_sync_manager()
    
    print("=" * 70)
    print("数据库同步管理器测试")
    print("=" * 70)
    
    # 获取统计信息
    stats = manager.get_database_stats()
    print("\n【数据库统计】")
    print("\n实时库:")
    for key, value in stats['realtime'].items():
        print(f"  {key}: {value}")
    
    print("\n历史库:")
    for key, value in stats['history'].items():
        print(f"  {key}: {value}")
    
    # 测试迁移（可选，慎用）
    # print("\n【测试数据迁移】")
    # manager.merge_to_history()
    
    print("\n✓ 测试完成")

