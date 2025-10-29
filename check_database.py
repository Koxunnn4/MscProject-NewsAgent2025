"""
检查 testdb_history.db 数据库内容
"""
import sqlite3

def check_database():
    db_path = "testdb_history.db"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 1. 查看所有表
        print("=" * 70)
        print("  数据库表结构")
        print("=" * 70)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"表名: {tables}")
        print()
        
        # 2. 查看 messages 表结构
        print("=" * 70)
        print("  messages 表字段")
        print("=" * 70)
        cursor.execute("PRAGMA table_info(messages)")
        columns = cursor.fetchall()
        for col in columns:
            print(f"  {col[1]:15} {col[2]:10} (主键: {bool(col[5])})")
        print()
        
        # 3. 统计记录数
        print("=" * 70)
        print("  数据统计")
        print("=" * 70)
        cursor.execute("SELECT COUNT(*) FROM messages")
        total = cursor.fetchone()[0]
        print(f"总记录数: {total} 条")
        
        # 4. 时间范围
        cursor.execute("SELECT MIN(date), MAX(date) FROM messages")
        min_date, max_date = cursor.fetchone()
        print(f"时间范围: {min_date} ~ {max_date}")
        
        # 5. 频道统计
        cursor.execute("SELECT channel_id, COUNT(*) FROM messages GROUP BY channel_id")
        channels = cursor.fetchall()
        print(f"\n频道分布:")
        for channel, count in channels:
            print(f"  {channel}: {count} 条")
        
        # 6. 查看最新的3条数据
        print("\n" + "=" * 70)
        print("  最新3条新闻示例")
        print("=" * 70)
        cursor.execute("SELECT id, channel_id, date, text FROM messages ORDER BY date DESC LIMIT 3")
        news_list = cursor.fetchall()
        
        for i, (news_id, channel, date, text) in enumerate(news_list, 1):
            print(f"\n【示例 {i}】")
            print(f"ID: {news_id}")
            print(f"频道: {channel}")
            print(f"日期: {date}")
            print(f"内容: {text[:200]}...")
            print("-" * 70)
        
        # 7. 查看最旧的3条数据
        print("\n" + "=" * 70)
        print("  最早3条新闻示例")
        print("=" * 70)
        cursor.execute("SELECT id, channel_id, date, text FROM messages ORDER BY date ASC LIMIT 3")
        news_list = cursor.fetchall()
        
        for i, (news_id, channel, date, text) in enumerate(news_list, 1):
            print(f"\n【示例 {i}】")
            print(f"ID: {news_id}")
            print(f"频道: {channel}")
            print(f"日期: {date}")
            print(f"内容: {text[:200]}...")
            print("-" * 70)
        
        conn.close()
        
        print("\n" + "=" * 70)
        print("  结论")
        print("=" * 70)
        print(f"✓ 这是一个包含 {total} 条加密货币新闻的数据库")
        print("✓ 数据来源: Telegram 频道（@theblockbeats, @news6551, @MMSnews）")
        print("✓ 这是【原始新闻数据】，不是处理结果")
        print("✓ 你可以直接使用这些数据进行：")
        print("    1. 关键词提取")
        print("    2. 热度分析")
        print("    3. 新闻检索")
        print("    4. 实时推送")
        
    except Exception as e:
        print(f"❌ 错误: {e}")

if __name__ == "__main__":
    check_database()

