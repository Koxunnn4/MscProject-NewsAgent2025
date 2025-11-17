#!/usr/bin/env python3
"""
测试生产者-消费者模式与传统模式的性能对比
"""

import time
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.crawler.HKStocks import AaStocksScraper


def test_old_mode(days=1, max_count=20):
    """测试传统模式：先爬取再保存"""
    print("\n" + "="*70)
    print("测试 1: 传统模式 (先爬取再保存)")
    print("="*70)
    
    scraper = AaStocksScraper()
    
    start_time = time.time()
    
    # 爬取新闻
    print("\n阶段1: 爬取新闻...")
    news_list = scraper.fetch_news(days=days, max_count=max_count, use_selenium=False)
    
    crawl_time = time.time() - start_time
    print(f"\n爬取完成: {len(news_list)} 条新闻，耗时 {crawl_time:.2f} 秒")
    
    # 保存新闻
    if news_list:
        print("\n阶段2: 保存到数据库...")
        save_start = time.time()
        saved_count = scraper.save_to_database(news_list, extract_keywords=True)
        save_time = time.time() - save_start
        
        total_time = time.time() - start_time
        
        print(f"\n保存完成: {saved_count} 条新闻，耗时 {save_time:.2f} 秒")
        print(f"\n总耗时: {total_time:.2f} 秒")
        
        return {
            'mode': 'traditional',
            'total_time': total_time,
            'crawl_time': crawl_time,
            'save_time': save_time,
            'count': len(news_list),
            'saved': saved_count
        }
    
    return None


def test_pipeline_mode(days=1, max_count=20, num_workers=3):
    """测试生产者-消费者模式：边爬取边保存"""
    print("\n" + "="*70)
    print(f"测试 2: 生产者-消费者模式 (边爬取边保存, {num_workers} 个工作线程)")
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


def compare_results(result1, result2):
    """比较两种模式的结果"""
    print("\n" + "="*70)
    print("性能对比结果")
    print("="*70)
    
    if result1 and result2:
        print(f"\n传统模式:")
        print(f"  总耗时: {result1['total_time']:.2f} 秒")
        print(f"  爬取时间: {result1['crawl_time']:.2f} 秒")
        print(f"  保存时间: {result1['save_time']:.2f} 秒")
        print(f"  处理新闻: {result1['count']} 条")
        
        print(f"\n生产者-消费者模式 ({result2['workers']} 个工作线程):")
        print(f"  总耗时: {result2['total_time']:.2f} 秒")
        print(f"  处理新闻: {result2['count']} 条")
        print(f"  新增: {result2['saved']} 条")
        print(f"  更新: {result2['updated']} 条")
        print(f"  重复: {result2['duplicated']} 条")
        
        # 计算性能提升
        improvement = ((result1['total_time'] - result2['total_time']) / result1['total_time']) * 100
        
        print(f"\n性能提升:")
        if improvement > 0:
            print(f"  ✓ 新模式快 {improvement:.1f}%")
            print(f"  ✓ 节省时间: {result1['total_time'] - result2['total_time']:.2f} 秒")
        else:
            print(f"  × 新模式慢 {abs(improvement):.1f}%")
        
        print(f"\n效率分析:")
        old_speed = result1['count'] / result1['total_time'] if result1['total_time'] > 0 else 0
        new_speed = result2['count'] / result2['total_time'] if result2['total_time'] > 0 else 0
        print(f"  传统模式: {old_speed:.2f} 条/秒")
        print(f"  新模式: {new_speed:.2f} 条/秒")
        print(f"  提升倍数: {new_speed/old_speed:.2f}x" if old_speed > 0 else "  N/A")
        
    print("\n" + "="*70)


def main():
    """主函数"""
    print("\n" + "="*70)
    print("港股新闻爬虫性能对比测试")
    print("="*70)
    print("\n注意: 为了公平对比，两次测试将爬取相同数量的新闻")
    print("      第二次测试可能会遇到重复新闻，这是正常的\n")
    
    # 测试参数
    DAYS = 1
    MAX_COUNT = 20
    NUM_WORKERS = 3
    
    try:
        # 测试传统模式
        result1 = test_old_mode(days=DAYS, max_count=MAX_COUNT)
        
        # 等待一下
        time.sleep(2)
        
        # 测试生产者-消费者模式
        result2 = test_pipeline_mode(days=DAYS, max_count=MAX_COUNT, num_workers=NUM_WORKERS)
        
        # 对比结果
        compare_results(result1, result2)
        
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
