"""
港股新闻数据模型
"""

from typing import Dict, Optional
from datetime import datetime


class HKStockNews:
    """港股新闻数据模型"""

    def __init__(
        self,
        title: str,
        url: str,
        content: str,
        publish_date: datetime,
        source: str = "AAStocks",
        category: Optional[str] = None
    ):
        """
        初始化港股新闻对象

        Args:
            title: 新闻标题
            url: 新闻URL
            content: 新闻正文
            publish_date: 发布时间
            source: 新闻来源
            category: 新闻分类
        """
        self.title = title
        self.url = url
        self.content = content
        self.publish_date = publish_date
        self.source = source
        self.category = category

    def to_dict(self) -> Dict:
        """
        转换为字典格式，便于数据库存储

        Returns:
            包含新闻信息的字典
        """
        return {
            'channel_id': 'aastocks',
            'message_id': hash(self.url),  # 使用URL哈希作为唯一ID
            'text': self._format_text(),
            'date': self.publish_date.isoformat(),
            'url': self.url,
            'title': self.title
        }

    def _format_text(self) -> str:
        """
        格式化新闻文本，将标题和正文组合

        Returns:
            格式化后的文本
        """
        return f"【{self.title}】\n\n{self.content}\n\n来源: {self.source}\nURL: {self.url}"

    def __repr__(self) -> str:
        return f"<HKStockNews(title='{self.title[:30]}...', date='{self.publish_date}')>"

    def __str__(self) -> str:
        return f"{self.title} ({self.publish_date.strftime('%Y-%m-%d %H:%M')})"
