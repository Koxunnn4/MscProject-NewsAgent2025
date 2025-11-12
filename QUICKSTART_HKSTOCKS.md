# 港股新闻爬虫 + 关键词提取 快速开始

## 5分钟快速开始

### 步骤 1: 安装依赖

```bash
# 安装 Python 包
pip install -r requirements.txt

# 下载 spaCy 中文模型
python -m spacy download zh_core_web_sm
```

### 步骤 2: 运行爬虫

```bash
# 基本用法：爬取最近1天的新闻，自动提取关键词
python run_hkstocks_crawler.py
```

### 步骤 3: 查看结果

```python
import sqlite3

conn = sqlite3.connect('data/news_analysis.db')
cursor = conn.cursor()

# 查询最新的新闻和关键词
cursor.execute("""
    SELECT title, keywords, publish_date
    FROM hkstocks_news
    WHERE keywords IS NOT NULL
    ORDER BY publish_date DESC
    LIMIT 5
""")

for title, keywords, date in cursor.fetchall():
    print(f"\n标题: {title}")
    print(f"日期: {date}")
    print(f"关键词: {keywords}")
```

完成！✅

---

## 常用命令

```bash
# 爬取最近3天的新闻
python run_hkstocks_crawler.py --days 3

# 只爬取10条（测试用）
python run_hkstocks_crawler.py --max-count 10

# 不提取关键词（只爬取）
python run_hkstocks_crawler.py --no-keywords

# 测试模式（不保存数据库）
python run_hkstocks_crawler.py --no-save

# 查看帮助
python run_hkstocks_crawler.py --help
```

---

## Python 代码示例

### 示例 1: 基本用法

```python
from src.crawler.HKStocks import scrape_hkstocks_news

# 爬取新闻，自动提取关键词
news_list = scrape_hkstocks_news(days=1, save_to_db=True)
print(f"爬取了 {len(news_list)} 条新闻")
```

### 示例 2: 不提取关键词

```python
from src.crawler.HKStocks import AaStocksScraper

scraper = AaStocksScraper()
news_list = scraper.fetch_news(days=1)
scraper.save_to_database(news_list, extract_keywords=False)
```

### 示例 3: 查询关键词

```python
import sqlite3

conn = sqlite3.connect('data/news_analysis.db')
cursor = conn.cursor()

# 查询包含"腾讯"关键词的新闻
cursor.execute("""
    SELECT title, keywords
    FROM hkstocks_news
    WHERE keywords LIKE '%腾讯%'
""")

for title, keywords in cursor.fetchall():
    print(f"{title}: {keywords}")
```

---

## 测试

```bash
# 检查数据库表结构
python test_crawler_with_keywords.py --check-schema

# 完整测试（爬取5条新闻）
python test_crawler_with_keywords.py
```

---

## 故障排查

### 问题：ModuleNotFoundError

```bash
# 解决方案：安装依赖
pip install -r requirements.txt
python -m spacy download zh_core_web_sm
```

### 问题：爬取不到新闻

- 检查网络连接
- 确认能访问 www.aastocks.com
- 可能网站暂时没有新新闻

### 问题：关键词提取失败

爬虫会继续运行，只是关键词字段为 NULL。可以：
1. 使用 `--no-keywords` 跳过关键词提取
2. 检查依赖是否安装完整

---

## 更多信息

- 详细文档: [HKSTOCKS_INTEGRATION.md](HKSTOCKS_INTEGRATION.md)
- 爬虫文档: [src/crawler/HKStocks/README.md](src/crawler/HKStocks/README.md)
- 关键词提取: [src/hkstocks_analysis/README.md](src/hkstocks_analysis/README.md)
