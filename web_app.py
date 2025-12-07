from fastapi import FastAPI, Request, Form, APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uvicorn
from news_search import NewsSearchEngine
from hkstocks_search import HKStocksSearchEngine
import logging
from typing import Optional, List, Dict
import json
import os
import sys
from collections import Counter
import re
from datetime import datetime, timedelta
from config import HISTORY_DB_PATH, CRYPTO_DB_PATH

# --- Start of web_analyzer integration ---

# 添加项目根目录到路径，以便导入分析器模块
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
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

SOURCE_OPTIONS = [
    {"key": "hkstocks", "label": "港股新闻"},
    {"key": "crypto", "label": "Web3 新闻"}
]
SOURCE_LABEL_MAP = {item["key"]: item["label"] for item in SOURCE_OPTIONS}
DEFAULT_SOURCE = "hkstocks"
SOURCE_BADGES = {"crypto": "Web3", "hkstocks": "港股"}


def normalize_source(source: Optional[str]) -> str:
    if not source:
        return DEFAULT_SOURCE
    key = str(source).lower()
    return key if key in SOURCE_LABEL_MAP else DEFAULT_SOURCE


_search_engine_cache: Dict[str, NewsSearchEngine] = {}


def get_search_engine(source_key: str) -> NewsSearchEngine:
    key = normalize_source(source_key)
    if key not in _search_engine_cache:
        if key == "hkstocks":
            _search_engine_cache[key] = HKStocksSearchEngine(db_path=HISTORY_DB_PATH)
        else:
            _search_engine_cache[key] = NewsSearchEngine(db_path=CRYPTO_DB_PATH)
    return _search_engine_cache[key]


def _split_keywords(raw_keywords: Optional[str]) -> List[str]:
    return [k.strip() for k in str(raw_keywords or "").split(',') if k.strip()]


def _enhance_news_results(results: List[Dict]):
    for news in results:
        news.setdefault('source_type', 'crypto')
        news['source_badge'] = SOURCE_BADGES.get(news['source_type'], 'News')
        news['keyword_list'] = _split_keywords(news.get('keywords', ''))
        if not news.get('title'):
            news['title'] = (news.get('text') or '')[:80]
        news['source'] = news.get('source') or (news.get('channel_id') or 'Web3 Feed')

