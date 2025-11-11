"""
关键词和币种分析模块
独立的离线分析脚本，不依赖 Redis 消息队列
根据数据库中的 text 字段，重新计算 keywords 和 industry 字段并覆盖存储
"""
import sqlite3
import logging
import os
import sys
from typing import Tuple

# 添加项目根目录到路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from crypto_analysis.crypto_analyzer import CryptoAnalyzer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class KeywordsAnalyzer:
    """
    关键词和币种分析器
    从数据库读取新闻文本，使用 CryptoAnalyzer 提取关键词和币种，并更新数据库
    """

    def __init__(self, db_path: str):
        """
        初始化分析器

        Args:
            db_path: SQLite 数据库路径
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.analyzer = CryptoAnalyzer()
        logger.info(f"✓ 已初始化 KeywordsAnalyzer，数据库: {db_path}")

    def capitalize_english(self, text: str) -> str:
        """将字符串中的英文部分转为大写，保留中文和其他字符不变"""
        result = []
        for char in text:
            if char.isalpha() and ord(char) < 128:  # ASCII 英文字符
                result.append(char.upper())
            else:
                result.append(char)
        return ''.join(result)

    def analyze_text(self, text: str, top_n: int = 10) -> Tuple[str, str]:
        """
        分析单条文本，提取关键词和币种

        Args:
            text: 新闻文本
            top_n: 提取的关键词数量

        Returns:
            (keywords_str, industry_str) 元组
        """
        try:
            # 提取关键词
            keywords = self.analyzer.extract_keywords(text, top_n=top_n)
            if keywords:
                keywords_str = ",".join([kw[0] for kw in keywords])
                # keywords_str = self.capitalize_english(keywords_str)  # 英文部分转大写
            else:
                keywords_str = ""

            # 识别币种
            mentioned_coins = self.analyzer.identify_currency(text)
            industry_str = ",".join(mentioned_coins)

            return keywords_str, industry_str

        except Exception as e:
            logger.error(f"分析文本失败: {e}")
            return "", ""

    def analyze_all_messages(self, batch_size: int = 10):
        """
        批量分析所有消息，更新 keywords 和 industry 字段

        Args:
            batch_size: 每次提交的批量大小
        """
        try:
            # 获取总行数
            self.cursor.execute("SELECT COUNT(*) FROM messages")
            total_count = self.cursor.fetchone()[0]

            if total_count == 0:
                logger.warning("数据库中没有消息")
                return

            logger.info(f"开始分析 {total_count} 条消息...")

            # 读取所有消息
            self.cursor.execute("SELECT id, text FROM messages WHERE text IS NOT NULL")
            rows = self.cursor.fetchall()

            processed = 0
            for idx, (msg_id, text) in enumerate(rows, 1):
                if not text or not text.strip():
                    logger.debug(f"[{idx}/{total_count}] 消息 ID {msg_id}: 文本为空，跳过")
                    continue

                # 分析文本
                keywords_str, industry_str = self.analyze_text(text)

                # 更新数据库
                try:
                    self.cursor.execute(
                        "UPDATE messages SET keywords = ?, industry = ? WHERE id = ?",
                        (keywords_str, industry_str, msg_id)
                    )
                    processed += 1

                    # 定期提交（避免频繁提交）
                    if processed % batch_size == 0:
                        self.conn.commit()
                        logger.info(f"[{idx}/{total_count}] 已处理 {processed} 条消息，进度: {idx/total_count*100:.1f}%")

                except Exception as e:
                    logger.error(f"更新消息 ID {msg_id} 失败: {e}")
                    continue

            # 最后提交
            self.conn.commit()
            logger.info(f"✓ 分析完成！共处理 {processed}/{total_count} 条消息")

        except Exception as e:
            logger.error(f"批量分析失败: {e}")
            self.conn.rollback()

    def analyze_by_channel(self, channel_id: str, batch_size: int = 10):
        """
        按频道分析消息，更新 keywords 和 industry 字段

        Args:
            channel_id: 频道 ID
            batch_size: 每次提交的批量大小
        """
        try:
            # 获取该频道的消息数
            self.cursor.execute(
                "SELECT COUNT(*) FROM messages WHERE channel_id = ? AND text IS NOT NULL",
                (channel_id,)
            )
            total_count = self.cursor.fetchone()[0]

            if total_count == 0:
                logger.warning(f"频道 {channel_id} 中没有有效消息")
                return

            logger.info(f"开始分析频道 {channel_id} 的 {total_count} 条消息...")

            # 读取该频道的消息
            self.cursor.execute(
                "SELECT id, text FROM messages WHERE channel_id = ? AND text IS NOT NULL",
                (channel_id,)
            )
            rows = self.cursor.fetchall()

            processed = 0
            for idx, (msg_id, text) in enumerate(rows, 1):
                if not text.strip():
                    continue

                # 分析文本
                keywords_str, industry_str = self.analyze_text(text)

                # 更新数据库
                try:
                    self.cursor.execute(
                        "UPDATE messages SET keywords = ?, industry = ? WHERE id = ?",
                        (keywords_str, industry_str, msg_id)
                    )
                    processed += 1

                    if processed % batch_size == 0:
                        self.conn.commit()
                        logger.info(f"[{idx}/{total_count}] 已处理 {processed} 条消息，进度: {idx/total_count*100:.1f}%")

                except Exception as e:
                    logger.error(f"更新消息 ID {msg_id} 失败: {e}")
                    continue

            # 最后提交
            self.conn.commit()
            logger.info(f"✓ 频道 {channel_id} 分析完成！共处理 {processed}/{total_count} 条消息")

        except Exception as e:
            logger.error(f"按频道分析失败: {e}")
            self.conn.rollback()

    def analyze_by_date_range(self, start_date: str, end_date: str, batch_size: int = 10):
        """
        按日期范围分析消息，更新 keywords 和 industry 字段

        Args:
            start_date: 开始日期 (ISO 格式)
            end_date: 结束日期 (ISO 格式)
            batch_size: 每次提交的批量大小
        """
        try:
            # 获取日期范围内的消息数
            self.cursor.execute(
                "SELECT COUNT(*) FROM messages WHERE date BETWEEN ? AND ? AND text IS NOT NULL",
                (start_date, end_date)
            )
            total_count = self.cursor.fetchone()[0]

            if total_count == 0:
                logger.warning(f"日期范围 {start_date} 到 {end_date} 中没有有效消息")
                return

            logger.info(f"开始分析 {start_date} 到 {end_date} 期间的 {total_count} 条消息...")

            # 读取日期范围内的消息
            self.cursor.execute(
                "SELECT id, text FROM messages WHERE date BETWEEN ? AND ? AND text IS NOT NULL",
                (start_date, end_date)
            )
            rows = self.cursor.fetchall()

            processed = 0
            for idx, (msg_id, text) in enumerate(rows, 1):
                if not text.strip():
                    continue

                # 分析文本
                keywords_str, industry_str = self.analyze_text(text)

                # 更新数据库
                try:
                    self.cursor.execute(
                        "UPDATE messages SET keywords = ?, industry = ? WHERE id = ?",
                        (keywords_str, industry_str, msg_id)
                    )
                    processed += 1

                    if processed % batch_size == 0:
                        self.conn.commit()
                        logger.info(f"[{idx}/{total_count}] 已处理 {processed} 条消息，进度: {idx/total_count*100:.1f}%")

                except Exception as e:
                    logger.error(f"更新消息 ID {msg_id} 失败: {e}")
                    continue

            # 最后提交
            self.conn.commit()
            logger.info(f"✓ 日期范围分析完成！共处理 {processed}/{total_count} 条消息")

        except Exception as e:
            logger.error(f"按日期范围分析失败: {e}")
            self.conn.rollback()

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            logger.info("✓ 数据库连接已关闭")

    def __del__(self):
        self.close()


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description="关键词和币种分析工具")
    parser.add_argument(
        "--db",
        type=str,
        default="historytest.db",
        help="数据库路径"
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["all", "channel", "date"],
        default="all",
        help="分析模式 (all=全部, channel=按频道, date=按日期)"
    )
    parser.add_argument(
        "--channel",
        type=str,
        help="频道 ID (mode=channel 时使用)"
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="开始日期，ISO 格式 (mode=date 时使用)"
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="结束日期，ISO 格式 (mode=date 时使用)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="批量提交大小 (默认: 10)"
    )

    args = parser.parse_args()

    # 检查数据库存在
    if not os.path.exists(args.db):
        logger.error(f"数据库文件不存在: {args.db}")
        return

    # 初始化分析器
    analyzer = KeywordsAnalyzer(args.db)

    try:
        # 根据模式执行
        if args.mode == "all":
            analyzer.analyze_all_messages(batch_size=args.batch_size)
        elif args.mode == "channel":
            if not args.channel:
                logger.error("mode=channel 时必须提供 --channel 参数")
                return
            analyzer.analyze_by_channel(args.channel, batch_size=args.batch_size)
        elif args.mode == "date":
            if not args.start_date or not args.end_date:
                logger.error("mode=date 时必须提供 --start-date 和 --end-date 参数")
                return
            analyzer.analyze_by_date_range(args.start_date, args.end_date, batch_size=args.batch_size)
    finally:
        analyzer.close()


if __name__ == "__main__":
    main()
