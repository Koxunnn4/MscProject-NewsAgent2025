"""
港股新闻爬虫模块

该模块用于从 AAStocks 网站爬取港股新闻
"""

from .aastocks_scraper import AaStocksScraper, scrape_hkstocks_news

__all__ = ['AaStocksScraper', 'scrape_hkstocks_news']
