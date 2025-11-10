"""
AAStocks 港股新闻爬虫 - 从汇总页面提取新闻
"""

import time
import requests
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import config

from .models import HKStockNews
from .utils import (
    parse_chinese_date,
    normalize_url,
    is_within_days
)


class AaStocksScraper:
    """AAStocks 新闻爬虫类 - 从汇总页面提取新闻链接并获取完整内容"""

    # 新闻类型映射
    NEWS_TYPES = {
        'top_news': '71',          # 重点新闻
        'popular_news': '91',       # 热门新闻
        'latest_news': '65',        # 即市新闻 (最新)
        'research_report': '102',   # 大行报告
        'result_announcement': '101',  # 公司业绩
        'recommend_news': '999998',  # 用户推荐
        'positive_news': '999997',   # 利好新闻
        'negative_news': '999996',   # 利空新闻
    }

    def __init__(self, config: Optional[Dict] = None):
        """
        初始化爬虫

        Args:
            config: 配置字典
        """
        if config is None:
            config = {}

        self.api_url = 'https://wdata.aastocks.com/datafeed/getaafnnews.ashx'
        self.detail_url_template = 'http://www.aastocks.com/tc/stocks/news/aafn-con/{news_id}/latest-news/AAFN'

        self.timeout = config.get('timeout', 30)
        self.delay = config.get('delay', 0.5)  # API请求可以快一些
        self.headers = config.get('headers', {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        })

        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def fetch_news(self, days: int = 1, news_type: str = 'latest_news', max_count: int = 100) -> List[HKStockNews]:
        """
        爬取指定天数内的新闻

        Args:
            days: 爬取最近几天的新闻，默认1天
            news_type: 新闻类型，默认'latest_news' (未使用，保留参数兼容性)
            max_count: 最多爬取数量

        Returns:
            新闻对象列表

        Raises:
            requests.RequestException: 网络请求失败
            Exception: 其他错误
        """
        print(f"开始爬取AAStocks新闻 (最近 {days} 天)...")
        print(f"汇总页面: {config.HKSTOCKS_BASE_URL}")

        news_list = []

        try:
            # 从汇总页面提取新闻链接
            news_links = self._extract_news_links_from_page()

            if not news_links:
                print("未在汇总页面找到任何新闻链接")
                return news_list

            print(f"汇总页面找到 {len(news_links)} 条新闻链接")

            # 限制爬取数量
            news_links = news_links[:max_count]

            # 访问每个新闻详情页获取完整内容
            for url, title in news_links:
                try:
                    # 获取新闻完整内容
                    content, publish_date = self._fetch_news_detail(url, title)

                    # 检查日期是否在指定范围内
                    if publish_date and not is_within_days(publish_date, days):
                        continue

                    # 如果无法提取发布日期，使用当前时间
                    if not publish_date:
                        publish_date = datetime.now()

                    # 创建新闻对象
                    news = HKStockNews(
                        title=title,
                        url=url,
                        content=content if content else title,
                        publish_date=publish_date,
                        source='AAStocks',
                        category='港股新闻'
                    )

                    news_list.append(news)
                    print(f"  ✓ [{publish_date.strftime('%Y-%m-%d %H:%M')}] {title[:50]}...")

                except Exception as e:
                    print(f"  × 处理新闻失败 [{title[:30]}...]: {e}")
                    continue

                # 添加延迟
                time.sleep(self.delay)

        except requests.RequestException as e:
            error_msg = f"网络请求失败: {str(e)}"
            print(f"错误: {error_msg}")
            raise

        except Exception as e:
            error_msg = f"爬取过程中发生错误: {str(e)}"
            print(f"错误: {error_msg}")
            raise

        print(f"爬取完成，共获取 {len(news_list)} 条新闻")
        return news_list

    def _extract_news_links_from_page(self) -> List[tuple]:
        """
        从汇总页面提取新闻链接

        Returns:
            新闻链接列表，每项为(url, title)元组
        """
        from bs4 import BeautifulSoup

        try:
            response = self.session.get(
                config.HKSTOCKS_BASE_URL,
                timeout=self.timeout
            )
            response.raise_for_status()
            response.encoding = 'utf-8'

            soup = BeautifulSoup(response.text, 'lxml')

            # 查找所有新闻链接
            news_links = []
            seen_urls = set()

            for link in soup.find_all('a', href=True):
                href = link.get('href', '')

                # 过滤出新闻详情页链接
                if '/stocks/news/aafn-con/' in href or '/news/aafn-con/' in href:
                    # 构建完整URL
                    if href.startswith('http'):
                        full_url = href
                    else:
                        full_url = 'http://www.aastocks.com' + href if href.startswith('/') else f'http://www.aastocks.com/{href}'

                    # 获取新闻标题
                    title = link.get_text().strip()

                    # 去重并确保有标题
                    if title and full_url not in seen_urls:
                        news_links.append((full_url, title))
                        seen_urls.add(full_url)

            return news_links

        except requests.Timeout:
            raise requests.RequestException(f"请求超时: {config.HKSTOCKS_BASE_URL}")
        except requests.ConnectionError:
            raise requests.RequestException(f"连接失败: {config.HKSTOCKS_BASE_URL}")
        except requests.HTTPError as e:
            raise requests.RequestException(f"HTTP错误 {e.response.status_code}: {config.HKSTOCKS_BASE_URL}")
        except Exception as e:
            raise Exception(f"提取新闻链接失败: {e}")

    def _fetch_news_detail(self, url: str, title: str) -> tuple:
        """
        获取新闻详情页的完整内容和发布日期

        Args:
            url: 新闻详情页URL
            title: 新闻标题

        Returns:
            (content, publish_date) 元组
        """
        from bs4 import BeautifulSoup
        import re

        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            response.encoding = 'utf-8'

            soup = BeautifulSoup(response.text, 'lxml')

            # 提取内容
            content = ""
            content_element = soup.find(id='spanContent')

            if not content_element:
                content_element = soup.find(id='divContentContainer')

            if content_element:
                text = content_element.get_text()
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                content = '\n'.join(lines)
                content = content.replace('AASTOCKS新聞', '').strip()

                # 过滤无效内容
                if '暫時沒有相關新聞' in content or '暂时没有相关新闻' in content:
                    content = ""
                elif '最HIT熱話' in content and len(content) > 500:
                    content = ""

            # 如果没有提取到内容，尝试p标签
            if not content:
                paragraphs = soup.find_all('p')
                content_paragraphs = [p.get_text().strip() for p in paragraphs
                                    if len(p.get_text().strip()) > 20]
                if content_paragraphs:
                    content = '\n\n'.join(content_paragraphs)

            # 提取发布日期
            publish_date = None

            # 尝试从页面提取日期
            date_patterns = [
                r'(\d{4})/(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{2})',  # 2025/11/05 16:30
                r'(\d{4})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{2})',  # 2025-11-05 16:30
            ]

            page_text = soup.get_text()
            for pattern in date_patterns:
                match = re.search(pattern, page_text)
                if match:
                    try:
                        year, month, day, hour, minute = map(int, match.groups())
                        publish_date = datetime(year, month, day, hour, minute)
                        break
                    except:
                        continue

            return content, publish_date

        except Exception as e:
            print(f"  × 获取新闻内容失败 [{url}]: {e}")
            return "", None

    def _create_news_object(self, item: Dict, publish_date: datetime) -> Optional[HKStockNews]:
        """
        从API数据创建新闻对象

        Args:
            item: API返回的新闻数据
            publish_date: 发布日期

        Returns:
            HKStockNews对象或None
        """
        try:
            news_id = item.get('NewsID', '')
            title = item.get('Title', '').strip()

            if not news_id or not title:
                return None

            # 生成详情页URL
            url = self.detail_url_template.format(news_id=news_id)

            # 获取新闻完整内容
            content = self._fetch_full_content(url)

            # 如果获取失败，使用标题作为内容
            if not content or len(content) < 10:
                content = title

            news = HKStockNews(
                title=title,
                url=url,
                content=content,
                publish_date=publish_date,
                source='AAStocks',
                category=item.get('NewsType', '')
            )

            return news

        except Exception as e:
            print(f"创建新闻对象失败: {e}")
            return None

    def _fetch_full_content(self, url: str) -> str:
        """
        获取新闻完整内容

        Args:
            url: 新闻详情页URL

        Returns:
            新闻正文内容
        """
        try:
            from bs4 import BeautifulSoup

            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            response.encoding = 'utf-8'

            soup = BeautifulSoup(response.text, 'lxml')

            # 查找新闻正文（按优先级尝试不同选择器）
            content_element = None

            # 方法1: 查找id="spanContent"
            content_element = soup.find(id='spanContent')

            # 方法2: 查找id="divContentContainer"
            if not content_element:
                content_element = soup.find(id='divContentContainer')

            # 方法3: 查找所有p标签
            if not content_element:
                paragraphs = soup.find_all('p')
                content_paragraphs = [p.get_text().strip() for p in paragraphs
                                    if len(p.get_text().strip()) > 20]
                if content_paragraphs:
                    return '\n\n'.join(content_paragraphs)

            if content_element:
                # 获取文本并清理
                text = content_element.get_text()
                # 移除多余的空白和换行
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                content = '\n'.join(lines)

                # 移除可能的无关内容
                content = content.replace('AASTOCKS新聞', '').strip()

                # 检查是否为"暫時沒有相關新聞"的无效页面
                if '暫時沒有相關新聞' in content or '暂时没有相关新闻' in content:
                    return ""

                # 检查是否只是热门话题列表（通常很长但不是新闻正文）
                if '最HIT熱話' in content and len(content) > 500:
                    return ""

                return content

            return ""

        except Exception as e:
            print(f"  × 获取新闻内容失败 [{url}]: {e}")
            return ""

    def save_to_database(self, news_list: List[HKStockNews], db_manager=None) -> int:
        """
        保存新闻到hkstocks_news表（按URL去重）

        Args:
            news_list: 新闻对象列表
            db_manager: 数据库管理器实例，如果为None则自动获取

        Returns:
            实际保存的新闻数量
        """
        if not news_list:
            print("没有新闻需要保存")
            return 0

        # 获取数据库管理器
        if db_manager is None:
            try:
                from src.database.db_manager import get_db_manager
                db_manager = get_db_manager()
            except ImportError:
                print("错误: 无法导入数据库管理器")
                return 0

        # 确保hkstocks_news表已创建
        try:
            from src.database.schema import (
                CREATE_HKSTOCKS_NEWS_TABLE,
                CREATE_HKSTOCKS_URL_INDEX,
                CREATE_HKSTOCKS_DATE_INDEX
            )

            db_manager.execute_update(CREATE_HKSTOCKS_NEWS_TABLE, (), db_manager.history_db_path)
            db_manager.execute_update(CREATE_HKSTOCKS_URL_INDEX, (), db_manager.history_db_path)
            db_manager.execute_update(CREATE_HKSTOCKS_DATE_INDEX, (), db_manager.history_db_path)
        except Exception as e:
            print(f"创建表失败: {e}")

        saved_count = 0
        duplicate_count = 0
        updated_count = 0

        for news in news_list:
            try:
                # 检查URL是否已存在
                check_query = """
                    SELECT id, content FROM hkstocks_news
                    WHERE url = ?
                """

                result = db_manager.execute_query(
                    check_query,
                    (news.url,),
                    db_manager.history_db_path
                )

                if result:
                    # 如果已存在，检查内容是否有更新
                    existing_id, existing_content = result[0]
                    if len(news.content) > len(existing_content):
                        # 更新内容（如果新内容更长）
                        update_query = """
                            UPDATE hkstocks_news
                            SET content = ?, updated_at = datetime('now')
                            WHERE id = ?
                        """
                        db_manager.execute_update(
                            update_query,
                            (news.content, existing_id),
                            db_manager.history_db_path
                        )
                        updated_count += 1
                        print(f"  ↻ 更新新闻: {news.title[:50]}...")
                    else:
                        duplicate_count += 1
                        print(f"  - 跳过重复新闻: {news.title[:50]}...")
                    continue

                # 插入新闻
                insert_query = """
                    INSERT INTO hkstocks_news (title, url, content, publish_date, source, category)
                    VALUES (?, ?, ?, ?, ?, ?)
                """

                db_manager.execute_update(
                    insert_query,
                    (
                        news.title,
                        news.url,
                        news.content,
                        news.publish_date.isoformat(),
                        news.source,
                        news.category
                    ),
                    db_manager.history_db_path
                )

                saved_count += 1
                print(f"  + 保存新闻: {news.title[:50]}...")

            except Exception as e:
                print(f"保存新闻失败 [{news.title[:30]}...]: {e}")
                continue

        print(f"\n保存完成: 新增 {saved_count} 条，更新 {updated_count} 条，跳过重复 {duplicate_count} 条")
        return saved_count


