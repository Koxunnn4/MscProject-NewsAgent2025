"""
Task 3: 关键词热度趋势分析（完整版，含可视化）
"""
import os
import sys
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import json

# 添加项目根目录到路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from config import SIMILARITY_THRESHOLD, PLOT_STYLE, PLOT_DPI, PLOT_FIGSIZE
from src.database.db_manager import get_db_manager
from src.keyword_extraction.keyword_extractor import get_keyword_extractor

# 尝试导入可视化库
try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
    plt.rcParams['axes.unicode_minus'] = False
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("⚠️  matplotlib 未安装，可视化功能不可用")

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMER_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMER_AVAILABLE = False
    print("⚠️  sentence-transformers 未安装，同义词识别功能不可用")


class TrendAnalyzer:
    """热度趋势分析器"""
    
    def __init__(self):
        self.db = get_db_manager()
        self.extractor = get_keyword_extractor()
        self.embedding_model = None
        
        # 加载词向量模型（用于同义词识别）
        if SENTENCE_TRANSFORMER_AVAILABLE:
            try:
                print("正在加载词向量模型（用于同义词识别）...")
                self.embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
                print("✓ 词向量模型加载完成")
            except Exception as e:
                print(f"⚠️  词向量模型加载失败: {e}")
                self.embedding_model = None
    
    def analyze_keyword_trend(self, keyword: str, start_date: str = None,
                             end_date: str = None, granularity: str = 'day',
                             use_cache: bool = True) -> Dict:
        """
        分析关键词热度趋势
        
        Args:
            keyword: 关键词
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            granularity: 时间粒度 (day/week/month)
            use_cache: 是否使用缓存
            
        Returns:
            {
                'keyword': 关键词,
                'data': [{'date': 日期, 'count': 次数, 'weight': 权重}, ...],
                'total_count': 总次数,
                'active_days': 活跃天数,
                'date_range': (开始日期, 结束日期)
            }
        """
        # 1. 获取同义词（如果启用）
        synonyms = self._get_synonyms(keyword)
        all_keywords = [keyword] + synonyms
        
        # 2. 从数据库查询
        query = """
        SELECT DATE(date) as day, COUNT(*) as count
        FROM messages
        WHERE ({keyword_conditions})
        {date_filter}
        GROUP BY DATE(date)
        ORDER BY day
        """
        
        # 构建关键词条件
        keyword_conditions = " OR ".join(["text LIKE ?" for _ in all_keywords])
        keyword_params = [f'%{kw}%' for kw in all_keywords]
        
        # 构建日期过滤
        date_filter = ""
        date_params = []
        if start_date and end_date:
            date_filter = "AND date >= ? AND date <= ?"
            date_params = [start_date, end_date]
        
        # 执行查询
        full_query = query.format(
            keyword_conditions=keyword_conditions,
            date_filter=date_filter
        )
        params = keyword_params + date_params
        
        results = self.db.execute_query(
            full_query,
            tuple(params),
            self.db.history_db_path
        )
        
        # 3. 处理结果
        trend_data = []
        total_count = 0
        
        for row in results:
            day = row['day']
            count = row['count']
            total_count += count
            
            trend_data.append({
                'date': day,
                'count': count,
                'weight': count  # 简化版权重 = 次数
            })
        
        # 4. 按时间粒度聚合
        if granularity == 'week':
            trend_data = self._aggregate_by_week(trend_data)
        elif granularity == 'month':
            trend_data = self._aggregate_by_month(trend_data)
        
        # 5. 返回结果
        date_range = (
            trend_data[0]['date'] if trend_data else None,
            trend_data[-1]['date'] if trend_data else None
        )
        
        return {
            'keyword': keyword,
            'synonyms': synonyms,
            'data': trend_data,
            'total_count': total_count,
            'active_days': len(trend_data),
            'date_range': date_range
        }
    
    def compare_keywords(self, keywords: List[str], start_date: str = None,
                        end_date: str = None) -> Dict:
        """
        对比多个关键词的热度
        
        Args:
            keywords: 关键词列表
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            {
                'keywords': [关键词列表],
                'comparison': [
                    {
                        'keyword': 关键词,
                        'total_count': 总次数,
                        'active_days': 活跃天数,
                        'avg_daily': 日均次数
                    },
                    ...
                ],
                'time_series': {
                    'dates': [日期列表],
                    'data': {
                        keyword1: [次数列表],
                        keyword2: [次数列表],
                        ...
                    }
                }
            }
        """
        comparison_results = []
        all_dates = set()
        keyword_data = {}
        
        # 分析每个关键词
        for keyword in keywords:
            trend = self.analyze_keyword_trend(keyword, start_date, end_date)
            
            # 收集统计信息
            comparison_results.append({
                'keyword': keyword,
                'total_count': trend['total_count'],
                'active_days': trend['active_days'],
                'avg_daily': trend['total_count'] / trend['active_days'] if trend['active_days'] > 0 else 0
            })
            
            # 收集时间序列数据
            keyword_data[keyword] = {item['date']: item['count'] for item in trend['data']}
            all_dates.update(keyword_data[keyword].keys())
        
        # 构建完整的时间序列（填充缺失日期）
        sorted_dates = sorted(all_dates)
        time_series_data = {}
        
        for keyword in keywords:
            time_series_data[keyword] = [
                keyword_data[keyword].get(date, 0) for date in sorted_dates
            ]
        
        # 按总次数排序
        comparison_results.sort(key=lambda x: x['total_count'], reverse=True)
        
        return {
            'keywords': keywords,
            'comparison': comparison_results,
            'time_series': {
                'dates': sorted_dates,
                'data': time_series_data
            }
        }
    
    def get_hot_dates(self, keyword: str, top_n: int = 10) -> List[Dict]:
        """
        获取关键词最热门的日期
        
        Args:
            keyword: 关键词
            top_n: 返回前N天
            
        Returns:
            [{'date': 日期, 'count': 次数}, ...]
        """
        trend = self.analyze_keyword_trend(keyword)
        sorted_data = sorted(trend['data'], key=lambda x: x['count'], reverse=True)
        return sorted_data[:top_n]
    
    def get_trending_keywords(self, start_date: str, end_date: str,
                             top_n: int = 20) -> List[Dict]:
        """
        获取时间段内的热门关键词
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            top_n: 返回前N个关键词
            
        Returns:
            [{'keyword': 关键词, 'count': 次数}, ...]
        """
        # 从数据库获取该时间段的所有新闻
        news_list = self.db.get_news_by_date_range(
            start_date, end_date, self.db.history_db_path
        )
        
        # 统计关键词频率
        keyword_counts = defaultdict(int)
        
        for news in news_list:
            keywords = self.extractor.extract_keywords(news['text'], top_n=5)
            for kw, weight in keywords:
                keyword_counts[kw] += 1
        
        # 排序并返回
        sorted_keywords = sorted(
            keyword_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_n]
        
        return [{'keyword': kw, 'count': count} for kw, count in sorted_keywords]
    
    def visualize_trend(self, keyword: str, start_date: str = None,
                       end_date: str = None, save_path: str = None) -> Optional[str]:
        """
        可视化关键词热度趋势
        
        Args:
            keyword: 关键词
            start_date: 开始日期
            end_date: 结束日期
            save_path: 保存路径（不指定则显示图表）
            
        Returns:
            保存路径或None
        """
        if not MATPLOTLIB_AVAILABLE:
            print("❌ matplotlib 未安装，无法生成可视化")
            return None
        
        # 获取趋势数据
        trend = self.analyze_keyword_trend(keyword, start_date, end_date)
        
        if not trend['data']:
            print(f"❌ 未找到关键词 '{keyword}' 的数据")
            return None
        
        # 准备数据
        dates = [datetime.fromisoformat(item['date']) for item in trend['data']]
        counts = [item['count'] for item in trend['data']]
        
        # 创建图表
        fig, ax = plt.subplots(figsize=PLOT_FIGSIZE, dpi=PLOT_DPI)
        
        # 绘制折线图
        ax.plot(dates, counts, marker='o', linewidth=2, markersize=6,
                color='#1f77b4', label=keyword)
        
        # 填充区域
        ax.fill_between(dates, counts, alpha=0.3, color='#1f77b4')
        
        # 设置标题和标签
        ax.set_title(f'关键词 "{keyword}" 热度趋势', fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('日期', fontsize=12)
        ax.set_ylabel('出现次数', fontsize=12)
        
        # 格式化日期轴
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        plt.xticks(rotation=45, ha='right')
        
        # 添加网格
        ax.grid(True, alpha=0.3, linestyle='--')
        
        # 添加统计信息
        stats_text = f"总计: {trend['total_count']}条\n活跃天数: {trend['active_days']}天"
        ax.text(0.02, 0.98, stats_text,
                transform=ax.transAxes,
                verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5),
                fontsize=10)
        
        # 调整布局
        plt.tight_layout()
        
        # 保存或显示
        if save_path:
            plt.savefig(save_path, dpi=PLOT_DPI, bbox_inches='tight')
            print(f"✓ 图表已保存到: {save_path}")
            plt.close()
            return save_path
        else:
            plt.show()
            return None
    
    def visualize_comparison(self, keywords: List[str], start_date: str = None,
                            end_date: str = None, save_path: str = None) -> Optional[str]:
        """
        可视化多个关键词的对比
        
        Args:
            keywords: 关键词列表
            start_date: 开始日期
            end_date: 结束日期
            save_path: 保存路径
            
        Returns:
            保存路径或None
        """
        if not MATPLOTLIB_AVAILABLE:
            print("❌ matplotlib 未安装，无法生成可视化")
            return None
        
        # 获取对比数据
        comparison = self.compare_keywords(keywords, start_date, end_date)
        
        if not comparison['time_series']['dates']:
            print("❌ 未找到数据")
            return None
        
        # 准备数据
        dates = [datetime.fromisoformat(d) for d in comparison['time_series']['dates']]
        
        # 创建图表
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(PLOT_FIGSIZE[0], PLOT_FIGSIZE[1] * 1.5), dpi=PLOT_DPI)
        
        # 1. 时间序列对比图
        colors = plt.cm.tab10(range(len(keywords)))
        for i, keyword in enumerate(keywords):
            counts = comparison['time_series']['data'][keyword]
            ax1.plot(dates, counts, marker='o', linewidth=2, markersize=4,
                    label=keyword, color=colors[i])
        
        ax1.set_title('关键词热度对比（时间序列）', fontsize=14, fontweight='bold')
        ax1.set_xlabel('日期', fontsize=11)
        ax1.set_ylabel('出现次数', fontsize=11)
        ax1.legend(loc='best', fontsize=10)
        ax1.grid(True, alpha=0.3)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        # 2. 总计对比柱状图
        keywords_sorted = [item['keyword'] for item in comparison['comparison']]
        counts_sorted = [item['total_count'] for item in comparison['comparison']]
        
        bars = ax2.bar(keywords_sorted, counts_sorted, color=colors[:len(keywords)])
        ax2.set_title('关键词总计对比', fontsize=14, fontweight='bold')
        ax2.set_xlabel('关键词', fontsize=11)
        ax2.set_ylabel('总次数', fontsize=11)
        ax2.grid(True, alpha=0.3, axis='y')
        
        # 在柱状图上添加数值
        for bar in bars:
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                    f'{int(height)}',
                    ha='center', va='bottom', fontsize=9)
        
        plt.tight_layout()
        
        # 保存或显示
        if save_path:
            plt.savefig(save_path, dpi=PLOT_DPI, bbox_inches='tight')
            print(f"✓ 图表已保存到: {save_path}")
            plt.close()
            return save_path
        else:
            plt.show()
            return None
    
    def _get_synonyms(self, keyword: str) -> List[str]:
        """获取关键词的同义词"""
        # 先从数据库查询
        rep_keyword = self.db.get_representative_keyword(keyword)
        if rep_keyword != keyword:
            return [rep_keyword]
        
        # TODO: 使用词向量模型查找同义词
        return []
    
    def _aggregate_by_week(self, data: List[Dict]) -> List[Dict]:
        """按周聚合数据"""
        weekly_data = defaultdict(lambda: {'count': 0, 'weight': 0})
        
        for item in data:
            date = datetime.fromisoformat(item['date'])
            week_start = date - timedelta(days=date.weekday())
            week_key = week_start.strftime('%Y-%m-%d')
            
            weekly_data[week_key]['count'] += item['count']
            weekly_data[week_key]['weight'] += item['weight']
        
        result = [
            {'date': week, 'count': stats['count'], 'weight': stats['weight']}
            for week, stats in sorted(weekly_data.items())
        ]
        return result
    
    def _aggregate_by_month(self, data: List[Dict]) -> List[Dict]:
        """按月聚合数据"""
        monthly_data = defaultdict(lambda: {'count': 0, 'weight': 0})
        
        for item in data:
            date = datetime.fromisoformat(item['date'])
            month_key = date.strftime('%Y-%m')
            
            monthly_data[month_key]['count'] += item['count']
            monthly_data[month_key]['weight'] += item['weight']
        
        result = [
            {'date': month + '-01', 'count': stats['count'], 'weight': stats['weight']}
            for month, stats in sorted(monthly_data.items())
        ]
        return result


# 单例模式
_trend_analyzer = None

def get_trend_analyzer() -> TrendAnalyzer:
    """获取趋势分析器单例"""
    global _trend_analyzer
    if _trend_analyzer is None:
        _trend_analyzer = TrendAnalyzer()
    return _trend_analyzer


if __name__ == "__main__":
    # 测试
    analyzer = get_trend_analyzer()
    
    # 测试1: 单个关键词趋势
    print("\n【测试1】分析'比特币'热度趋势")
    trend = analyzer.analyze_keyword_trend("比特币")
    print(f"  总计: {trend['total_count']}条")
    print(f"  活跃天数: {trend['active_days']}天")
    
    # 测试2: 多关键词对比
    print("\n【测试2】对比多个关键词")
    comparison = analyzer.compare_keywords(["比特币", "BTC", "Jupiter"])
    for item in comparison['comparison']:
        print(f"  {item['keyword']}: {item['total_count']}条")
    
    # 测试3: 可视化（如果可用）
    if MATPLOTLIB_AVAILABLE:
        print("\n【测试3】生成可视化图表")
        analyzer.visualize_trend("比特币", save_path="data/trend_bitcoin.png")

