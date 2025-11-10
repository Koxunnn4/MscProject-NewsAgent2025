"""
关键词匹配模块
用于判断新闻是否与用户订阅的关键词相关
"""
import os
import sys
import re
from typing import List, Dict, Tuple
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.crypto_analysis.crypto_analyzer import get_crypto_analyzer


class KeywordMatcher:
    """关键词匹配器"""
    
    def __init__(self):
        self.analyzer = get_crypto_analyzer()
    
    def match_keyword(self, news_text: str, user_keyword: str,
                     threshold: float = 0.3) -> Dict:
        """
        判断新闻是否匹配用户订阅的关键词
        
        Args:
            news_text: 新闻文本
            user_keyword: 用户订阅的关键词
            threshold: 匹配阈值（0-1）
            
        Returns:
            {
                'is_match': bool,              # 是否匹配
                'relevance_score': float,      # 相关性得分 (0-1)
                'matched_keywords': List[str], # 匹配到的关键词
                'context': str,                # 关键词上下文片段
                'match_method': str            # 匹配方法
            }
        """
        # 1. 直接字符串匹配（最快）
        if user_keyword.lower() in news_text.lower():
            context = self._extract_context(news_text, user_keyword)
            return {
                'is_match': True,
                'relevance_score': 1.0,
                'matched_keywords': [user_keyword],
                'context': context,
                'match_method': 'exact'
            }
        
        # 2. 提取新闻关键词
        news_keywords = self.analyzer.extract_keywords(news_text, top_n=20)
        
        if not news_keywords:
            return {
                'is_match': False,
                'relevance_score': 0.0,
                'matched_keywords': [],
                'context': '',
                'match_method': 'none'
            }
        
        # 3. 关键词相似度匹配
        keyword_list = [kw for kw, _ in news_keywords]
        
        # 检查是否有关键词包含用户关键词（部分匹配）
        matched_keywords = []
        for kw in keyword_list:
            if user_keyword.lower() in kw.lower() or kw.lower() in user_keyword.lower():
                matched_keywords.append(kw)
        
        if matched_keywords:
            # 提取上下文
            context = self._extract_context(news_text, matched_keywords[0])
            return {
                'is_match': True,
                'relevance_score': 0.8,
                'matched_keywords': matched_keywords,
                'context': context,
                'match_method': 'partial'
            }
        
        # 4. 使用余弦相似度（语义匹配）
        try:
            similarity_score = self._calculate_semantic_similarity(
                user_keyword, keyword_list
            )
            
            if similarity_score >= threshold:
                return {
                    'is_match': True,
                    'relevance_score': float(similarity_score),
                    'matched_keywords': keyword_list[:3],  # 返回前3个关键词
                    'context': news_text[:200] + '...',
                    'match_method': 'semantic'
                }
        except Exception as e:
            print(f"语义匹配失败: {e}")
        
        # 5. 不匹配
        return {
            'is_match': False,
            'relevance_score': 0.0,
            'matched_keywords': [],
            'context': '',
            'match_method': 'none'
        }
    
    def match_keywords_batch(self, news_text: str, 
                            user_keywords: List[str],
                            threshold: float = 0.3) -> List[Dict]:
        """
        批量匹配多个关键词
        
        Args:
            news_text: 新闻文本
            user_keywords: 用户订阅的关键词列表
            threshold: 匹配阈值
            
        Returns:
            匹配结果列表，按相关性得分降序排列
        """
        results = []
        
        for keyword in user_keywords:
            result = self.match_keyword(news_text, keyword, threshold)
            if result['is_match']:
                result['user_keyword'] = keyword
                results.append(result)
        
        # 按相关性得分排序
        results.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        return results
    
    def get_top_relevant_news(self, user_keyword: str, 
                             news_list: List[Dict],
                             top_k: int = 10,
                             threshold: float = 0.3) -> List[Dict]:
        """
        获取与用户关键词最相关的新闻
        
        Args:
            user_keyword: 用户关键词
            news_list: 新闻列表（每个新闻是Dict，包含'text'字段）
            top_k: 返回前K条
            threshold: 最低相关性阈值
            
        Returns:
            相关性最高的新闻列表（包含relevance_score字段）
        """
        scored_news = []
        
        for news in news_list:
            match_result = self.match_keyword(
                news.get('text', ''),
                user_keyword,
                threshold
            )
            
            if match_result['is_match']:
                news_copy = news.copy()
                news_copy['match_result'] = match_result
                news_copy['relevance_score'] = match_result['relevance_score']
                scored_news.append(news_copy)
        
        # 按相关性排序
        scored_news.sort(
            key=lambda x: (x['relevance_score'], x.get('date', '')),
            reverse=True
        )
        
        return scored_news[:top_k]
    
    def _extract_context(self, text: str, keyword: str, 
                        context_window: int = 100) -> str:
        """
        提取关键词的上下文片段
        
        Args:
            text: 文本
            keyword: 关键词
            context_window: 上下文窗口大小（字符数）
            
        Returns:
            上下文片段
        """
        # 查找关键词位置（不区分大小写）
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        match = pattern.search(text)
        
        if not match:
            return text[:200] + '...' if len(text) > 200 else text
        
        # 提取上下文
        start_pos = match.start()
        context_start = max(0, start_pos - context_window)
        context_end = min(len(text), start_pos + len(keyword) + context_window)
        
        context = text[context_start:context_end]
        
        # 添加省略号
        if context_start > 0:
            context = '...' + context
        if context_end < len(text):
            context = context + '...'
        
        return context
    
    def _calculate_semantic_similarity(self, user_keyword: str,
                                      news_keywords: List[str]) -> float:
        """
        计算用户关键词与新闻关键词的语义相似度
        
        Args:
            user_keyword: 用户关键词
            news_keywords: 新闻关键词列表
            
        Returns:
            相似度得分 (0-1)
        """
        if not news_keywords:
            return 0.0
        
        try:
            # 使用词袋模型计算余弦相似度
            all_keywords = [user_keyword] + news_keywords
            
            vectorizer = CountVectorizer()
            vectors = vectorizer.fit_transform(all_keywords)
            
            # 计算用户关键词与所有新闻关键词的相似度
            user_vector = vectors[0:1]
            news_vectors = vectors[1:]
            
            similarities = cosine_similarity(user_vector, news_vectors)[0]
            
            # 返回最大相似度
            max_similarity = float(np.max(similarities)) if len(similarities) > 0 else 0.0
            
            return max_similarity
            
        except Exception as e:
            print(f"相似度计算失败: {e}")
            return 0.0


