"""
AAStocks 港股新闻爬虫 - 从汇总页面提取新闻
"""

import time
import requests
from typing import List, Dict, Optional
from datetime import datetime
import config
from queue import Queue
from threading import Thread, Lock

from .models import HKStockNews
from .utils import is_within_days


class AaStocksScraper:
    """AAStocks 新闻爬虫类 - 从汇总页面提取新闻链接并获取完整内容"""

    def __init__(self, config: Optional[Dict] = None):
        """
        初始化爬虫

        Args:
            config: 配置字典
        """
        if config is None:
            config = {}

        self.timeout = config.get('timeout', 30)
        self.delay = config.get('delay', 0.5)  # API请求可以快一些
        self.headers = config.get('headers', {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        })

        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def fetch_and_save_with_pipeline(
        self,
        days: int = 1,
        max_count: int = 100,
        use_selenium: bool = False,
        extract_keywords: bool = True,
        num_workers: int = 3
    ) -> Dict[str, int]:
        """
        使用生产者-消费者模式边爬取边保存新闻

        Args:
            days: 爬取最近几天的新闻，默认1天
            max_count: 最多爬取数量
            use_selenium: 是否使用Selenium滚动加载更多
            extract_keywords: 是否提取关键词
            num_workers: 消费者线程数量，默认3

        Returns:
            统计信息字典 {'saved': 保存数, 'updated': 更新数, 'duplicated': 重复数, 'failed': 失败数}
        """
        print(f"\n{'='*60}")
        print(f"生产者-消费者模式爬取 (工作线程: {num_workers})")
        print(f"{'='*60}")
        print(f"开始爬取AAStocks新闻 (最近 {days} 天)...")
        print(f"汇总页面: {config.HKSTOCKS_BASE_URL}")

        # 创建任务队列和结果统计
        news_queue = Queue(maxsize=50)  # 限制队列大小，避免内存占用过多
        stats = {
            'saved': 0,
            'updated': 0,
            'duplicated': 0,
            'failed': 0,
            'processed': 0
        }
        stats_lock = Lock()

        def update_stat(key: str, delta: int = 1):
            """线程安全地更新统计数据"""
            with stats_lock:
                stats[key] += delta

        # 初始化数据库管理器和关键词提取器
        try:
            from src.database.db_manager import get_db_manager
            db_manager = get_db_manager()
        except ImportError:
            print("错误: 无法导入数据库管理器")
            return stats

        analyzer = None
        if extract_keywords:
            try:
                from src.hkstocks_analysis.hkstocks_analyzer import get_hkstocks_analyzer
                print("初始化关键词提取器...")
                analyzer = get_hkstocks_analyzer()
                print("关键词提取器已就绪")
            except Exception as e:
                print(f"警告: 无法初始化关键词提取器: {e}")
                extract_keywords = False

        # 确保表已创建
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

        # 定义消费者函数
        def consumer_worker(worker_id: int):
            """消费者线程：从队列取新闻并保存到数据库"""
            while True:
                news = news_queue.get()
                
                if news is None:  # 结束信号
                    news_queue.task_done()
                    break

                try:
                    # 检查URL是否已存在
                    check_query = "SELECT id, content FROM hkstocks_news WHERE url = ?"
                    result = db_manager.execute_query(
                        check_query,
                        (news.url,),
                        db_manager.history_db_path
                    )

                    if result:
                        existing_id, existing_content = result[0]
                        if len(news.content) > len(existing_content):
                            # 提取关键词和行业
                            keywords_str, industry_str = None, None
                            if extract_keywords and analyzer:
                                keywords_str, industry_str = self._extract_keywords_and_industry(
                                    news, analyzer
                                )

                            # 更新内容
                            update_query = """
                                UPDATE hkstocks_news
                                SET content = ?, keywords = ?, industry = ?, updated_at = datetime('now')
                                WHERE id = ?
                            """
                            db_manager.execute_update(
                                update_query,
                                (news.content, keywords_str, industry_str, existing_id),
                                db_manager.history_db_path
                            )
                            update_stat('updated')
                            print(f"  [Worker-{worker_id}] ↻ 更新: {news.title[:40]}...")
                        else:
                            update_stat('duplicated')
                            print(f"  [Worker-{worker_id}] - 跳过: {news.title[:40]}...")
                    else:
                        # 提取关键词和行业
                        keywords_str, industry_str = None, None
                        if extract_keywords and analyzer:
                            keywords_str, industry_str = self._extract_keywords_and_industry(
                                news, analyzer
                            )

                        # 插入新闻
                        insert_query = """
                            INSERT INTO hkstocks_news (title, url, content, publish_date, source, category, keywords, industry)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """
                        db_manager.execute_update(
                            insert_query,
                            (
                                news.title,
                                news.url,
                                news.content,
                                news.publish_date.isoformat(),
                                news.source,
                                news.category,
                                keywords_str,
                                industry_str
                            ),
                            db_manager.history_db_path
                        )
                        update_stat('saved')
                        print(f"  [Worker-{worker_id}] + 保存: {news.title[:40]}...")
                        if keywords_str:
                            print(f"    关键词: {keywords_str[:60]}...")

                    update_stat('processed')

                except Exception as e:
                    update_stat('failed')
                    print(f"  [Worker-{worker_id}] × 保存失败 [{news.title[:30]}...]: {e}")

                finally:
                    news_queue.task_done()

        # 启动消费者线程
        workers = []
        for i in range(num_workers):
            worker = Thread(target=consumer_worker, args=(i+1,), daemon=True)
            worker.start()
            workers.append(worker)
        print(f"\n已启动 {num_workers} 个消费者线程\n")

        # 生产者：爬取新闻并放入队列
        try:
            # 从汇总页面提取新闻链接
            if use_selenium:
                news_links = self._extract_news_links_with_selenium(max_count=max_count)
            else:
                news_links = self._extract_news_links_from_page()

            if not news_links:
                print("未在汇总页面找到任何新闻链接")
            else:
                print(f"汇总页面找到 {len(news_links)} 条新闻链接")
                news_links = news_links[:max_count]

                # 逐条爬取并放入队列
                for idx, item in enumerate(news_links, 1):
                    try:
                        # 兼容两种格式
                        if len(item) == 3:
                            url, title, list_publish_date = item
                        else:
                            url, title = item
                            list_publish_date = None

                        # 获取新闻完整内容
                        content, detail_publish_date = self._fetch_news_detail(url, title)

                        # 优先使用列表页的时间
                        publish_date = list_publish_date or detail_publish_date

                        # 检查日期是否在指定范围内
                        if publish_date and not is_within_days(publish_date, days):
                            continue

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

                        # 放入队列（如果队列满了会阻塞）
                        news_queue.put(news)
                        print(f"  [Producer] ✓ [{idx}/{len(news_links)}] 爬取: {title[:40]}...")

                    except Exception as e:
                        print(f"  [Producer] × 爬取失败 [{title[:30]}...]: {e}")
                        continue

                    # 添加延迟
                    time.sleep(self.delay)

        except Exception as e:
            print(f"\n爬取过程中发生错误: {e}")
            import traceback
            traceback.print_exc()

        finally:
            # 发送结束信号给所有工作线程
            print("\n发送结束信号给消费者...")
            for _ in range(num_workers):
                news_queue.put(None)

            # 等待队列处理完成
            print("等待队列处理完成...")
            news_queue.join()

            # 等待所有工作线程结束
            for worker in workers:
                worker.join()

            print(f"\n{'='*60}")
            print("爬取完成统计")
            print(f"{'='*60}")
            print(f"新增: {stats['saved']} 条")
            print(f"更新: {stats['updated']} 条")
            print(f"跳过重复: {stats['duplicated']} 条")
            print(f"失败: {stats['failed']} 条")
            print(f"总处理: {stats['processed']} 条")
            print(f"{'='*60}")

        return stats

    def _extract_keywords_and_industry(self, news: HKStockNews, analyzer) -> tuple:
        """
        提取关键词和行业

        Args:
            news: 新闻对象
            analyzer: 关键词分析器

        Returns:
            (keywords_str, industry_str) 元组
        """
        keywords_str = None
        industry_str = None
        full_text = f"{news.title}\n{news.content}"

        try:
            keywords = analyzer.extract_keywords(full_text, top_n=5)
            if keywords:
                top_keywords = keywords[:5]
                keywords_str = ",".join([kw[0] for kw in top_keywords])
        except Exception as e:
            print(f"    × 关键词提取失败: {e}")

        try:
            industries = analyzer.identify_industry(full_text, top_n=1)
            if industries:
                _, industry_name, match_count = industries[0]
                industry_str = industry_name
        except Exception as e:
            print(f"    × 行业识别失败: {e}")

        return keywords_str, industry_str

    def _extract_news_links_with_selenium(self, max_count: int = 100, browser: str = 'chrome') -> List[tuple]:
        """
        使用Selenium滚动加载更多新闻链接

        Args:
            max_count: 最多提取的新闻数量
            browser: 使用的浏览器 ('safari', 'chrome', 'firefox')

        Returns:
            新闻链接列表，每项为(url, title, publish_date)元组
        """
        try:
            from selenium import webdriver
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
        except ImportError:
            print("× Selenium未安装，请运行: pip install selenium")
            print("  回退到基础爬取方式...")
            return self._extract_news_links_from_page()

        print(f"使用Selenium ({browser}) 滚动加载新闻...")

        driver = None
        news_links = []
        seen_urls = set()

        try:
            # 根据指定的浏览器启动
            print("  正在启动浏览器...")
            if browser.lower() == 'safari':
                # 使用 Safari（macOS 自带，无需安装额外驱动）
                # 首次使用需要启用：Safari -> 开发 -> 允许远程自动化
                print("  提示：如果首次使用，请确保已启用 Safari 远程自动化")
                print("       Safari菜单 -> 开发 -> 允许远程自动化")
                driver = webdriver.Safari()
            elif browser.lower() == 'chrome':
                from selenium.webdriver.chrome.options import Options

                chrome_options = Options()
                chrome_options.add_argument('--headless=new')  # 使用新的无头模式
                chrome_options.add_argument('--no-sandbox')
                chrome_options.add_argument('--disable-dev-shm-usage')
                chrome_options.add_argument('--disable-gpu')
                chrome_options.add_argument('--disable-extensions')
                chrome_options.add_argument('--disable-software-rasterizer')
                chrome_options.add_argument('--blink-settings=imagesEnabled=false')  # 禁用图片
                chrome_options.add_argument(f'user-agent={self.headers["User-Agent"]}')

                # 设置页面加载策略
                chrome_options.page_load_strategy = 'normal'  # 等待页面完全加载

                print("  启动 Chrome (无头模式)...")
                driver = webdriver.Chrome(options=chrome_options)
                driver.set_page_load_timeout(90)  # 增加超时到90秒
                driver.implicitly_wait(10)  # 隐式等待
            elif browser.lower() == 'firefox':
                from selenium.webdriver.firefox.options import Options
                firefox_options = Options()
                firefox_options.add_argument('--headless')
                driver = webdriver.Firefox(options=firefox_options)
            else:
                print(f"× 不支持的浏览器: {browser}，使用 Safari")
                driver = webdriver.Safari()

            print("  浏览器已启动，正在访问页面...")
            driver.get(config.HKSTOCKS_BASE_URL)
            print("  页面加载中...")

            # 等待页面加载
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "a"))
            )

            last_count = 0
            no_new_count = 0
            scroll_count = 0
            max_scrolls = 50  # 最多滚动次数

            while len(news_links) < max_count and scroll_count < max_scrolls:
                # 从页面HTML中提取新闻信息（包括时间）
                from bs4 import BeautifulSoup
                import re

                page_source = driver.page_source
                soup = BeautifulSoup(page_source, 'lxml')

                # 查找所有新闻链接
                for link in soup.find_all('a', href=True):
                    href = link.get('href', '')

                    if '/stocks/news/aafn-con/' in href or '/news/aafn-con/' in href:
                        # 构建完整URL
                        if href.startswith('http'):
                            full_url = href
                        else:
                            full_url = 'http://www.aastocks.com' + href if href.startswith('/') else f'http://www.aastocks.com/{href}'

                        if full_url in seen_urls:
                            continue

                        title = link.get_text().strip()
                        if not title:
                            continue

                        # 查找这个链接所在的新闻条目，提取时间
                        publish_date = None
                        parent = link.parent

                        # 方法1: 向上查找父元素，寻找包含时间的div
                        temp_parent = parent
                        for _ in range(10):  # 最多向上10层
                            if temp_parent is None:
                                break

                            # 查找 newstime4 或包含时间脚本的div
                            time_div = temp_parent.find('div', class_='newstime4')
                            if time_div:
                                # 从JavaScript中提取时间: dt:'2025/11/12 23:45'
                                script = time_div.find('script')
                                if script and script.string:
                                    time_match = re.search(r"dt:\s*['\"](\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{2})['\"]", script.string)
                                    if time_match:
                                        try:
                                            date_str = time_match.group(1)
                                            publish_date = datetime.strptime(date_str, '%Y/%m/%d %H:%M')
                                        except:
                                            pass
                                break

                            temp_parent = temp_parent.parent

                        # 方法2: 如果没找到，查找同级或附近的元素
                        if not publish_date and parent:
                            # 查找紧邻的script标签
                            siblings = parent.find_next_siblings('script', limit=3)
                            for sibling in siblings:
                                if sibling.string:
                                    time_match = re.search(r"dt:\s*['\"](\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{2})['\"]", sibling.string)
                                    if time_match:
                                        try:
                                            date_str = time_match.group(1)
                                            publish_date = datetime.strptime(date_str, '%Y/%m/%d %H:%M')
                                            break
                                        except:
                                            pass

                        # 方法3: 从整个页面的script标签中查找包含该新闻链接的时间
                        if not publish_date:
                            # 提取新闻ID (例如: NOW.1483265)
                            news_id_match = re.search(r'/([A-Z]+\.\d+)/', full_url)
                            if news_id_match:
                                news_id = news_id_match.group(1)
                                # 在页面中查找包含这个ID的script
                                all_scripts = soup.find_all('script')
                                for script in all_scripts:
                                    if script.string and news_id in script.string:
                                        time_match = re.search(r"dt:\s*['\"](\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{2})['\"]", script.string)
                                        if time_match:
                                            try:
                                                date_str = time_match.group(1)
                                                publish_date = datetime.strptime(date_str, '%Y/%m/%d %H:%M')
                                                break
                                            except:
                                                pass

                        # 添加到列表（包含时间）
                        news_links.append((full_url, title, publish_date))
                        seen_urls.add(full_url)

                        if len(news_links) >= max_count:
                            break

                if len(news_links) >= max_count:
                    break

                # 检查是否有新内容
                if len(news_links) == last_count:
                    no_new_count += 1
                    if no_new_count >= 3:  # 连续3次没有新内容，停止
                        print(f"  连续{no_new_count}次滚动无新内容，停止加载")
                        break
                else:
                    no_new_count = 0
                    print(f"  已加载 {len(news_links)} 条新闻...")

                last_count = len(news_links)

                # 滚动到页面底部
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                scroll_count += 1

                # 等待新内容加载
                time.sleep(0.5)

            print(f"✓ Selenium加载完成，共找到 {len(news_links)} 条新闻")
            return news_links

        except Exception as e:
            print(f"× Selenium加载失败: {e}")
            print("  回退到基础爬取方式...")
            return self._extract_news_links_from_page()

        finally:
            if driver:
                driver.quit()

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

            # 方法1: 从 JavaScript 变量中提取新闻时间
            # AAStocks 在页面中有 JavaScript 变量包含新闻时间
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string:
                    # 尝试多种模式提取时间
                    time_patterns = [
                        r"dt:\s*['\"](\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{2})['\"]",  # dt:'2025/11/12 23:45'
                        r"newstime['\"]?\s*[:=]\s*['\"](\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{2})['\"]",  # newstime:'...'
                    ]
                    
                    for pattern in time_patterns:
                        time_match = re.search(pattern, script.string)
                        if time_match:
                            try:
                                date_str = time_match.group(1)
                                # 尝试两种日期格式
                                for fmt in ['%Y/%m/%d %H:%M', '%Y-%m-%d %H:%M']:
                                    try:
                                        potential_date = datetime.strptime(date_str, fmt)
                                        # 确保日期合理（不是未来日期）
                                        if potential_date <= datetime.now() and potential_date.year >= 2020:
                                            publish_date = potential_date
                                            break
                                    except:
                                        continue
                                if publish_date:
                                    break
                            except:
                                continue
                    
                    if publish_date:
                        break

            # 方法2: 从 URL 中的新闻ID提取时间信息
            # URL格式: /aafn-con/NOW.1458883/latest-news
            # NOW 开头的通常是最新新闻，数字可能包含时间信息
            if not publish_date:
                # 对于最新新闻，从 meta 标签获取页面更新时间作为参考
                meta_date = soup.find('meta', attrs={'name': 'aa-update'})
                if meta_date and meta_date.get('content'):
                    try:
                        date_str = meta_date.get('content')
                        publish_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                    except:
                        pass

            # 方法3: 从页面文本提取日期
            if not publish_date:
                # 查找内容区域附近的日期
                content_div = soup.find(id='spanContent') or soup.find(id='divContentContainer')
                search_text = content_div.get_text() if content_div else soup.get_text()

                date_patterns = [
                    r'(\d{4})/(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{2})',  # 2025/11/05 16:30
                    r'(\d{4})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{2})',  # 2025-11-05 16:30
                ]

                for pattern in date_patterns:
                    match = re.search(pattern, search_text)
                    if match:
                        try:
                            year, month, day, hour, minute = map(int, match.groups())
                            # 确保日期合理（不是未来日期）
                            potential_date = datetime(year, month, day, hour, minute)
                            if potential_date <= datetime.now():
                                publish_date = potential_date
                                break
                        except:
                            continue

            return content, publish_date

        except Exception as e:
            print(f"  × 获取新闻内容失败 [{url}]: {e}")
            return "", None
