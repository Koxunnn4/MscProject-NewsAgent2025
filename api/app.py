"""
Flask API 接口
提供 RESTful API 供前端调用
"""
import os
import sys
from flask import Flask, jsonify, request
from flask_cors import CORS
import asyncio

# 添加项目根目录到路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from config import API_HOST, API_PORT, API_DEBUG
from src.database.db_manager import get_db_manager
from src.crypto_analysis.crypto_analyzer import get_keyword_extractor
from src.crypto_analysis.summarizer import get_summarizer
from src.trend_analysis.trend_analyzer import get_trend_analyzer
from src.push_system.push_manager import get_push_manager
from src.utils.helpers import format_date, get_date_range

# 创建 Flask 应用
app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 初始化管理器
db = get_db_manager()
extractor = get_keyword_extractor()
summarizer = get_summarizer()
analyzer = get_trend_analyzer()
push_manager = get_push_manager()


# ==================== 健康检查 ====================

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({
        'status': 'healthy',
        'message': '新闻分析系统运行正常'
    })


# ==================== 新闻相关接口 ====================

@app.route('/api/news/search', methods=['GET'])
def search_news():
    """
    搜索新闻
    参数:
        keyword: 关键词
        limit: 返回数量（默认10）
    """
    keyword = request.args.get('keyword', '')
    limit = int(request.args.get('limit', 10))

    if not keyword:
        return jsonify({'error': '请提供关键词'}), 400

    news_list = db.get_news_by_keyword(keyword, limit)

    return jsonify({
        'keyword': keyword,
        'count': len(news_list),
        'data': news_list
    })


@app.route('/api/news/<int:news_id>', methods=['GET'])
def get_news_detail(news_id):
    """
    获取新闻详情
    """
    query = "SELECT * FROM messages WHERE id = ?"
    results = db.execute_query(query, (news_id,), db.history_db_path)

    if not results:
        return jsonify({'error': '新闻不存在'}), 404

    news = results[0]

    # 获取关键词
    keywords = db.get_news_keywords(news_id)
    news['keywords'] = keywords

    return jsonify(news)


@app.route('/api/news/top', methods=['GET'])
def get_top_news_by_keyword():
    """
    获取关键词相关的Top-K新闻（女同学的功能）
    参数:
        keyword: 用户关键词
        k: 返回数量（默认10）
    """
    keyword = request.args.get('keyword', '')
    k = int(request.args.get('k', 10))

    if not keyword:
        return jsonify({'error': '请提供关键词'}), 400

    # 获取所有新闻并提取关键词
    query = "SELECT id, text, date FROM messages"
    news_list = db.execute_query(query, db_path=db.history_db_path)

    # 为每条新闻提取关键词
    for news in news_list:
        keywords = extractor.extract_keywords(news['text'], top_n=5)
        news['keywords'] = [kw for kw, weight in keywords]
        news['weights'] = [weight for kw, weight in keywords]

    # 获取相关性最高的新闻
    top_news = extractor.get_top_relevant_news(keyword, news_list, top_k=k)

    # 生成摘要
    for news in top_news:
        news['summary'] = summarizer.generate_summary(news['text'])

    return jsonify({
        'keyword': keyword,
        'count': len(top_news),
        'data': top_news
    })


# ==================== 关键词趋势分析接口（Task 3）====================

@app.route('/api/trend/keyword', methods=['GET'])
def get_keyword_trend():
    """
    获取关键词热度趋势
    参数:
        keyword: 关键词
        start_date: 开始日期 (可选)
        end_date: 结束日期 (可选)
        granularity: 时间粒度 (day/week/month, 默认day)
    """
    keyword = request.args.get('keyword', '')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    granularity = request.args.get('granularity', 'day')

    if not keyword:
        return jsonify({'error': '请提供关键词'}), 400

    trend = analyzer.analyze_keyword_trend(
        keyword, start_date, end_date, granularity
    )

    return jsonify(trend)


@app.route('/api/trend/compare', methods=['POST'])
def compare_keywords():
    """
    对比多个关键词
    请求体:
        {
            "keywords": ["关键词1", "关键词2"],
            "start_date": "2024-01-01",
            "end_date": "2024-12-31"
        }
    """
    data = request.get_json()

    if not data or 'keywords' not in data:
        return jsonify({'error': '请提供关键词列表'}), 400

    keywords = data['keywords']
    start_date = data.get('start_date')
    end_date = data.get('end_date')

    comparison = analyzer.compare_keywords(keywords, start_date, end_date)

    return jsonify(comparison)


