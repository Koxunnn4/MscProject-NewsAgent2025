"""
预生成新闻摘要脚本
"""
import sqlite3
import logging
import os
import sys
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch
from tqdm import tqdm

# 添加项目根目录到路径
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from config import HISTORY_DB_PATH

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SummaryGenerator:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model_id = "csebuetnlp/mT5_multilingual_XLSum"
        self.tokenizer = None
        self.model = None
        self._init_model()
        self._init_db()

    def _init_model(self):
        """初始化摘要模型"""
        try:
            logger.info(f"正在加载摘要模型 {self.model_id} (Device: {self.device})...")
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_id, use_fast=False)
            self.model = AutoModelForSeq2SeqLM.from_pretrained(self.model_id).to(self.device)
            logger.info("模型加载完成")
        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            sys.exit(1)

    def _init_db(self):
        """初始化数据库表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建摘要表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS news_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            news_id INTEGER NOT NULL,
            summary TEXT NOT NULL,
            method TEXT DEFAULT 'mT5',
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(news_id)
        );
        """)
        
        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_summary_news_id ON news_summaries(news_id);")
        
        conn.commit()
        conn.close()

    def generate_summary(self, text: str) -> str:
        """生成单条摘要"""
        if not text or len(text) < 50:
            return text  # 文本太短直接返回原文本

        try:
            input_ids = self.tokenizer(
                [text],
                return_tensors="pt",
                padding="max_length",
                truncation=True,
                max_length=512
            )["input_ids"].to(self.device)

            output_ids = self.model.generate(
                input_ids=input_ids,
                max_length=84,
                min_length=10,
                no_repeat_ngram_size=2,
                num_beams=4
            )[0]

            summary = self.tokenizer.decode(
                output_ids,
                skip_special_tokens=True,
                clean_up_tokenization_spaces=False
            )
            return summary
        except Exception as e:
            logger.error(f"摘要生成出错: {e}")
            return text[:100] + "..."

    def process_all_news(self, table_name: str = "messages"):
        """处理所有未生成摘要的新闻"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 获取未生成摘要的新闻
        # 假设新闻表名为 messages (Crypto) 或 hkstocks_news (HKStocks)
        # 且都有 id 和 text/content 字段
        
        text_col = "content"
        
        query = f"""
        SELECT n.id, n.{text_col}
        FROM {table_name} n
        LEFT JOIN news_summaries s ON n.id = s.news_id
        WHERE s.id IS NULL AND n.{text_col} IS NOT NULL AND length(n.{text_col}) > 20
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        total = len(rows)
        logger.info(f"发现 {total} 条待处理新闻 (表: {table_name})")
        
        if total == 0:
            conn.close()
            return

        count = 0
        for news_id, text in tqdm(rows, desc="生成摘要中"):
            summary = self.generate_summary(text)
            
            try:
                cursor.execute(
                    "INSERT OR IGNORE INTO news_summaries (news_id, summary) VALUES (?, ?)",
                    (news_id, summary)
                )
                count += 1
                
                # 每10条提交一次
                if count % 10 == 0:
                    conn.commit()
                    
            except Exception as e:
                logger.error(f"保存摘要失败 (ID: {news_id}): {e}")

        conn.commit()
        conn.close()
        logger.info(f"处理完成，共生成 {count} 条摘要")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="预生成新闻摘要")
    parser.add_argument("--source", type=str, default="all", choices=["crypto", "hkstocks", "all"], help="数据源")
    args = parser.parse_args()

    # if args.source in ["crypto", "all"]:
        # logger.info("=== 开始处理 Crypto 新闻 ===")
        # generator = SummaryGenerator(CRYPTO_DB_PATH)
        # generator.process_all_news(table_name="messages")

    if args.source in ["hkstocks", "all"]:
        logger.info("=== 开始处理 HKStocks 新闻 ===")
        generator = SummaryGenerator(HISTORY_DB_PATH)
        generator.process_all_news(table_name="hkstocks_news")

if __name__ == "__main__":
    main()
