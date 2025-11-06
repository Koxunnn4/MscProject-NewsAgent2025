# 本周工作报告 — Crypto 模块重构总结

时间：2025-11-06
作者：你的名字

---

## 概要
本周工作主要聚焦于 `crypto` 模块的重构与健壮性改进，重点文件为：

- `src/crawler/crpyto_news/crypto_analyzer.py`（重构与健壮性修复）
- `src/crawler/crpyto_news/similarity_analyzer.py`（整理与接口健全化）

目标：提高关键词提取与相似度分析的稳定性，在遇到极端文本（例如“只有停用词”）时不崩溃，并为离线相似度计算提供可靠的工具函数。

---

## 1. crypto 模块概览
本系统实现了从 Web3 新闻采集、分析的完整链路，包含实时消息处理、关键词提取、币种识别和数据分析四大核心模块。

消息源(Redis) → 文本预处理 → 关键词提取 + 币种识别 → 入库(SQLite) → 离线分析

- 实时处理模块：消息消费、文本清洗、特征提取、数据持久化
- 分析模块：统计分析、相似度计算、趋势识别

项目构成（`src/crawler/crpyto_news`）
```
coin_dict.json
config.yaml
consumer.py
crypto_analyzer.py
producer.py
run_crypto_crawler.py
similarity_analyzer.py
stopwords.txt
test_ana.ipynb
tg_session.session
```

---

### Telegram Crypto news sources
- @theblockbeats
- @news6551
- @MMSnews
- @TechFlowDaily

---

## 1.1 文本预处理（目标与策略）
目标：降低噪声，提升后续识别准确率

策略：
- 通用清洗：空格标准化、多行合并
- 频道定制：针对不同新闻源的特定格式（前缀、链接、特殊符号）进行适配清理

示例代码片段（节选自 `crypto_analyzer` 的预处理实现）：

```python
def news_preprocess(self, data):
    content = data['content']
    def clean_text(text):
        # 删除除了字母之间以外的所有空格
        text = re.sub(r'(?<![a-zA-Z]) | (?![a-zA-Z])', '', text)
        # 去掉所有空行,添加一个空格
        text = re.sub(r'\n+', ' ', text).strip()
        return text
    content = clean_text(content)

    if data['channel'] == '-1001387109317': # @theblockbeats
        content = re.sub(r'BlockBeats消息，', '', content)
        content = re.sub(r'^原文链接\s*\[.*?\]\(.*?\)\s*$', '', content, count=0, flags=re.M)

    # 针对其他频道的定制化清洗...

    data['content'] = content
    return data
```

---

## 1.2 关键词提取（实现与改进）
方案：jieba 中文分词 + 规则过滤 + KeyBERT 语义提取

流程细节：

1. 分词：使用 `jieba` 进行分词，过滤停用词（`stopwords.txt`）
2. 过滤规则：
   - 过滤单字
   - 单字母
   - 无意义数字（除年份）
   - 含特殊字符的 token

关键词过滤函数（节选）:

```python
def tokenize_and_filter(self, text):
    # 1. jieba分词
    tokens = jieba.lcut(text)
    # 2. 去除停用词
    if self.stopwords:
        tokens = [tok for tok in tokens if tok not in self.stopwords]
    # 3. 过滤不符合规则的词
    allowed_pattern = re.compile(r'^[A-Za-z0-9\u4e00-\u9fff]+$')
    def is_valid_keyword(w):
        if not w:
            return False
        w = w.strip()
        # 单独汉字、单字母、无意义数字、特殊字符等过滤
        ...
        return True
    filtered = [tok for tok in tokens if is_valid_keyword(tok)]
    return filtered
```

3. 调用 KeyBERT 提取关键词：

```python
self._kw_model = KeyBERT(model="paraphrase-multilingual-MiniLM-L12-v2")
keywords = self._kw_model.extract_keywords(
    text,
    vectorizer=vectorizer,
    keyphrase_ngram_range=(1, 3),
    top_n=top_n,
)
```

改动点（本周完成）：
- 增加对 `CountVectorizer` 警告的兼容处理：在传入自定义 `tokenizer` 时将 `token_pattern=None` 来避免 sklearn 的噪音警告。
- 当 KeyBERT 抛出 `empty vocabulary` 或其他异常（例如文档只包含停用词）时，新增后备逻辑：使用 `jieba` 分词 + `Counter` 词频作为兜底返回（防止服务因未捕获异常崩溃）。
- 修复了若 KeyBERT 提取失败导致未定义局部变量而抛出的 `UnboundLocalError`。

改进效果：在极端短文本或高噪声输入下系统不会中断，能返回合理的后备关键词（词频权重），保障下游流程稳定。

---

## 1.3 币种识别（实现与数据）
方法：词典映射 + spaCy PhraseMatcher

1. 词典：维护币种 ID 与别名映射（`coin_dict.json`），数据来源参照 CoinMarketCap 前 50

示例（词典结构）:

```json
{
  "Bitcoin": ["比特币", "BTC", "Bitcoin", "大饼"],
  "Ethereum": ["以太坊", "ETH", "Ethereum", "以太币"],
  ...
}
```

2. 匹配：使用 spaCy `PhraseMatcher` 提高匹配速度与稳定性

```python
def _build_matcher(self):
    patterns = []
    for synonyms in self.coin_dict.values():
        for name in synonyms:
            name_lower = name.lower()
            patterns.append(self.nlp.make_doc(name_lower))
    matcher = PhraseMatcher(self.nlp.vocab, attr="LOWER")
    matcher.add("COIN", patterns)
    return matcher
```

3. 容错：实现了英文大小写兼容，中文简体支持；后续可加入繁体和别名扩展。

---

