#!/usr/bin/env python3
"""仅保留生产者-消费者模式的港股新闻爬虫脚本。"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(
        description='港股新闻爬虫 - 自动提取关键词',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    # 使用默认参数（最近1天，3个工作线程）
    python run_hkstocks_crawler.py

    # 爬取最近3天的新闻，使用5个工作线程
    python run_hkstocks_crawler.py --days 3 --workers 5

    # 限制爬取数量为50条
    python run_hkstocks_crawler.py --max-count 50

    # 使用Selenium滚动加载更多新闻
    python run_hkstocks_crawler.py --use-selenium --max-count 100

    # 不提取关键词（仅保存原文）
    python run_hkstocks_crawler.py --no-keywords
        """
    )

    parser.add_argument(
        '--days',
        type=int,
        default=1,
        help='爬取最近几天的新闻（默认: 1）'
    )

    parser.add_argument(
        '--max-count',
        type=int,
        default=1000,
        help='最多爬取数量（默认: 1000）'
    )

    parser.add_argument(
        '--no-keywords',
        action='store_true',
        help='不提取关键词'
    )

    parser.add_argument(
        '--workers',
        type=int,
        default=3,
        help='消费者线程数量（默认: 3）'
    )

    parser.add_argument(
        '--use-selenium',
        action='store_true',
        help='使用Selenium滚动加载更多新闻'
    )

    args = parser.parse_args()

    print("=" * 60)
    print("港股新闻爬虫 - AAStocks")
    print("=" * 60)
    print(f"爬取范围: 最近 {args.days} 天")
    print(f"最大数量: {args.max_count} 条")
    print(f"提取关键词: {'否' if args.no_keywords else '是'}")
    print(f"使用Selenium: {'是' if args.use_selenium else '否'}")
    print(f"工作模式: 生产者-消费者 (线程数: {args.workers})")
    print("=" * 60)

    try:
        # 导入爬虫
        from src.crawler.HKStocks import AaStocksScraper

        # 创建爬虫实例
        scraper = AaStocksScraper()

        print("\n使用生产者-消费者模式...")
        stats = scraper.fetch_and_save_with_pipeline(
            days=args.days,
            max_count=args.max_count,
            use_selenium=args.use_selenium,
            extract_keywords=not args.no_keywords,
            num_workers=args.workers
        )

        print("\n运行完成:")
        print(f"  新增: {stats['saved']}")
        print(f"  更新: {stats['updated']}")
        print(f"  重复: {stats['duplicated']}")
        print(f"  失败: {stats['failed']}")

        import sqlite3
        db_path = project_root / 'data' / 'news_analysis.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM hkstocks_news")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM hkstocks_news WHERE keywords IS NOT NULL")
        with_keywords = cursor.fetchone()[0]

        conn.close()

        print("\n" + "=" * 60)
        print("数据库统计")
        print("=" * 60)
        print(f"总新闻数: {total}")
        print(f"已提取关键词: {with_keywords}")
        print(f"未提取关键词: {total - with_keywords}")
        print("=" * 60)

    except ImportError as e:
        print(f"\n错误: 模块导入失败: {e}")
        print("\n请确保已安装所有依赖:")
        print("  pip install -r requirements.txt")
        if not args.no_keywords:
            print("  python -m spacy download zh_core_web_sm")
        sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n用户中断")
        sys.exit(0)

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
