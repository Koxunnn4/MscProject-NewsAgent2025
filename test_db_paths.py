#!/usr/bin/env python3
"""测试数据库路径和数据读取"""

import sqlite3
from config import HISTORY_DB_PATH, CRYPTO_DB_PATH

def test_database(db_path, db_name):
    """测试数据库连接和数据"""
    print(f"\n{'='*60}")
    print(f"测试数据库: {db_name}")
    print(f"路径: {db_path}")
    print(f"{'='*60}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 获取所有表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"\n表列表: {[t[0] for t in tables]}")
        
        # 检查messages表
        if any('messages' in t for t in tables):
            cursor.execute("SELECT COUNT(*) FROM messages;")
            count = cursor.fetchone()[0]
            print(f"\nmessages表记录数: {count}")
            
            if count > 0:
                cursor.execute("SELECT * FROM messages LIMIT 1;")
                sample = cursor.fetchone()
                cursor.execute("PRAGMA table_info(messages);")
                columns = [col[1] for col in cursor.fetchall()]
                print(f"列名: {columns}")
                print(f"\n示例数据 (前3个字段):")
                for i, col in enumerate(columns[:3]):
                    print(f"  {col}: {sample[i] if i < len(sample) else 'N/A'}")
        
        # 检查hkstocks_news表
        if any('hkstocks_news' in t for t in tables):
            cursor.execute("SELECT COUNT(*) FROM hkstocks_news;")
            count = cursor.fetchone()[0]
            print(f"\nhkstocks_news表记录数: {count}")
            
            if count > 0:
                cursor.execute("SELECT * FROM hkstocks_news LIMIT 1;")
                sample = cursor.fetchone()
                cursor.execute("PRAGMA table_info(hkstocks_news);")
                columns = [col[1] for col in cursor.fetchall()]
                print(f"列名: {columns}")
                print(f"\n示例数据 (前3个字段):")
                for i, col in enumerate(columns[:3]):
                    print(f"  {col}: {sample[i] if i < len(sample) else 'N/A'}")
        
        conn.close()
        print(f"\n✓ {db_name} 测试成功")
        
    except Exception as e:
        print(f"\n✗ {db_name} 测试失败: {e}")

if __name__ == "__main__":
    print("\n" + "="*60)
    print("数据库路径配置测试")
    print("="*60)
    
    test_database(CRYPTO_DB_PATH, "Crypto新闻数据库")
    test_database(HISTORY_DB_PATH, "港股数据库")
    
    print("\n" + "="*60)
    print("测试完成")
    print("="*60)