## 2. `crypto_analyzer.py` 本周重构要点（详细）
改动范围与目的：提高关键词提取稳定性，修复异常流，添加兜底策略，增强数据库批量处理接口。

主要改动：
- 修复 KeyBERT 抛异常时可能触发的 `kw_results` 未定义问题。
- 将 `CountVectorizer` 调用中设置 `token_pattern=None`，避免 sklearn 关于 `token_pattern` 被忽略的警告。
- 在 KeyBERT 抛出异常时添加后备逻辑：使用 `tokenize_and_filter` + `Counter`，生成词频归一化权重作为返回值。
- 增强 `extract_keywords_batch`（数据库批量处理）逻辑，确保对 `news` 表逐条处理并将 `keywords` 与 `industry`（币种）写回数据库。

示例（后备提取逻辑）:

```python
try:
    kw_results = self.model.extract_keywords(...)
except Exception as e:
    print(f"关键词提取失败: {e}")
    tokens = self.tokenize_and_filter(text)
    if not tokens:
        return []
    cnt = Counter(tokens)
    total = sum(cnt.values()) or 1
    kw_results = [(tok, cnt[tok] / total) for tok, _ in cnt.most_common(top_n)]
```

验证方法：
- 单条文本（含大量停用词）测试，确保不会抛出 `UnboundLocalError`，且得到后备关键词列表或空列表。
- 在已有 `history.db` 上运行 `extract_keywords_batch` 以观察批量写回是否正确。

---

## 3. `similarity_analyzer.py` （本周整理与说明）
该文件实现了离线的关键词统计与相似度计算工具，主要功能包括：

- 支持按频道 / 时间范围筛选数据
- 统计 `keywords` / `industry` 列的频率及出现占比
- 使用 spaCy 向量计算高频关键词之间的相似度并按相似度降序输出
- 支持交互式查询：给定输入关键词，返回数据库中最相似的 top-N 关键词

关键接口与设计：

- `SimilarityAnalyzer(...).load_spacy_model()`：按优先级尝试加载 `zh_core_web_lg / zh_core_web_trf / zh_core_web_md / zh_core_web_sm`，保证尽量获得有向量的模型
- `fetch_column_data(column, channel_ids=None, time_range=None)`：支持频道与时间范围过滤
- `calculate_similarity(nlp, counter)`：从 `counter` 筛选高频词（>= min_count），构建 Doc 向量集合并两两计算相似度，按相似度排序输出
- `query_keyword_similarity(nlp, input_keyword, keyword_counter)`：为交互查询提供 top-10 相似词返回

本周整理要点：
- 将文件封装为 `SimilarityAnalyzer` 可复用类，外部可通过参数控制 `db_path / min_count / top_n` 等行为
- 增加对 channel/time 过滤的 SQL 构造，便于按来源或时间段分析
- 保持与 `crypto_analyzer` 一致的分词/小写处理策略，确保统计口径一致

---

## 4. 验证与运行示例
1. 手动运行 `similarity_analyzer.py`：

```bash
python src/crawler/crpyto_news/similarity_analyzer.py
```

交互步骤会让你选择时间范围与频道，脚本会输出统计和相似度结果。

2. 在 Python 中使用 `CryptoAnalyzer`：

```python
from src.crawler.crpyto_news.crypto_analyzer import get_crypto_analyzer
an = get_crypto_analyzer()
kw = an.extract_keywords(text, top_n=10)
print(kw)

# 计算数据库中高频关键词相似度（如果实现了同名函数）
pairs = an.calculate_relevance(r"E:\path\to\history.db", table="messages")
```

---

## 5. 遇到的问题与解决
- 问题：KeyBERT 在短文本或只有停用词时抛出 `empty vocabulary`，并导致局部变量未定义错误。
  - 解决：捕获异常，提供分词+词频后备方案，修复变量作用域，消除因异常导致的程序崩溃。

- 问题：sklearn 在传入自定义 tokenizer 时发出 `token_pattern` 警告。
  - 解决：显式把 `CountVectorizer(..., token_pattern=None)` 以压制该警告并保证行为一致。

- 问题：部分 spaCy 小模型（如 `zh_core_web_sm`）没有向量表示，无法用于语义相似度计算。
  - 解决：在 `similarity_analyzer.py`、`crypto_analyzer.py` 中加入模型优先加载逻辑，并在无向量情况下友好提示（建议安装 `zh_core_web_lg` 或 `zh_core_web_trf`）。

---

## 6. 后续计划（建议）
1. 把 `MIN_COUNT`、`top_n`、数据库路径等参数化为配置项（`config.yaml`）或命令行参数。
2. 将相似度计算结果支持导出为 CSV/JSON 以便可视化（Graph / Network）。
3. 为 `extract_keywords` 与相似度计算编写自动化单元测试（pytest）：覆盖正常文本 / 全停用词 / 空文本等场景。
4. 在生产部署时：将 KeyBERT 与模型下载的缓存目录改到数据盘（避免填满系统盘），并在 README 中写明依赖模型和 spaCy 模型安装步骤。

---

## 附录：本周关键代码位置
- `src/crawler/crpyto_news/crypto_analyzer.py` — 关键词提取、币种识别、DB 批量写回、错误兜底逻辑
- `src/crawler/crpyto_news/similarity_analyzer.py` — 离线统计、相似度分析、交互式查询

---

如果需要，我可以：
- 把报告转为 PPT 幻灯片大纲（每页 1-2 个要点 + 代码示例）以便组会展示；
- 将 `MIN_COUNT` 等参数配置化并把运行命令写入 `Makefile` 或小脚本；
- 编写 3 个 pytest 用例，自动验证 `extract_keywords` 在异常/极端输入下的行为。

请选择下一步，我会继续实现。