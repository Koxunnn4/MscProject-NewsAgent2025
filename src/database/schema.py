"""
数据库表结构定义
"""

# 新闻消息表（已存在于 testdb_history.db）
CREATE_MESSAGES_TABLE = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id TEXT,
    message_id INTEGER,
    text TEXT NOT NULL,
    date TEXT NOT NULL
);
"""

# 新闻关键词表（避免重复计算）
CREATE_NEWS_KEYWORDS_TABLE = """
CREATE TABLE IF NOT EXISTS news_keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    news_id INTEGER NOT NULL,
    keyword TEXT NOT NULL,
    weight REAL NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (news_id) REFERENCES messages(id),
    UNIQUE(news_id, keyword)
);
"""

# 关键词索引
CREATE_NEWS_KEYWORDS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_keyword 
ON news_keywords(keyword);
"""

CREATE_NEWS_ID_INDEX = """
CREATE INDEX IF NOT EXISTS idx_news_id 
ON news_keywords(news_id);
"""

# 关键词热度缓存表
CREATE_KEYWORD_TRENDS_TABLE = """
CREATE TABLE IF NOT EXISTS keyword_trends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT NOT NULL,
    date TEXT NOT NULL,
    count INTEGER DEFAULT 0,
    total_weight REAL DEFAULT 0.0,
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(keyword, date)
);
"""

# 关键词同义词映射表
CREATE_KEYWORD_SYNONYMS_TABLE = """
CREATE TABLE IF NOT EXISTS keyword_synonyms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT NOT NULL,
    representative_keyword TEXT NOT NULL,
    similarity REAL,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(keyword, representative_keyword)
);
"""

# 用户订阅表（Task 4）
CREATE_SUBSCRIPTIONS_TABLE = """
CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    keyword TEXT NOT NULL,
    push_channel TEXT DEFAULT 'telegram',
    telegram_chat_id TEXT,
    wechat_id TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(user_id, keyword)
);
"""

# 推送历史表
CREATE_PUSH_HISTORY_TABLE = """
CREATE TABLE IF NOT EXISTS push_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subscription_id INTEGER NOT NULL,
    news_id INTEGER NOT NULL,
    pushed_at TEXT DEFAULT (datetime('now')),
    status TEXT DEFAULT 'success',
    FOREIGN KEY (subscription_id) REFERENCES subscriptions(id),
    FOREIGN KEY (news_id) REFERENCES messages(id)
);
"""

# 新闻摘要缓存表
CREATE_NEWS_SUMMARIES_TABLE = """
CREATE TABLE IF NOT EXISTS news_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    news_id INTEGER NOT NULL UNIQUE,
    summary TEXT NOT NULL,
    method TEXT DEFAULT 'simple',
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (news_id) REFERENCES messages(id)
);
"""

# 情感分析结果表（预留给其他同学）
CREATE_SENTIMENT_ANALYSIS_TABLE = """
CREATE TABLE IF NOT EXISTS sentiment_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    news_id INTEGER NOT NULL UNIQUE,
    sentiment_score REAL,
    sentiment_label TEXT,
    confidence REAL,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (news_id) REFERENCES messages(id)
);
"""

# 港股新闻表（HKStocks专用）
CREATE_HKSTOCKS_NEWS_TABLE = """
CREATE TABLE IF NOT EXISTS hkstocks_news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    content TEXT NOT NULL,
    publish_date TEXT NOT NULL,
    source TEXT DEFAULT 'AAStocks',
    category TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
"""

# HKStocks新闻URL索引（用于快速去重）
CREATE_HKSTOCKS_URL_INDEX = """
CREATE INDEX IF NOT EXISTS idx_hkstocks_url
ON hkstocks_news(url);
"""

# HKStocks新闻日期索引（用于按日期查询）
CREATE_HKSTOCKS_DATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_hkstocks_date
ON hkstocks_news(publish_date DESC);
"""

# 新闻消息表索引（优化查询性能）
CREATE_MESSAGES_DATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_messages_date 
ON messages(date DESC);
"""

CREATE_MESSAGES_CHANNEL_INDEX = """
CREATE INDEX IF NOT EXISTS idx_messages_channel 
ON messages(channel_id, date);
"""

# 推送历史索引（用于快速查询是否已推送）
CREATE_PUSH_HISTORY_INDEX = """
CREATE INDEX IF NOT EXISTS idx_push_history_sub 
ON push_history(subscription_id, news_id);
"""

# 关键词热度趋势索引（用于热度查询）
CREATE_KEYWORD_TRENDS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_keyword_trends 
ON keyword_trends(keyword, date);
"""

# 所有表的创建语句列表
ALL_TABLES = [
    CREATE_MESSAGES_TABLE,
    CREATE_NEWS_KEYWORDS_TABLE,
    CREATE_NEWS_KEYWORDS_INDEX,
    CREATE_NEWS_ID_INDEX,
    CREATE_KEYWORD_TRENDS_TABLE,
    CREATE_KEYWORD_TRENDS_INDEX,
    CREATE_KEYWORD_SYNONYMS_TABLE,
    CREATE_SUBSCRIPTIONS_TABLE,
    CREATE_PUSH_HISTORY_TABLE,
    CREATE_PUSH_HISTORY_INDEX,
    CREATE_NEWS_SUMMARIES_TABLE,
    CREATE_SENTIMENT_ANALYSIS_TABLE,
    CREATE_HKSTOCKS_NEWS_TABLE,
    CREATE_HKSTOCKS_URL_INDEX,
    CREATE_HKSTOCKS_DATE_INDEX,
    CREATE_MESSAGES_DATE_INDEX,
    CREATE_MESSAGES_CHANNEL_INDEX
]

