# 港股新闻采集与分析指南

> 本指南整合了原先分散在 `INSTALL_SELENIUM.md`、`PIPELINE_MODE.md`、`QUICKSTART_HKSTOCKS.md` 与 `src/hkstocks_analysis/README.md` 中的内容，并删除了已废弃的旧模式和脚本说明。阅读本文即可完成环境准备、爬虫运行、关键词/行业分析、数据验证与排障。

## 1. 功能概览

- **生产者-消费者爬虫**：单生产者 + 多消费者线程，边爬取边写入数据库。
- **Selenium 滚动加载（可选）**：突破静态汇总页约 30 条的限制，按需获取更多新闻。
- **关键词与行业分析**：KeyBERT + jieba + spaCy，最多返回 5 个关键词，并提供行业兜底分类（默认“其他”）。
- **持久化存储**：所有新闻写入 `testdb_history.db`（SQLite），可重复运行自动去重/更新长文内容。
- **批量回填工具**：`scripts/update_hkstocks_metadata.py` 用于为旧新闻补齐关键词与行业。

## 2. 环境准备

### 2.1 Python 依赖（推荐虚拟环境）

```bash
cd /Users/admin/code/MscProject-NewsAgent2025
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m spacy download zh_core_web_sm
```

> Hugging Face 模型已默认走 `https://hf-mirror.com`，首次运行会自动下载 `paraphrase-multilingual-MiniLM-L12-v2`。

### 2.2 可选：安装 Selenium + 浏览器驱动

Selenium 仅在需要滚动加载更多新闻时启用。

```bash
# 若尚未安装 Selenium（requirements 已含，可单独升级）
pip install selenium webdriver-manager

# macOS + Chrome 推荐
brew install --cask chromedriver
chromedriver --version

# 验证 Python 侧安装
python -c "import selenium; print(selenium.__version__)"
```

- **Safari**：macOS 自带，无需驱动；须在 Safari → 开发 → 允许远程自动化 中开启。
- **故障回退**：若 Selenium 初始化失败，爬虫会自动退回基础模式并给出提示。

## 3. Pipeline 工作流

```
          Producer (1)                     Consumer Pool (N)
  ┌────────────────────────┐      ┌─────────────────────────────┐
  │ 解析 AAStocks 汇总页    │ ---> │ 提取关键词+行业 → 写入 SQLite │
  │ (可选 Selenium 滚动)   │      │   自动去重/更新长内容        │
  └────────────────────────┘      └─────────────────────────────┘
```

- **队列**：容量 50，平衡下载与写库速度。
- **消费者线程**：默认 3 个，可通过 `--workers` 调整。建议 ≤5，避免 SQLite 锁竞争。
- **延迟**：生产端默认 0.5s，减少被封几率。

## 4. 运行方式

### 4.1 基本命令

```bash
python run_hkstocks_crawler.py
```

- 默认最近 1 天、最多 100 条、消费者 3 个、启用关键词/行业分析、Selenium 关闭。
- 新增/更新统计会在控制台实时输出。

### 4.2 常见参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--days` | 爬取最近 N 天 | `--days 3` |
| `--max-count` | 限制最大抓取数量 | `--max-count 200` |
| `--workers` | 消费者线程数 | `--workers 5` |
| `--use-selenium` | 启用 Selenium 滚动加载 | `--use-selenium --browser chrome` |
| `--browser` | 指定浏览器（`chrome` / `safari` / `firefox`）| `--use-selenium --browser safari` |
| `--no-keywords` | 跳过关键词与行业分析 | `--no-keywords` |
| `--no-save` | 仅测试爬取流程，不写库 | `--no-save --max-count 10` |

> 旧的 `--old-mode`、`scrape_hkstocks_news` 等功能已移除。

### 4.3 进阶示例

```bash
# Selenium + 大批量采集 + 5 个工作线程
python run_hkstocks_crawler.py --days 5 --max-count 500 --use-selenium --workers 5

# 快速冒烟：爬 5 条、不保存、观察日志
python run_hkstocks_crawler.py --max-count 5 --no-save
```

## 5. 结果验证与数据管理

### 5.1 查询最新写入

```python
import sqlite3
conn = sqlite3.connect('testdb_history.db')
cur = conn.cursor()
cur.execute("""
    SELECT title, publish_date, keywords, industry
    FROM hkstocks_news
    ORDER BY publish_date DESC
    LIMIT 5
""")
for title, date, keywords, industry in cur.fetchall():
    print(date, title, keywords, industry)
```

- 新增新闻：`keywords` 为逗号分隔的前 5 个词。
- 行业字段：若未匹配成功，则为“其他”。

### 5.2 回填旧数据

```bash
python scripts/update_hkstocks_metadata.py --limit 500
```

- 对历史库中缺少关键词/行业的记录重新跑分析器。
- 可配合 `--days`、`--force` 等参数（详见脚本帮助）。

### 5.3 性能测试

```bash
python test_pipeline_performance.py
```

- 对比不同线程数、Selenium 开关下的耗时，验证生产者-消费者模式收益。

## 6. 关键词与行业分析

| 能力 | 说明 |
|------|------|
| 关键词提取 | KeyBERT + jieba，自定义 `tokenize_and_filter`，默认最多返回 5 个关键词。 |
| 停用词 | `src/hkstocks_analysis/stopwords.txt`，包含金融领域特词，可自行扩展。 |
| 行业映射 | `src/hkstocks_analysis/hkstocks_industry.yaml`，新增“其他”兜底行业。 |
| 文本预处理 | 去除 AAStocks 前缀、URL、免责声明，并压缩空白字符。 |

**在代码中直接复用分析器：**

```python
from src.hkstocks_analysis.hkstocks_analyzer import get_hkstocks_analyzer

analyzer = get_hkstocks_analyzer()
text = "騰訊控股公布第三季度業績 淨利潤同比增長39%"
keywords = analyzer.extract_keywords(text, top_n=5)
industry = analyzer.identify_industry(text, top_n=1)
```

## 7. 常见问题

| 问题 | 处理方式 |
|------|----------|
| `ModuleNotFoundError` / spaCy 模型缺失 | 重新执行依赖安装与 `python -m spacy download zh_core_web_sm`。 |
| Selenium 启动失败或超时 | 确认浏览器驱动版本，或暂时去掉 `--use-selenium`，系统会自动回退基础模式。 |
| 消费者线程卡住 | 降低 `--workers`，同时确认 `testdb_history.db` 未被其他程序占用。 |
| 关键词提取缓慢 | 确保首次加载后模型已缓存；必要时减少线程或临时 `--no-keywords`。 |
| 关键词全为空 | 检查新闻内容是否过短、停用词是否过严，或执行回填脚本重新生成。 |

## 8. 后续规划（可选）

- 异步/协程版生产者。
- Redis / MQ 作为跨进程队列。
- 行业分类器模型化（替换关键字计数）。
- 关键词热度与推送 pipeline 的自动串联。

如需贡献或反馈，请直接在仓库提交 Issue / PR。
