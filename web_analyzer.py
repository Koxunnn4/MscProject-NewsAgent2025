"""
相似度分析工具 - Web 前端版本
使用 Flask 提供后端 API，前端通过 HTML/JS 呈现
已适配重构后的分析模块：使用 SimilarityAnalyzer 和 model_loader
"""
import sqlite3
import re
import argparse
import json
from datetime import datetime, timedelta, timezone
from collections import Counter
from flask import Flask, render_template, request, jsonify, send_from_directory
from pathlib import Path
import os
import sys
import logging

# 添加项目根目录到路径
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 导入新的分析模块
from src.crypto_analysis.similarity_analyzer import SimilarityAnalyzer
from src.crypto_analysis.model_loader import get_spacy_model

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ======= 默认配置参数 =======
DEFAULT_DB_PATH = r"E:\msc_proj\cjyBranch\MscProject-NewsAgent2025-chenjingyin\src\crawler\crpyto_news\stream.db"
DEFAULT_TABLE = "messages"
DEFAULT_KEYWORD_COLUMN = "keywords"
DEFAULT_CURRENCY_COLUMN = "industry"
DEFAULT_MIN_COUNT = 5
DEFAULT_TOP_N = 100

SPLIT_RE = re.compile(r"[,，]+")

# 频道映射
CHANNEL_MAP = {
    "1": ("-1001387109317", "@theblockbeats"),
    "2": ("-1001735732363", "@TechFlowDaily"),
    "3": ("-1002395608815", "@news6551"),
    "4": ("-1002117032512", "@MMSnews"),
}

app = Flask(__name__, template_folder='templates', static_folder='static')

class WebSimilarityAnalyzer:
    """
    Web 版本的相似度分析器
    基于 SimilarityAnalyzer 的包装，提供 Web API 所需的接口
    """

    def __init__(self, db_path=DEFAULT_DB_PATH, table=DEFAULT_TABLE,
                 keyword_column=DEFAULT_KEYWORD_COLUMN,
                 currency_column=DEFAULT_CURRENCY_COLUMN,
                 min_count=DEFAULT_MIN_COUNT, top_n=DEFAULT_TOP_N):
        """初始化分析器，创建 SimilarityAnalyzer 实例"""
        self.db_path = db_path
        self.table = table
        self.keyword_column = keyword_column
        self.currency_column = currency_column
        self.min_count = min_count
        self.top_n = top_n

        # 使用新的分析模块
        try:
            self.analyzer = SimilarityAnalyzer(
                db_path=db_path,
                table=table,
                keyword_column=keyword_column,
                currency_column=currency_column,
                min_count=min_count,
                top_n=top_n
            )
            logger.info(f"✓ 分析器初始化成功 | 数据库: {db_path}")
        except Exception as e:
            logger.error(f"✗ 分析器初始化失败: {e}")
            self.analyzer = None

    def get_total_rows(self, channel_ids=None, time_range=None):
        """获取数据库总行数"""
        try:
            return self.analyzer.get_total_rows(channel_ids=channel_ids, time_range=time_range)
        except Exception as e:
            logger.error(f"获取总行数失败: {e}")
            return 0

    def fetch_column_data(self, column, channel_ids=None, time_range=None):
        """从数据库读取指定列数据"""
        try:
            return self.analyzer.fetch_column_data(column=column, channel_ids=channel_ids, time_range=time_range)
        except Exception as e:
            logger.error(f"读取列数据失败: {e}")
            return []

    def count_items_with_occurrence(self, rows, case_insensitive=True):
        """统计分隔字符串中各项的出现次数"""
        try:
            return self.analyzer.count_items_with_occurrence(rows=rows, case_insensitive=case_insensitive)
        except Exception as e:
            logger.error(f"统计项目出现次数失败: {e}")
            return Counter(), Counter()

    def calculate_similarity(self, keyword_counter, limit=None):
        """
        计算关键词相似度

        Args:
            keyword_counter: 关键词计数器
            limit: 返回结果数量限制

        Returns:
            相似度对列表
        """
        try:
            pairs = self.analyzer.calculate_similarity(keyword_counter)
            limit = limit or self.top_n
            return pairs[:limit]
        except Exception as e:
            logger.error(f"计算相似度失败: {e}")
            return []

    def query_keyword_similarity(self, input_keyword, keyword_counter):
        """
        查询关键词相似度

        Args:
            input_keyword: 输入的关键词
            keyword_counter: 关键词计数器

        Returns:
            (exists, similar_words) 元组
        """
        try:
            return self.analyzer.query_keyword_similarity(
                input_keyword=input_keyword,
                keyword_counter=keyword_counter,
                top_n=10
            )
        except Exception as e:
            logger.error(f"查询相似度失败: {e}")
            return False, []


# 初始化分析器
analyzer = WebSimilarityAnalyzer()


@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


