from fastapi import FastAPI, Request, Form, APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uvicorn
from news_search import NewsSearchEngine
from hkstocks_search import HKStocksSearchEngine
import logging
from typing import Optional, List, Dict, Any
import json
import os
import sys
from collections import Counter
import re
from datetime import datetime, timedelta
from pathlib import Path
from config import HISTORY_DB_PATH, CRYPTO_DB_PATH
import requests

from src.realtime_ingest import get_realtime_ingestor

# --- Start of web_analyzer integration ---

# 添加项目根目录到路径，以便导入分析器模块
APP_ROOT = Path(__file__).resolve().parent
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

CHANNEL_KEY_TO_NAME = {key: meta[1] for key, meta in CHANNEL_MAP.items()}
CHANNEL_ID_TO_NAME = {meta[0]: meta[1] for meta in CHANNEL_MAP.values()}

SOURCE_OPTIONS = [
    {"key": "crypto", "label": "Web3 新闻"},
    {"key": "hkstocks", "label": "港股新闻"}
]
SOURCE_LABEL_MAP = {item["key"]: item["label"] for item in SOURCE_OPTIONS}
DEFAULT_SOURCE = "crypto"
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


def _resolve_channel_label(raw_source: Optional[str], raw_channel_id: Optional[str]) -> Optional[str]:
    """Resolve channel display label from raw values."""
    candidates = []
    if raw_source is not None:
        candidates.append(str(raw_source).strip())
    if raw_channel_id is not None:
        candidates.append(str(raw_channel_id).strip())
    for candidate in candidates:
        if not candidate:
            continue
        if candidate.startswith('@'):
            return candidate
        if candidate in CHANNEL_KEY_TO_NAME:
            return CHANNEL_KEY_TO_NAME[candidate]
        if candidate in CHANNEL_ID_TO_NAME:
            return CHANNEL_ID_TO_NAME[candidate]
    return None


def _enhance_news_results(results: List[Dict]):
    for news in results:
        news.setdefault('source_type', 'crypto')
        news['source_badge'] = SOURCE_BADGES.get(news['source_type'], 'News')
        if not news.get('summary') and news.get('abstract'):
            news['summary'] = news['abstract']
        news['keyword_list'] = _split_keywords(news.get('keywords', ''))
        if not news.get('title'):
            news['title'] = (news.get('text') or '')[:80]
        resolved_source = _resolve_channel_label(news.get('source'), news.get('channel_id'))
        original_source = news.get('source') or news.get('channel_id')
        news['source'] = resolved_source or original_source or 'Web3 Feed'


FNG_API_ENDPOINT = "https://api.alternative.me/fng/?limit=1"
COINGECKO_MARKET_ENDPOINT = "https://api.coingecko.com/api/v3/coins/markets"

# 默认关闭实时管道，除非显式设置 ENABLE_REALTIME_PIPELINE=1
REALTIME_PIPELINE_ENABLED = os.getenv("ENABLE_REALTIME_PIPELINE", "0") == "1"

realtime_ingestor = None
if REALTIME_PIPELINE_ENABLED:
    try:
        realtime_ingestor = get_realtime_ingestor(Path(CRYPTO_DB_PATH))
    except Exception as exc:
        logging.error("初始化实时新闻管道失败: %s", exc)
        realtime_ingestor = None
else:
    logging.info("实时管道已禁用（默认离线模式，使用本地数据库进行分析）")


def _get_int_from_env(env_name: str, default: int) -> int:
    raw_value = os.getenv(env_name)
    if raw_value in (None, ""):
        return default
    try:
        return int(raw_value)
    except ValueError:
        logging.warning("环境变量 %s=%s 非法，默认采用 %s", env_name, raw_value, default)
        return default


AUTO_REFRESH_INTERVAL = _get_int_from_env("AUTO_REFRESH_INTERVAL", 60)
AUTO_REFRESH_ENABLED = REALTIME_PIPELINE_ENABLED and AUTO_REFRESH_INTERVAL > 0
MARKET_BOARD_CACHE_TTL = _get_int_from_env("CRYPTO_MARKET_CACHE_TTL", 180)
MARKET_BOARD_ITEMS = _get_int_from_env("CRYPTO_MARKET_BOARD_SIZE", 8)

_crypto_market_cache: Dict[str, Optional[Any]] = {
    "payload": None,
    "timestamp": None,
}

# 缓存币种统计结果，降低首页统计开销
_coin_stats_cache: Dict[str, Optional[Any]] = {
    "payload": None,
    "timestamp": None,
}

