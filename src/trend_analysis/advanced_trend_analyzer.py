"""
高级热度分析模块
新增功能：
1. 异常检测（突然爆发、断崖式下跌）
2. 热度增长速度（变化率）
3. 关联词分析（关键词关联性、时间序列相关性）
"""
import os
import sys
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np
from scipy import stats
from scipy.signal import find_peaks

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from src.trend_analysis.trend_analyzer import get_trend_analyzer
from src.database.db_manager import get_db_manager
from src.crypto_analysis.crypto_analyzer import get_crypto_analyzer


class AdvancedTrendAnalyzer:
    """高级热度趋势分析器"""
    
    def __init__(self):
        self.base_analyzer = get_trend_analyzer()
        self.db = get_db_manager()
        self.analyzer = get_crypto_analyzer()
    
    def detect_anomalies(self, keyword: str, 
                        start_date: str = None,
                        end_date: str = None,
                        sensitivity: float = 2.0) -> Dict:
        """
        检测关键词热度异常波动
        
        Args:
            keyword: 关键词
            start_date: 开始日期
            end_date: 结束日期
            sensitivity: 敏感度（标准差倍数，越大越不敏感）
            
        Returns:
            {
                'keyword': 关键词,
                'anomalies': [
                    {
                        'date': 日期,
                        'value': 热度值,
                        'type': 'surge'/'drop',  # 爆发/下跌
                        'z_score': Z分数,
                        'change_rate': 变化率,
                        'description': 描述
                    },
                    ...
                ],
                'summary': 统计摘要
            }
        """
        # 获取趋势数据
        trend = self.base_analyzer.analyze_keyword_trend(
            keyword, start_date, end_date
        )
        
        if not trend['data'] or len(trend['data']) < 3:
            return {
                'keyword': keyword,
                'anomalies': [],
                'summary': '数据不足，无法检测异常'
            }
        
        # 提取时间序列
        dates = [item['date'] for item in trend['data']]
        values = np.array([item['count'] for item in trend['data']])
        
        # 计算统计指标
        mean = np.mean(values)
        std = np.std(values)
        
        if std == 0:
            return {
                'keyword': keyword,
                'anomalies': [],
                'summary': '热度无变化'
            }
        
        # 计算Z分数
        z_scores = (values - mean) / std
        
        # 检测异常
        anomalies = []
        
        for i in range(len(values)):
            z_score = z_scores[i]
            
            # 异常判断：Z分数超过阈值
            if abs(z_score) > sensitivity:
                # 计算变化率
                if i > 0:
                    change_rate = (values[i] - values[i-1]) / (values[i-1] + 1)
                else:
                    change_rate = 0.0
                
                # 判断类型
                if z_score > 0:
                    anomaly_type = 'surge'
                    description = f"突然爆发：热度达到 {values[i]} (平均值的 {z_score:.1f} 倍标准差)"
                else:
                    anomaly_type = 'drop'
                    description = f"断崖式下跌：热度降至 {values[i]} (低于平均值 {abs(z_score):.1f} 倍标准差)"
                
                anomalies.append({
                    'date': dates[i],
                    'value': int(values[i]),
                    'type': anomaly_type,
                    'z_score': float(z_score),
                    'change_rate': float(change_rate),
                    'description': description
                })
        
        # 排序（按日期）
        anomalies.sort(key=lambda x: x['date'])
        
        # 统计摘要
        surge_count = sum(1 for a in anomalies if a['type'] == 'surge')
        drop_count = sum(1 for a in anomalies if a['type'] == 'drop')
        
        summary = f"检测到 {len(anomalies)} 个异常: {surge_count} 次爆发, {drop_count} 次下跌"
        
        return {
            'keyword': keyword,
            'anomalies': anomalies,
            'statistics': {
                'mean': float(mean),
                'std': float(std),
                'max': float(np.max(values)),
                'min': float(np.min(values))
            },
            'summary': summary
        }
    
    def calculate_growth_velocity(self, keyword: str,
                                  start_date: str = None,
                                  end_date: str = None,
                                  window: int = 7) -> Dict:
        """
        计算热度增长速度（变化率）
        
        Args:
            keyword: 关键词
            start_date: 开始日期
            end_date: 结束日期
            window: 滑动窗口大小（天）
            
        Returns:
            {
                'keyword': 关键词,
                'velocity_data': [
                    {
                        'date': 日期,
                        'value': 热度值,
                        'velocity': 速度（每日变化率）,
                        'acceleration': 加速度（速度变化率）
                    },
                    ...
                ],
                'summary': {
                    'avg_velocity': 平均速度,
                    'max_velocity': 最大速度,
                    'trend': 'accelerating'/'decelerating'/'stable'
                }
            }
        """
        # 获取趋势数据
        trend = self.base_analyzer.analyze_keyword_trend(
            keyword, start_date, end_date
        )
        
        if not trend['data'] or len(trend['data']) < 2:
            return {
                'keyword': keyword,
                'velocity_data': [],
                'summary': {'avg_velocity': 0, 'max_velocity': 0, 'trend': 'stable'}
            }
        
        # 提取数据
        dates = [item['date'] for item in trend['data']]
        values = np.array([item['count'] for item in trend['data']], dtype=float)
        
        velocity_data = []
        velocities = []
        
        for i in range(len(values)):
            # 计算速度（相对于前一天的变化率）
            if i > 0:
                velocity = (values[i] - values[i-1]) / (values[i-1] + 1)
            else:
                velocity = 0.0
            
            # 计算加速度（速度的变化率）
            if i > 1:
                prev_velocity = (values[i-1] - values[i-2]) / (values[i-2] + 1)
                acceleration = velocity - prev_velocity
            else:
                acceleration = 0.0
            
            velocity_data.append({
                'date': dates[i],
                'value': int(values[i]),
                'velocity': float(velocity),
                'acceleration': float(acceleration)
            })
            
            velocities.append(velocity)
        
        # 统计摘要
        avg_velocity = np.mean(velocities)
        max_velocity = np.max(np.abs(velocities))
        
        # 判断趋势
        if avg_velocity > 0.1:
            trend_direction = 'accelerating'
        elif avg_velocity < -0.1:
            trend_direction = 'decelerating'
        else:
            trend_direction = 'stable'
        
        return {
            'keyword': keyword,
            'velocity_data': velocity_data,
            'summary': {
                'avg_velocity': float(avg_velocity),
                'max_velocity': float(max_velocity),
                'trend': trend_direction
            }
        }
    
    def analyze_keyword_correlation(self, keyword1: str, keyword2: str,
                                   start_date: str = None,
                                   end_date: str = None) -> Dict:
        """
        分析两个关键词的关联性
        
        Args:
            keyword1: 关键词1
            keyword2: 关键词2
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            {
                'keyword1': 关键词1,
                'keyword2': 关键词2,
                'correlation': 相关系数 (-1到1),
                'p_value': 显著性,
                'co_occurrence': 共现次数,
                'relationship': 'positive'/'negative'/'none',
                'description': 描述
            }
        """
        # 获取两个关键词的趋势
        trend1 = self.base_analyzer.analyze_keyword_trend(
            keyword1, start_date, end_date
        )
        trend2 = self.base_analyzer.analyze_keyword_trend(
            keyword2, start_date, end_date
        )
        
        if not trend1['data'] or not trend2['data']:
            return {
                'keyword1': keyword1,
                'keyword2': keyword2,
                'correlation': 0.0,
                'p_value': 1.0,
                'co_occurrence': 0,
                'relationship': 'none',
                'description': '数据不足'
            }
        
        # 构建时间序列（对齐日期）
        dates1 = {item['date']: item['count'] for item in trend1['data']}
        dates2 = {item['date']: item['count'] for item in trend2['data']}
        
        common_dates = sorted(set(dates1.keys()) & set(dates2.keys()))
        
        if len(common_dates) < 3:
            return {
                'keyword1': keyword1,
                'keyword2': keyword2,
                'correlation': 0.0,
                'p_value': 1.0,
                'co_occurrence': 0,
                'relationship': 'none',
                'description': '共同日期不足'
            }
        
        # 提取对齐的值
        values1 = np.array([dates1[date] for date in common_dates])
        values2 = np.array([dates2[date] for date in common_dates])
        
        # 计算相关系数
        correlation, p_value = stats.pearsonr(values1, values2)
        
        # 计算共现次数（同一天都有提及）
        co_occurrence = len([d for d in common_dates 
                           if dates1[d] > 0 and dates2[d] > 0])
        
        # 判断关系类型
        if p_value < 0.05:  # 显著
            if correlation > 0.5:
                relationship = 'strong_positive'
                description = f"强正相关：两个关键词热度高度一致（相关系数: {correlation:.2f}）"
            elif correlation > 0.2:
                relationship = 'positive'
                description = f"正相关：两个关键词热度同步变化（相关系数: {correlation:.2f}）"
            elif correlation < -0.5:
                relationship = 'strong_negative'
                description = f"强负相关：两个关键词热度反向变化（相关系数: {correlation:.2f}）"
            elif correlation < -0.2:
                relationship = 'negative'
                description = f"负相关：一个上升时另一个下降（相关系数: {correlation:.2f}）"
            else:
                relationship = 'weak'
                description = f"弱相关（相关系数: {correlation:.2f}）"
        else:
            relationship = 'none'
            description = f"无显著相关性（相关系数: {correlation:.2f}, p={p_value:.3f}）"
        
        return {
            'keyword1': keyword1,
            'keyword2': keyword2,
            'correlation': float(correlation),
            'p_value': float(p_value),
            'co_occurrence': int(co_occurrence),
            'relationship': relationship,
            'description': description
        }
    
    def find_related_trending_keywords(self, keyword: str,
                                      start_date: str = None,
                                      end_date: str = None,
                                      top_n: int = 10,
                                      min_correlation: float = 0.3) -> List[Dict]:
        """
        找出与目标关键词相关的其他热门词
        
        Args:
            keyword: 目标关键词
            start_date: 开始日期
            end_date: 结束日期
            top_n: 返回前N个
            min_correlation: 最小相关系数
            
        Returns:
            [
                {
                    'keyword': 相关关键词,
                    'correlation': 相关系数,
                    'co_occurrence': 共现次数,
                    'total_count': 总出现次数
                },
                ...
            ]
        """
        # 获取时间段内的热门关键词
        trending_keywords = self.base_analyzer.get_trending_keywords(
            start_date or (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
            end_date or datetime.now().strftime('%Y-%m-%d'),
            top_n=50  # 获取更多候选
        )
        
        related_keywords = []
        
        for kw_info in trending_keywords:
            related_kw = kw_info['keyword']
            
            # 跳过自己
            if related_kw.lower() == keyword.lower():
                continue
            
            # 计算相关性
            correlation_result = self.analyze_keyword_correlation(
                keyword, related_kw, start_date, end_date
            )
            
            if correlation_result['correlation'] >= min_correlation:
                related_keywords.append({
                    'keyword': related_kw,
                    'correlation': correlation_result['correlation'],
                    'co_occurrence': correlation_result['co_occurrence'],
                    'total_count': kw_info['count'],
                    'relationship': correlation_result['relationship']
                })
        
        # 按相关系数排序
        related_keywords.sort(key=lambda x: x['correlation'], reverse=True)
        
        return related_keywords[:top_n]
    
    def get_comprehensive_analysis(self, keyword: str,
                                  start_date: str = None,
                                  end_date: str = None) -> Dict:
        """
        获取关键词的综合分析报告
        
        Args:
            keyword: 关键词
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            完整的分析报告
        """
        # 基础趋势
        trend = self.base_analyzer.analyze_keyword_trend(
            keyword, start_date, end_date
        )
        
        # 异常检测
        anomalies = self.detect_anomalies(keyword, start_date, end_date)
        
        # 增长速度
        velocity = self.calculate_growth_velocity(keyword, start_date, end_date)
        
        # 相关关键词
        related = self.find_related_trending_keywords(
            keyword, start_date, end_date, top_n=5
        )
        
        return {
            'keyword': keyword,
            'date_range': (start_date, end_date),
            'basic_trend': {
                'total_count': trend['total_count'],
                'active_days': trend['active_days'],
                'avg_daily': trend['total_count'] / trend['active_days'] if trend['active_days'] > 0 else 0
            },
            'anomalies': anomalies,
            'growth_velocity': velocity,
            'related_keywords': related,
            'generated_at': datetime.now().isoformat()
        }


# 单例模式
_advanced_analyzer = None

def get_advanced_trend_analyzer() -> AdvancedTrendAnalyzer:
    """获取高级趋势分析器单例"""
    global _advanced_analyzer
    if _advanced_analyzer is None:
        _advanced_analyzer = AdvancedTrendAnalyzer()
    return _advanced_analyzer


if __name__ == "__main__":
    # 测试高级分析功能
    analyzer = get_advanced_trend_analyzer()
    
    print("=" * 70)
    print("高级热度分析测试")
    print("=" * 70)
    
    test_keyword = "比特币"
    
    # 测试1: 异常检测
    print(f"\n【测试1】异常检测 - '{test_keyword}'")
    anomalies = analyzer.detect_anomalies(test_keyword, sensitivity=1.5)
    print(f"  {anomalies['summary']}")
    for anomaly in anomalies['anomalies'][:3]:
        print(f"    - {anomaly['date']}: {anomaly['description']}")
    
    # 测试2: 增长速度
    print(f"\n【测试2】增长速度分析 - '{test_keyword}'")
    velocity = analyzer.calculate_growth_velocity(test_keyword)
    print(f"  平均速度: {velocity['summary']['avg_velocity']:.2%}")
    print(f"  趋势: {velocity['summary']['trend']}")
    
    # 测试3: 关联分析
    print(f"\n【测试3】关联分析 - '比特币' vs 'BTC'")
    correlation = analyzer.analyze_keyword_correlation("比特币", "BTC")
    print(f"  {correlation['description']}")
    print(f"  共现次数: {correlation['co_occurrence']}")
    
    # 测试4: 相关关键词
    print(f"\n【测试4】相关热门关键词 - '{test_keyword}'")
    related = analyzer.find_related_trending_keywords(test_keyword, top_n=5)
    print(f"  找到 {len(related)} 个相关关键词:")
    for kw in related:
        print(f"    - {kw['keyword']}: 相关系数 {kw['correlation']:.2f}")
    
    print("\n✓ 测试完成")