class WebSimilarityAnalyzer:
    """面向 Web 的多数据源相似度分析调度器"""

    def __init__(self):
        self.source_configs: Dict[str, Dict] = {}
        if ANALYZER_AVAILABLE:
            self._init_sources()
        else:
            logging.warning("SimilarityAnalyzer 模块不可用，关键词分析接口将被禁用")

    def _load_stopwords(self, path: str) -> set:
        stopwords = set()
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    stopwords = set(line.strip() for line in f if line.strip())
                logging.info(f"Loaded {len(stopwords)} stopwords from {path}")
            else:
                logging.warning(f"Stopwords file not found at {path}")
        except Exception as e:
            logging.error(f"Error loading stopwords from {path}: {e}")
        return stopwords

    def _init_sources(self):
        configs: Dict[str, Dict] = {}
        try:
            configs["crypto"] = {
                "label": SOURCE_LABEL_MAP["crypto"],
                "analyzer": SimilarityAnalyzer(
                    db_path=CRYPTO_DB_PATH,
                    table="messages",
                    keyword_column="keywords",
                    currency_column="currency",
                    channel_column="channel_id",
                    date_column="date",
                    min_count=5,
                    top_n=100
                ),
                "keyword_column": "keywords",
                "currency_column": "currency",
                "supports_channels": True,
                "channels": CHANNEL_MAP
            }

            hkstocks_stopwords_path = os.path.join(PROJECT_ROOT, 'src', 'hkstocks_analysis', 'stopwords.txt')
            hkstocks_stopwords = self._load_stopwords(hkstocks_stopwords_path)

            configs["hkstocks"] = {
                "label": SOURCE_LABEL_MAP["hkstocks"],
                "analyzer": SimilarityAnalyzer(
                    db_path=HISTORY_DB_PATH,
                    table="hkstocks_news",
                    keyword_column="keywords",
                    currency_column="industry",
                    channel_column=None,
                    date_column="publish_date",
                    min_count=2,
                    top_n=100,
                    stopwords=hkstocks_stopwords
                ),
                "keyword_column": "keywords",
                "currency_column": "industry",
                "supports_channels": False,
                "channels": {}
            }
            logging.info("✓ 多数据源分析器初始化完成")
        except Exception as e:
            logging.error(f"初始化分析器失败: {e}")
        self.source_configs = configs

    def _get_config(self, source_key: str) -> Optional[Dict]:
        if not self.source_configs:
            return None
        return self.source_configs.get(source_key) or self.source_configs.get(DEFAULT_SOURCE)

    def _get_analyzer(self, source_key: str):
        config = self._get_config(source_key)
        return config.get("analyzer") if config else None

    def supports_channels(self, source_key: str) -> bool:
        config = self._get_config(source_key)
        return bool(config and config.get("supports_channels"))

    def get_channels(self, source_key: str) -> List[Dict]:
        config = self._get_config(source_key)
        if not config:
            return []
        channels = config.get("channels", {})
        return [
            {'id': key, 'name': meta[1], 'channel_id': meta[0]}
            for key, meta in channels.items()
        ]

    def _sanitize_channels(self, source_key: str, channel_ids: Optional[List[str]]) -> Optional[List[str]]:
        if not channel_ids:
            return None
        if not self.supports_channels(source_key):
            return None
        return channel_ids

    def get_keyword_column(self, source_key: str) -> str:
        config = self._get_config(source_key)
        return config.get("keyword_column", "keywords") if config else "keywords"

    def get_currency_column(self, source_key: str) -> str:
        config = self._get_config(source_key)
        return config.get("currency_column", "industry") if config else "industry"

    def get_total_rows(self, source_key: str, channel_ids=None, time_range=None):
        analyzer = self._get_analyzer(source_key)
        if not analyzer:
            return 0
        try:
            return analyzer.get_total_rows(
                channel_ids=self._sanitize_channels(source_key, channel_ids),
                time_range=time_range
            )
        except Exception as e:
            logging.error(f"获取总行数失败: {e}")
            return 0

    def fetch_column_data(self, source_key: str, column: str, channel_ids=None, time_range=None):
        analyzer = self._get_analyzer(source_key)
        if not analyzer:
            return []
        try:
            return analyzer.fetch_column_data(
                column=column,
                channel_ids=self._sanitize_channels(source_key, channel_ids),
                time_range=time_range
            )
        except Exception as e:
            logging.error(f"读取列数据失败: {e}")
            return []

    def count_items_with_occurrence(self, source_key: str, rows, case_insensitive=True):
        analyzer = self._get_analyzer(source_key)
        if not analyzer:
            return Counter(), Counter()
        try:
            return analyzer.count_items_with_occurrence(rows=rows, case_insensitive=case_insensitive)
        except Exception as e:
            logging.error(f"统计项目出现次数失败: {e}")
            return Counter(), Counter()

    def calculate_similarity(self, source_key: str, keyword_counter, limit=None):
        analyzer = self._get_analyzer(source_key)
        if not analyzer:
            return []
        try:
            pairs = analyzer.calculate_similarity(keyword_counter)
            limit = limit or analyzer.top_n
            return pairs[:limit]
        except Exception as e:
            logging.error(f"计算相似度失败: {e}")
            return []

    def query_keyword_similarity(self, source_key: str, input_keyword, keyword_counter):
        analyzer = self._get_analyzer(source_key)
        if not analyzer:
            return False, []
        try:
            return analyzer.query_keyword_similarity(
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
app = FastAPI(title="Web3&HK Stocks新闻分析平台", description="一个集新闻搜索与关键词分析于一体的平台")

# 挂载 static 文件夹
app.mount("/static", StaticFiles(directory="static"), name="static")

# 配置模板目录
templates = Jinja2Templates(directory="templates_UI")

# 主页
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("home.html", {"request": request, "source_options": SOURCE_OPTIONS})

# 新闻搜索页面
@app.get("/search", response_class=HTMLResponse)
async def search_page(request: Request, keyword: Optional[str] = None,
                      source: str = DEFAULT_SOURCE):
    return await search_news_get(request, keyword or "", source)

# 关键词分析器页面
@app.get("/analyzer", response_class=HTMLResponse)
async def analyzer_page(request: Request):
    return templates.TemplateResponse("analyzer.html", {"request": request})


# --- API for News Search ---

@app.get("/search_action", response_class=HTMLResponse)
async def search_news_get(request: Request, keyword: str = "",
                          source: str = DEFAULT_SOURCE):
    try:
        source_key = normalize_source(source)
        engine = get_search_engine(source_key)

        raw_keyword = keyword or ""
        clean_keyword = raw_keyword.strip()
        keyword_mode = bool(clean_keyword)

        if keyword_mode:
            results = engine.search_by_keyword(clean_keyword)
            keyword_heading = f"关键词 “{clean_keyword}”"
            result_summary = f"共 {len(results)} 条结果"
        else:
            results = engine.get_recent_news(limit=50)
            keyword_heading = "最新快讯"
            result_summary = f"展示最新 {len(results)} 条资讯"

        for news in results:
            news['summary'] = engine.generate_summary(news['original_text'], news_id=news.get('id'))

        _enhance_news_results(results)

        top_keywords_counts = engine.get_top_keywords_with_counts(20)
        max_count = max([item["count"] for item in top_keywords_counts]) if top_keywords_counts else 1
        min_count = min([item["count"] for item in top_keywords_counts]) if top_keywords_counts else 0

        if keyword_mode:
            trend_day = engine.get_keyword_trend(clean_keyword, granularity="day")
            trend_labels = json.dumps([p['time'] for p in trend_day], ensure_ascii=False)
            trend_counts = json.dumps([p['count'] for p in trend_day], ensure_ascii=False)
        else:
            trend_labels = "[]"
            trend_counts = "[]"

        return templates.TemplateResponse("search_results.html", {
            "request": request,
            "keyword": clean_keyword,
            "keyword_heading": keyword_heading,
            "has_keyword": keyword_mode,
            "result_summary": result_summary,
            "results": results,
            "top_keywords_counts": top_keywords_counts,
            "max_count": max_count,
            "min_count": min_count,
            "total_results": len(results),
            "trend_labels": trend_labels,
            "trend_counts": trend_counts,
            "source": source_key,
            "source_label": SOURCE_LABEL_MAP[source_key],
            "available_sources": SOURCE_OPTIONS,
            "search_value": clean_keyword
        })
    except Exception as e:
        logger.error(f"搜索出错: {e}")
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_message": f"搜索出错: {str(e)}"
        })

