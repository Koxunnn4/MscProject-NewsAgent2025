import asyncio
import argparse
import yaml
import sys

from producer import NewsProducer
from consumer import NewsConsumer
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def main():
    # 加载配置
    try:
        with open("config.yaml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        logger.info("配置文件加载成功")
    except Exception as e:
        logger.error(f"配置文件加载失败: {e}")
        return

    # 解析命令行参数
    parser = argparse.ArgumentParser(description="Web3 Crypto News Agent")
    parser.add_argument(
        "-mode", choices=["history", "stream"],
        default="stream",
        help="运行模式：history(历史回溯) 或 stream(实时监听)"
    )
    args = parser.parse_args()

    # 创建生产者和消费者
    try:
        producer = NewsProducer(
            config["redis"],
            {
                "session": config["session"],
                "api_id": config["api_id"],
                "api_hash": config["api_hash"],
                "channels": config["channels"],
                "backfill_limit": config["backfill_limit"],
                "proxy": config.get("proxy"),
            },
        )

        consumer = NewsConsumer(
            config["redis"],
            config.get("sqlite_path", "default_db.db"),
        )
        logger.info("生产者和消费者初始化成功")
    except Exception as e:
        logger.error(f"生产者或消费者初始化失败: {e}")
        return

    # 启动生产者
    await producer.start()

    try:
        if args.mode == "history":
            logger.info(">>> 开始历史模式")
            # 先执行生产者的历史模式
            await producer.run_history_mode()

            # 然后消费者处理历史消息
            await consumer.run_history_mode()
            logger.info(">>> 历史消息处理完成")
        else:
            logger.info(">>> 开始实时模式")
            # 创建两个协程任务
            producer_task = asyncio.create_task(producer.run_stream_mode())
            consumer_task = asyncio.create_task(consumer.run_stream_mode())
            # 等待任务完成（实际上会一直运行）
            await asyncio.gather(producer_task, consumer_task)
    except Exception as e:
        logger.error(f"运行过程中出现错误: {e}")
    finally:
        await producer.stop()


if __name__ == "__main__":
    asyncio.run(main())
