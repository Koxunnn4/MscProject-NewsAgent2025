#!/usr/bin/env python3
"""
测试时间提取逻辑
"""

import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

def test_date_extraction(url):
    """测试从新闻详情页提取时间"""
    print(f"测试URL: {url}\n")
    
    response = requests.get(url, timeout=10)
    response.encoding = 'utf-8'
    soup = BeautifulSoup(response.text, 'lxml')
    
    publish_date = None
    
    # 方法1: 从 JavaScript 变量中提取
    print("方法1: 查找JavaScript中的时间...")
    scripts = soup.find_all('script')
    for i, script in enumerate(scripts):
        if script.string:
            # 查找包含日期的行
            if '20' in script.string:
                # 尝试多种模式
                patterns = [
                    r"dt:\s*['\"](\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{2})['\"]",
                    r"newstime['\"]?\s*[:=]\s*['\"](\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{2})['\"]",
                    r"['\"](\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{2})['\"]"
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, script.string)
                    if matches:
                        print(f"  Script {i} 找到匹配: {matches[:3]}")
                        for date_str in matches:
                            try:
                                date = datetime.strptime(date_str, '%Y/%m/%d %H:%M')
                                if date <= datetime.now() and date.year >= 2020:
                                    print(f"  ✓ 提取成功: {date}")
                                    if not publish_date or date > publish_date:
                                        publish_date = date
                            except:
                                pass
    
    # 方法2: 从页面文本提取
    if not publish_date:
        print("\n方法2: 从页面文本提取...")
        # 查找新闻内容区域
        content_div = soup.find(id='spanContent') or soup.find(id='divContentContainer')
        if content_div:
            text = content_div.get_text()
            print(f"  内容区域文本长度: {len(text)}")
            
            # 查找日期
            date_patterns = [
                r'(\d{4})/(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{2})',
                r'(\d{4})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{2})',
            ]
            
            for pattern in date_patterns:
                matches = re.findall(pattern, text[:1000])  # 只搜索前1000字符
                if matches:
                    print(f"  找到匹配: {matches[:3]}")
                    for match in matches:
                        try:
                            year, month, day, hour, minute = map(int, match)
                            date = datetime(year, month, day, hour, minute)
                            if date <= datetime.now() and date.year >= 2020:
                                print(f"  ✓ 提取成功: {date}")
                                publish_date = date
                                break
                        except:
                            pass
                if publish_date:
                    break
    
    # 方法3: 从整个页面HTML中搜索
    if not publish_date:
        print("\n方法3: 从整个页面HTML搜索...")
        all_dates = re.findall(r'20\d{2}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{2}', response.text)
        print(f"  找到 {len(all_dates)} 个日期")
        
        # 过滤合理的日期
        valid_dates = []
        for date_str in all_dates:
            try:
                date = datetime.strptime(date_str, '%Y/%m/%d %H:%M')
                if date <= datetime.now() and date.year >= 2020:
                    # 排除服务器时间（通常是当前时间）
                    if (datetime.now() - date).total_seconds() > 60:
                        valid_dates.append((date, date_str))
            except:
                pass
        
        if valid_dates:
            # 按时间排序，取最新的
            valid_dates.sort(reverse=True)
            print(f"  有效日期:")
            for date, date_str in valid_dates[:5]:
                print(f"    {date_str} -> {date}")
            
            publish_date = valid_dates[0][0]
    
    print(f"\n最终结果: {publish_date}")
    return publish_date

if __name__ == '__main__':
    # 测试几个URL
    test_urls = [
        'http://www.aastocks.com/tc/stocks/news/aafn-con/NOW.1483265/latest-news/AAFN',
    ]
    
    for url in test_urls:
        print("="*80)
        test_date_extraction(url)
        print()
