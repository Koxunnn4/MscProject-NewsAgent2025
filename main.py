"""
新闻分析系统 - 主程序入口
"""
import os
import sys
import asyncio
import argparse

# 添加项目根目录到路径
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from config import PROJECT_ROOT, DATA_DIR, LOGS_DIR
from src.database.db_manager import get_db_manager
from src.crypto_analysis.keyword_extractor import get_keyword_extractor
from src.trend_analysis.trend_analyzer import get_trend_analyzer
from src.push_system.push_manager import get_push_manager


def init_system():
    """初始化系统"""
    print("=" * 70)
    print("  新闻分析系统初始化")
    print("=" * 70)
    print()

    # 1. 初始化数据库
    print("[1/3] 初始化数据库...")
    db = get_db_manager()
    print("✓ 数据库初始化完成\n")

    # 2. 加载模型
    print("[2/3] 加载模型...")
    extractor = get_keyword_extractor()
    print("✓ 模型加载完成\n")

    # 3. 检查数据
    print("[3/3] 检查数据...")
    query = "SELECT COUNT(*) as count FROM messages"
    count = db.execute_query(query, db_path=db.history_db_path)[0]['count']
    print(f"✓ 数据库中有 {count} 条新闻\n")

    print("=" * 70)
    print("  系统初始化完成")
    print("=" * 70)
    print()


def run_api_server():
    """运行 API 服务器"""
    from api.app import app
    from config import API_HOST, API_PORT

    print("\n启动 API 服务器...")
    app.run(host=API_HOST, port=API_PORT, debug=False)


def run_push_service():
    """运行推送服务"""
    push_manager = get_push_manager()

    print("\n启动推送服务...")
    asyncio.run(push_manager.run_push_service())


def run_trend_analysis_demo():
    """运行热度分析演示"""
    analyzer = get_trend_analyzer()

    print("\n" + "=" * 70)
    print("  热度分析演示")
    print("=" * 70)
    print()

    # 1. 单关键词分析
    print("【1】分析关键词: 比特币")
    trend = analyzer.analyze_keyword_trend("比特币")
    print(f"  总计: {trend['total_count']}条")
    print(f"  活跃天数: {trend['active_days']}天")
    print(f"  时间范围: {trend['date_range'][0]} ~ {trend['date_range'][1]}")
    print()

    # 2. 多关键词对比
    print("【2】对比关键词: 比特币 vs BTC vs Jupiter")
    comparison = analyzer.compare_keywords(["比特币", "BTC", "Jupiter"])
    print("  排行榜:")
    for item in comparison['comparison']:
        print(f"    {item['keyword']}: {item['total_count']}条 ({item['active_days']}天活跃)")
    print()

    # 3. 最热门日期
    print("【3】比特币最热门的5天")
    hot_dates = analyzer.get_hot_dates("比特币", top_n=5)
    for i, item in enumerate(hot_dates, 1):
        print(f"    #{i} {item['date']}: {item['count']}条")
    print()

    # 4. 生成可视化
    print("【4】生成可视化图表")
    save_path = os.path.join(DATA_DIR, 'trend_demo.png')
    result = analyzer.visualize_trend("比特币", save_path=save_path)
    if result:
        print(f"  ✓ 图表已保存: {result}")
    else:
        print("  ⚠️  图表生成功能不可用（需要安装 matplotlib）")
    print()

    print("=" * 70)
    print("  演示完成")
    print("=" * 70)


def run_interactive_mode():
    """运行交互式模式"""
    analyzer = get_trend_analyzer()

    print("\n" + "=" * 70)
    print("  新闻分析系统 - 交互式模式")
    print("=" * 70)
    print()
    print("可用命令:")
    print("  1. 分析关键词热度")
    print("  2. 对比多个关键词")
    print("  3. 查看热门日期")
    print("  4. 生成可视化图表")
    print("  5. 退出")
    print()

    while True:
        try:
            choice = input("请选择功能 (1-5): ").strip()

            if choice == '1':
                keyword = input("请输入关键词: ").strip()
                if keyword:
                    trend = analyzer.analyze_keyword_trend(keyword)
                    print(f"\n关键词: {keyword}")
                    print(f"总计: {trend['total_count']}条")
                    print(f"活跃天数: {trend['active_days']}天\n")

            elif choice == '2':
                keywords_input = input("请输入关键词（用逗号分隔）: ").strip()
                keywords = [k.strip() for k in keywords_input.split(',')]
                if keywords:
                    comparison = analyzer.compare_keywords(keywords)
                    print("\n对比结果:")
                    for item in comparison['comparison']:
                        print(f"  {item['keyword']}: {item['total_count']}条\n")

            elif choice == '3':
                keyword = input("请输入关键词: ").strip()
                if keyword:
                    hot_dates = analyzer.get_hot_dates(keyword, top_n=10)
                    print(f"\n{keyword} 最热门的日期:")
                    for i, item in enumerate(hot_dates, 1):
                        print(f"  #{i} {item['date']}: {item['count']}条")
                    print()

            elif choice == '4':
                keyword = input("请输入关键词: ").strip()
                if keyword:
                    save_path = os.path.join(DATA_DIR, f'trend_{keyword}.png')
                    result = analyzer.visualize_trend(keyword, save_path=save_path)
                    if result:
                        print(f"\n✓ 图表已保存: {result}\n")
                    else:
                        print("\n⚠️  图表生成失败\n")

            elif choice == '5':
                print("\n再见！👋\n")
                break

            else:
                print("无效选项，请重新选择\n")

        except KeyboardInterrupt:
            print("\n\n再见！👋\n")
            break
        except Exception as e:
            print(f"\n错误: {e}\n")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='新闻分析系统')
    parser.add_argument(
        'mode',
        choices=['init', 'api', 'push', 'demo', 'interactive'],
        help='运行模式'
    )

    args = parser.parse_args()

    if args.mode == 'init':
        # 初始化系统
        init_system()

    elif args.mode == 'api':
        # 启动 API 服务器
        init_system()
        run_api_server()

    elif args.mode == 'push':
        # 启动推送服务
        init_system()
        run_push_service()

    elif args.mode == 'demo':
        # 运行演示
        init_system()
        run_trend_analysis_demo()

    elif args.mode == 'interactive':
        # 交互式模式
        init_system()
        run_interactive_mode()


if __name__ == "__main__":
    # 如果没有参数，显示帮助信息
    if len(sys.argv) == 1:
        print("\n" + "=" * 70)
        print("  新闻分析系统")
        print("=" * 70)
        print("\n使用方法:")
        print("  python main.py init         # 初始化系统")
        print("  python main.py api          # 启动 API 服务器")
        print("  python main.py push         # 启动推送服务")
        print("  python main.py demo         # 运行功能演示")
        print("  python main.py interactive  # 交互式模式")
        print()
        print("示例:")
        print("  python main.py demo")
        print()
        sys.exit(0)

    main()

