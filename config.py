"""
项目配置文件
"""
import os

# 项目路径配置
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
LOGS_DIR = os.path.join(PROJECT_ROOT, 'logs')

# 数据库配置
DATABASE_PATH = os.path.join(DATA_DIR, 'news_analysis.db')  # 主数据库
HISTORY_DB_PATH = os.path.join(PROJECT_ROOT, 'testdb_history.db')  # 历史数据

# 关键词提取配置
KEYBERT_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
TOP_N_KEYWORDS = 10
KEYWORD_NGRAM_RANGE = (1, 2)

# 摘要生成配置
SUMMARY_MODEL = 'facebook/bart-large-cnn'  # 或 'facebook/bart-base'
SUMMARY_MIN_LENGTH = 50
SUMMARY_MAX_LENGTH = 150

# Hugging Face 镜像配置（加速下载）
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

# 热度分析配置
TREND_CACHE_HOURS = 1  # 缓存时间（小时）
SIMILARITY_THRESHOLD = 0.7  # 同义词识别阈值

# Telegram Bot 配置（Task 4）
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
TELEGRAM_API_ID = os.getenv('TELEGRAM_API_ID', '26287711')
TELEGRAM_API_HASH = os.getenv('TELEGRAM_API_HASH', '6e86edabc6868b8d0f9f1c9381d66350')

# 推送配置
PUSH_CHECK_INTERVAL = 300  # 检查新消息的间隔（秒）
MAX_PUSH_PER_USER = 50  # 每个用户最多推送次数

# API 配置
API_HOST = '127.0.0.1'
API_PORT = 8000
API_DEBUG = True

# 日志配置
LOG_LEVEL = 'INFO'
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_FILE = os.path.join(LOGS_DIR, 'app.log')

# 可视化配置
PLOT_STYLE = 'seaborn-v0_8-darkgrid'
PLOT_DPI = 100
PLOT_FIGSIZE = (12, 6)

# 港股新闻爬虫配置
HKSTOCKS_SOURCE_ID = 'aastocks'
HKSTOCKS_BASE_URL = 'http://www.aastocks.com/tc/stocks/news/aafn'
HKSTOCKS_REQUEST_TIMEOUT = 30  # 请求超时时间（秒）
HKSTOCKS_REQUEST_DELAY = 1.5  # 请求延迟（秒），避免过快访问
HKSTOCKS_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
}

# 创建必要的目录
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

