# 港股新闻爬虫模块

从 AAStocks 网站爬取港股新闻的爬虫模块。

## 功能特性

- 爬取指定时间范围内的港股新闻（默认最近1天）
- 支持URL和标题双重去重
- 自动保存到数据库
- 完整的错误处理和日志输出
- 可配置的请求头和延迟，避免反爬虫

## 模块结构

```
src/crawler/HKStocks/
├── __init__.py           # 模块初始化，导出主要接口
├── aastocks_scraper.py   # 爬虫核心实现
├── models.py             # 新闻数据模型
├── utils.py              # 工具函数（日期解析、URL处理等）
└── README.md             # 本文档
```

## 快速开始

### 1. 安装依赖

```bash
pip install beautifulsoup4 lxml requests
```

或使用项目的 requirements.txt:

```bash
pip install -r requirements.txt
```

### 2. 基本使用

#### 方式一：使用便捷函数（推荐）

```python
from src.crawler.HKStocks import scrape_hkstocks_news

# 爬取最近1天的新闻并保存到数据库
news_list = scrape_hkstocks_news(days=1, save_to_db=True)

print(f"成功爬取 {len(news_list)} 条新闻")
```

#### 方式二：使用爬虫类

```python
from src.crawler.HKStocks import AaStocksScraper

# 创建爬虫实例
scraper = AaStocksScraper()

# 爬取新闻
news_list = scraper.fetch_news(days=1)

# 保存到数据库
saved_count = scraper.save_to_database(news_list)
print(f"保存了 {saved_count} 条新闻")
```

#### 方式三：自定义配置

```python
from src.crawler.HKStocks import AaStocksScraper
import config

# 使用配置文件中的设置
scraper_config = {
    'base_url': config.HKSTOCKS_BASE_URL,
    'timeout': config.HKSTOCKS_REQUEST_TIMEOUT,
    'delay': config.HKSTOCKS_REQUEST_DELAY,
    'headers': config.HKSTOCKS_HEADERS
}

scraper = AaStocksScraper(config=scraper_config)
news_list = scraper.fetch_news(days=2)  # 爬取最近2天
```

### 3. 运行测试脚本

```bash
# 在项目根目录下运行
python test_hkstocks_crawler.py
```

测试脚本会：
1. 爬取最近1天的新闻
2. 显示前5条新闻详情
3. 询问是否保存到数据库

## API 文档

### `scrape_hkstocks_news()`

便捷函数，一键爬取港股新闻。

**参数:**
- `days` (int): 爬取最近几天的新闻，默认1
- `config` (dict, optional): 爬虫配置字典
- `save_to_db` (bool): 是否保存到数据库，默认True

**返回:**
- `List[HKStockNews]`: 新闻对象列表

**示例:**
```python
# 爬取最近3天的新闻
news = scrape_hkstocks_news(days=3)
```

---

### `AaStocksScraper` 类

AAStocks 爬虫核心类。

#### 初始化

```python
scraper = AaStocksScraper(config=None)
```

**参数:**
- `config` (dict, optional): 配置字典，可包含:
  - `base_url`: 目标网站URL
  - `timeout`: 请求超时时间（秒）
  - `delay`: 请求延迟（秒）
  - `headers`: HTTP请求头

#### 方法

##### `fetch_news(days=1)`

爬取新闻。

**参数:**
- `days` (int): 爬取最近几天的新闻

**返回:**
- `List[HKStockNews]`: 新闻对象列表

**异常:**
- `requests.RequestException`: 网络请求失败

**示例:**
```python
news_list = scraper.fetch_news(days=1)
```

##### `save_to_database(news_list, db_manager=None)`

保存新闻到数据库，自动去重。

**参数:**
- `news_list` (List[HKStockNews]): 新闻列表
- `db_manager` (optional): 数据库管理器实例

**返回:**
- `int`: 实际保存的新闻数量

**示例:**
```python
saved_count = scraper.save_to_database(news_list)
```

---

### `HKStockNews` 类

新闻数据模型。

#### 属性

- `title` (str): 新闻标题
- `url` (str): 新闻URL
- `content` (str): 新闻正文
- `publish_date` (datetime): 发布时间
- `source` (str): 新闻来源（默认"AAStocks"）
- `category` (str, optional): 新闻分类

