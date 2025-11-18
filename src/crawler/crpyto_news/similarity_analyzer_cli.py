"""
相似度分析 CLI 工具
调用 SimilarityAnalyzer 的分析逻辑，提供命令行交互界面
"""
import argparse
import sys
from datetime import datetime, timedelta, timezone
from collections import Counter
import os

# 添加项目根目录到路径
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.crypto_analysis.similarity_analyzer import SimilarityAnalyzer

# ======= 默认配置参数 =======
DEFAULT_DB_PATH = r"stream.db"
DEFAULT_TABLE = "messages"
DEFAULT_KEYWORD_COLUMN = "keywords"
DEFAULT_CURRENCY_COLUMN = "industry"
DEFAULT_MIN_COUNT = 5
DEFAULT_TOP_N = 100


def get_time_range_interactive():
    """
    交互式时间范围选择

    Returns:
        (start_time_iso, end_time_iso) 或 None（不限制）
    """
    print("""\n请输入对应数字选择时间范围:（回车代表不限制时间）
    1. 最近5分钟
    2. 最近15分钟
    3. 最近30分钟
    4. 最近60分钟
    5. 最近12小时
    6. 最近24小时
    7. 最近一周
    8. 最近30天
    9. 最近90天
    """)

    choice = input("请输入对应数字: ").strip()

    now = datetime.now(timezone.utc)
    time_mapping = {
        "1": timedelta(minutes=5),
        "2": timedelta(minutes=15),
        "3": timedelta(minutes=30),
        "4": timedelta(hours=1),
        "5": timedelta(hours=12),
        "6": timedelta(hours=24),
        "7": timedelta(days=7),
        "8": timedelta(days=30),
        "9": timedelta(days=90),
    }

    if choice not in time_mapping:
        return None  # 不限制时间

    start = now - time_mapping[choice]
    return (start.isoformat(), now.isoformat())


def get_channel_ids_interactive():
    """
    交互式频道选择

    Returns:
        频道 ID 列表，或 None（所有频道）
    """
    print("\n请输入对应数字选择频道:（回车代表所有频道）")
    print("1. @theblockbeats")
    print("2. @TechFlowDaily")
    print("3. @news6551")
    print("4. @MMSnews")

    choice = input("请输入对应数字，多个数字用空格分隔: ").strip()

    channel_map = {
        "1": "-1001387109317",
        "2": "-1001735732363",
        "3": "-1002395608815",
        "4": "-1002117032512",
    }

    if not choice:
        return None  # 所有频道

    channel_choices = choice.split()
    channel_ids = [channel_map.get(ch) for ch in channel_choices if ch in channel_map]

    return channel_ids if channel_ids else None


def print_counter_with_ratio(item_counter, occurrence_counter, total_rows, title, top_n=None):
    """打印计数结果（带比例）"""
    print(f"\n{'='*80}")
    print(f"{title}")
    print(f"{'='*80}")
    print(f"总种类数: {len(item_counter)}")
    print(f"总出现次数: {sum(item_counter.values())}")
    print(f"数据库总行数: {total_rows}\n")

    print(f"{'序号':<6}{'项目':<30}{'出现次数':<12}{'占比':<10}")
    print(f"{'-'*60}")

    items = item_counter.most_common(top_n) if top_n else item_counter.most_common()
    for i, (item, count) in enumerate(items, 1):
        occur_count = occurrence_counter[item]
        ratio = (occur_count / total_rows * 100) if total_rows > 0 else 0
        print(f"{i:<6}{item:<30}{count:<12}{ratio:.2f}%")


def print_counter(counter, title, top_n=None):
    """打印计数结果"""
    print(f"\n{'='*60}")
    print(f"{title}")
    print(f"{'='*60}")
    print(f"总种类数: {len(counter)}")
    print(f"总出现次数: {sum(counter.values())}\n")

    items = counter.most_common(top_n) if top_n else counter.most_common()
    for i, (item, count) in enumerate(items, 1):
        print(f"{i:>4}. {item}: {count}")


