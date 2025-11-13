# 加密货币新闻相似度分析工具 - Web 版本

一个轻量级的 Web 应用，用于分析加密货币相关新闻数据，支持关键词统计、币种识别、相似度计算和关键词查询。

## ✨ 功能特性

- 📊 **数据统计**: 统计关键词和币种的出现频率及占比
- 🔗 **相似度分析**: 使用 spaCy 计算关键词之间的语义相似度
- 🔍 **关键词查询**: 输入感兴趣的关键词，查询最相似的 Top 10 结果
- 🔐 **时间筛选**: 支持按时间范围筛选数据（最近5分钟~30天）
- 📡 **频道筛选**: 支持按新闻源频道筛选数据
- 🎨 **美观界面**: 现代化、响应式的前端设计，支持各种设备

## 🚀 快速开始

### 1. 环境要求

- Python 3.8+
- Flask 3.0.0+
- spaCy 3.7.2+
- 中文 spaCy 模型（自动加载）

### 2. 安装依赖

```bash
# 安装 Python 依赖
pip install -r requirements_web.txt

# 下载中文 spaCy 模型（选择一个即可）
python -m spacy download zh_core_web_lg    # 最推荐（大模型，精度高）
python -m spacy download zh_core_web_md    # 中等大小
python -m spacy download zh_core_web_sm    # 最小（最快）
```

### 3. 运行应用

```bash
# 使用默认配置
python web_analyzer.py

# 自定义数据库路径
python web_analyzer.py --db-path ./stream.db

# 自定义服务端口
python web_analyzer.py --port 8080

# 自定义主机地址（允许远程访问）
python web_analyzer.py --host 0.0.0.0 --port 5000
```

### 4. 访问应用

启动成功后，在浏览器打开：
```
http://127.0.0.1:5000
```

## 📖 使用说明

### 基本流程

1. **选择筛选条件** (可选)
   - 选择时间范围（不选则不限制）
   - 选择一个或多个新闻源频道（不选则包含所有频道）

2. **点击「开始分析」按钮**
   - 系统会加载数据库中的数据
   - 计算统计信息和相似度

3. **查看结果**
   - **关键词统计**: 显示出现频率最高的关键词
   - **币种统计**: 显示提及最频繁的加密货币
   - **相似度分析**: 显示语义相似的关键词对
   - **关键词查询**: 输入关键词，查询最相似的 Top 10

### 标签页说明

#### 📝 关键词统计
- 显示数据范围内出现的所有关键词
- 按出现频率排序（默认显示 Top 50）
- 包含：序号、关键词、出现次数、出现行数、占比

#### 💰 币种统计
- 显示提及的所有加密货币
- 按出现频率排序
- 包含：序号、币种、出现次数、出现行数、占比

#### 🔗 相似度分析
- 显示语义相似的关键词对（前 50 对）
- 相似度分数：0-1（1 表示完全相同）
- 默认仅显示频率 ≥ 5 的关键词之间的相似度

#### 🔎 关键词查询
- 输入任意关键词，查询最相似的 Top 10 结果
- 显示是否存在于数据库中
- 与每个相似词的相似度百分比

## 🏗️ 项目结构

```
MscProject-NewsAgent2025-chenjingyin/
├── web_analyzer.py              # Flask 后端应用
├── requirements_web.txt         # Python 依赖清单
├── templates/
│   └── index.html              # 前端 HTML 模板
└── static/
    ├── style.css               # 前端样式
    └── app.js                  # 前端 JavaScript 逻辑
```

## 🔧 配置说明

### 数据库配置

编辑 `web_analyzer.py` 顶部的默认常量：

```python
DEFAULT_DB_PATH = r"path/to/your/database.db"    # 数据库路径
DEFAULT_TABLE = "messages"                        # 表名
DEFAULT_KEYWORD_COLUMN = "keywords"               # 关键词列名
DEFAULT_CURRENCY_COLUMN = "industry"              # 币种列名
DEFAULT_MIN_COUNT = 5                             # 相似度计算最小词频
DEFAULT_TOP_N = 100                               # 输出条数
```