COIN_DICT_PATH = Path(__file__).resolve().parent / "src" / "crawler" / "crpyto_news" / "coin_dict.json"

def _load_coin_dict() -> Dict[str, Any]:
    try:
        with open(COIN_DICT_PATH, 'r', encoding='utf-8') as f:
            return json.load(f) or {}
    except Exception as exc:
        logging.warning("加载 coin_dict.json 失败: %s", exc)
        return {}

def _build_lower_synonyms_map(raw_map: Dict[str, Any]) -> Dict[str, Any]:
    lower_map: Dict[str, Any] = {}
    for key, names in (raw_map or {}).items():
        norm_list = []
        for n in names or []:
            try:
                norm_list.append(str(n).strip())
            except Exception:
                continue
        lower_map[key] = {
            "synonyms": norm_list,
            "synonyms_lower": [s.lower() for s in norm_list],
        }
    return lower_map

def _compute_crypto_coin_stats() -> Dict[str, Dict[str, Any]]:
    """统计 coin_dict 中每个币在新闻数据库中的出现次数和占比（按行计次，忽略大小写）。"""
    try:
        total_rows = web_analyzer.get_total_rows("crypto")
        # 拉取两个相关列，尽量覆盖币种信息
        currency_col = web_analyzer.fetch_column_data("crypto", web_analyzer.get_currency_column("crypto"))
        rows: List[str] = []
        for r in (currency_col or []):
            if r:
                rows.append(str(r))

        coin_dict_raw = _load_coin_dict()
        coin_dict = _build_lower_synonyms_map(coin_dict_raw)

        stats: Dict[str, Dict[str, Any]] = {k: {"count": 0, "ratio": 0.0} for k in coin_dict.keys()}
        if not rows:
            return stats

        # 为降低重复匹配，逐行处理，命中则+1（每行计一次）
        for raw in rows:
            text = str(raw).lower()
            for coin_key, meta in coin_dict.items():
                for syn in meta["synonyms_lower"]:
                    if not syn:
                        continue
                    if syn in text:
                        stats[coin_key]["count"] += 1
                        break  # 同一 coin 本行只计一次

        denom = float(total_rows or 1)
        for coin_key, d in stats.items():
            d["ratio"] = round((d["count"] / denom) * 100.0, 2)
        return stats
    except Exception as exc:
        logging.warning("计算币种统计失败: %s", exc)
        return {}

def _get_coin_stats_cached(ttl_sec: int = 600) -> Dict[str, Dict[str, Any]]:
    now = datetime.utcnow()
    ts = _coin_stats_cache.get("timestamp")
    payload = _coin_stats_cache.get("payload")
    if payload and ts and (now - ts) < timedelta(seconds=ttl_sec):
        return payload
    payload = _compute_crypto_coin_stats()
    _coin_stats_cache["payload"] = payload
    _coin_stats_cache["timestamp"] = now
    return payload

def _match_coin_key_for_market_item(coin_name: Optional[str], coin_symbol: Optional[str]) -> Optional[str]:
    """根据 market 行情项名称/符号，在 coin_dict 中找到对应的 coin key（忽略大小写）。"""
    coin_dict_raw = _load_coin_dict()
    if not coin_dict_raw:
        return None
    name_l = (coin_name or "").lower()
    sym_l = (coin_symbol or "").lower()
    for coin_key, names in coin_dict_raw.items():
        syn_lowers = [str(x).lower() for x in (names or [])]
        if name_l and name_l in syn_lowers:
            return coin_key
        if sym_l and sym_l in syn_lowers:
            return coin_key
    return None


def _format_iso_timestamp(raw_value: Optional[str]) -> Optional[str]:
    if not raw_value:
        return None
    try:
        sanitized = raw_value.replace('Z', '+00:00')
        dt_obj = datetime.fromisoformat(sanitized)
        return dt_obj.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return raw_value


