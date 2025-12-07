# Web3 & 港股新闻智能体系统 - 技术报告

## 摘要

在信息爆炸的金融市场中，投资者每天面对来自 Telegram 群组、财经网站、社交媒体的海量新闻，如何从噪音中提取信号、捕捉市场趋势，成为一个核心痛点。本项目构建了一个**端到端的金融新闻智能体系统**，覆盖 **Web3/加密货币** 和 **香港股票市场** 两大领域，实现从数据采集、智能分析到个性化推送的完整闭环。系统已部署为可交互的 Web 应用，为投资者提供即时可用的市场洞察工具。

---

## 第一章：项目背景与目标

### 1.1 问题定义：信息过载与洞察缺失

现代金融市场的特点是信息高度碎片化：
- **Web3/加密货币领域**：核心信息散布在 Telegram 群组（如 @theblockbeats、@TechFlowDaily）中，以非结构化文本形式实时发布，传统搜索引擎无法索引。
- **港股市场**：专业财经网站（如 AAStocks）每日发布数百条快讯，但缺乏有效的聚合和趋势分析工具。

投资者面临的核心挑战：
1. **信息获取难**：需要同时监控多个 Telegram 频道和财经网站。
2. **趋势识别慢**：人工阅读无法快速识别"哪些概念正在升温"。
3. **个性化缺失**：无法针对关注的特定股票或概念获得实时提醒。

### 1.2 项目目标：构建金融新闻的"第二大脑"

本项目旨在解决上述痛点，构建一个**多数据源、智能分析、主动推送**的新闻智能体：

| 目标 | 具体能力 |
|------|----------|
| **数据聚合** | 自动采集 Telegram 加密货币频道 + AAStocks 港股新闻 |
| **智能分析** | 关键词提取、币种/股票识别、语义相似度计算、趋势可视化 |
| **精准检索** | 基于 TF-IDF 的语义搜索，超越简单关键词匹配 |
| **主动推送** | 用户订阅关键词，新消息匹配后通过 Telegram Bot 推送 |
| **统一交互** | 提供 Web 界面，一站式访问所有功能 |

### 1.3 项目价值：从"代码玩具"到"落地产品"

本项目不是一个孤立的技术演示，而是一个**故事闭环**的完整产品：

**用户故事**：
> 作为一名同时关注 Web3 和港股的投资者，我希望有一个工具能够：
> 1. 每天自动帮我收集 Telegram 和 AAStocks 的新闻；
> 2. 当有关于"以太坊 ETF"或"腾讯"的重要消息时，立刻通知我；
> 3. 让我能够搜索历史新闻，查看某个概念的热度变化趋势。

**本系统如何满足**：
1. **爬虫模块**：24/7 自动采集，用户无需手动刷新。
2. **推送模块**：订阅"以太坊"或"腾讯"后，匹配的新消息通过 Telegram Bot 即时推送。
3. **Web 应用**：提供搜索、分析、可视化功能，历史数据随时可查。

---

## 第二章：系统整体架构

### 2.1 四层架构设计

系统采用经典的分层架构，各层职责清晰、松耦合：

```
┌─────────────────────────────────────────────────────────────────┐
│                      展示层 (Presentation)                       │
│   FastAPI Web Server + Jinja2 SSR + Chart.js 可视化              │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      分析层 (Analysis)                           │
│   • CryptoAnalyzer: KeyBERT + spaCy 关键词提取                   │
│   • HKStocksAnalyzer: Jieba 分词 + 行业词典                      │
│   • SimilarityAnalyzer: TF-IDF + 余弦相似度                      │
│   • TrendAnalyzer: 时间序列热度统计                              │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      存储层 (Storage)                            │
│   SQLite 数据库                                                  │
│   • messages 表: Telegram 消息                                   │
│   • hkstocks_news 表: 港股新闻                                   │
│   • subscriptions 表: 用户订阅                                   │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      采集层 (Collection)                         │
│   • Telegram Producer/Consumer: 实时监听 + 历史回溯              │
│   • AAStocks Scraper: Selenium + BeautifulSoup 混合爬取          │
│   • Redis 消息队列: 解耦生产与消费                               │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 数据流全景

```
[Telegram Channels]              [AAStocks Website]
        │                                │
        ▼                                ▼