@app.post("/search_action", response_class=HTMLResponse)
async def search_news_post(request: Request, keyword: str = Form(...),
                           source: str = Form(DEFAULT_SOURCE)):
    return await search_news_get(request, keyword, source)

# --- APIs for Keyword Analyzer ---

analyzer_router = APIRouter(prefix="/api")

@analyzer_router.get("/channels")
async def get_channels(source: str = DEFAULT_SOURCE):
    """获取可用频道列表"""
    source_key = normalize_source(source)
    channels = web_analyzer.get_channels(source_key)
    return JSONResponse(content={
        'channels': channels,
        'supports_channels': web_analyzer.supports_channels(source_key)
    })

@analyzer_router.post("/analyze")
async def analyze_data(request: Request):
    """分析数据的主要接口"""
    try:
        data = await request.json()
        source_key = normalize_source(data.get('data_source'))
        channel_ids = data.get('channel_ids', []) or None
        if not web_analyzer.supports_channels(source_key):
            channel_ids = None
        time_range_str = data.get('time_range')

        logger.info(f"\n📊 开始分析 {SOURCE_LABEL_MAP.get(source_key, source_key)} 数据...")
        logger.info(f"   频道 ID: {channel_ids}")
        logger.info(f"   时间范围: {time_range_str}")

        total_rows = web_analyzer.get_total_rows(source_key, channel_ids, time_range_str)
        logger.info(f"✓ 总行数: {total_rows}")

        keyword_rows = web_analyzer.fetch_column_data(
            source_key,
            web_analyzer.get_keyword_column(source_key),
            channel_ids,
            time_range_str
        )
        logger.info(f"✓ 读取关键词行数: {len(keyword_rows)}")
        keyword_counter, keyword_occurrence = web_analyzer.count_items_with_occurrence(source_key, keyword_rows)
        logger.info(f"✓ 关键词种类: {len(keyword_counter)}")

        currency_rows = web_analyzer.fetch_column_data(
            source_key,
            web_analyzer.get_currency_column(source_key),
            channel_ids,
            time_range_str
        )
        logger.info(f"✓ 读取币种行数: {len(currency_rows)}")
        currency_counter, currency_occurrence = web_analyzer.count_items_with_occurrence(source_key, currency_rows)
        logger.info(f"✓ 币种种类: {len(currency_counter)}")

        # similarity_pairs = web_analyzer.calculate_similarity(source_key, keyword_rows, keyword_counter, limit=50)
        # similarity_results = [
        #     {'word1': a, 'count1': ca, 'word2': b, 'count2': cb, 'similarity': round(s, 4)}
        #     for a, ca, b, cb, s in similarity_pairs
        # ]
        similarity_results = [] # Disable similarity analysis

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

        # Determine trend targets based on source
        trend_targets = []
        target_column = None
        
        # Always use top keywords for trend analysis
        for item in keyword_stats[:20]:
             if isinstance(item, dict) and 'word' in item:
                 trend_targets.append(item['word'])
        target_column = None # Use default keyword column

        # Fetch trend data
        trend_data = {}
        analyzer = web_analyzer._get_analyzer(source_key)
        if analyzer and trend_targets:
            try:
                # Special handling for crypto trend analysis time range
                actual_time_range = time_range_str
                if source_key == 'crypto' and not actual_time_range:
                    latest_date_str = analyzer.get_latest_date()
                    if latest_date_str:
                        try:
                            # Try ISO format first (e.g. 2024-04-09T12:02:53+00:00)
                            latest_date = datetime.fromisoformat(latest_date_str.replace('Z', '+00:00'))
                        except:
                            try:
                                # Fallback to simple format
                                latest_date = datetime.strptime(latest_date_str, '%Y-%m-%d %H:%M:%S')
                            except:
                                latest_date = None
                        
                        if latest_date:
                            start_date = latest_date - timedelta(days=7)
                            # Use ISO format for consistency with DB
                            actual_time_range = [start_date.isoformat(), latest_date.isoformat()]
                            logger.info(f"   Web3 默认趋势范围: {actual_time_range}")

                trend_data = analyzer.get_top_keywords_trend(
                    top_keywords=trend_targets,
                    channel_ids=web_analyzer._sanitize_channels(source_key, channel_ids),
                    time_range=actual_time_range,
                    target_column=target_column
                )
            except Exception as e:
                logger.error(f"获取趋势数据失败: {e}")

        logger.info("✅ 分析完成\n")
        # Return the analysis result
        return JSONResponse(content={
            'success': True,
            'total_rows': total_rows,
            'keyword_stats': keyword_stats,
            'currency_stats': currency_stats,
            'similarity_results': similarity_results,
            'trend_data': trend_data,
            'keyword_total': len(keyword_counter),
            'currency_total': len(currency_counter)
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
        source_key = normalize_source(data.get('data_source'))
        keyword = data.get('keyword', '').strip()
        channel_ids = data.get('channel_ids', []) or None
        if not web_analyzer.supports_channels(source_key):
            channel_ids = None
        time_range = data.get('time_range')

        logger.info(f"\n🔍 查询请求: '{keyword}'")
        if not keyword:
            return JSONResponse(status_code=400, content={'success': False, 'error': '请输入关键词'})

        keyword_rows = web_analyzer.fetch_column_data(
            source_key,
            web_analyzer.get_keyword_column(source_key),
            channel_ids,
            time_range
        )
        keyword_counter, _ = web_analyzer.count_items_with_occurrence(source_key, keyword_rows)
        
        exists, top_similar = web_analyzer.query_keyword_similarity(source_key, keyword, keyword_counter)
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