# 单例模式
_keyword_matcher = None

def get_keyword_matcher() -> KeywordMatcher:
    """获取关键词匹配器单例"""
    global _keyword_matcher
    if _keyword_matcher is None:
        _keyword_matcher = KeywordMatcher()
    return _keyword_matcher


if __name__ == "__main__":
    # 测试关键词匹配
    matcher = get_keyword_matcher()
    
    print("=" * 70)
    print("测试关键词匹配功能")
    print("=" * 70)
    
    # 测试文本
    test_text = """
    比特币价格今日突破 $95,000，创下近期新高。
    分析师认为这与美联储降息预期有关，投资者情绪乐观。
    以太坊和其他主流币种也随之上涨。
    """
    
    # 测试1: 精确匹配
    print("\n【测试1】精确匹配 - '比特币'")
    result1 = matcher.match_keyword(test_text, '比特币')
    print(f"  匹配结果: {result1['is_match']}")
    print(f"  相关性得分: {result1['relevance_score']:.2f}")
    print(f"  匹配方法: {result1['match_method']}")
    print(f"  上下文: {result1['context'][:100]}...")
    
    # 测试2: 部分匹配
    print("\n【测试2】部分匹配 - 'BTC'")
    result2 = matcher.match_keyword(test_text, 'BTC')
    print(f"  匹配结果: {result2['is_match']}")
    print(f"  相关性得分: {result2['relevance_score']:.2f}")
    
    # 测试3: 语义匹配
    print("\n【测试3】语义匹配 - '数字货币'")
    result3 = matcher.match_keyword(test_text, '数字货币')
    print(f"  匹配结果: {result3['is_match']}")
    print(f"  相关性得分: {result3['relevance_score']:.2f}")
    print(f"  匹配方法: {result3['match_method']}")
    
    # 测试4: 批量匹配
    print("\n【测试4】批量匹配")
    keywords = ['比特币', '以太坊', 'Jupiter']
    batch_results = matcher.match_keywords_batch(test_text, keywords)
    print(f"  共匹配到 {len(batch_results)} 个关键词")
    for result in batch_results:
        print(f"    - {result['user_keyword']}: {result['relevance_score']:.2f}")
    
    print("\n✓ 测试完成")

