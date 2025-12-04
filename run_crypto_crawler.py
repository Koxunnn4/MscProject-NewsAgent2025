import argparse
import asyncio
import logging
from typing import Literal

from config import (
    CRYPTO_DB_PATH,
    get_crypto_redis_config,
    get_crypto_telegram_config,
)
from src.crawler.crpyto_news.consumer import NewsConsumer
from src.crawler.crpyto_news.producer import NewsProducer

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def run_history(producer: NewsProducer, consumer: NewsConsumer):
    logger.info(">>> 开始历史模式")
    await producer.run_history_mode()
    await consumer.run_history_mode()
    logger.info(">>> 历史消息处理完成")


async def run_stream(producer: NewsProducer, consumer: NewsConsumer):
    logger.info(">>> 开始实时模式")
    producer_task = asyncio.create_task(producer.run_stream_mode(), name="crypto-news-producer")
    consumer_task = asyncio.create_task(consumer.run_stream_mode(), name="crypto-news-consumer")
    await asyncio.gather(producer_task, consumer_task)


async def main(mode: Literal["history", "stream"] = "stream"):
    telegram_config = get_crypto_telegram_config()
    redis_config = get_crypto_redis_config()

    try:
        producer = NewsProducer(redis_config, telegram_config)
        consumer = NewsConsumer(redis_config, CRYPTO_DB_PATH)
        logger.info("生产者和消费者初始化成功 (DB: %s)", CRYPTO_DB_PATH)
    except Exception as exc:
        logger.error("生产者或消费者初始化失败: %s", exc)
        return

    try:
        await producer.start()
        if mode == "history":
            await run_history(producer, consumer)
        else:
            await run_stream(producer, consumer)
    except Exception as exc:
        logger.error("运行过程中出现错误: %s", exc)
    finally:
        await producer.stop()
        consumer.close()


def parse_args() -> Literal["history", "stream"]:
    parser = argparse.ArgumentParser(description="Web3 Crypto News Agent")
    parser.add_argument(
        "-mode",
        choices=["history", "stream"],
        default="stream",
        help="运行模式：history(历史回溯) 或 stream(实时监听)",
    )
    parsed = parser.parse_args()
    return parsed.mode  # type: ignore[return-value]


if __name__ == "__main__":
    args_mode = parse_args()
    asyncio.run(main(args_mode))
