"""
Task 4: 实时新闻推送系统
"""
import os
import sys
import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timedelta

# 添加项目根目录到路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from config import TELEGRAM_BOT_TOKEN, PUSH_CHECK_INTERVAL, MAX_PUSH_PER_USER
from src.database.db_manager import get_db_manager
from src.crypto_analysis.crypto_analyzer import get_keyword_extractor

# 尝试导入 Telegram Bot API
try:
    from telegram import Bot
    from telegram.error import TelegramError
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("⚠️  python-telegram-bot 未安装，推送功能不可用")
    print("    安装命令: pip install python-telegram-bot")


class PushManager:
    """推送管理器"""

    def __init__(self):
        self.db = get_db_manager()
        self.extractor = get_keyword_extractor()
        self.bot = None
        self.last_check_time = None

        # 初始化 Telegram Bot
        if TELEGRAM_AVAILABLE and TELEGRAM_BOT_TOKEN != 'YOUR_BOT_TOKEN_HERE':
            try:
                self.bot = Bot(token=TELEGRAM_BOT_TOKEN)
                print("✓ Telegram Bot 初始化成功")
            except Exception as e:
                print(f"⚠️  Telegram Bot 初始化失败: {e}")
                self.bot = None
        else:
            print("⚠️  Telegram Bot Token 未配置")

    def subscribe(self, user_id: str, keyword: str,
                 telegram_chat_id: str = None) -> Dict:
        """
        创建订阅

        Args:
            user_id: 用户ID
            keyword: 订阅的关键词
            telegram_chat_id: Telegram 聊天ID

        Returns:
            {'success': bool, 'message': str, 'subscription_id': int}
        """
        try:
            subscription_id = self.db.create_subscription(
                user_id, keyword, telegram_chat_id
            )

            return {
                'success': True,
                'message': f'订阅关键词 "{keyword}" 成功',
                'subscription_id': subscription_id
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'订阅失败: {str(e)}',
                'subscription_id': None
            }

    def unsubscribe(self, subscription_id: int) -> Dict:
        """
        取消订阅

        Args:
            subscription_id: 订阅ID

        Returns:
            {'success': bool, 'message': str}
        """
        try:
            rows = self.db.deactivate_subscription(subscription_id)

            if rows > 0:
                return {
                    'success': True,
                    'message': '取消订阅成功'
                }
            else:
                return {
                    'success': False,
                    'message': '订阅不存在'
                }
        except Exception as e:
            return {
                'success': False,
                'message': f'取消订阅失败: {str(e)}'
            }

    def get_user_subscriptions(self, user_id: str) -> List[Dict]:
        """
        获取用户的订阅列表

        Args:
            user_id: 用户ID

        Returns:
            订阅列表
        """
        return self.db.get_user_subscriptions(user_id)

    def check_new_messages(self, since_minutes: int = 60) -> List[Dict]:
        """
        检查新消息

        Args:
            since_minutes: 检查最近N分钟的消息

        Returns:
            新消息列表
        """
        # 计算起始时间
        since_time = datetime.now() - timedelta(minutes=since_minutes)
        since_time_str = since_time.strftime('%Y-%m-%dT%H:%M:%S')

        # 查询新消息
        query = """
        SELECT id, channel_id, text, date
        FROM messages
        WHERE date >= ?
        ORDER BY date DESC
        """

        news_list = self.db.execute_query(
            query,
            (since_time_str,),
            self.db.history_db_path
        )

        return news_list

    def match_subscriptions(self, news: Dict) -> List[Dict]:
        """
        匹配新闻与订阅

        Args:
            news: 新闻字典

        Returns:
            匹配的订阅列表
        """
        # 提取新闻关键词
        keywords = self.extractor.extract_keywords(news['text'], top_n=10)
        keyword_list = [kw for kw, weight in keywords]

        # 查询所有活跃订阅
        query = """
        SELECT id, user_id, keyword, telegram_chat_id
        FROM subscriptions
        WHERE is_active = 1
        """
        subscriptions = self.db.execute_query(query)

        # 匹配订阅
        matched = []
        for sub in subscriptions:
            sub_keyword = sub['keyword'].lower()

            # 检查关键词是否匹配
            if any(sub_keyword in kw.lower() for kw in keyword_list):
                # 检查是否已推送过
                if not self.db.check_news_pushed(sub['id'], news['id']):
                    matched.append(sub)

        return matched

    async def send_telegram_message(self, chat_id: str, news: Dict,
                                   keyword: str) -> bool:
        """
        发送 Telegram 消息

        Args:
            chat_id: Telegram 聊天ID
            news: 新闻字典
            keyword: 触发的关键词

        Returns:
            是否发送成功
        """
        if not self.bot:
            print("⚠️  Telegram Bot 未初始化")
            return False

        try:
            # 构建消息
            message = self._format_push_message(news, keyword)

            # 发送消息
            await self.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode='Markdown'
            )

            return True

        except TelegramError as e:
            print(f"❌ Telegram 消息发送失败: {e}")
            return False
        except Exception as e:
            print(f"❌ 发送消息时出错: {e}")
            return False

    async def push_to_subscribers(self, news: Dict, subscriptions: List[Dict]):
        """
        向订阅者推送新闻

        Args:
            news: 新闻字典
            subscriptions: 订阅列表
        """
        for sub in subscriptions:
            # 发送推送
            success = await self.send_telegram_message(
                sub['telegram_chat_id'],
                news,
                sub['keyword']
            )

            # 记录推送历史
            status = 'success' if success else 'failed'
            self.db.save_push_history(sub['id'], news['id'], status)

            if success:
                print(f"✓ 推送成功: 用户 {sub['user_id']}, 关键词 '{sub['keyword']}'")
            else:
                print(f"✗ 推送失败: 用户 {sub['user_id']}, 关键词 '{sub['keyword']}'")

    async def run_push_service(self, check_interval: int = None):
        """
        运行推送服务（持续监听）

        Args:
            check_interval: 检查间隔（秒）
        """
        check_interval = check_interval or PUSH_CHECK_INTERVAL

        print("=" * 70)
        print("  实时新闻推送服务启动")
        print("=" * 70)
        print(f"检查间隔: {check_interval}秒")
        print("按 Ctrl+C 停止服务")
        print()

        while True:
            try:
                # 检查新消息
                check_minutes = check_interval // 60 + 1
                new_messages = self.check_new_messages(since_minutes=check_minutes)

                if new_messages:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 发现 {len(new_messages)} 条新消息")

                    # 处理每条新消息
                    for news in new_messages:
                        # 匹配订阅
                        matched_subs = self.match_subscriptions(news)

                        if matched_subs:
                            print(f"  匹配到 {len(matched_subs)} 个订阅")

                            # 推送
                            await self.push_to_subscribers(news, matched_subs)
                else:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 无新消息")

                # 等待下次检查
                await asyncio.sleep(check_interval)

            except KeyboardInterrupt:
                print("\n服务已停止")
                break
            except Exception as e:
                print(f"❌ 服务运行出错: {e}")
                await asyncio.sleep(check_interval)

    def _format_push_message(self, news: Dict, keyword: str) -> str:
        """
        格式化推送消息

        Args:
            news: 新闻字典
            keyword: 关键词

        Returns:
            格式化的消息文本
        """
        # 提取新闻摘要（前150字符）
        text = news['text']
        summary = text[:150] + '...' if len(text) > 150 else text

        # 格式化日期
        date_str = news['date']
        try:
            date_obj = datetime.fromisoformat(date_str.replace('T', ' ').replace('+00:00', ''))
            date_formatted = date_obj.strftime('%Y-%m-%d %H:%M')
        except:
            date_formatted = date_str

        # 构建消息
        message = f"""
🔔 *关键词推送：{keyword}*

📰 *新闻内容：*
{summary}

📅 *发布时间：*
{date_formatted}

_来自 新闻分析系统_
        """.strip()

        return message


# 单例模式
_push_manager = None

def get_push_manager() -> PushManager:
    """获取推送管理器单例"""
    global _push_manager
    if _push_manager is None:
        _push_manager = PushManager()
    return _push_manager


if __name__ == "__main__":
    # 测试订阅功能
    manager = get_push_manager()

    # 创建测试订阅
    result = manager.subscribe(
        user_id="test_user_001",
        keyword="比特币",
        telegram_chat_id="123456789"
    )
    print(f"\n订阅结果: {result}")

    # 查询订阅
    subscriptions = manager.get_user_subscriptions("test_user_001")
    print(f"\n用户订阅列表: {len(subscriptions)}条")
    for sub in subscriptions:
        print(f"  - {sub['keyword']} (ID: {sub['id']})")

    # 测试新消息检查
    print("\n检查最近60分钟的新消息:")
    new_messages = manager.check_new_messages(since_minutes=60)
    print(f"  发现 {len(new_messages)} 条新消息")

    # 如果要运行推送服务（需要 Telegram Bot Token）
    # asyncio.run(manager.run_push_service())

