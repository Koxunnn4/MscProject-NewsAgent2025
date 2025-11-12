"""
Process HKStocks news and extract keywords

This script reads news from hkstocks_news table, extracts keywords,
and saves them to hkstocks_keywords table.
"""

import os
import sys
import sqlite3
from pathlib import Path
from typing import List, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.hkstocks_analysis.hkstocks_analyzer import get_hkstocks_analyzer


class HKStocksKeywordProcessor:
    """Process HKStocks news and extract keywords"""

    def __init__(self, db_path: str = None):
        """
        Initialize processor

        Args:
            db_path: Path to news_analysis.db (defaults to project data directory)
        """
        if db_path is None:
            db_path = project_root / 'data' / 'news_analysis.db'

        self.db_path = db_path
        self.conn = None
        self.analyzer = None

    def connect(self):
        """Connect to database"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        print(f"Connected to database: {self.db_path}")

    def disconnect(self):
        """Disconnect from database"""
        if self.conn:
            self.conn.close()
            print("Disconnected from database")

    def get_news_without_keywords(self, limit: int = None) -> List[dict]:
        """
        Get news items that haven't been processed yet

        Args:
            limit: Maximum number of news to fetch

        Returns:
            List of news items
        """
        cursor = self.conn.cursor()

        query = """
            SELECT n.id, n.title, n.content, n.publish_date
            FROM hkstocks_news n
            WHERE NOT EXISTS (
                SELECT 1 FROM hkstocks_keywords k
                WHERE k.news_id = n.id
            )
            ORDER BY n.publish_date DESC
        """

        if limit:
            query += f" LIMIT {limit}"

        cursor.execute(query)
        return [dict(row) for row in cursor.fetchall()]

    def save_keywords(self, news_id: int, keywords: List[Tuple[str, float]]):
        """
        Save extracted keywords to database

        Args:
            news_id: News item ID
            keywords: List of (keyword, weight) tuples
        """
        cursor = self.conn.cursor()

        for keyword, weight in keywords:
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO hkstocks_keywords (news_id, keyword, weight)
                    VALUES (?, ?, ?)
                """, (news_id, keyword, weight))
            except Exception as e:
                print(f"Error saving keyword '{keyword}' for news {news_id}: {e}")

        self.conn.commit()

    def process_news_item(self, news_item: dict) -> int:
        """
        Process a single news item

        Args:
            news_item: News item dict with id, title, content

        Returns:
            Number of keywords extracted
        """
        news_id = news_item['id']
        title = news_item['title']
        content = news_item['content']

        # Combine title and content for better keyword extraction
        full_text = f"{title}\n{content}"

        # Extract keywords
        keywords = self.analyzer.extract_keywords(full_text, top_n=10)

        if keywords:
            # Save to database
            self.save_keywords(news_id, keywords)
            print(f"  News {news_id}: Extracted {len(keywords)} keywords")
            return len(keywords)
        else:
            print(f"  News {news_id}: No keywords extracted")
            return 0

    def process_all(self, limit: int = None, batch_size: int = 10):
        """
        Process all unprocessed news items

        Args:
            limit: Maximum number of news to process (None for all)
            batch_size: Number of news to process in each batch
        """
        self.connect()

        # Initialize analyzer (singleton)
        print("Initializing HKStocks analyzer...")
        self.analyzer = get_hkstocks_analyzer()

        # Get unprocessed news
        print(f"Fetching unprocessed news...")
        news_items = self.get_news_without_keywords(limit)

        if not news_items:
            print("No unprocessed news found!")
            self.disconnect()
            return

        total = len(news_items)
        print(f"Found {total} unprocessed news items")
        print("-" * 50)

        # Process in batches
        processed = 0
        total_keywords = 0

        for i, news_item in enumerate(news_items, 1):
            print(f"Processing {i}/{total}...")
            try:
                num_keywords = self.process_news_item(news_item)
                total_keywords += num_keywords
                processed += 1

                # Progress update every batch
                if i % batch_size == 0:
                    print(f"Progress: {i}/{total} processed, {total_keywords} keywords extracted")
                    print("-" * 50)

            except Exception as e:
                print(f"Error processing news {news_item['id']}: {e}")
                continue

        print("=" * 50)
        print(f"Processing complete!")
        print(f"  Total processed: {processed}/{total}")
        print(f"  Total keywords: {total_keywords}")
        print(f"  Average keywords per news: {total_keywords/processed:.2f}" if processed > 0 else "")

        self.disconnect()

    def get_statistics(self):
        """Print statistics about processed keywords"""
        self.connect()
        cursor = self.conn.cursor()

        # Total news and processed news
        cursor.execute("SELECT COUNT(*) FROM hkstocks_news")
        total_news = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(DISTINCT news_id) FROM hkstocks_keywords
        """)
        processed_news = cursor.fetchone()[0]

        # Total keywords
        cursor.execute("SELECT COUNT(*) FROM hkstocks_keywords")
        total_keywords = cursor.fetchone()[0]

        # Top keywords
        cursor.execute("""
            SELECT keyword, COUNT(*) as frequency, AVG(weight) as avg_weight
            FROM hkstocks_keywords
            GROUP BY keyword
            ORDER BY frequency DESC
            LIMIT 20
        """)
        top_keywords = cursor.fetchall()

        print("=" * 50)
        print("HKStocks Keywords Statistics")
        print("=" * 50)
        print(f"Total news: {total_news}")
        print(f"Processed news: {processed_news}")
        print(f"Unprocessed news: {total_news - processed_news}")
        print(f"Total keywords: {total_keywords}")
        print(f"Average keywords per news: {total_keywords/processed_news:.2f}" if processed_news > 0 else "")
        print("\nTop 20 Keywords:")
        print("-" * 50)
        for keyword, freq, avg_weight in top_keywords:
            print(f"  {keyword:20s} | Frequency: {freq:3d} | Avg Weight: {avg_weight:.4f}")

        self.disconnect()


def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description='Process HKStocks news and extract keywords')
    parser.add_argument('--limit', type=int, help='Limit number of news to process')
    parser.add_argument('--batch-size', type=int, default=10, help='Batch size for progress updates')
    parser.add_argument('--stats', action='store_true', help='Show statistics only')
    parser.add_argument('--db', type=str, help='Path to database file')

    args = parser.parse_args()

    processor = HKStocksKeywordProcessor(db_path=args.db)

    if args.stats:
        processor.get_statistics()
    else:
        processor.process_all(limit=args.limit, batch_size=args.batch_size)


if __name__ == '__main__':
    main()