def fetch_crypto_market_board(limit: Optional[int] = None) -> Dict[str, Any]:
    """Fetch 24h performance snapshot for major crypto assets."""
    # Limit to top 20 for card display
    limit = 20
    now = datetime.utcnow()
    cached_ts = _crypto_market_cache["timestamp"]
    cached_payload = _crypto_market_cache["payload"]
    if cached_payload and cached_ts and (now - cached_ts) < timedelta(seconds=MARKET_BOARD_CACHE_TTL):
        return cached_payload

    fallback = {
        "coins": [],
        "currency": "USD",
        "last_updated": None,
    }
    try:
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": limit,
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "24h",
        }
        response = requests.get(COINGECKO_MARKET_ENDPOINT, params=params, timeout=8)
        response.raise_for_status()
        data = response.json() or []
        coins = []
        for entry in data:
            try:
                price = entry.get("current_price")
                pct = entry.get("price_change_percentage_24h")
                change = entry.get("price_change_24h")
                last_updated = entry.get("last_updated")
                coins.append({
                    "id": entry.get("id"),
                    "symbol": (entry.get("symbol") or "").upper(),
                    "name": entry.get("name"),
                    "price": price,
                    "price_change_pct": pct,
                    "price_change": change,
                    "market_cap": entry.get("market_cap"),
                    "volume_24h": entry.get("total_volume"),
                    "image": entry.get("image"),
                    "last_updated": last_updated,
                    "trend": "up" if (pct or 0) >= 0 else "down",
                })
            except Exception:
                continue
        raw_last_updated = coins[0].get("last_updated") if coins else None
        # 计算币种新闻统计并附加到 coins
        coin_stats = _get_coin_stats_cached(ttl_sec=max(MARKET_BOARD_CACHE_TTL, 300))
        for c in coins:
            key = _match_coin_key_for_market_item(c.get("name"), c.get("symbol"))
            stat = coin_stats.get(key or "", {"count": 0, "ratio": 0.0})
            c["news_count"] = int(stat.get("count", 0))
            c["news_ratio"] = float(stat.get("ratio", 0.0))

        payload = {
            "coins": coins,
            "currency": "USD",
            "last_updated": _format_iso_timestamp(raw_last_updated),
            "raw_last_updated": raw_last_updated,
        }
        _crypto_market_cache["payload"] = payload
        _crypto_market_cache["timestamp"] = now
        return payload
    except Exception as exc:
        logging.warning("获取加密货币涨跌榜失败: %s", exc)
        return fallback


def fetch_fear_greed_index() -> Dict[str, Optional[str]]:
    """从 Alternative.me 获取 Crypto Fear & Greed Index。"""
    fallback = {
        "value": None,
        "classification": "数据不可用",
        "value_class": "neutral",
        "timestamp": None,
    }
    try:
        response = requests.get(FNG_API_ENDPOINT, timeout=5)
        response.raise_for_status()
        payload = response.json() or {}
        entry = (payload.get("data") or [fallback])[0]
        value = entry.get("value") or fallback["value"]
        classification_raw = (
            entry.get("value_classification")
            or entry.get("classification")
            or fallback["classification"]
        )
        classification_str = str(classification_raw).strip() or "未知"
        # 显示中文标签
        cn_map = {
            "extreme greed": "极度贪婪",
            "greed": "贪婪",
            "neutral": "中性",
            "fear": "恐惧",
            "extreme fear": "极度恐惧",
        }
        classification_cn = cn_map.get(classification_str.lower(), classification_str)
        class_slug = classification_str.lower().replace(' ', '-')
        allowed_classes = {"extreme-greed", "greed", "neutral", "fear", "extreme-fear"}
        value_class = class_slug if class_slug in allowed_classes else "neutral"
        timestamp_raw = entry.get("timestamp")
        readable_time = None
        if timestamp_raw:
            try:
                readable_time = datetime.fromtimestamp(int(timestamp_raw)).strftime("%Y-%m-%d %H:%M")
            except Exception:
                readable_time = None
        return {
            "value": value,
            "classification": classification_cn,
            "value_class": value_class,
            "timestamp": readable_time,
        }
    except Exception as exc:
        logging.warning("获取恐慌指数失败: %s", exc)
        return fallback


def resolve_tradingview_symbol(term: Optional[str], source: str = DEFAULT_SOURCE) -> Optional[str]:
    """根据关键词推断 TradingView 的交易对符号。"""
    if not term:
        return None
    sanitized = re.sub(r"[^A-Za-z0-9]", "", str(term).upper())
    if not sanitized:
        return None
    if source == "hkstocks":
        if sanitized.isdigit():
            return f"HKEX:{sanitized}"
        if sanitized.startswith("HK") and sanitized[2:].isdigit():
            return f"HKEX:{sanitized[2:]}"
        return None
    if sanitized.endswith("USDT") or sanitized.endswith("USD"):
        return sanitized
    if len(sanitized) <= 6:
        return f"{sanitized}USDT"
    return sanitized


