#!/usr/bin/env python3
"""重新计算港股新闻的关键词与行业标签。"""

from __future__ import annotations

import argparse
import sqlite3
from typing import List, Tuple

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import HISTORY_DB_PATH
from src.hkstocks_analysis import get_hkstocks_analyzer


def fetch_news(conn: sqlite3.Connection, only_missing: bool, limit: int | None) -> List[sqlite3.Row]:
    """读取需要重新处理的新闻记录。"""
    base_query = [
        "SELECT id, title, content",
        "FROM hkstocks_news",
    ]
    params: List[object] = []

    if only_missing:
        base_query.append(
            "WHERE (keywords IS NULL OR keywords = '')"
            " OR (industry IS NULL OR industry = '')"
        )

    base_query.append("ORDER BY publish_date DESC")

    if limit:
        base_query.append("LIMIT ?")
        params.append(limit)

    query = " ".join(base_query)
    cursor = conn.execute(query, params)
    return cursor.fetchall()


def build_metadata(analyzer, title: str, content: str, top_n: int = 5) -> Tuple[str | None, str]:
    """根据标题与内容生成关键词与行业。"""
    full_text = f"{title}\n{content}" if content else title

    keywords = analyzer.extract_keywords(full_text, top_n=top_n)
    keyword_str = ",".join([kw[0] for kw in keywords]) if keywords else None

    industries = analyzer.identify_industry(full_text, top_n=1)
    industry_name = industries[0][1] if industries else '其他'

    return keyword_str, industry_name


def main() -> None:
    parser = argparse.ArgumentParser(
        description="刷新 testdb_history.db 中港股新闻的关键词与行业",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="只处理最近的 N 条新闻",
    )
    parser.add_argument(
        "--missing-only",
        action="store_true",
        help="仅处理缺失关键词或行业的记录",
    )

    args = parser.parse_args()

    analyzer = get_hkstocks_analyzer()
    print("分析器已加载，开始读取数据库...")

    with sqlite3.connect(HISTORY_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = fetch_news(conn, args.missing_only, args.limit)

        if not rows:
            print("没有符合条件的新闻。")
            return

        print(f"待处理新闻: {len(rows)} 条")
        update_sql = (
            "UPDATE hkstocks_news"
            " SET keywords = ?, industry = ?, updated_at = datetime('now')"
            " WHERE id = ?"
        )

        updated = 0
        for row in rows:
            try:
                keywords_str, industry_name = build_metadata(
                    analyzer, row["title"], row["content"], top_n=5
                )
                conn.execute(update_sql, (keywords_str, industry_name, row["id"]))
                updated += 1
                if updated % 50 == 0:
                    print(f"  已处理 {updated} 条新闻...")
            except Exception as exc:  # pragma: no cover - 记录异常但不中断
                print(f"  × 处理新聞 {row['id']} 失败: {exc}")

        conn.commit()
        print(f"完成！共更新 {updated} 条新闻。")


if __name__ == "__main__":
    main()
