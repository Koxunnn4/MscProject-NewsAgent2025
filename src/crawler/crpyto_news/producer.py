import json
from datetime import datetime
import redis
from telethon import TelegramClient, events
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)



class NewsProducer:
    def __init__(self, redis_config, telegram_config):
        # Redis连接
        self.redis_client = redis.Redis(host=redis_config["host"], port=redis_config["port"], decode_responses=True)
        self.list_key = redis_config["stream_key"]  # 复用stream_key作为list名
        self.max_len = redis_config["max_len"]

        # Telegram客户端
        # 代理配置
        proxy = None
        if telegram_config.get("proxy", {}).get("enabled"):
            proxy = (
                telegram_config["proxy"]["type"],
                telegram_config["proxy"]["host"],
                telegram_config["proxy"]["port"],
            )
        self.client = TelegramClient(telegram_config["session"], telegram_config["api_id"], telegram_config["api_hash"], proxy=proxy)
        self.channels = telegram_config["channels"]
        self.backfill_limit = telegram_config["backfill_limit"]

    async def start(self):
        await self.client.start()

    async def stop(self):
        await self.client.disconnect()

    def _format_message(self, message):
        return {"id": message.id, "timestamp": message.date.isoformat(), "channel": str(message.chat_id), "content": message.text}

    async def process_message(self, message):
        if not message.text:
            return

        news = self._format_message(message)
        # 使用Redis List代替Stream
        self.redis_client.lpush(self.list_key, json.dumps(news))
        # 维护列表长度
        if self.max_len > 0:
            self.redis_client.ltrim(self.list_key, 0, self.max_len - 1)

    async def run_history_mode(self):
        """历史模式：获取历史消息"""
        for channel in self.channels:
            async for message in self.client.iter_messages(channel, limit=self.backfill_limit):
                await self.process_message(message)

    async def run_stream_mode(self):
        """实时模式：监听新消息"""

        @self.client.on(events.NewMessage(chats=self.channels))
        async def handler(event):
            await self.process_message(event.message)

        # 保持运行
        await self.client.run_until_disconnected()