### 频道配置

编辑 `web_analyzer.py` 中的 `CHANNEL_MAP` 字典：

```python
CHANNEL_MAP = {
    "1": ("-1001387109317", "@theblockbeats"),
    "2": ("-1001735732363", "@TechFlowDaily"),
    "3": ("-1002395608815", "@news6551"),
    "4": ("-1002117032512", "@MMSnews"),
}
```

## 🎯 API 端点

### POST /api/analyze
执行数据分析

**请求参数:**
```json
{
  "channel_ids": ["channel_id_1", "channel_id_2"],  // 可选，频道 ID 列表
  "time_range": ["2025-01-01T00:00:00Z", "2025-01-02T00:00:00Z"]  // 可选，时间范围
}
```

**响应:**
```json
{
  "success": true,
  "total_rows": 1000,
  "keyword_total": 150,
  "currency_total": 25,
  "keyword_stats": [...],
  "currency_stats": [...],
  "similarity_results": [...]
}
```

### POST /api/query-keyword
查询关键词相似度

**请求参数:**
```json
{
  "keyword": "Bitcoin",
  "channel_ids": [],  // 可选
  "time_range": null  // 可选
}
```

**响应:**
```json
{
  "success": true,
  "keyword": "Bitcoin",
  "exists": true,
  "similar_words": [
    {
      "word": "BTC",
      "count": 150,
      "similarity": 0.95
    },
    ...
  ]
}
```

### GET /api/channels
获取频道列表

**响应:**
```json
{
  "channels": [
    {
      "id": "1",
      "name": "@theblockbeats",
      "channel_id": "-1001387109317"
    },
    ...
  ]
}
```

## ⚠️ 注意事项

1. **spaCy 模型**: 首次加载模型时可能需要几秒钟，请耐心等待
2. **性能**: 大数据库可能导致分析速度变慢，建议设置合理的时间范围或频道过滤
3. **相似度计算**: 仅对频率 ≥ MIN_COUNT 的关键词进行计算，提高效率
4. **数据库**: 确保数据库路径正确且文件可读写权限正常
5. **时间格式**: 使用 ISO 8601 格式（UTC）

## 🐛 故障排除

### 问题：加载 spaCy 模型失败
**解决:**
```bash
python -m spacy download zh_core_web_lg
```

### 问题：无法连接数据库
**解决:**
- 检查数据库路径是否正确
- 确保数据库文件存在且可读

### 问题：分析时间过长
**解决:**
- 减少时间范围
- 选择特定频道进行筛选
- 增大 MIN_COUNT 值（减少参与计算的关键词数）

### 问题：前端不显示
**解决:**
- 检查 Flask 服务是否正常运行
- 清除浏览器缓存
- 尝试另一个浏览器或无痕窗口

## 📊 示例使用流程

### 分析场景 1：最近24小时 Telegram 新闻
1. 时间范围选择 → "最近24小时"
2. 频道选择 → 多选几个频道
3. 点击「开始分析」
4. 查看关键词、币种、相似度结果

### 分析场景 2：查询特定关键词的相关信息
1. 执行分析
2. 切换到「关键词查询」标签
3. 输入感兴趣的关键词，如 "DeFi"
4. 查看最相似的 Top 10 关键词

## 🛠️ 开发注意

### 扩展 API 端点

在 `web_analyzer.py` 中添加新路由：

```python
@app.route('/api/your-endpoint', methods=['POST'])
def your_endpoint():
    try:
        data = request.json
        # 您的逻辑
        return jsonify({'success': True, 'data': ...})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
```

### 自定义前端样式

编辑 `static/style.css`，遵循现有的 CSS 变量：

```css
:root {
    --primary-color: #667eea;
    --secondary-color: #764ba2;
    --success-color: #48bb78;
    /* ... */
}
```

## 📝 许可证

MIT License

## 👨‍💼 作者

基于 News Agent 项目开发的 Web 分析工具

---

**更新日期**: 2025年1月
**版本**: 1.0.0