#### 方法

##### `to_dict()`

转换为数据库兼容的字典格式。

**返回:**
```python
{
    'channel_id': 'aastocks',
    'message_id': 123456789,  # URL+标题的哈希值
    'text': '【标题】\n\n正文...',
    'date': '2025-11-05T14:30:00',
    'url': 'https://...',
    'title': '标题'
}
```

---

## 工具函数

### `parse_chinese_date(date_str)`

解析AAStocks日期格式 "2025/11/04 09:50 HKT"。

**参数:**
- `date_str` (str): 日期字符串

**返回:**
- `datetime`: 解析后的日期对象，失败返回None

---

### `normalize_url(url, base_url)`

规范化URL，处理相对路径。

---

### `is_within_days(date, days)`

判断日期是否在指定天数内。

---

### `generate_message_id(url, title)`

生成唯一的消息ID用于去重。

## 配置说明

在 `config.py` 中的配置项：

```python
# 港股新闻爬虫配置
HKSTOCKS_SOURCE_ID = 'aastocks'
HKSTOCKS_BASE_URL = 'http://www.aastocks.com/tc/stocks/news/aafn'
HKSTOCKS_REQUEST_TIMEOUT = 30  # 请求超时（秒）
HKSTOCKS_REQUEST_DELAY = 1.5   # 请求延迟（秒）
HKSTOCKS_HEADERS = {
    'User-Agent': '...',
    'Accept': '...',
    # ... 其他请求头
}
```

## 数据库结构

新闻存储在 `testdb_history.db` 的 `messages` 表中：

```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id TEXT,      -- 固定为 'aastocks'
    message_id INTEGER,   -- URL+标题的哈希值（用于去重）
    text TEXT NOT NULL,   -- 格式化后的新闻文本
    date TEXT NOT NULL    -- ISO 8601格式的日期
);
```

### 去重机制

使用双重去重策略：
1. **message_id**: URL和标题的哈希值
2. **text LIKE 模式**: 检查标题是否已存在

## 错误处理

### 常见错误及解决方案

#### 1. 网络连接失败

```
错误: 网络请求失败: Connection refused
```

**解决方案:**
- 检查网络连接
- 确认网站是否可访问
- 检查是否需要代理

#### 2. 请求超时

```
错误: 请求超时: http://...
```

**解决方案:**
- 增加超时时间: `config['timeout'] = 60`
- 检查网络速度

#### 3. HTTP错误

```
错误: HTTP错误 403: http://...
```

**解决方案:**
- 网站可能有反爬虫机制
- 尝试更换User-Agent
- 增加请求延迟

#### 4. 解析失败

```
无法解析日期格式: ...
```

**解决方案:**
- 网站HTML结构可能变化
- 需要更新 `_parse_news_list()` 方法
- 查看网页源码，调整CSS选择器

## 扩展开发

### 添加新的新闻源

1. 在 `src/crawler/` 下创建新文件夹，如 `USStocks/`
2. 参考 `HKStocks/` 的结构创建文件
3. 修改 `base_url` 和解析逻辑
4. 确保 `to_dict()` 返回相同格式

### 自定义解析逻辑

如果网站结构变化，需要修改 `aastocks_scraper.py` 中的：

1. `_parse_news_list()` - 新闻列表解析
2. `_fetch_news_detail()` - 新闻详情解析

参考BeautifulSoup文档：https://www.crummy.com/software/BeautifulSoup/

## 注意事项

1. **遵守网站条款**: 爬取前请阅读网站的robots.txt和使用条款
2. **适当延迟**: 避免频繁请求，建议至少1秒延迟
3. **数据隐私**: 不要爬取用户隐私信息
4. **错误处理**: 生产环境建议添加重试机制和告警
5. **定期维护**: 网站结构可能变化，需要定期检查和更新

## 示例代码

### 定时爬取

```python
import schedule
import time
from src.crawler.HKStocks import scrape_hkstocks_news

def job():
    """定时任务"""
    print("开始爬取港股新闻...")
    news = scrape_hkstocks_news(days=1)
    print(f"完成！爬取了 {len(news)} 条新闻")

# 每小时执行一次
schedule.every().hour.do(job)

while True:
    schedule.run_pending()
    time.sleep(60)
```