┌───────────────┐              ┌──────────────────┐
│ NewsProducer  │              │ AaStocksScraper  │
│ (Telethon)    │              │ (Selenium/HTTP)  │
└───────┬───────┘              └────────┬─────────┘
        │                                │
        ▼                                ▼
┌───────────────┐              ┌──────────────────┐
│ Redis Queue   │              │ Producer-Consumer│
│ (List)        │              │ Pipeline         │
└───────┬───────┘              └────────┬─────────┘
        │                                │
        ▼                                ▼
┌───────────────┐              ┌──────────────────┐
│ NewsConsumer  │              │ HKStocksAnalyzer │
│ + CryptoAnal. │              │ (KeyBERT+Jieba)  │
└───────┬───────┘              └────────┬─────────┘
        │                                │
        └────────────┬───────────────────┘
                     ▼
            ┌─────────────────┐
            │  SQLite Database │
            │  (Unified Schema)│
            └────────┬────────┘
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
┌─────────────┐ ┌──────────┐ ┌──────────────┐
│ Web Search  │ │ Analyzer │ │ Push Manager │
│ Engine      │ │ Dashboard│ │ (Telegram)   │
└─────────────┘ └──────────┘ └──────────────┘
```

---

## 第三章：核心模块技术详解

### 3.1 Crypto 新闻采集模块

#### 3.1.1 技术选型：Telethon + Redis

**为什么选择 Telethon？**

Telegram 官方 Bot API 只能接收发给 Bot 的消息，无法监听公开频道。Telethon 是一个基于 MTProto 协议的 Python 库，以"用户身份"登录 Telegram，能够：
- 监听任意公开频道的新消息（实时模式）
- 回溯获取频道历史消息（历史模式）

**为什么引入 Redis？**

采集和处理的速度不匹配：网络 I/O 快（毫秒级收到消息），但 NLP 处理慢（秒级提取关键词）。引入 Redis List 作为消息队列，实现**生产者-消费者解耦**：
- Producer 将原始消息 `LPUSH` 到队列
- Consumer 异步 `RPOP` 消费，避免阻塞

#### 3.1.2 实现细节

**Producer（`src/crawler/crpyto_news/producer.py`）**：
```
1. 初始化 TelegramClient，配置代理（支持国内访问）
2. 实时模式：注册 NewMessage 事件处理器，监听指定频道
3. 历史模式：iter_messages 遍历历史消息
4. 将消息格式化为 JSON，LPUSH 到 Redis
```

**Consumer（`src/crawler/crpyto_news/consumer.py`）**：
```
1. RPOP 从 Redis 获取消息
2. 调用 CryptoAnalyzer 提取关键词 + 识别币种
3. 写入 SQLite messages 表
```

**关键技术创新**：
- **币种识别**：加载 `coin_dict.json`（包含 BTC、ETH 等主流币种及其别名），使用 spaCy PhraseMatcher 进行快速匹配，从新闻中识别提及的币种。
- **中英混合分词**：使用 Jieba 处理中文，结合正则表达式提取英文缩写（如 ETF、SEC）。

---

### 3.2 港股新闻采集模块

#### 3.2.1 技术挑战：动态网页与反爬虫

AAStocks 网站的技术特点：
1. **无限滚动**：首页新闻列表使用 JavaScript 动态加载，传统 HTTP 请求只能获取首屏 ~20 条。
2. **反爬措施**：频繁请求会触发 IP 封禁。

#### 3.2.2 解决方案：Selenium 浏览器自动化

**什么是 Selenium？**

Selenium 是一个浏览器自动化框架，最初用于 Web 应用测试。它可以驱动真实的浏览器（Chrome/Firefox）执行操作，包括：
- 打开页面、执行 JavaScript
- 模拟用户滚动、点击
- 等待动态内容加载完成

**如何解决无限滚动？**

在 `aastocks_scraper.py` 中，当用户指定 `--use-selenium` 参数时：
1. 启动 Headless Chrome（无界面模式，节省资源）
2. 加载新闻列表页
3. 执行 `window.scrollTo(0, document.body.scrollHeight)` 模拟滚动
4. 等待新内容加载（通过检测页面高度变化或新元素出现）
5. 重复滚动直到达到目标数量或无新内容
6. 使用 BeautifulSoup 解析完整 HTML

**Fallback 策略**：
- 默认使用轻量级 HTTP 请求（快速但数量有限）
- 需要大量历史数据时启用 Selenium（慢但完整）

#### 3.2.3 生产者-消费者模式

`run_hkstocks_crawler.py` 实现了与 Crypto 类似的并发模式：

```
[主线程 - Producer]
    │
    ├── 获取新闻列表页
    ├── 解析新闻链接
    └── 将 (url, title) 放入 Queue
           │
           ├── [Worker 1] 获取详情页 → 提取关键词 → 写入 DB
           ├── [Worker 2] 获取详情页 → 提取关键词 → 写入 DB
           └── [Worker 3] 获取详情页 → 提取关键词 → 写入 DB
