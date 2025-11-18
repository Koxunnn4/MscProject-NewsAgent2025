# 📦 crpyto_news 说明

## 1. 目录定位

本目录为加密货币新闻爬虫与分析的主入口，负责数据采集、关键词分析、生产/消费队列、命令行工具等。

---

## 2. 主要功能模块

| 文件/模块                | 主要功能简介                                               |
|-------------------------|----------------------------------------------------------|
| `run_crypto_crawler.py` | 主爬虫入口，采集 Telegram 等渠道的加密新闻                |
| `consumer.py`           | 消费队列中的新闻数据，进行处理和入库                       |
| `producer.py`           | 生产队列，将采集到的原始新闻推送到消息队列                 |
| `keywords_analyzer.py`  | 关键词提取与分析，支持分词、去除停用词等                   |
| `similarity_analyzer_cli.py` | 命令行工具，批量计算关键词相似度，适合离线分析         |
| `coin_dict.json`        | 币种字典，辅助币种识别与归类                               |
| `config.yaml`           | 配置文件，定义爬虫参数、API 密钥、数据库路径等              |
| `stopwords.txt`         | 停用词表，提升关键词分析准确性                             |
| `tg_session.session`    | Telegram 会话缓存，避免频繁登录                            |

---

## 3. 快速开始

### 环境准备

1. 安装依赖包（建议使用 requirements.txt）
   ```bash
   pip install -r ../requirements.txt
   ```
2. 配置 Telegram API 密钥、数据库路径等（编辑 `config.yaml`）

### 启动爬虫

```bash
# 进入本目录
cd src/crawler/crpyto_news

# 启动主爬虫（采集新闻）
python run_crypto_crawler.py
# 在爬取新闻过程中自动执行关键词分析和币种分析
```

### 命令行相似度分析

```bash
python similarity_analyzer_cli.py --help
# 示例：分析关键词相似度
python similarity_analyzer_cli.py --input keywords.txt --output result.json
```

---

### 数据库关键词分析
```bash
# 对已有的数据库进行关键词和币种分析，没有爬取过程
python keywords_analyzer.py
```


## 4. 依赖说明

- Python >= 3.8
- 主要依赖：requests, telethon, jieba, pyyaml, tqdm, sqlite3, logging
- NLP/分析相关依赖建议参考项目根目录的 requirements.txt

---

## 5. 其他说明

- **币种字典**：`coin_dict.json` 可自定义扩展，支持主流币种和部分新币
- **停用词表**：`stopwords.txt` 可根据实际需求补充，提升分析效果
- **会话缓存**：`tg_session.session` 自动生成，无需手动修改
- **配置文件**：`config.yaml` 支持多渠道参数，建议每次部署前检查

---

## 6. 推荐工作流

1. 配置好 `config.yaml` 和依赖环境
2. 启动 `run_crypto_crawler.py` 采集新闻
3. 启动 `consumer.py` 进行数据消费和入库
4. 使用 `keywords_analyzer.py` 或 `similarity_analyzer_cli.py` 进行分析
5. 如需批量分析或离线处理，优先用 CLI 工具

---

## 7. 常见问题

- **Telegram 登录失败**：请检查 API 密钥和网络环境
- **数据库连接异常**：确认 `config.yaml` 路径配置正确
- **依赖缺失**：请先执行 `pip install -r ../requirements.txt`
- **分析结果为空**：检查输入数据格式和停用词表设置

---


