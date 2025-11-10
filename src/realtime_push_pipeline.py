"""
实时推送Pipeline
整合爬虫、关键词提取、订阅匹配和推送的完整流程
"""
import os
import sys
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
import logging

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.unified_news_interface import get_unified_news_interface
from src.keyword_matching import get_keyword_matcher
from src.push_system.push_manager import get_push_manager
from src.database.db_manager import get_db_manager
from src.trend_analysis.trend_analyzer import get_trend_analyzer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RealtimePushPipeline:
    """实时推送Pipeline"""
    
    def __init__(self, db_path: str = None):
        """
        初始化Pipeline
        
        Args:
            db_path: 实时数据库路径（如果使用新老分离策略）
        """
        self.news_interface = get_unified_news_interface()
        self.keyword_matcher = get_keyword_matcher()
        self.push_manager = get_push_manager()
        self.db = get_db_manager()
        self.trend_analyzer = get_trend_analyzer()
        
        # 使用实时数据库或历史数据库
        self.db_path = db_path or self.db.history_db_path
        
        # 新闻队列
        self.news_queue = asyncio.Queue()
        
        # 推送频率限制（每个用户每小时最多推送）
        self.push_frequency_limit = {}
        self.push_limit_per_hour = 10
        
        logger.info(f"实时推送Pipeline初始化完成，数据库: {self.db_path}")
    
    async def on_news_received(self, news_data: Dict, source_type: str = 'crypto'):
        """
        当爬虫抓取到新新闻时的回调（Pipeline入口）
        
        Args:
            news_data: 新闻数据
            source_type: 'crypto' 或 'hkstock'
        """
        logger.info(f"收到新新闻 [{source_type}]: {news_data.get('text', '')[:50]}...")
        
        # 添加到队列（异步处理）
        await self.news_queue.put({
            'news_data': news_data,
            'source_type': source_type,
            'received_at': datetime.now().isoformat()
        })
    
    async def process_news_pipeline(self):
        """新闻处理Pipeline主循环"""
        logger.info("启动新闻处理Pipeline...")
        
        while True:
            try:
                # 从队列获取新闻
                item = await self.news_queue.get()
                
                news_data = item['news_data']
                source_type = item['source_type']
                
                logger.info(f"开始处理新闻 [ID: {news_data.get('id')}]")
                
                # Step 1: 保存新闻到数据库
                news_id = await self._save_news(news_data, source_type)
                if not news_id:
                    logger.error("保存新闻失败，跳过")
                    continue
                
                # Step 2: 提取关键词
                keywords = await self._extract_keywords(news_id, news_data['text'])
                if not keywords:
                    logger.warning(f"未提取到关键词 [ID: {news_id}]")
                
                # Step 3: 匹配订阅用户
                matched_subscriptions = await self._match_subscriptions(
                    news_data['text'], keywords
                )
                
                # Step 4: 推送给订阅用户
                if matched_subscriptions:
                    logger.info(f"匹配到 {len(matched_subscriptions)} 个订阅")
                    await self._push_to_subscribers(
                        news_id, news_data, matched_subscriptions
                    )
                else:
                    logger.debug(f"无匹配订阅 [ID: {news_id}]")
                
                # Step 5: 更新热度统计（异步）
                asyncio.create_task(
                    self._update_trend_stats(keywords, news_data.get('date'))
                )
                
                logger.info(f"新闻处理完成 [ID: {news_id}]")
                
            except Exception as e:
                logger.error(f"处理新闻时出错: {e}", exc_info=True)
                await asyncio.sleep(1)  # 出错后短暂等待
    
    async def _save_news(self, news_data: Dict, source_type: str) -> Optional[int]:
        """
        保存新闻到数据库
        
        Args:
            news_data: 新闻数据
            source_type: 新闻源类型
            
        Returns:
            新闻ID，失败返回None
        """
        try:
            news_id = self.news_interface.save_news(
                news_data, source_type, self.db_path
            )
            logger.debug(f"新闻已保存 [ID: {news_id}]")
            return news_id
        except Exception as e:
            logger.error(f"保存新闻失败: {e}", exc_info=True)
            return None
    
    async def _extract_keywords(self, news_id: int, text: str) -> List[tuple]:
        """
        提取并保存关键词
        
        Args:
            news_id: 新闻ID
            text: 新闻文本
            
        Returns:
            关键词列表 [(keyword, weight), ...]
        """
        try:
            keywords = self.news_interface.extract_keywords(text, top_n=10)
            
            if keywords:
                # 保存到数据库
                self.db.save_news_keywords(news_id, keywords)
                logger.debug(f"关键词已保存 [ID: {news_id}]: {[kw for kw, _ in keywords]}")
            
            return keywords
        except Exception as e:
            logger.error(f"提取关键词失败: {e}", exc_info=True)
            return []
    
    async def _match_subscriptions(self, news_text: str,
                                   keywords: List[tuple]) -> List[Dict]:
        """
        匹配订阅用户
        
        Args:
            news_text: 新闻文本
            keywords: 关键词列表
            
        Returns:
            匹配的订阅列表
        """
        try:
            # 获取所有活跃订阅
            query = """
            SELECT id, user_id, keyword, telegram_chat_id
            FROM subscriptions
            WHERE is_active = 1
            """
            all_subscriptions = self.db.execute_query(query, db_path=self.db_path)
            
            if not all_subscriptions:
                return []
            
            matched = []
            
            for sub in all_subscriptions:
                # 关键词匹配
                match_result = self.keyword_matcher.match_keyword(
                    news_text, sub['keyword'], threshold=0.3
                )
                
                if match_result['is_match']:
                    # 检查推送频率限制
                    if self._check_push_frequency(sub['user_id']):
                        matched.append({
                            'subscription_id': sub['id'],
                            'user_id': sub['user_id'],
                            'keyword': sub['keyword'],
                            'telegram_chat_id': sub['telegram_chat_id'],
                            'relevance_score': match_result['relevance_score'],
                            'matched_context': match_result.get('context', ''),
                            'match_method': match_result['match_method']
                        })
            
            return matched
            
        except Exception as e:
            logger.error(f"匹配订阅失败: {e}", exc_info=True)
            return []
    
    async def _push_to_subscribers(self, news_id: int, news_data: Dict,
                                   subscriptions: List[Dict]):
        """
        推送给订阅用户
        
        Args:
            news_id: 新闻ID
            news_data: 新闻数据
            subscriptions: 订阅列表
        """
        for sub in subscriptions:
            try:
                # 检查是否已推送
                if self.db.check_news_pushed(sub['subscription_id'], news_id):
                    logger.debug(f"新闻已推送过 [订阅ID: {sub['subscription_id']}]")
                    continue
                
                # 格式化推送消息
                message = self._format_push_message(
                    news_data,
                    sub['keyword'],
                    sub['relevance_score'],
                    sub.get('matched_context', '')
                )
                
                # 发送Telegram消息
                success = await self.push_manager.send_telegram_message(
                    chat_id=sub['telegram_chat_id'],
                    news=news_data,
                    keyword=sub['keyword']
                )
                
                # 保存推送历史
                status = 'success' if success else 'failed'
                self.db.save_push_history(
                    sub['subscription_id'],
                    news_id,
                    status
                )
                
                if success:
                    # 更新推送频率记录
                    self._record_push(sub['user_id'])
                    logger.info(
                        f"✓ 推送成功 [用户: {sub['user_id']}, "
                        f"关键词: '{sub['keyword']}', "
                        f"相关性: {sub['relevance_score']:.2f}]"
                    )
                else:
                    logger.warning(f"✗ 推送失败 [用户: {sub['user_id']}]")
                
            except Exception as e:
                logger.error(
                    f"推送出错 [订阅ID: {sub['subscription_id']}]: {e}",
                    exc_info=True
                )
    
    def _format_push_message(self, news_data: Dict, keyword: str,
                            relevance_score: float, context: str = '') -> str:
        """格式化推送消息"""
        text = news_data['text']
        title = news_data.get('title', text[:100] + '...')
        date = news_data.get('date', '')
        
        # 截取摘要
        summary = text[:300] + '...' if len(text) > 300 else text
        
        # 格式化日期
        try:
            date_obj = datetime.fromisoformat(date.replace('T', ' ').replace('+00:00', ''))
            date_formatted = date_obj.strftime('%Y-%m-%d %H:%M')
        except:
            date_formatted = date
        
        message = f"""
🔔 *关键词推送：{keyword}*

📰 *标题：*
{title}

📝 *摘要：*
{summary}

📅 *时间：* {date_formatted}
⭐ *相关性：* {relevance_score:.0%}

_来自 新闻分析系统_
        """.strip()
        
        return message
    
    def _check_push_frequency(self, user_id: str) -> bool:
        """
        检查推送频率限制
        
        Args:
            user_id: 用户ID
            
        Returns:
            是否允许推送
        """
        now = datetime.now()
        hour_key = now.strftime('%Y-%m-%d-%H')
        
        key = f"{user_id}_{hour_key}"
        
        if key not in self.push_frequency_limit:
            self.push_frequency_limit[key] = 0
        
        if self.push_frequency_limit[key] >= self.push_limit_per_hour:
            logger.warning(
                f"用户 {user_id} 本小时推送次数已达上限 "
                f"({self.push_limit_per_hour})"
            )
            return False
        
        return True
    
    def _record_push(self, user_id: str):
        """记录推送次数"""
        now = datetime.now()
        hour_key = now.strftime('%Y-%m-%d-%H')
        key = f"{user_id}_{hour_key}"
        
        if key not in self.push_frequency_limit:
            self.push_frequency_limit[key] = 0
        
        self.push_frequency_limit[key] += 1
    
    async def _update_trend_stats(self, keywords: List[tuple], date_str: str):
        """
        更新热度统计（异步）
        
        Args:
            keywords: 关键词列表
            date_str: 日期字符串
        """
        try:
            if not date_str:
                return
            
            # 提取日期部分
            date = date_str.split('T')[0] if 'T' in date_str else date_str[:10]
            
            for keyword, weight in keywords:
                self.db.save_keyword_trend(keyword, date, 1, weight)
            
            logger.debug(f"热度统计已更新 [{len(keywords)} 个关键词]")
            
        except Exception as e:
            logger.error(f"更新热度统计失败: {e}", exc_info=True)
    
    async def run(self):
        """启动Pipeline"""
        logger.info("=" * 70)
        logger.info("  实时推送Pipeline启动")
        logger.info("=" * 70)
        logger.info(f"数据库: {self.db_path}")
        logger.info(f"推送频率限制: {self.push_limit_per_hour}/小时/用户")
        logger.info("")
        
        # 启动新闻处理循环
        await self.process_news_pipeline()


# 单例模式
_pipeline = None

def get_realtime_push_pipeline(db_path: str = None) -> RealtimePushPipeline:
    """获取实时推送Pipeline单例"""
    global _pipeline
    if _pipeline is None:
        _pipeline = RealtimePushPipeline(db_path)
    return _pipeline


if __name__ == "__main__":
    # 测试Pipeline
    async def test_pipeline():
        pipeline = get_realtime_push_pipeline()
        
        # 模拟新闻数据
        test_news = {
            'id': 999999,
            'channel_id': 'test_channel',
            'message_id': 999999,
            'text': '比特币价格突破$95,000美元，创下历史新高。市场分析师认为这与机构投资者增加有关。',
            'date': datetime.now().isoformat(),
            'title': '比特币突破$95,000'
        }
        
        # 发送到Pipeline
        await pipeline.on_news_received(test_news, 'crypto')
        
        # 运行Pipeline（会持续运行）
        await pipeline.run()
    
    # 运行测试
    asyncio.run(test_pipeline())

