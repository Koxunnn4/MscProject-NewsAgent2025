# 新闻分析系统

一个基于AI的新闻分析系统，支持关键词提取、热度分析、新闻摘要生成和实时推送功能。

## 🎯 项目简介

本系统专注于加密货币和港股新闻分析，提供以下核心功能：

1. **关键词提取**：使用 KeyBERT 自动提取新闻关键词
2. **新闻检索**：基于关键词相关性的智能新闻检索
3. **摘要生成**：自动生成新闻摘要（BART模型）
4. **热度分析**（Task 3）：分析关键词在时间维度的热度变化，支持可视化
5. **实时推送**（Task 4）：订阅关键词，自动推送相关新闻到 Telegram

## 📁 项目结构

```
project/
├── src/                          # 源代码
│   ├── keyword_extraction/       # 关键词提取模块
│   │   ├── keyword_extractor.py  # 关键词提取器（整合女同学代码）
│   │   └── summarizer.py         # 摘要生成器
│   ├── sentiment_analysis/       # 情感分析模块（预留）
│   ├── trend_analysis/           # 热度分析模块（Task 3）
│   │   └── trend_analyzer.py     # 趋势分析器（含可视化）
│   ├── push_system/              # 推送系统（Task 4）
│   │   └── push_manager.py       # 推送管理器
│   ├── database/                 # 数据库模块
│   │   ├── schema.py             # 数据库表结构
│   │   └── db_manager.py         # 数据库管理器
│   ├── crawler/                  # 爬虫模块（telegram-crypto）
│   └── utils/                    # 工具函数
│       └── helpers.py
├── api/                          # API 接口
│   └── app.py                    # Flask API 服务器
├── data/                         # 数据文件
├── docs/                         # 文档
├── tests/                        # 测试
├── logs/                         # 日志
├── config.py                     # 配置文件
├── main.py                       # 主程序入口
├── requirements.txt              # 依赖列表
└── README.md                     # 本文件
```

## 🚀 快速开始

### 1. 环境配置

#### linux 用户（使用 conda）

```
# 激活环境
conda activate py310
```

#### 安装依赖

```bash
# 完整安装（包含所有功能）
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 或分步安装
# 基础功能（关键词提取、数据库）
pip install pandas numpy scikit-learn keybert sentence-transformers jieba

# 可视化功能
pip install matplotlib seaborn

# API 服务器
pip install flask flask-cors

# 推送功能
pip install python-telegram-bot

# 摘要生成（可选，模型较大）
pip install torch transformers
```

### 2. 初始化系统

```bash
python main.py init
```

### 3. 运行功能演示

```bash
python main.py demo
```

### 4. 启动 API 服务器

```bash
python main.py api
```

访问：http://localhost:8000/api/health

### 5. 交互式模式

```bash
python main.py interactive
```

## 📊 核心功能

### Task 1 & 2: 关键词提取与新闻检索

```python
from src.keyword_extraction.keyword_extractor import get_keyword_extractor

# 初始化
extractor = get_keyword_extractor()

# 提取关键词
keywords = extractor.extract_keywords("比特币价格上涨...")

# 获取相关新闻
top_news = extractor.get_top_relevant_news("比特币", news_list, top_k=10)
```

### Task 3: 热度分析（含可视化）

```python
from src.trend_analysis.trend_analyzer import get_trend_analyzer

# 初始化
analyzer = get_trend_analyzer()

# 分析单个关键词
trend = analyzer.analyze_keyword_trend("比特币")

# 对比多个关键词
comparison = analyzer.compare_keywords(["比特币", "BTC", "Jupiter"])

# 生成可视化图表
analyzer.visualize_trend("比特币", save_path="data/trend.png")
```

### Task 4: 实时推送

```python
from src.push_system.push_manager import get_push_manager

# 初始化
push_manager = get_push_manager()

# 创建订阅
push_manager.subscribe(
    user_id="user_001",
    keyword="比特币",
    telegram_chat_id="123456789"
)

# 启动推送服务
import asyncio
asyncio.run(push_manager.run_push_service())
```