def print_similarity_results(pairs, top_n=None):
    """打印相似度结果"""
    print(f"\n{'='*60}")
    print(f"关键词相似度分析")
    print(f"{'='*60}")

    if not pairs:
        print("暂无相似度数据")
        return

    print(f"按相似度降序输出前 {min(top_n or len(pairs), len(pairs))} 对结果:")
    print(f"{'-'*60}")
    for i, (a, ca, b, cb, s) in enumerate(pairs[:top_n] if top_n else pairs, 1):
        print(f"{i:>4} | {a}({ca}) — {b}({cb}) : {s:.4f}")


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="相似度分析 CLI 工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python similarity_analyzer_cli.py                                    # 交互模式
  python similarity_analyzer_cli.py --db-path ./stream.db --min-count 3
  python similarity_analyzer_cli.py --no-interactive                   # 自动模式（不提示）
        """
    )

    parser.add_argument(
        "--db-path",
        type=str,
        default=DEFAULT_DB_PATH,
        help=f"数据库文件路径 (默认: {DEFAULT_DB_PATH})"
    )

    parser.add_argument(
        "--table",
        type=str,
        default=DEFAULT_TABLE,
        help=f"数据库表名 (默认: {DEFAULT_TABLE})"
    )

    parser.add_argument(
        "--keyword-column",
        type=str,
        default=DEFAULT_KEYWORD_COLUMN,
        help=f"关键词列名 (默认: {DEFAULT_KEYWORD_COLUMN})"
    )

    parser.add_argument(
        "--currency-column",
        type=str,
        default=DEFAULT_CURRENCY_COLUMN,
        help=f"币种列名 (默认: {DEFAULT_CURRENCY_COLUMN})"
    )

    parser.add_argument(
        "--min-count",
        type=int,
        default=DEFAULT_MIN_COUNT,
        help=f"相似度计算最小词频阈值 (默认: {DEFAULT_MIN_COUNT})"
    )

    parser.add_argument(
        "--top-n",
        type=int,
        default=DEFAULT_TOP_N,
        help=f"输出相似度结果前 N 对 (默认: {DEFAULT_TOP_N})"
    )

    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="禁用交互模式，使用默认参数"
    )

    return parser.parse_args()


def main():
    """主函数"""
    args = parse_arguments()

    print(f"\n{'#'*80}")
    print(f"# 相似度分析 CLI 工具")
    print(f"# 数据库: {args.db_path}")
    print(f"# 表名: {args.table}")
    print(f"# 最小词频: {args.min_count}")
    print(f"# 输出条数: {args.top_n}")
    print(f"{'#'*80}")

    analyzer = SimilarityAnalyzer(
        db_path=args.db_path,
        table=args.table,
        keyword_column=args.keyword_column,
        currency_column=args.currency_column,
        min_count=args.min_count,
        top_n=args.top_n,
    )

    # 获取筛选条件
    if args.no_interactive:
        time_range = None
        channel_ids = None
    else:
        time_range = get_time_range_interactive()
        channel_ids = get_channel_ids_interactive()

    print("\n[0/4] 统计数据库总行数...")
    total_rows = analyzer.get_total_rows(channel_ids=channel_ids, time_range=time_range)
    print(f"✓ 数据库总行数: {total_rows}")

    print("\n[1/4] 读取关键词数据...")
    keyword_rows = analyzer.fetch_column_data(analyzer.keyword_column, channel_ids=channel_ids, time_range=time_range)
    keyword_counter, keyword_occurrence = analyzer.count_items_with_occurrence(keyword_rows, case_insensitive=True)
    print_counter_with_ratio(
        keyword_counter,
        keyword_occurrence,
        total_rows,
        "关键词统计 (Keywords)",
        top_n=50
    )

    print("\n[2/4] 读取币种数据...")
    currency_rows = analyzer.fetch_column_data(analyzer.currency_column, channel_ids=channel_ids, time_range=time_range)
    currency_counter, currency_occurrence = analyzer.count_items_with_occurrence(currency_rows, case_insensitive=True)
    print_counter_with_ratio(
        currency_counter,
        currency_occurrence,
        total_rows,
        "币种统计 (Currency)",
        top_n=None
    )

    print("\n[3/4] 加载 spaCy 模型...")
    try:
        analyzer._load_spacy_model()
        print("✓ spaCy 模型加载成功")
    except Exception as e:
        print(f"✗ spaCy 模型加载失败: {e}")
        return

    print("\n[4/4] 计算关键词相似度...")
    pairs = analyzer.calculate_similarity(keyword_counter)

    print_similarity_results(pairs, top_n=args.top_n)

    print(f"\n{'='*80}")
    print("分析完成!")
    print(f"{'='*80}")
    print(f"✓ 数据库总行数: {total_rows}")
    print(f"✓ 关键词种类: {len(keyword_counter)}")
    print(f"✓ 币种种类: {len(currency_counter)}")
    print(f"✓ 相似度对数: {len(pairs)}")
    print(f"{'='*80}\n")

    # 交互式查询
    if not args.no_interactive:
        while True:
            input_keyword = input("请输入你感兴趣的关键词 (回车退出): ").strip()
            if not input_keyword:
                break

            print("="*60)
            exists, top_similar = analyzer.query_keyword_similarity(input_keyword, keyword_counter)

            if exists:
                print(f"✓ 关键词 '{input_keyword}' 在数据库中存在。")
            else:
                print(f"✗ 关键词 '{input_keyword}' 在数据库中不存在。")

            print("与输入关键词最接近的 top 10 关键词及相似度：")
            for i, (word, count, sim) in enumerate(top_similar, 1):
                print(f"{i}. {word} (出现次数: {count}) - 相似度: {sim:.4f}")

            print("="*60)
            print()


if __name__ == "__main__":
    main()
