#!/usr/bin/env python3
"""仅验证生产者-消费者模式表现。"""

import time
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.crawler.HKStocks import AaStocksScraper


def test_pipeline_mode(days=1, max_count=20, num_workers=3):
    """测试生产者-消费者模式：边爬取边保存"""
    print("\n" + "="*70)
    print(f"生产者-消费者模式 (边爬取边保存, {num_workers} 个工作线程)")
    print("="*70)
    
    scraper = AaStocksScraper()
    
    start_time = time.time()
    
    # 使用生产者-消费者模式
    stats = scraper.fetch_and_save_with_pipeline(
        days=days,
        max_count=max_count,
        use_selenium=False,
        extract_keywords=True,
        num_workers=num_workers
    )
    
    total_time = time.time() - start_time
    
    print(f"\n总耗时: {total_time:.2f} 秒")
    
    assert stats['processed'] >= stats['saved'], "处理数量应大于等于新增数量"
    assert num_workers >= 1, "至少需要1个工作线程"

    return {
        'mode': 'pipeline',
        'total_time': total_time,
        'count': stats['processed'],
        'saved': stats['saved'],
        'updated': stats['updated'],
        'duplicated': stats['duplicated'],
        'failed': stats['failed'],
        'workers': num_workers
    }


def main():
    """主函数"""
    print("\n" + "="*70)
    print("港股新闻爬虫性能测试 (仅生产者-消费者)")
    print("="*70)
    
    # 测试参数
    DAYS = 1
    MAX_COUNT = 20
    NUM_WORKERS = 3
    
    try:
        result = test_pipeline_mode(days=DAYS, max_count=MAX_COUNT, num_workers=NUM_WORKERS)
        print("\n测试结果:")
        print(f"  总耗时: {result['total_time']:.2f} 秒")
        print(f"  处理新闻: {result['count']} 条")
        print(f"  新增: {result['saved']} 条")
        print(f"  更新: {result['updated']} 条")
        print(f"  重复: {result['duplicated']} 条")
        print(f"  失败: {result['failed']} 条")
        
    except KeyboardInterrupt:
        print("\n\n用户中断测试")
        sys.exit(0)
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
