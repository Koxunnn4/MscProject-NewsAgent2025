from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uvicorn
from news_search import NewsSearchEngine
import logging
from typing import Optional
import json

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(title="Web3新闻搜索引擎", description="基于关键词的新闻搜索和摘要系统")

# 配置模板
templates = Jinja2Templates(directory="templates")

# 初始化搜索引擎
search_engine = NewsSearchEngine()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    top_keywords_counts = search_engine.get_top_keywords_with_counts(20)
    max_count = max([item["count"] for item in top_keywords_counts]) if top_keywords_counts else 1
    min_count = min([item["count"] for item in top_keywords_counts]) if top_keywords_counts else 0
    default_keyword = top_keywords_counts[0]["keyword"] if top_keywords_counts else ""
    results = search_engine.search_by_keyword(default_keyword, top_k=5) if default_keyword else []
    for news in results:
        news['summary'] = search_engine.generate_summary(news['original_text'])
    trend_day = search_engine.get_keyword_trend(default_keyword, granularity="day") if default_keyword else []
    trend_labels = json.dumps([p['time'] for p in trend_day], ensure_ascii=False)
    trend_counts = json.dumps([p['count'] for p in trend_day], ensure_ascii=False)
    return templates.TemplateResponse("search_results.html", {
        "request": request,
        "keyword": default_keyword,
        "results": results,
        "top_keywords_counts": top_keywords_counts,
        "max_count": max_count,
        "min_count": min_count,
        "total_results": len(results),
        "trend_labels": trend_labels,
        "trend_counts": trend_counts,
    })

@app.get("/search", response_class=HTMLResponse)
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

@app.post("/search", response_class=HTMLResponse)
async def search_news(
    request: Request,
    keyword: str = Form(...),
    top_k: int = Form(5)
):
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

@app.get("/api/keywords")
async def get_keywords():
    """API接口：获取热门关键词（含计数）"""
    try:
        items = search_engine.get_top_keywords_with_counts(50)
        return {"keywords": items}
    except Exception as e:
        logger.error(f"获取关键词失败: {e}")
        return {"error": str(e)}

@app.get("/api/search")
async def api_search(keyword: str, top_k: int = 5):
    """API接口：搜索新闻并返回摘要与趋势（按日）"""
    try:
        results = search_engine.search_by_keyword(keyword, top_k)
        for news in results:
            news['summary'] = search_engine.generate_summary(news['original_text'])
        trend_day = search_engine.get_keyword_trend(keyword, granularity="day")
        return {
            "keyword": keyword,
            "total_results": len(results),
            "results": results,
            "trend_day": trend_day,
        }
    except Exception as e:
        logger.error(f"API搜索出错: {e}")
        return {"error": str(e)}

@app.get("/api/trend")
async def api_trend(
    keyword: str,
    granularity: str = "day",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """API接口：返回指定关键词的热度趋势"""
    try:
        trend = search_engine.get_keyword_trend(keyword, granularity=granularity, start_date=start_date, end_date=end_date)
        return {
            "keyword": keyword,
            "granularity": granularity,
            "trend": trend,
        }
    except Exception as e:
        logger.error(f"获取趋势失败: {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    uvicorn.run("web_app:app", host="127.0.0.1", port=8001, reload=True)