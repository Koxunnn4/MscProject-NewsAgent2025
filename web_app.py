from fastapi import FastAPI, Request, Form, APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uvicorn
from news_search import NewsSearchEngine
import logging
from typing import Optional, List
import json
import os
import sys
from collections import Counter
import re
from datetime import datetime, timedelta

# --- Start of web_analyzer integration ---

# 添加项目根目录到路径，以便导入分析器模块
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from src.crypto_analysis.similarity_analyzer import SimilarityAnalyzer
    from src.crypto_analysis.model_loader import get_spacy_model
    ANALYZER_AVAILABLE = True
except ImportError as e:
    logging.warning(f"无法导入分析器模块，分析功能将不可用: {e}")
    ANALYZER_AVAILABLE = False
    SimilarityAnalyzer = None
    get_spacy_model = None

# 频道映射
CHANNEL_MAP = {
    "1": ("-1001387109317", "@theblockbeats"),
    "2": ("-1001735732363", "@TechFlowDaily"),
    "3": ("-1002395608815", "@news6551"),
    "4": ("-1002117032512", "@MMSnews"),
}

class WebSimilarityAnalyzer:
    """
    Web 版本的相似度分析器
    基于 SimilarityAnalyzer 的包装，提供 Web API 所需的接口
    """
    def __init__(self, db_path=r"src/crawler/crpyto_news/stream.db", table="messages",
                 keyword_column="keywords", currency_column="industry",
                 min_count=5, top_n=100):
        self.db_path = db_path
        self.table = table
        self.keyword_column = keyword_column
        self.currency_column = currency_column
        self.min_count = min_count
        self.top_n = top_n

        if ANALYZER_AVAILABLE:
            try:
                self.analyzer = SimilarityAnalyzer(
                    db_path=db_path, table=table, keyword_column=keyword_column,
                    currency_column=currency_column, min_count=min_count, top_n=top_n
                )
                logging.info(f"✓ 分析器初始化成功 | 数据库: {db_path}")
            except Exception as e:
                logging.error(f"✗ 分析器初始化失败: {e}")
                self.analyzer = None
        else:
            self.analyzer = None

    def get_total_rows(self, channel_ids=None, time_range=None):
        if not self.analyzer: return 0
        try:
            return self.analyzer.get_total_rows(channel_ids=channel_ids, time_range=time_range)
        except Exception as e:
            logging.error(f"获取总行数失败: {e}")
            return 0

    def fetch_column_data(self, column, channel_ids=None, time_range=None):
        if not self.analyzer: return []
        try:
            return self.analyzer.fetch_column_data(column=column, channel_ids=channel_ids, time_range=time_range)
        except Exception as e:
            logging.error(f"读取列数据失败: {e}")
            return []

    def count_items_with_occurrence(self, rows, case_insensitive=True):
        if not self.analyzer: return Counter(), Counter()
        try:
            return self.analyzer.count_items_with_occurrence(rows=rows, case_insensitive=case_insensitive)
        except Exception as e:
            logging.error(f"统计项目出现次数失败: {e}")
            return Counter(), Counter()

    def calculate_similarity(self, keyword_counter, limit=None):
        if not self.analyzer: return []
        try:
            pairs = self.analyzer.calculate_similarity(keyword_counter)
            limit = limit or self.top_n
            return pairs[:limit]
        except Exception as e:
            logging.error(f"计算相似度失败: {e}")
            return []

    def query_keyword_similarity(self, input_keyword, keyword_counter):
        if not self.analyzer: return False, []
        try:
            return self.analyzer.query_keyword_similarity(
                input_keyword=input_keyword, keyword_counter=keyword_counter, top_n=10
            )
        except Exception as e:
            logging.error(f"查询相似度失败: {e}")
            return False, []

# 初始化分析器实例
web_analyzer = WebSimilarityAnalyzer()

# --- End of web_analyzer integration ---

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(title="Web3新闻分析平台", description="一个集新闻搜索与关键词分析于一体的平台")

# 挂载 static 文件夹
app.mount("/static", StaticFiles(directory="static"), name="static")

# 配置模板目录
templates = Jinja2Templates(directory="templates_UI")

# 初始化搜索引擎
search_engine = NewsSearchEngine()

# 主页
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

# 新闻搜索页面
@app.get("/search", response_class=HTMLResponse)
async def search_page(request: Request, keyword: Optional[str] = None, top_k: int = 5):
    if keyword:
        return await search_news_get(request, keyword, top_k)
    
    top_keywords_counts = search_engine.get_top_keywords_with_counts(20)
    default_keyword = top_keywords_counts[0]["keyword"] if top_keywords_counts else ""
    
    if default_keyword:
        return await search_news_get(request, default_keyword, top_k)
    
    return templates.TemplateResponse("search_results.html", {
        "request": request, "keyword": "无", "results": [], "top_keywords_counts": [],
        "max_count": 1, "min_count": 0, "total_results": 0, 
        "trend_labels": "[]", "trend_counts": "[]"
    })

# 关键词分析器页面
@app.get("/analyzer", response_class=HTMLResponse)
async def analyzer_page(request: Request):
    return templates.TemplateResponse("analyzer.html", {"request": request})


# --- API for News Search ---

