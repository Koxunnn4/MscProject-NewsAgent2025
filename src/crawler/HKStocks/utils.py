"""HKStocks 爬虫仅保留所需的工具函数。"""

from datetime import datetime


def is_within_days(date: datetime, days: int) -> bool:
    """
    判断日期是否在指定天数内

    Args:
        date: 要检查的日期
        days: 天数范围

    Returns:
        是否在范围内
    """
    if not date:
        return False

    now = datetime.now()
    delta = now - date

    return 0 <= delta.days <= days