def build_dashboard_snapshot() -> Dict[str, Any]:
    """构建首页仪表盘所需的数据。"""
    snapshot = {
        "crypto_trending": [],
        "hk_trending": [],
        "crypto_latest": [],
        "hk_latest": [],
        "spotlight_symbols": [],
        "fear_greed": fetch_fear_greed_index(),
        "crypto_market_board": fetch_crypto_market_board(),
    }

    try:
        crypto_engine = get_search_engine("crypto")
        snapshot["crypto_trending"] = crypto_engine.get_top_keywords_with_counts(6)
        crypto_latest = crypto_engine.get_recent_news(limit=4)
        _enhance_news_results(crypto_latest)
        snapshot["crypto_latest"] = crypto_latest
        for item in snapshot["crypto_trending"]:
            item["symbol"] = resolve_tradingview_symbol(item.get("keyword"))
    except Exception as exc:
        logging.error("加载 Crypto 仪表盘数据失败: %s", exc)

    try:
        hk_engine = get_search_engine("hkstocks")
        snapshot["hk_trending"] = hk_engine.get_top_keywords_with_counts(6)
        hk_latest = hk_engine.get_recent_news(limit=4)
        _enhance_news_results(hk_latest)
        snapshot["hk_latest"] = hk_latest
        for item in snapshot["hk_trending"]:
            item["symbol"] = resolve_tradingview_symbol(item.get("keyword"), "hkstocks")
    except Exception as exc:
        logging.error("加载港股仪表盘数据失败: %s", exc)

    spotlight = []
    for item in snapshot["crypto_trending"][:4]:
        symbol = resolve_tradingview_symbol(item.get("keyword"))
        if not symbol:
            continue
        spotlight.append({
            "keyword": item.get("keyword"),
            "count": item.get("count"),
            "symbol": symbol,
            "url": f"https://www.tradingview.com/chart/?symbol={symbol}",
        })
    snapshot["spotlight_symbols"] = spotlight

    return snapshot

class WebSimilarityAnalyzer:
    """面向 Web 的多数据源相似度分析调度器"""

    def __init__(self):
        self.source_configs: Dict[str, Dict] = {}
        if ANALYZER_AVAILABLE:
            self._init_sources()
        else:
            logging.warning("SimilarityAnalyzer 模块不可用，关键词分析接口将被禁用")

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
                    top_n=100
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


@app.on_event("startup")
async def startup_realtime_pipeline():
    if not REALTIME_PIPELINE_ENABLED:
        logging.info("启动: 离线模式 (未启动实时抓取)")
        return
    if realtime_ingestor is None:
        logging.warning("启动: 期望实时模式，但 ingestor 未初始化")
        return
    logging.info("启动: 实时模式，初始化抓取任务")
    await realtime_ingestor.start()


@app.on_event("shutdown")
async def shutdown_realtime_pipeline():
    if not REALTIME_PIPELINE_ENABLED or realtime_ingestor is None:
        return
    await realtime_ingestor.stop()

# 主页
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    snapshot = build_dashboard_snapshot()
    context = {
        "request": request,
        "source_options": SOURCE_OPTIONS,
        "auto_refresh": AUTO_REFRESH_ENABLED,
        "refresh_interval": AUTO_REFRESH_INTERVAL,
        **snapshot,
    }
    return templates.TemplateResponse("home.html", context)


