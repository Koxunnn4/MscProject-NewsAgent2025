#!/usr/bin/env python3
"""
港股新闻爬虫运行脚本

爬取 AAStocks 港股新闻并自动提取关键词
"""

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
  # 使用生产者-消费者模式爬取最近1天的新闻（默认，3个工作线程）
  python run_hkstocks_crawler.py

  # 爬取最近3天的新闻，使用5个工作线程
  python run_hkstocks_crawler.py --days 3 --workers 5

  # 限制爬取数量为50条
  python run_hkstocks_crawler.py --max-count 50

  # 使用Selenium滚动加载更多新闻
  python run_hkstocks_crawler.py --use-selenium --max-count 100

  # 使用旧的传统模式（先爬取再保存）
  python run_hkstocks_crawler.py --old-mode

  # 不提取关键词
  python run_hkstocks_crawler.py --no-keywords

  # 不保存到数据库（仅测试）
  python run_hkstocks_crawler.py --no-save
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
        '--no-save',
        action='store_true',
        help='不保存到数据库（仅测试爬取）'
    )

    parser.add_argument(
        '--workers',
        type=int,
        default=3,
        help='消费者线程数量（默认: 3）'
    )

    parser.add_argument(
        '--old-mode',
        action='store_true',
        help='使用旧的先爬取再保存模式（默认使用新的生产者-消费者模式）'
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
    print(f"保存数据库: {'否' if args.no_save else '是'}")
    print(f"使用Selenium: {'是' if args.use_selenium else '否'}")
    if not args.no_save and not args.old_mode:
        print(f"工作模式: 生产者-消费者 (线程数: {args.workers})")
    else:
        print(f"工作模式: 传统模式")
    print("=" * 60)

    try:
        # 导入爬虫
        from src.crawler.HKStocks import AaStocksScraper

        # 创建爬虫实例
        scraper = AaStocksScraper()

        # 如果不保存或使用旧模式，使用传统方式
        if args.no_save or args.old_mode:
            # 传统模式：先爬取再保存
            print("\n开始爬取...")
            news_list = scraper.fetch_news(
                days=args.days,
                max_count=args.max_count,
                use_selenium=args.use_selenium
            )

            if not news_list:
                print("\n未爬取到新闻")
                return

            print(f"\n成功爬取 {len(news_list)} 条新闻")

            # 保存到数据库
            if not args.no_save:
                print("\n保存到数据库...")
                saved_count = scraper.save_to_database(
                    news_list,
                    extract_keywords=not args.no_keywords
                )
                print(f"\n完成！实际保存 {saved_count} 条新闻")
            else:
                print("\n跳过数据库保存")
                # 显示前3条新闻预览
                print("\n前3条新闻预览:")
                for i, news in enumerate(news_list[:3], 1):
                    print(f"\n{i}. {news.title}")
                    print(f"   时间: {news.publish_date}")
                    print(f"   链接: {news.url}")
                    print(f"   内容: {news.content[:100]}...")

        else:
            # 新模式：生产者-消费者，边爬取边保存
            print("\n使用生产者-消费者模式...")
            stats = scraper.fetch_and_save_with_pipeline(
                days=args.days,
                max_count=args.max_count,
                use_selenium=args.use_selenium,
                extract_keywords=not args.no_keywords,
                num_workers=args.workers
            )

        # 显示统计信息
        if not args.no_save:
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
