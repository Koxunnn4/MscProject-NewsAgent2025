#!/usr/bin/env python3
"""离线生成新闻摘要并写入 SQLite 数据库的脚本。

示例用法：
    python scripts/precompute_abstracts.py --db-path data/history.db
    python scripts/precompute_abstracts.py --db-path src/crawler/crpyto_news/stream.db --table messages
"""
from __future__ import annotations

import argparse
import logging
import re
import sqlite3
import sys
from pathlib import Path
from typing import Optional

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

# 将项目根目录加入路径，便于读取 config 以及复用常量
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from config import CRYPTO_DB_PATH, HISTORY_DB_PATH  # noqa: E402

LOGGER = logging.getLogger("precompute_abstracts")
MODEL_ID = "csebuetnlp/mT5_multilingual_XLSum"
SUMMARY_MIN_LEN = 16
SUMMARY_MAX_LEN = 84


def _load_model(device: torch.device):
    LOGGER.info("加载摘要模型 %s 到设备 %s", MODEL_ID, device)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, use_fast=False)
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_ID)
    model.to(device)
    model.eval()
    return tokenizer, model


def _summarize(text: str, tokenizer, model, device: torch.device) -> str:
    if not text:
        return ""
    clean_text = re.sub(r"\s+", " ", text.strip())
    if not clean_text:
        return ""

    inputs = tokenizer(
        clean_text,
        return_tensors="pt",
        padding="max_length",
        truncation=True,
        max_length=512,
    ).to(device)

    with torch.no_grad():
        summary_ids = model.generate(
            inputs["input_ids"],
            max_length=SUMMARY_MAX_LEN,
            min_length=SUMMARY_MIN_LEN,
            num_beams=4,
            no_repeat_ngram_size=2,
            early_stopping=True,
        )

    summary = tokenizer.decode(
        summary_ids[0],
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False,
    )
    return summary.strip()


def _ensure_abstract_column(conn: sqlite3.Connection, table: str) -> None:
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table})")
    columns = {row[1] for row in cursor.fetchall()}
    if "abstract" in columns:
        return
    LOGGER.info("表 %s 缺少 abstract 列，正在新增...", table)
    cursor.execute(f"ALTER TABLE {table} ADD COLUMN abstract TEXT")
    conn.commit()


def _detect_original_text(conn: sqlite3.Connection, table: str) -> bool:
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table})")
    columns = {row[1] for row in cursor.fetchall()}
    return "original_text" in columns


def precompute(db_path: Path, table: str, limit: Optional[int], force: bool, commit_every: int, device: torch.device) -> None:
    if not db_path.exists():
        raise FileNotFoundError(f"数据库文件不存在: {db_path}")

    conn = sqlite3.connect(db_path)
    _ensure_abstract_column(conn, table)
    has_original_text = _detect_original_text(conn, table)

    conditions = []
    if not force:
        conditions.append("(abstract IS NULL OR TRIM(abstract) = '')")
    if has_original_text:
        conditions.append(
            "((original_text IS NOT NULL AND TRIM(original_text) != '') OR (text IS NOT NULL AND TRIM(text) != ''))"
        )
        select_sql = f"SELECT id, original_text, text, abstract FROM {table}"
    else:
        conditions.append("(text IS NOT NULL AND TRIM(text) != '')")
        select_sql = f"SELECT id, text, abstract FROM {table}"

    if conditions:
        select_sql += " WHERE " + " AND ".join(conditions)
    select_sql += " ORDER BY id"
    if limit:
        select_sql += f" LIMIT {int(limit)}"

    cursor = conn.cursor()
    LOGGER.info("开始读取待处理的新闻...")
    cursor.execute(select_sql)
    rows = cursor.fetchall()
    total = len(rows)
    if total == 0:
        LOGGER.info("没有需要生成摘要的记录，任务完成")
        conn.close()
        return

    tokenizer, model = _load_model(device)

    processed = 0
    updated = 0
    for row in rows:
        if has_original_text:
            news_id, original_text, text, abstract = row
            content = original_text or text or ""
        else:
            news_id, text, abstract = row
            content = text or ""
        processed += 1

        if not force and abstract and abstract.strip():
            continue

        summary = _summarize(content, tokenizer, model, device)
        if not summary:
            continue

        cursor.execute(
            f"UPDATE {table} SET abstract = ? WHERE id = ?",
            (summary, news_id),
        )
        updated += 1

        if updated % commit_every == 0:
            conn.commit()
            LOGGER.info("已处理 %s/%s 条新闻，已写入 %s 条摘要", processed, total, updated)

    conn.commit()
    conn.close()
    LOGGER.info("摘要生成完成，共处理 %s 条新闻，写入摘要 %s 条", processed, updated)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="为 SQLite 新闻库预生成摘要")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path(CRYPTO_DB_PATH),
        # default=Path(HISTORY_DB_PATH),
        help="SQLite 数据库路径 (默认使用 config.CRYPTO_DB_PATH)",
    )
    parser.add_argument(
        "--table",
        type=str,
        default="messages",
        help="需要处理的数据表名称，默认 messages",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="只处理前 N 条记录，用于调试",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="无论 abstract 是否已有内容都重新生成",
    )
    parser.add_argument(
        "--commit-every",
        type=int,
        default=25,
        help="每处理多少条提交一次事务，默认 25",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="auto",
        choices=["auto", "cpu", "cuda"],
        help="推理设备 (auto/cpu/cuda)，默认 auto",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        help="日志级别，默认 INFO",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))

    if args.device == "cpu":
        device = torch.device("cpu")
    elif args.device == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("请求使用 CUDA 但当前环境不可用")
        device = torch.device("cuda")
    else:  # auto
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    precompute(
        db_path=args.db_path,
        table=args.table,
        limit=args.limit,
        force=args.force,
        commit_every=max(1, args.commit_every),
        device=device,
    )


if __name__ == "__main__":
    main()