@app.get("/api/dashboard", response_class=JSONResponse)
async def dashboard_snapshot_api():
    snapshot = build_dashboard_snapshot()
    return JSONResponse(snapshot)

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
            results = engine.get_recent_news(limit=20)
            keyword_heading = "最新快讯"
            result_summary = f"展示最新 {len(results)} 条资讯"

        for news in results:
            candidate_summary = (news.get('abstract') or '').strip()
            text_for_summary = news.get('original_text') or news.get('text') or ''
            if candidate_summary:
                news['summary'] = candidate_summary
                continue

            generated_summary = engine.generate_summary(text_for_summary)
            news['summary'] = generated_summary
            if generated_summary and generated_summary != "模型不可用":
                try:
                    engine.persist_summary(news.get('id'), generated_summary)
                except Exception as exc:
                    logging.debug("摘要写回失败: %s", exc)

        _enhance_news_results(results)

        top_keywords_counts = engine.get_top_keywords_with_counts(20)
        max_count = max([item["count"] for item in top_keywords_counts]) if top_keywords_counts else 1
        min_count = min([item["count"] for item in top_keywords_counts]) if top_keywords_counts else 0

        trading_symbol = resolve_tradingview_symbol(clean_keyword, source_key) if keyword_mode else None
        related_symbols = []
        seen_symbols = set()

        for news in results:
            currency_field = news.get('currency') or ''
            candidates = _split_keywords(currency_field) if currency_field else []
            if not candidates and currency_field:
                candidates = [currency_field]
            for candidate in candidates:
                symbol = resolve_tradingview_symbol(candidate, source_key)
                if symbol and symbol not in seen_symbols:
                    seen_symbols.add(symbol)
                    related_symbols.append({
                        "label": candidate,
                        "symbol": symbol,
                        "url": f"https://www.tradingview.com/chart/?symbol={symbol}",
                    })
                    news.setdefault('trading_symbol', symbol)
                    if trading_symbol is None:
                        trading_symbol = symbol
            if 'trading_symbol' not in news:
                news['trading_symbol'] = resolve_tradingview_symbol(currency_field, source_key)

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
            "search_value": clean_keyword,
            "trading_symbol": trading_symbol,
            "related_symbols": related_symbols,
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

        similarity_pairs = web_analyzer.calculate_similarity(source_key, keyword_counter, limit=50)
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
            'success': True,
            'total_rows': total_rows,
            'keyword_stats': keyword_stats,
            'currency_stats': currency_stats,
            'similarity_results': similarity_results,
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
        
        exists = keyword in keyword_counter
        
        exists_api, top_similar = web_analyzer.query_keyword_similarity(source_key, keyword, keyword_counter)
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

# MVP 报告生成接口：接受前端拼接的上下文，尝试调用 Dify 工作流，若不可用则返回占位报告
@app.post("/api/generate-report")
async def generate_report_api(request: Request):
    try:
        data = await request.json()
        context_text = str(data.get('context') or '').strip()
        source = normalize_source(data.get('source'))
        if not context_text:
            return JSONResponse(status_code=400, content={"success": False, "error": "缺少上下文"})

        dify_api_key = os.getenv('DIFY_API_KEY', "app-YUKyYyF2DEc4xG5Y4zUvbOaR")
        dify_base_url = os.getenv('DIFY_BASE_URL', 'http://localhost/v1').rstrip('/')
        user_id = os.getenv('DIFY_USER_ID', 'web-user-001')
        debug_enabled = os.getenv('GENERATE_REPORT_DEBUG', '0') == '1'

        logger.info("[generate-report] source=%s, context_len=%d", source, len(context_text))

        if not dify_api_key.startswith('app-'):
            logger.error("[generate-report] 缺少有效的 DIFY_API_KEY")
            return JSONResponse(status_code=500, content={"success": False, "error": "服务未配置：缺少 DIFY_API_KEY"})

        try:
            url = f"{dify_base_url}/workflows/run"
            headers = {"Authorization": f"Bearer {dify_api_key}", "Content-Type": "application/json"}
            payload = {"inputs": {"context": context_text}, "user": user_id, "response_mode": "blocking"}
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            if resp.status_code != 200:
                logger.error("[generate-report] API 调用失败 status=%s body=%s", resp.status_code, resp.text)
                return JSONResponse(status_code=500, content={"success": False, "error": f"Dify接口调用失败({resp.status_code})"})
            dify_data = resp.json()
            status = dify_data.get('data', {}).get('status')
            if status != 'succeeded':
                err_msg = dify_data.get('data', {}).get('error') or '工作流未成功'
                logger.error("[generate-report] 工作流未成功 status=%s error=%s", status, err_msg)
                return JSONResponse(status_code=500, content={"success": False, "error": f"工作流未成功: {err_msg}"})
            outputs = dify_data.get('data', {}).get('outputs') or {}
            # 仅输出精炼报告内容
            report_text = outputs.get('report') or outputs.get('text') or outputs.get('content')
            if not report_text or not str(report_text).strip():
                logger.error("[generate-report] 后端返回为空或缺少报告字段 outputs=%s", outputs)
                return JSONResponse(status_code=500, content={"success": False, "error": "报告内容为空"})
            return JSONResponse(content={"success": True, "report": report_text})
        except Exception as exc:
            logger.error("[generate-report] Dify 调用异常: %s", exc)
            return JSONResponse(status_code=500, content={"success": False, "error": "Dify调用异常"})
    except Exception as e:
        logger.error(f"生成报告失败: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


if __name__ == "__main__":
    uvicorn.run("web_app:app", host="127.0.0.1", port=8001, reload=True)