@app.route('/api/trend/hot-dates', methods=['GET'])
def get_hot_dates():
    """
    获取关键词最热门的日期
    参数:
        keyword: 关键词
        top_n: 返回数量（默认10）
    """
    keyword = request.args.get('keyword', '')
    top_n = int(request.args.get('top_n', 10))

    if not keyword:
        return jsonify({'error': '请提供关键词'}), 400

    hot_dates = analyzer.get_hot_dates(keyword, top_n)

    return jsonify({
        'keyword': keyword,
        'data': hot_dates
    })


@app.route('/api/trend/visualize', methods=['GET'])
def visualize_trend():
    """
    生成关键词趋势可视化图表
    参数:
        keyword: 关键词
        start_date: 开始日期 (可选)
        end_date: 结束日期 (可选)
    """
    keyword = request.args.get('keyword', '')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if not keyword:
        return jsonify({'error': '请提供关键词'}), 400

    # 生成图表并保存
    save_path = f"data/trend_{keyword}.png"
    result = analyzer.visualize_trend(keyword, start_date, end_date, save_path)

    if result:
        return jsonify({
            'success': True,
            'image_path': result
        })
    else:
        return jsonify({
            'success': False,
            'error': '图表生成失败'
        }), 500


# ==================== 订阅推送接口（Task 4）====================

@app.route('/api/subscription/subscribe', methods=['POST'])
def subscribe():
    """
    创建订阅
    请求体:
        {
            "user_id": "用户ID",
            "keyword": "关键词",
            "telegram_chat_id": "Telegram聊天ID"
        }
    """
    data = request.get_json()

    if not data or 'user_id' not in data or 'keyword' not in data:
        return jsonify({'error': '请提供用户ID和关键词'}), 400

    result = push_manager.subscribe(
        data['user_id'],
        data['keyword'],
        data.get('telegram_chat_id')
    )

    return jsonify(result)


@app.route('/api/subscription/unsubscribe/<int:subscription_id>', methods=['DELETE'])
def unsubscribe(subscription_id):
    """取消订阅"""
    result = push_manager.unsubscribe(subscription_id)
    return jsonify(result)


@app.route('/api/subscription/list/<user_id>', methods=['GET'])
def get_subscriptions(user_id):
    """获取用户订阅列表"""
    subscriptions = push_manager.get_user_subscriptions(user_id)

    return jsonify({
        'user_id': user_id,
        'count': len(subscriptions),
        'data': subscriptions
    })


# ==================== 统计接口 ====================

@app.route('/api/stats/overview', methods=['GET'])
def get_overview_stats():
    """获取系统概况统计"""
    # 统计新闻总数
    query = "SELECT COUNT(*) as count FROM messages"
    news_count = db.execute_query(query, db_path=db.history_db_path)[0]['count']

    # 统计日期范围
    query = "SELECT MIN(date) as min_date, MAX(date) as max_date FROM messages"
    date_range = db.execute_query(query, db_path=db.history_db_path)[0]

    # 统计订阅数
    query = "SELECT COUNT(*) as count FROM subscriptions WHERE is_active = 1"
    try:
        sub_count = db.execute_query(query)[0]['count']
    except:
        sub_count = 0

    return jsonify({
        'total_news': news_count,
        'date_range': {
            'start': format_date(date_range['min_date'], 'date'),
            'end': format_date(date_range['max_date'], 'date')
        },
        'active_subscriptions': sub_count
    })


# ==================== 错误处理 ====================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': '接口不存在'}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': '服务器内部错误'}), 500


# ==================== 启动应用 ====================

if __name__ == '__main__':
    print("=" * 70)
    print("  新闻分析系统 API 服务")
    print("=" * 70)
    print(f"  地址: http://{API_HOST}:{API_PORT}")
    print(f"  文档: http://{API_HOST}:{API_PORT}/api/health")
    print("=" * 70)
    print()

    app.run(
        host=API_HOST,
        port=API_PORT,
        debug=API_DEBUG
    )