## 🔌 API 接口

### 新闻相关

- `GET /api/news/search?keyword=比特币&limit=10` - 搜索新闻
- `GET /api/news/<id>` - 获取新闻详情
- `GET /api/news/top?keyword=比特币&k=10` - 获取Top-K相关新闻

### 热度分析（Task 3）

- `GET /api/trend/keyword?keyword=比特币` - 获取关键词热度趋势
- `POST /api/trend/compare` - 对比多个关键词
- `GET /api/trend/hot-dates?keyword=比特币` - 获取最热门日期
- `GET /api/trend/visualize?keyword=比特币` - 生成可视化图表

### 订阅推送（Task 4）

- `POST /api/subscription/subscribe` - 创建订阅
- `DELETE /api/subscription/unsubscribe/<id>` - 取消订阅
- `GET /api/subscription/list/<user_id>` - 获取订阅列表

### 统计

- `GET /api/stats/overview` - 获取系统概况

## 📚 数据库设计

### messages 表（原始新闻）
- `id`: 主键
- `channel_id`: 频道ID
- `message_id`: 消息ID
- `text`: 新闻正文
- `date`: 发布日期

### news_keywords 表（关键词索引）
- `id`: 主键
- `news_id`: 新闻ID
- `keyword`: 关键词
- `weight`: 权重

### keyword_trends 表（热度缓存）
- `id`: 主键
- `keyword`: 关键词
- `date`: 日期
- `count`: 出现次数
- `total_weight`: 总权重

### subscriptions 表（用户订阅）
- `id`: 主键
- `user_id`: 用户ID
- `keyword`: 订阅关键词
- `telegram_chat_id`: Telegram聊天ID
- `is_active`: 是否激活

## 🎨 可视化示例

系统支持生成多种可视化图表：

1. **关键词热度趋势图**：折线图展示关键词随时间的热度变化
2. **多关键词对比图**：多条曲线对比不同关键词的热度
3. **热度排行柱状图**：展示关键词总计对比

## 🔧 配置说明

编辑 `config.py` 文件进行配置：

```python
# 数据库路径
DATABASE_PATH = 'data/news_analysis.db'
HISTORY_DB_PATH = 'testdb_history.db'

# Telegram Bot Token（Task 4 ）
TELEGRAM_BOT_TOKEN = 'YOUR_BOT_TOKEN_HERE'

# API 配置
API_HOST = '127.0.0.1'
API_PORT = 8000

# 其他配置...
```

### 接口对接

各模块通过 API 接口统一对接，前端通过 HTTP 请求调用后端功能。

## 📝 开发指南

### 添加新功能

1. 在相应的模块目录下创建新文件
2. 在 `api/app.py` 中添加 API 接口
3. 更新 `main.py` 添加命令行支持
4. 编写测试用例
5. 更新文档

### 数据库扩展

1. 在 `src/database/schema.py` 中定义新表
2. 在 `src/database/db_manager.py` 中添加操作方法
3. 运行 `python main.py init` 初始化新表

## 🐛 常见问题

### Q: KeyBERT 模型加载失败？
A: 检查网络连接，系统会自动使用国内镜像。首次加载需要下载模型。

### Q: BART 摘要效果不好？
A: BART主要针对英文，对中文支持有限。可以使用简单摘要方法，或替换为中文模型。

### Q: Telegram 推送不工作？
A: 检查 `config.py` 中的 `TELEGRAM_BOT_TOKEN` 是否配置正确。

### Q: 可视化图表中文乱码？
A: 系统已配置中文字体，如仍有问题，检查系统是否安装中文字体。

## 📄 许可证

本项目为学术项目，仅供学习使用。

## 👥 贡献者

- 项目成员：4人团队
- 指导老师：Jameschen