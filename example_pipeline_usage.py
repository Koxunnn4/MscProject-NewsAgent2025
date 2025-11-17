#!/usr/bin/env python3
"""
简单示例：展示如何使用生产者-消费者模式
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def example_1_traditional_mode():
    """示例1: 传统模式（先爬取再保存）"""
    print("\n" + "="*60)
    print("示例 1: 传统模式")
    print("="*60)
    
    from src.crawler.HKStocks import AaStocksScraper
    
    scraper = AaStocksScraper()
    
    # 步骤1: 爬取所有新闻（阻塞，等待爬取完成）
    print("\n[1/2] 正在爬取新闻...")
    news_list = scraper.fetch_news(days=1, max_count=5)
    print(f"爬取完成: {len(news_list)} 条")
    
    # 步骤2: 保存所有新闻（阻塞，等待保存完成）
    print("\n[2/2] 正在保存到数据库...")
    saved_count = scraper.save_to_database(news_list, extract_keywords=True)
    print(f"保存完成: {saved_count} 条")
    
    print("\n✓ 传统模式完成")


def example_2_pipeline_mode():
    """示例2: 生产者-消费者模式（边爬取边保存）"""
    print("\n" + "="*60)
    print("示例 2: 生产者-消费者模式")
    print("="*60)
    
    from src.crawler.HKStocks import AaStocksScraper
    
    scraper = AaStocksScraper()
    
    # 一步完成：边爬取边保存（并行处理）
    print("\n正在并行爬取和保存...")
    stats = scraper.fetch_and_save_with_pipeline(
        days=15,
        max_count=1000,
        use_selenium=True,
        extract_keywords=True,
        num_workers=2  # 使用2个工作线程
    )
    
    print(f"\n✓ 生产者-消费者模式完成")
    print(f"  新增: {stats['saved']} 条")
    print(f"  更新: {stats['updated']} 条")
    print(f"  重复: {stats['duplicated']} 条")


def example_3_custom_workers():
    """示例3: 自定义工作线程数量"""
    print("\n" + "="*60)
    print("示例 3: 自定义工作线程数量")
    print("="*60)
    
    from src.crawler.HKStocks import AaStocksScraper
    
    scraper = AaStocksScraper()
    
    # 使用5个工作线程，适合快速网络和强劲CPU
    print("\n使用 5 个工作线程...")
    stats = scraper.fetch_and_save_with_pipeline(
        days=1,
        max_count=10,
        use_selenium=False,
        extract_keywords=True,
        num_workers=5  # 5个工作线程并行处理
    )
    
    print(f"\n✓ 完成 (5个工作线程)")
    print(f"  处理: {stats['processed']} 条")
    print(f"  新增: {stats['saved']} 条")


def main():
    """主函数"""
    print("\n" + "="*60)
    print("生产者-消费者模式使用示例")
    print("="*60)
    print("\n请选择要运行的示例：")
    print("1. 传统模式（先爬取再保存）")
    print("2. 生产者-消费者模式（推荐）")
    print("3. 自定义工作线程数量")
    print("4. 运行全部示例")
    print("0. 退出")
    
    try:
        choice = input("\n请输入选项 (0-4): ").strip()
        
        if choice == '1':
            example_1_traditional_mode()
        elif choice == '2':
            example_2_pipeline_mode()
        elif choice == '3':
            example_3_custom_workers()
        elif choice == '4':
            print("\n将依次运行所有示例...\n")
            example_1_traditional_mode()
            example_2_pipeline_mode()
            example_3_custom_workers()
        elif choice == '0':
            print("\n再见！")
            return
        else:
            print("\n无效的选项")
            return
        
        print("\n" + "="*60)
        print("示例运行完成！")
        print("="*60)
        print("\n提示：")
        print("- 生产者-消费者模式可以显著提升大规模爬取的效率")
        print("- 建议根据网络速度和CPU性能调整工作线程数量")
        print("- 默认3个工作线程适合大多数情况")
        print("\n详细文档请查看: PIPELINE_MODE.md")
        
    except KeyboardInterrupt:
        print("\n\n用户中断")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
