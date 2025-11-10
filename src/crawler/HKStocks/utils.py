"""
港股新闻爬虫工具函数
"""

import re
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urljoin, urlparse


def parse_chinese_date(date_str: str) -> Optional[datetime]:
    """
    解析AAStocks日期格式: "2025/11/04 09:50 HKT"

    Args:
        date_str: 日期字符串

    Returns:
        datetime对象，解析失败返回None
    """
    if not date_str:
        return None

    date_str = date_str.strip()

    try:
        # 格式: "YYYY/MM/DD HH:MM HKT" 或 "YYYY/MM/DD HH:MM"
        match = re.search(r'(\d{4})/(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{2})', date_str)
        if match:
            year, month, day, hour, minute = map(int, match.groups())
            return datetime(year, month, day, hour, minute)

    except ValueError as e:
        print(f"日期解析错误: {date_str}, 错误: {e}")
        return None

    print(f"无法解析日期格式: {date_str}")
    return None


def normalize_url(url: str, base_url: str) -> str:
    """
    规范化URL，处理相对路径

    Args:
        url: 原始URL
        base_url: 基础URL

    Returns:
        完整的URL
    """
    if not url:
        return ""

    # 如果已经是完整URL，直接返回
    if url.startswith(('http://', 'https://')):
        return url

    # 处理相对路径
    return urljoin(base_url, url)


def extract_domain(url: str) -> str:
    """
    从URL中提取域名

    Args:
        url: 完整URL

    Returns:
        域名字符串
    """
    parsed = urlparse(url)
    return parsed.netloc


def is_valid_url(url: str) -> bool:
    """
    验证URL是否有效

    Args:
        url: URL字符串

    Returns:
        是否有效
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False


def clean_text(text: str) -> str:
    """
    清理文本，移除多余的空白字符

    Args:
        text: 原始文本

    Returns:
        清理后的文本
    """
    if not text:
        return ""

    # 移除多余空格
    text = re.sub(r'\s+', ' ', text)
    # 移除首尾空格
    text = text.strip()

    return text


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

    return delta.days <= days and delta.days >= 0


def generate_message_id(url: str, title: str) -> int:
    """
    生成唯一的消息ID（用于数据库去重）

    Args:
        url: 新闻URL
        title: 新闻标题

    Returns:
        唯一ID
    """
    # 结合URL和标题生成哈希值
    unique_string = f"{url}|{title}"
    return abs(hash(unique_string))