@app.route('/api/analyze', methods=['POST'])
def analyze():
    """分析数据的主要接口"""
    try:
        data = request.json
        channel_ids = data.get('channel_ids', [])
        time_range = data.get('time_range')

        print(f"\n📊 开始分析...")
        print(f"   频道 ID: {channel_ids}")
        print(f"   时间范围: {time_range}")

        # 获取数据库总行数
        total_rows = analyzer.get_total_rows(channel_ids or None, time_range)
        print(f"✓ 总行数: {total_rows}")

        # 获取关键词数据
        print("📥 正在读取关键词数据...")
        keyword_rows = analyzer.fetch_column_data(
            analyzer.keyword_column,
            channel_ids or None,
            time_range
        )
        print(f"✓ 读取关键词行数: {len(keyword_rows)}")
        keyword_counter, keyword_occurrence = analyzer.count_items_with_occurrence(keyword_rows)
        print(f"✓ 关键词种类: {len(keyword_counter)}")

        # 获取币种数据
        print("📥 正在读取币种数据...")
        currency_rows = analyzer.fetch_column_data(
            analyzer.currency_column,
            channel_ids or None,
            time_range
        )
        print(f"✓ 读取币种行数: {len(currency_rows)}")
        currency_counter, currency_occurrence = analyzer.count_items_with_occurrence(currency_rows)
        print(f"✓ 币种种类: {len(currency_counter)}")

        # 计算相似度（返回 top 50）
        print("🔗 计算相似度...")
        similarity_pairs = analyzer.calculate_similarity(keyword_counter, limit=50)
        similarity_results = [
            {
                'word1': a,
                'count1': ca,
                'word2': b,
                'count2': cb,
                'similarity': round(s, 4)
            }
            for a, ca, b, cb, s in similarity_pairs
        ]

        # 构建关键词统计结果（返回全部数据，由前端分页）
        print("📝 构建关键词统计...")
        keyword_stats = []
        for word, count in keyword_counter.most_common():
            occur_count = keyword_occurrence[word]
            ratio = (occur_count / total_rows * 100) if total_rows > 0 else 0
            keyword_stats.append({
                'word': word,
                'count': count,
                'occur_count': occur_count,
                'ratio': round(ratio, 2)
            })
        print(f"✓ 关键词统计条目: {len(keyword_stats)}")

        # 构建币种统计结果
        print("💰 构建币种统计...")
        currency_stats = []
        for word, count in currency_counter.most_common():
            occur_count = currency_occurrence[word]
            ratio = (occur_count / total_rows * 100) if total_rows > 0 else 0
            currency_stats.append({
                'word': word,
                'count': count,
                'occur_count': occur_count,
                'ratio': round(ratio, 2)
            })
        print(f"✓ 币种统计条目: {len(currency_stats)}")

        print("✅ 分析完成\n")
        return jsonify({
            'success': True,
            'total_rows': total_rows,
            'keyword_stats': keyword_stats,
            'currency_stats': currency_stats,
            'similarity_results': similarity_results,
            'keyword_total': len(keyword_counter),
            'currency_total': len(currency_counter)
        })

    except Exception as e:
        print(f"❌ 分析失败: {e}\n")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/query-keyword', methods=['POST'])
def query_keyword():
    """查询关键词相似度"""
    try:
        data = request.json
        keyword = data.get('keyword', '').strip()
        channel_ids = data.get('channel_ids', [])
        time_range = data.get('time_range')

        print(f"\n🔍 查询请求: '{keyword}'")

        if not keyword:
            print("⚠️ 关键词为空")
            return jsonify({'success': False, 'error': '请输入关键词'}), 400

        # 获取范围内的关键词统计
        print("📥 正在读取关键词数据...")
        keyword_rows = analyzer.fetch_column_data(
            analyzer.keyword_column,
            channel_ids or None,
            time_range
        )
        print(f"✓ 读取关键词行数: {len(keyword_rows)}")
        keyword_counter, _ = analyzer.count_items_with_occurrence(keyword_rows)
        print(f"✓ 关键词种类: {len(keyword_counter)}")

        # 查询相似度
        exists, top_similar = analyzer.query_keyword_similarity(keyword, keyword_counter)

        similar_results = [
            {
                'word': word,
                'count': count,
                'similarity': round(similarity, 4)
            }
            for word, count, similarity in top_similar
        ]

        print(f"✅ 查询完成，找到 {len(similar_results)} 个相似词\n")
        return jsonify({
            'success': True,
            'keyword': keyword,
            'exists': exists,
            'similar_words': similar_results
        })

    except Exception as e:
        print(f"❌ 查询失败: {e}\n")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500
@app.route('/api/channels', methods=['GET'])
def get_channels():
    """获取可用频道列表"""
    channels = [
        {'id': k, 'name': v[1], 'channel_id': v[0]}
        for k, v in CHANNEL_MAP.items()
    ]
    return jsonify({'channels': channels})


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="Web 版本相似度分析工具")
    parser.add_argument('--db-path', type=str, default=DEFAULT_DB_PATH,
                       help="数据库文件路径")
    parser.add_argument('--table', type=str, default=DEFAULT_TABLE,
                       help="数据库表名")
    parser.add_argument('--port', type=int, default=5000,
                       help="Flask 服务端口")
    parser.add_argument('--host', type=str, default='127.0.0.1',
                       help="Flask 服务主机")
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_arguments()
    analyzer.db_path = args.db_path
    analyzer.table = args.table

    print(f"\n{'='*80}")
    print("相似度分析工具 - Web 版本")
    print(f"{'='*80}")
    print(f"数据库: {args.db_path}")
    print(f"表名: {args.table}")
    print(f"服务器: http://{args.host}:{args.port}")
    print(f"{'='*80}\n")

    app.run(host=args.host, port=args.port, debug=True)
