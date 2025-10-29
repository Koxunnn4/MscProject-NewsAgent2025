"""
工具函数模块
"""
import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import json

# 添加项目根目录到路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)


def format_date(date_str: str, format_type: str = 'datetime') -> str:
    """
    格式化日期字符串
    
    Args:
        date_str: 日期字符串
        format_type: 格式类型 ('date', 'datetime', 'time')
        
    Returns:
        格式化后的日期字符串
    """
    try:
        # 解析ISO格式日期
        date_obj = datetime.fromisoformat(date_str.replace('T', ' ').replace('+00:00', ''))
        
        if format_type == 'date':
            return date_obj.strftime('%Y-%m-%d')
        elif format_type == 'datetime':
            return date_obj.strftime('%Y-%m-%d %H:%M:%S')
        elif format_type == 'time':
            return date_obj.strftime('%H:%M:%S')
        else:
            return date_str
    except:
        return date_str


def get_date_range(days_ago: int = 30) -> tuple:
    """
    获取日期范围
    
    Args:
        days_ago: 多少天前
        
    Returns:
        (start_date, end_date) 元组
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_ago)
    
    return (
        start_date.strftime('%Y-%m-%d'),
        end_date.strftime('%Y-%m-%d')
    )


def truncate_text(text: str, max_length: int = 200, suffix: str = '...') -> str:
    """
    截断文本
    
    Args:
        text: 原始文本
        max_length: 最大长度
        suffix: 后缀
        
    Returns:
        截断后的文本
    """
    if len(text) <= max_length:
        return text
    return text[:max_length].rstrip() + suffix


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    安全除法
    
    Args:
        numerator: 分子
        denominator: 分母
        default: 分母为0时的默认值
        
    Returns:
        结果
    """
    return numerator / denominator if denominator != 0 else default


def dict_to_json(data: Dict, pretty: bool = False) -> str:
    """
    字典转JSON字符串
    
    Args:
        data: 字典
        pretty: 是否格式化
        
    Returns:
        JSON字符串
    """
    if pretty:
        return json.dumps(data, ensure_ascii=False, indent=2)
    return json.dumps(data, ensure_ascii=False)


def json_to_dict(json_str: str) -> Dict:
    """
    JSON字符串转字典
    
    Args:
        json_str: JSON字符串
        
    Returns:
        字典
    """
    try:
        return json.loads(json_str)
    except:
        return {}


def ensure_dir(directory: str):
    """
    确保目录存在
    
    Args:
        directory: 目录路径
    """
    os.makedirs(directory, exist_ok=True)


def get_file_size(file_path: str) -> str:
    """
    获取文件大小（人类可读格式）
    
    Args:
        file_path: 文件路径
        
    Returns:
        文件大小字符串
    """
    if not os.path.exists(file_path):
        return "0 B"
    
    size = os.path.getsize(file_path)
    
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    
    return f"{size:.2f} TB"


def batch_list(data: List[Any], batch_size: int) -> List[List[Any]]:
    """
    将列表分批
    
    Args:
        data: 数据列表
        batch_size: 每批大小
        
    Returns:
        批次列表
    """
    return [data[i:i + batch_size] for i in range(0, len(data), batch_size)]


def merge_dicts(*dicts: Dict) -> Dict:
    """
    合并多个字典
    
    Args:
        *dicts: 多个字典
        
    Returns:
        合并后的字典
    """
    result = {}
    for d in dicts:
        result.update(d)
    return result


def filter_dict(data: Dict, keys: List[str]) -> Dict:
    """
    过滤字典，只保留指定的键
    
    Args:
        data: 原始字典
        keys: 要保留的键列表
        
    Returns:
        过滤后的字典
    """
    return {k: v for k, v in data.items() if k in keys}


def calculate_percentage(part: float, total: float, decimal_places: int = 2) -> float:
    """
    计算百分比
    
    Args:
        part: 部分
        total: 总数
        decimal_places: 小数位数
        
    Returns:
        百分比
    """
    if total == 0:
        return 0.0
    percentage = (part / total) * 100
    return round(percentage, decimal_places)


def normalize_keyword(keyword: str) -> str:
    """
    标准化关键词（去除空格、转小写）
    
    Args:
        keyword: 原始关键词
        
    Returns:
        标准化后的关键词
    """
    return keyword.strip().lower()


def highlight_keyword(text: str, keyword: str, 
                     highlight_tag: tuple = ('<mark>', '</mark>')) -> str:
    """
    在文本中高亮关键词
    
    Args:
        text: 原始文本
        keyword: 关键词
        highlight_tag: 高亮标签（开始标签，结束标签）
        
    Returns:
        高亮后的文本
    """
    start_tag, end_tag = highlight_tag
    return text.replace(keyword, f'{start_tag}{keyword}{end_tag}')


if __name__ == "__main__":
    # 测试工具函数
    print("测试工具函数:")
    
    # 日期格式化
    date_str = "2025-10-16T02:00:05+00:00"
    print(f"\n原始日期: {date_str}")
    print(f"格式化日期: {format_date(date_str, 'date')}")
    print(f"格式化时间: {format_date(date_str, 'datetime')}")
    
    # 获取日期范围
    start, end = get_date_range(30)
    print(f"\n最近30天: {start} ~ {end}")
    
    # 文本截断
    long_text = "这是一段很长的文本" * 50
    print(f"\n截断前长度: {len(long_text)}")
    truncated = truncate_text(long_text, 50)
    print(f"截断后: {truncated}")
    print(f"截断后长度: {len(truncated)}")