@app.get("/search_action", response_class=HTMLResponse)
async def search_news_get(request: Request, keyword: str, top_k: int = 5):
    try:
        results = search_engine.search_by_keyword(keyword, top_k)
        for news in results:
            news['summary'] = search_engine.generate_summary(news['original_text'])
        top_keywords_counts = search_engine.get_top_keywords_with_counts(20)
        max_count = max([item["count"] for item in top_keywords_counts]) if top_keywords_counts else 1
        min_count = min([item["count"] for item in top_keywords_counts]) if top_keywords_counts else 0
        trend_day = search_engine.get_keyword_trend(keyword, granularity="day")
        trend_labels = json.dumps([p['time'] for p in trend_day], ensure_ascii=False)
        trend_counts = json.dumps([p['count'] for p in trend_day], ensure_ascii=False)
        return templates.TemplateResponse("search_results.html", {
            "request": request,
            "keyword": keyword,
            "results": results,
            "top_keywords_counts": top_keywords_counts,
            "max_count": max_count,
            "min_count": min_count,
            "total_results": len(results),
            "trend_labels": trend_labels,
            "trend_counts": trend_counts,
        })
    except Exception as e:
        logger.error(f"搜索出错: {e}")
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_message": f"搜索出错: {str(e)}"
        })

@app.post("/search_action", response_class=HTMLResponse)
async def search_news_post(request: Request, keyword: str = Form(...), top_k: int = Form(5)):
    return await search_news_get(request, keyword, top_k)

# --- APIs for Keyword Analyzer ---

analyzer_router = APIRouter(prefix="/api")

@analyzer_router.get("/channels")
async def get_channels():
    """获取可用频道列表"""
    channels = [{'id': k, 'name': v[1], 'channel_id': v[0]} for k, v in CHANNEL_MAP.items()]
    return JSONResponse(content={'channels': channels})

@analyzer_router.post("/analyze")
async def analyze_data(request: Request):
    """分析数据的主要接口"""
    try:
        data = await request.json()
        channel_ids = data.get('channel_ids', [])
        time_range_str = data.get('time_range')

        logger.info(f"\n📊 开始分析...")
        logger.info(f"   频道 ID: {channel_ids}")
        logger.info(f"   时间范围: {time_range_str}")

        total_rows = web_analyzer.get_total_rows(channel_ids or None, time_range_str)
        logger.info(f"✓ 总行数: {total_rows}")

        keyword_rows = web_analyzer.fetch_column_data(web_analyzer.keyword_column, channel_ids or None, time_range_str)
        logger.info(f"✓ 读取关键词行数: {len(keyword_rows)}")
        keyword_counter, keyword_occurrence = web_analyzer.count_items_with_occurrence(keyword_rows)
        logger.info(f"✓ 关键词种类: {len(keyword_counter)}")

        currency_rows = web_analyzer.fetch_column_data(web_analyzer.currency_column, channel_ids or None, time_range_str)
        logger.info(f"✓ 读取币种行数: {len(currency_rows)}")
        currency_counter, currency_occurrence = web_analyzer.count_items_with_occurrence(currency_rows)
        logger.info(f"✓ 币种种类: {len(currency_counter)}")

        similarity_pairs = web_analyzer.calculate_similarity(keyword_counter, limit=50)
        similarity_results = [
            {'word1': a, 'count1': ca, 'word2': b, 'count2': cb, 'similarity': round(s, 4)}
            for a, ca, b, cb, s in similarity_pairs
        ]

        keyword_stats = []
        for word, count in keyword_counter.most_common():
            occur_count = keyword_occurrence[word]
            ratio = (occur_count / total_rows * 100) if total_rows > 0 else 0
            keyword_stats.append({'word': word, 'count': count, 'occur_count': occur_count, 'ratio': round(ratio, 2)})

        currency_stats = []
        for word, count in currency_counter.most_common():
            occur_count = currency_occurrence[word]
            ratio = (occur_count / total_rows * 100) if total_rows > 0 else 0
            currency_stats.append({'word': word, 'count': count, 'occur_count': occur_count, 'ratio': round(ratio, 2)})

        logger.info("✅ 分析完成\n")
        return JSONResponse(content={
            'success': True, 'total_rows': total_rows, 'keyword_stats': keyword_stats,
            'currency_stats': currency_stats, 'similarity_results': similarity_results,
            'keyword_total': len(keyword_counter), 'currency_total': len(currency_counter)
        })
    except Exception as e:
        logger.error(f"❌ 分析失败: {e}\n")
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={'success': False, 'error': str(e)})

@analyzer_router.post("/query-keyword")
async def query_keyword_similarity(request: Request):
    """查询关键词相似度"""
    try:
        data = await request.json()
        keyword = data.get('keyword', '').strip()
        channel_ids = data.get('channel_ids', [])
        time_range = data.get('time_range')

        logger.info(f"\n🔍 查询请求: '{keyword}'")
        if not keyword:
            return JSONResponse(status_code=400, content={'success': False, 'error': '请输入关键词'})

        keyword_rows = web_analyzer.fetch_column_data(web_analyzer.keyword_column, channel_ids or None, time_range)
        keyword_counter, _ = web_analyzer.count_items_with_occurrence(keyword_rows)
        
        exists, top_similar = web_analyzer.query_keyword_similarity(keyword, keyword_counter)
        similar_results = [{'word': word, 'count': count, 'similarity': round(similarity, 4)} for word, count, similarity in top_similar]

        logger.info(f"✅ 查询完成，找到 {len(similar_results)} 个相似词\n")
        return JSONResponse(content={'success': True, 'keyword': keyword, 'exists': exists, 'similar_words': similar_results})
    except Exception as e:
        logger.error(f"❌ 查询失败: {e}\n")
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={'success': False, 'error': str(e)})

app.include_router(analyzer_router)

# --- Original API endpoints (can be kept or refactored) ---


if __name__ == "__main__":
    uvicorn.run("web_app:app", host="127.0.0.1", port=8001, reload=True)