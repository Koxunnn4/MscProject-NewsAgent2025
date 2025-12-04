"""Realtime ingestion pipeline bridging crawler and web app."""
from __future__ import annotations

import asyncio
import contextlib
import logging
from pathlib import Path
from typing import Optional

_IMPORT_ERROR: Optional[ModuleNotFoundError] = None

try:  # pragma: no cover - optional dependency resolution
    from src.crawler.crpyto_news.producer import NewsProducer
    from src.crawler.crpyto_news.consumer import NewsConsumer
except ModuleNotFoundError as exc:  # pragma: no cover - import side effects
    NewsProducer = None  # type: ignore[assignment]
    NewsConsumer = None  # type: ignore[assignment]
    _IMPORT_ERROR = exc

from config import CRYPTO_DB_PATH, get_crypto_redis_config, get_crypto_telegram_config

logger = logging.getLogger(__name__)


class RealtimeNewsIngestor:
    """Orchestrates Telegram streaming ingestion into the analytics database."""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self._producer: Optional[object] = None
        self._consumer: Optional[object] = None
        self._tasks: list[asyncio.Task] = []
        self._lock = asyncio.Lock()
        self._started = False

    async def start(self, run_history: bool = False):
        async with self._lock:
            if self._started:
                return

            if NewsProducer is None or NewsConsumer is None:
                missing = _IMPORT_ERROR.name if _IMPORT_ERROR else "未知依赖"
                logger.error("实时管道缺少依赖模块: %s", missing)
                return

            redis_config = get_crypto_redis_config()
            if not redis_config:
                logger.error("缺少 Redis 配置，实时管道未启动")
                return

            sqlite_path = str(self.db_path)

            telegram_config = get_crypto_telegram_config()

            missing = [key for key, value in telegram_config.items() if key in {"session", "api_id", "api_hash"} and not value]
            if missing:
                logger.error("实时管道缺少 Telegram 配置字段: %s", ", ".join(missing))
                return

            logger.info("启动实时新闻摄取管道，数据库: %s", sqlite_path)

            try:
                self._producer = NewsProducer(redis_config, telegram_config)
                self._consumer = NewsConsumer(redis_config, db_path=sqlite_path)
                await self._producer.start()

                if run_history:
                    await self._producer.run_history_mode()
                    await self._consumer.run_history_mode()

                producer_task = asyncio.create_task(self._producer.run_stream_mode(), name="news-producer-stream")
                consumer_task = asyncio.create_task(self._consumer.run_stream_mode(), name="news-consumer-stream")

                self._tasks = [producer_task, consumer_task]
                self._started = True
            except Exception as exc:  # pragma: no cover - runtime errors
                if isinstance(exc, ModuleNotFoundError) and exc.name == "socks":
                    logger.error(
                        "实时新闻管道启动失败: 缺少 PySocks 依赖 (pip install PySocks) 或关闭配置中的 proxy",
                        exc_info=True,
                    )
                else:
                    logger.error("实时新闻管道启动失败: %s", exc, exc_info=True)
                await self.stop()

    async def stop(self):
        async with self._lock:
            if not self._started:
                return

            logger.info("停止实时新闻摄取管道")
            for task in self._tasks:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            self._tasks.clear()

            if self._producer:
                with contextlib.suppress(Exception):
                    await self._producer.stop()
            if self._consumer:
                self._consumer.close()

            self._producer = None
            self._consumer = None
            self._started = False

    @property
    def is_running(self) -> bool:
        return self._started


_ingestor: Optional[RealtimeNewsIngestor] = None


def get_realtime_ingestor(db_path: Path | str = Path(CRYPTO_DB_PATH)) -> RealtimeNewsIngestor:
    global _ingestor
    if _ingestor is None:
        _ingestor = RealtimeNewsIngestor(db_path=db_path)
    return _ingestor
