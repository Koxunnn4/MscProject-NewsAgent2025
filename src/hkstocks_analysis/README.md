# HKStocks Analysis Module

港股新闻分析模块，提供关键词提取和行业分类功能。

## 功能特性

- ✅ **关键词提取**: 使用 KeyBERT + jieba 分词提取新闻关键词
- ⏳ **行业分类**: 识别新闻相关的行业类别（待实现）

## 安装依赖

### 1. 安装 Python 包

```bash
pip install -r requirements.txt
```

### 2. 下载 spaCy 中文模型

```bash
python -m spacy download zh_core_web_sm
```

## 使用方法

### 1. 作为 Python 模块使用

```python
from src.hkstocks_analysis import get_hkstocks_analyzer

# 获取分析器实例（单例模式）
analyzer = get_hkstocks_analyzer()

# 提取关键词
text = "腾讯控股公布第三季度业绩，净利润同比增长39%"
keywords = analyzer.extract_keywords(text, top_n=10)

# 打印结果
for keyword, weight in keywords:
    print(f"{keyword}: {weight:.4f}")
```

### 2. 批量处理新闻数据

```bash
# 处理所有未处理的新闻
python src/hkstocks_analysis/process_keywords.py

# 只处理前 100 条新闻
python src/hkstocks_analysis/process_keywords.py --limit 100

# 查看统计信息
python src/hkstocks_analysis/process_keywords.py --stats
```

### 3. 运行测试

```bash
# 使用示例数据测试关键词提取
python test_hkstocks_analyzer.py
```

## 数据库表结构

### hkstocks_keywords 表

存储提取的关键词及其权重：

```sql
CREATE TABLE hkstocks_keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    news_id INTEGER NOT NULL,              -- 关联 hkstocks_news.id
    keyword TEXT NOT NULL,                 -- 关键词
    weight REAL NOT NULL,                  -- 权重（0-1之间）
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (news_id) REFERENCES hkstocks_news(id) ON DELETE CASCADE,
    UNIQUE(news_id, keyword)
);
```

## 技术架构

### 核心组件

1. **HKStocksAnalyzer**: 主分析器类
   - KeyBERT: 基于 BERT 的关键词提取
   - jieba: 中文分词
   - spaCy: 中文 NLP 处理

2. **停用词过滤**:
   - 基础停用词（中英文）
   - 金融领域特定停用词
   - 共 1201 个停用词

3. **文本预处理**:
   - 清理 AAStocks 特定格式
   - 移除 URL 和免责声明
   - 规范化空白字符

### 关键词提取流程

```
原始文本
   ↓
文本预处理 (清理格式、移除噪声)
   ↓
jieba 分词
   ↓
停用词过滤
   ↓
关键词验证 (长度、字符类型)
   ↓
KeyBERT 提取 (语义嵌入 + 多样性优化)
   ↓
返回 (关键词, 权重) 列表
```

## 配置参数

### KeyBERT 参数

- **模型**: `paraphrase-multilingual-MiniLM-L12-v2` (多语言)
- **ngram范围**: (1, 3) - 提取 1-3 个词的短语
- **多样性**: 0.3 - 平衡相关性和多样性
- **top_n**: 10 - 默认提取 10 个关键词

### 关键词验证规则

- ❌ 单个中文字符
- ❌ 单个英文字母
- ❌ 纯数字（年份除外: 1950-2050）
- ✅ 字母数字和中文的组合
- ✅ 长度 >= 2 的词

## 性能优化

- **单例模式**: 避免重复加载模型
- **批量处理**: 支持分批处理大量新闻
- **索引优化**: 对 keyword 和 news_id 建立索引

## 示例输出

### 输入新闻

```
标题: 騰訊控股公布第三季度業績 淨利潤同比增長39%
內容: 騰訊控股(00700.HK)今日公布2024年第三季度業績報告...
```

### 提取的关键词

```
1. 騰訊控股     (weight: 0.7234)
2. 第三季度     (weight: 0.6821)
3. 淨利潤       (weight: 0.6543)
4. 業績報告     (weight: 0.6012)
5. 金融科技     (weight: 0.5876)
6. 企業服務     (weight: 0.5432)
7. 遊戲業務     (weight: 0.5123)
8. 人工智能     (weight: 0.4987)
9. 雲計算       (weight: 0.4765)
10. 同比增長    (weight: 0.4321)
```

## 故障排查

### 模块导入错误

```bash
# 确保安装所有依赖
pip install -r requirements.txt

# 下载 spaCy 中文模型
python -m spacy download zh_core_web_sm
```

### Hugging Face 模型下载缓慢

代码已配置国内镜像源：
```python
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
```

### 关键词提取结果为空

1. 检查输入文本长度（至少 10 个字符）
2. 检查停用词列表是否过于严格
3. 调整 `top_n` 参数增加返回数量

## 未来扩展

- [ ] 实现行业分类功能
- [ ] 添加关键词趋势分析
- [ ] 支持关键词同义词映射
- [ ] 添加情感分析功能
- [ ] 优化关键词权重计算

## 参考

- 参照 `src/crypto_analysis/` 的实现架构
- KeyBERT: https://github.com/MaartenGr/KeyBERT
- spaCy: https://spacy.io/
- jieba: https://github.com/fxsjy/jieba