### 爬取并分析

```python
from src.crawler.HKStocks import scrape_hkstocks_news
from src.keyword_extraction.keyword_extractor import get_keyword_extractor

# 爬取新闻
news_list = scrape_hkstocks_news(days=1)

# 提取关键词
extractor = get_keyword_extractor()

for news in news_list:
    keywords = extractor.extract_keywords(news.content)
    print(f"{news.title}")
    print(f"关键词: {', '.join([kw['keyword'] for kw in keywords[:5]])}")
    print()
```

## 许可证

本模块为学术项目的一部分，仅供学习和研究使用。

## 关键词提取集成 (NEW)

### 功能说明

从 v1.1.0 开始，爬虫集成了自动关键词提取功能。爬取新闻后会自动提取关键词并保存到数据库的 `keywords` 字段。

### 使用方法

#### 1. 默认启用关键词提取

```python
from src.crawler.HKStocks import scrape_hkstocks_news

# 爬取新闻，自动提取关键词（默认行为）
news_list = scrape_hkstocks_news(days=1, save_to_db=True)
```

#### 2. 禁用关键词提取

```python
from src.crawler.HKStocks import AaStocksScraper

scraper = AaStocksScraper()
news_list = scraper.fetch_news(days=1)

# 保存时禁用关键词提取
scraper.save_to_database(news_list, extract_keywords=False)
```

### 关键词提取技术

- **模型**: KeyBERT (paraphrase-multilingual-MiniLM-L12-v2)
- **分词**: jieba 中文分词
- **停用词**: 1201个（包含金融领域术语）
- **提取数量**: 每条新闻 10 个关键词
- **输入**: 新闻标题 + 内容

详细信息请查看: [src/hkstocks_analysis/README.md](../../hkstocks_analysis/README.md)

### 数据库表结构更新

`hkstocks_news` 表新增 `keywords` 字段：

```sql
CREATE TABLE hkstocks_news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    content TEXT NOT NULL,
    publish_date TEXT NOT NULL,
    source TEXT DEFAULT 'AAStocks',
    category TEXT,
    keywords TEXT,                          -- 新增：关键词（逗号分隔）
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
```

### 关键词格式

关键词以逗号分隔的字符串存储：

```
腾讯控股,第三季度,净利润,业绩报告,金融科技,企业服务,游戏业务,人工智能,云计算,同比增长
```

解析示例：

```python
import sqlite3

conn = sqlite3.connect('data/news_analysis.db')
cursor = conn.cursor()

cursor.execute("""
    SELECT title, keywords
    FROM hkstocks_news
    WHERE keywords IS NOT NULL
    LIMIT 1
""")

title, keywords_str = cursor.fetchone()
keywords_list = keywords_str.split(',')

print(f"新闻: {title}")
print(f"关键词: {keywords_list}")
```

### 测试

运行集成测试：

```bash
# 检查数据库表结构
python test_crawler_with_keywords.py --check-schema

# 完整测试（爬取并提取关键词）
python test_crawler_with_keywords.py
```

### 依赖要求

关键词提取需要额外的依赖：

```bash
pip install keybert sentence-transformers spacy jieba
python -m spacy download zh_core_web_sm
```

如果缺少依赖，爬虫会自动降级为不提取关键词模式。

### 示例输出

```
开始爬取AAStocks新闻 (最近 1 天)...
汇总页面找到 45 条新闻链接
初始化关键词提取器...
Loading KeyBERT model...
关键词提取器已就绪

  ✓ [2025-11-12 14:30] 騰訊控股公布第三季度業績...
  + 保存新闻: 騰訊控股公布第三季度業績...
    关键词: 腾讯控股,第三季度,净利润,业绩报告,金融科技...

保存完成: 新增 5 条，更新 0 条，跳过重复 0 条
```

## 更新日志

### v1.1.0 (2025-11-12)
- ✨ 新增自动关键词提取功能
- ✨ 数据库表新增 keywords 字段
- ✨ 集成 KeyBERT + jieba 关键词提取
- 🔧 支持禁用关键词提取选项
- 📝 更新文档和测试脚本

### v1.0.0 (2025-11-05)
- 初始版本
- 支持AAStocks新闻爬取
- 实现URL+标题双重去重
- 添加完整的错误处理