```

**优势**：
- 网络 I/O 并行化（3 个 Worker 同时请求）
- 主线程不阻塞，可提前发现新链接
- 数据库写入有序（每个 Worker 独立 commit）

---

### 3.3 关键词提取与 NLP 分析

#### 3.3.1 技术栈

| 工具 | 用途 | 适用场景 |
|------|------|----------|
| **KeyBERT** | 基于 BERT 的关键词提取 | 提取语义相关的关键短语 |
| **Jieba** | 中文分词 | 将连续汉字切分为词语 |
| **spaCy** | NER + 词性标注 | 识别专有名词、过滤无意义词 |
| **TF-IDF** | 词权重计算 | 搜索排序、相似度计算 |

#### 3.3.2 KeyBERT 关键词提取原理

KeyBERT 是一种基于 Transformer 的关键词提取方法，核心思想：
1. 使用预训练的 Sentence-BERT 模型将**整篇文档**编码为向量
2. 将文档中的**每个候选词/短语**也编码为向量
3. 计算候选词向量与文档向量的**余弦相似度**
4. 相似度最高的词即为"最能代表文档"的关键词

**为什么优于传统 TF-IDF？**
- TF-IDF 只考虑词频统计，无法理解语义
- KeyBERT 能识别同义词（如"涨"和"上升"语义接近）
- 支持多语言模型（`paraphrase-multilingual-MiniLM-L12-v2`）

#### 3.3.3 中文分词：Jieba + 自定义词典

**Jieba 分词原理**：
1. 基于前缀词典构建**有向无环图（DAG）**
2. 使用**动态规划**找到最大概率路径
3. 对未登录词使用 **HMM（隐马尔可夫模型）** 进行识别

**金融领域优化**：

系统加载自定义词典 `hkstocks_industry.yaml`，包含：
- 港股专有名词：恒指、北水、蓝筹、窝轮
- 公司名称：腾讯、阿里、美团
- 金融术语：做多、做空、爆仓

这确保"北水"不会被错误切分为"北"+"水"。

#### 3.3.4 停用词过滤

`stopwords.txt` 包含 ~500 个高频无意义词：
- 中文：的、是、在、了、和、与
- 英文：the、a、an、is、are
- 标点：，。！？

过滤后，关键词更精准反映文章主题。

---

### 3.4 语义搜索引擎

#### 3.4.1 TF-IDF 向量化

**TF-IDF（词频-逆文档频率）** 是信息检索领域的经典算法：

$$\text{TF-IDF}(t, d, D) = \text{TF}(t, d) \times \text{IDF}(t, D)$$

- **TF（词频）**：词 $t$ 在文档 $d$ 中的出现次数
- **IDF（逆文档频率）**：$\log \frac{|D|}{|\{d \in D : t \in d\}|}$，衡量词的稀有度

**直觉理解**：
- "的"在每篇文章都出现 → IDF 低 → 不重要
- "以太坊"只在少数文章出现 → IDF 高 → 重要

#### 3.4.2 搜索实现

`news_search.py` 的搜索流程：
1. 启动时，对所有新闻构建 TF-IDF 矩阵（`TfidfVectorizer`）
2. 用户输入关键词时，同样转换为 TF-IDF 向量
3. 计算关键词向量与每篇新闻的**余弦相似度**
4. 返回相似度最高的 Top-K 结果

**余弦相似度公式**：

$$\text{similarity}(A, B) = \frac{A \cdot B}{\|A\| \|B\|}$$

取值范围 [0, 1]，1 表示完全相同。

---

### 3.5 订阅与推送系统

#### 3.5.1 功能概述

用户可以通过 Web 界面订阅关键词（如"比特币"、"腾讯"）。当新消息到达且包含订阅词时，系统通过 Telegram Bot 发送推送。

#### 3.5.2 技术实现

**订阅存储**（`src/database/schema.py`）：
```sql
CREATE TABLE subscriptions (
    id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL,
    keyword TEXT NOT NULL,
    telegram_chat_id TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

**匹配算法**（`src/push_system/push_manager.py`）：
1. 新消息到达后，提取其关键词
2. 查询所有活跃订阅
3. 对每个订阅，检查新闻关键词是否包含订阅词
4. 匹配成功则调用 Telegram Bot API 发送消息

**推送限流**：
- 每用户每小时最多 10 条推送，防止骚扰
- 使用内存字典记录推送时间戳

---

### 3.6 Web 应用与可视化

#### 3.6.1 技术栈

- **FastAPI**：高性能 Python Web 框架，支持异步
- **Jinja2**：服务端模板引擎，动态生成 HTML
- **Chart.js**：前端图表库，绘制趋势图

#### 3.6.2 核心功能

| 页面 | 功能 |
|------|------|
| `/` (首页) | 数据源切换（Web3/港股）、最新新闻预览 |
| `/search` | 关键词搜索 + 结果列表 |
| `/analyzer` | 热门关键词统计、关键词相似度分析、趋势可视化 |

#### 3.6.3 多数据源架构

`web_app.py` 实现了**数据源无关**的设计：
```python
def get_search_engine(source_key: str) -> NewsSearchEngine:
    if source_key == "hkstocks":
        return HKStocksSearchEngine(db_path=HISTORY_DB_PATH)
    else:
        return NewsSearchEngine(db_path=CRYPTO_DB_PATH)
```

前端通过 `?source=hkstocks` 参数切换数据源，后端动态实例化对应的搜索引擎。

---

## 第四章：创新点总结

| 创新点 | 描述 |
|--------|------|
| **多数据源统一架构** | 同一套分析/展示代码支持 Crypto + 港股 |
| **混合爬虫策略** | HTTP 优先 + Selenium Fallback，平衡效率与完整性 |
| **生产者-消费者解耦** | Redis/Queue 实现采集与处理的异步流水线 |
| **语义搜索** | TF-IDF + Jieba 分词，超越简单关键词匹配 |
| **领域自适应 NLP** | 自定义词典 + 停用词表，适配金融文本特点 |
| **实时推送闭环** | 从爬取到推送的完整 Pipeline，无需人工干预 |

---

## 第五章：项目使用指南

### 5.1 环境准备

```bash
# 安装依赖
pip install -r requirements.txt

# 下载 spaCy 中文模型
python -m spacy download zh_core_web_sm
```

### 5.2 数据采集

```bash
# 港股新闻（最近 3 天，5 个 Worker）
python run_hkstocks_crawler.py --days 3 --workers 5

# 使用 Selenium 获取更多历史数据
python run_hkstocks_crawler.py --days 7 --use-selenium --max-count 500

# Crypto 新闻（需配置 Telegram API）
python src/crawler/crpyto_news/run_crypto_crawler.py
```

### 5.3 启动 Web 应用

```bash
python web_app.py
# 访问 http://127.0.0.1:8000
```

### 5.4 功能演示

1. **搜索**：输入"腾讯"，查看相关港股新闻
2. **分析**：进入 Analyzer 页面，查看热门关键词和趋势图
3. **切换数据源**：点击"Web3 新闻"/"港股新闻"切换

---

## 第六章：未来规划

1. **LLM 集成**：使用 GPT-4 生成新闻摘要、情感分析（看涨/看跌）
2. **跨市场相关性**：分析"比特币"与"港股科技股"的联动关系
3. **实时流水线**：将批处理爬虫升级为 24/7 服务 + WebSocket 推送
4. **移动端适配**：响应式 UI + PWA 支持

---

## 结语

本项目从真实的投资者痛点出发，构建了一个**完整、可用、可扩展**的金融新闻智能体。它不仅是一个技术演示，更是一个**故事闭环**的产品：用户可以实际使用它来监控市场、发现趋势、获取推送。未来，随着 LLM 和实时流处理技术的集成，这个平台有潜力成为金融信息领域的"智能助手"。

---

*文档生成时间：2025年11月26日*
*项目仓库：MscProject-NewsAgent2025*
