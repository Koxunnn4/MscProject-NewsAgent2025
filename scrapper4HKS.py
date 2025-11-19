#!/usr/bin/env python3
"""展示生产者-消费者模式的唯一示例。"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


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
    
    print("\n✓ 生产者-消费者模式完成")
    print(f"  新增: {stats['saved']} 条")
    print(f"  更新: {stats['updated']} 条")
    print(f"  重复: {stats['duplicated']} 条")


def main():
    """主函数：直接运行生产者-消费者示例"""
    try:
        print("\n" + "="*60)
        print("AAStocks 生产者-消费者示例")
        print("="*60)
        print("\n开始运行示例 2（唯一保留模式）...")
        example_2_pipeline_mode()
        print("\n" + "="*60)
        print("执行完成")
        print("="*60)
    except KeyboardInterrupt:
        print("\n\n用户中断")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
