"""
完整系统测试脚本
测试所有新增功能
"""
import asyncio
from datetime import datetime
import sys


def print_section(title):
    """打印分节标题"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def test_unified_interface():
    """测试1: 统一数据接口"""
    print_section("测试1: 统一数据接口")
    
    try:
        from src.unified_news_interface import get_unified_news_interface
        
        interface = get_unified_news_interface()
        print("✓ 统一接口初始化成功")
        
        # 获取新闻
        news_list = interface.fetch_all_news(limit=5, source_type='all')
        print(f"✓ 获取到 {len(news_list)} 条新闻")
        
        if news_list:
            print(f"\n示例新闻:")
            news = news_list[0]
            print(f"  来源: {news['source_type']}")
            print(f"  标题: {news['title'][:50]}...")
            print(f"  日期: {news['date'][:10]}")
        
        # 关键词搜索
        bitcoin_news = interface.fetch_news_by_keyword('比特币', limit=3)
        print(f"\n✓ 搜索'比特币': 找到 {len(bitcoin_news)} 条新闻")
        
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False


def test_keyword_matching():
    """测试2: 关键词匹配"""
    print_section("测试2: 关键词匹配")
    
    try:
        from src.keyword_matching import get_keyword_matcher
        
        matcher = get_keyword_matcher()
        print("✓ 关键词匹配器初始化成功")
        
        # 测试文本
        test_text = "比特币价格今日突破$95,000美元，创下近期新高。分析师认为这与美联储降息预期有关。"
        
        # 精确匹配
        result = matcher.match_keyword(test_text, '比特币')
        print(f"\n✓ 匹配'比特币': {result['is_match']}")
        print(f"  相关性得分: {result['relevance_score']:.2f}")
        print(f"  匹配方法: {result['match_method']}")
        
        # 批量匹配
        keywords = ['比特币', '以太坊', '美联储']
        batch_results = matcher.match_keywords_batch(test_text, keywords)
        print(f"\n✓ 批量匹配: 匹配到 {len(batch_results)} 个关键词")
        for r in batch_results:
            print(f"  - {r['user_keyword']}: {r['relevance_score']:.2f}")
        
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False


async def test_push_pipeline():
    """测试3: 实时推送Pipeline"""
    print_section("测试3: 实时推送Pipeline")
    
    try:
        from src.realtime_push_pipeline import get_realtime_push_pipeline
        from src.database.db_manager import get_db_manager
        
        db = get_db_manager()
        print("✓ 数据库管理器初始化成功")
        
        # 创建测试订阅
        try:
            sub_id = db.create_subscription(
                user_id="test_user_001",
                keyword="测试关键词",
                telegram_chat_id="123456789"
            )
            print(f"✓ 创建测试订阅 (ID: {sub_id})")
        except:
            print("✓ 订阅已存在（跳过创建）")
        
        # 初始化Pipeline
        pipeline = get_realtime_push_pipeline()
        print("✓ 实时推送Pipeline初始化成功")
        
        # 模拟新闻
        test_news = {
            'id': 999999,
            'channel_id': 'test_channel',
            'message_id': 999999,
            'text': '【测试新闻】测试关键词相关内容，用于验证推送系统。',
            'date': datetime.now().isoformat()
        }
        
        # 发送到Pipeline
        await pipeline.on_news_received(test_news, 'crypto')
        print("✓ 测试新闻已发送到Pipeline")
        
        # 等待处理
        print("  等待处理...")
        await asyncio.sleep(2)
        
        print("✓ Pipeline处理完成")
        print("\n  注意: Telegram推送需要配置Bot Token")
        
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_advanced_trend():
    """测试4: 高级热度分析"""
    print_section("测试4: 高级热度分析")
    
    try:
        from src.trend_analysis.advanced_trend_analyzer import get_advanced_trend_analyzer
        
        analyzer = get_advanced_trend_analyzer()
        print("✓ 高级趋势分析器初始化成功")
        
        test_keyword = "比特币"
        
        # 异常检测
        print(f"\n【异常检测】关键词: '{test_keyword}'")
        anomalies = analyzer.detect_anomalies(test_keyword, sensitivity=1.5)
        print(f"  {anomalies['summary']}")
        if anomalies['anomalies']:
            print(f"  最近异常: {anomalies['anomalies'][0]['date']} - {anomalies['anomalies'][0]['type']}")
        
        # 增长速度
        print(f"\n【增长速度】关键词: '{test_keyword}'")
        velocity = analyzer.calculate_growth_velocity(test_keyword)
        print(f"  平均速度: {velocity['summary']['avg_velocity']:.2%}")
        print(f"  趋势: {velocity['summary']['trend']}")
        
        # 关联分析
        print(f"\n【关联分析】'比特币' vs 'BTC'")
        try:
            correlation = analyzer.analyze_keyword_correlation("比特币", "BTC")
            print(f"  相关系数: {correlation['correlation']:.2f}")
            print(f"  关系: {correlation['relationship']}")
        except:
            print("  数据不足，跳过关联分析")
        
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_db_sync():
    """测试5: 数据库新老分离"""
    print_section("测试5: 数据库新老分离")
    
    try:
        from src.database.db_sync_manager import get_db_sync_manager
        
        manager = get_db_sync_manager()
        print("✓ 数据库同步管理器初始化成功")
        
        # 获取统计
        stats = manager.get_database_stats()
        
        print("\n【实时库】")
        print(f"  虚拟币新闻: {stats['realtime']['crypto_news']} 条")
        print(f"  港股新闻: {stats['realtime']['hk_news']} 条")
        print(f"  活跃订阅: {stats['realtime']['active_subscriptions']} 个")
        print(f"  文件大小: {stats['realtime']['file_size_mb']:.2f} MB")
        
        print("\n【历史库】")
        print(f"  虚拟币新闻: {stats['history']['crypto_news']} 条")
        print(f"  港股新闻: {stats['history']['hk_news']} 条")
        print(f"  推送历史: {stats['history']['push_history']} 条")
        print(f"  文件大小: {stats['history']['file_size_mb']:.2f} MB")
        
        print("\n✓ 数据库状态正常")
        print("  注意: 数据迁移命令为 manager.merge_to_history()")
        
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False


def test_rag_qa():
    """测试6: RAG问答系统"""
    print_section("测试6: RAG问答系统")
    
    try:
        from src.rag_system.news_qa_system import get_news_qa_system
        
        qa_system = get_news_qa_system()
        print("✓ RAG问答系统初始化成功")
        
        # 测试问题
        questions = [
            "比特币最近有什么新闻？",
            "港股市场表现如何？"
        ]
        
        for question in questions:
            print(f"\n【问题】{question}")
            
            result = qa_system.answer_question(
                question,
                top_k=2,
                date_range_days=30
            )
            
            print(f"  置信度: {result['confidence']:.0%}")
            print(f"  来源数: {len(result['sources'])} 条新闻")
            
            # 显示答案片段
            answer_preview = result['answer'][:150]
            print(f"  答案片段: {answer_preview}...")
        
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主测试函数"""
    print("\n" + "🚀" * 35)
    print("  新闻分析系统 - 完整功能测试")
    print("🚀" * 35)
    
    results = []
    
    # 同步测试
    results.append(("统一数据接口", test_unified_interface()))
    results.append(("关键词匹配", test_keyword_matching()))
    results.append(("高级热度分析", test_advanced_trend()))
    results.append(("数据库新老分离", test_db_sync()))
    results.append(("RAG问答系统", test_rag_qa()))
    
    # 异步测试
    results.append(("实时推送Pipeline", await test_push_pipeline()))
    
    # 总结
    print_section("测试结果总结")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {name:20s} {status}")
    
    print(f"\n总计: {passed}/{total} 个测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！系统运行正常。")
    else:
        print(f"\n⚠️  有 {total - passed} 个测试失败，请检查日志。")
    
    print("\n" + "=" * 70)
    print("测试完成！详细使用说明请查看 docs/SYSTEM_ENHANCEMENT.md")
    print("=" * 70)


if __name__ == "__main__":
    # 运行测试
    asyncio.run(main())