def scrape_hkstocks_news(days: int = 1, news_type: str = 'latest_news', config: Optional[Dict] = None, save_to_db: bool = True) -> List[HKStockNews]:
    """
    便捷函数：爬取港股新闻

    Args:
        days: 爬取最近几天的新闻
        news_type: 新闻类型 (latest_news, top_news, popular_news等)
        config: 爬虫配置
        save_to_db: 是否保存到数据库

    Returns:
        新闻对象列表
    """
    scraper = AaStocksScraper(config)
    news_list = scraper.fetch_news(days, news_type=news_type, max_count=5)

    if save_to_db and news_list:
        scraper.save_to_database(news_list)

    return news_list


# 测试代码
if __name__ == '__main__':
    print("=" * 60)
    print("AAStocks 港股新闻爬虫测试 (API版本)")
    print("=" * 60)

    try:
        news = scrape_hkstocks_news(days=1, save_to_db=False)
        print(f"\n成功爬取 {len(news)} 条新闻")

        if news:
            print("\n前3条新闻预览:")
            for i, n in enumerate(news[:3], 1):
                print(f"\n{i}. {n.title}")
                print(f"   时间: {n.publish_date}")
                print(f"   链接: {n.url}")
                print(f"   内容: {n.content[:100]}...")

    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()
