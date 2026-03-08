"""
爬虫配置。可通过环境变量覆盖（若存在 .env 会先加载）：
  WORK_SPACE  工作目录根路径，其下放置 football-betting-data、football-betting-report、football-betting-log 等
  CRAWLER_BASE_URL  页面地址
  CRAWLER_DOWNLOAD_DIR  下载目录（crawl 的 xls、merge_data 的 Master*.csv）
  CRAWLER_REPORT_DIR  报告目录（calc_car 的 CAR*.xlsx、plot_car 的 *_曲线.png，其下按 YYYYMMDD 子目录）
  CRAWLER_CUTOFF_HOUR  跨天时间临界点（时，0～23），默认 12
  CRAWLER_TIMEZONE  用于“当前时间”的时区（决定下载目录/文件名），默认 Asia/Tokyo
  CRAWLER_HEADLESS  设为 1 则无头模式
  CRAWLER_DEBUG_LOG_DIR  日志目录（定时任务日志、debug_export_page_*.html 等），默认 football-betting-log
  CRAWLER_LOG_RETENTION_DAYS  日志保留天数，超过此天数的日志文件将被删除，默认 7
"""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 工作目录：其下统一管理 data、report、log 等子目录，便于迁移或换机器时只改一处
WORK_SPACE = os.environ.get(
    "WORK_SPACE",
    os.path.expanduser("~/Documents/cursor")
).rstrip(os.sep)

BASE_URL = os.environ.get(
    "CRAWLER_BASE_URL",
    "https://live.nowscore.com/2in1.aspx"
)
DOWNLOAD_DIR = os.environ.get(
    "CRAWLER_DOWNLOAD_DIR",
    os.path.join(WORK_SPACE, "football-betting-data")
)
# calc_car.py / plot_car.py 生成文件（CAR*.xlsx、*_曲线.png）的根目录，其下按 YYYYMMDD 建子目录
REPORT_DIR = os.environ.get(
    "CRAWLER_REPORT_DIR",
    os.path.join(WORK_SPACE, "football-betting-report")
)
# 跨天时间临界点（时）：当日该时及之后 → 当日文件夹；次日该时之前 → 前一日文件夹
CUTOFF_HOUR = int(os.environ.get("CRAWLER_CUTOFF_HOUR", "12"))
# 用于“当前时间”的时区（避免服务器 UTC 导致临界点错位）
TIMEZONE = os.environ.get("CRAWLER_TIMEZONE", "Asia/Tokyo")
HEADLESS = os.environ.get("CRAWLER_HEADLESS", "1") == "1"
# 日志目录：定时任务 stdout/stderr、调试导出的页面 HTML（debug_export_page_*.html）等
DEBUG_LOG_DIR = os.environ.get(
    "CRAWLER_DEBUG_LOG_DIR",
    os.path.join(WORK_SPACE, "football-betting-log")
)
# 日志保留天数：crawl/merge_data/calc_car/plot_car 执行前会删除超过此天数的日志文件
LOG_RETENTION_DAYS = int(os.environ.get("CRAWLER_LOG_RETENTION_DAYS", "7"))

# 足彩子菜单：目前只抓取「北单」
ZUCAI_MENU_OPTIONS = ["北单"]

# 表格列索引（与页面一致）：选、日期、时间、状态、主队、比分、客队、…
COL_DATE = 1
COL_TIME = 2
COL_HOME = 4
COL_AWAY = 6

# 等待时间（秒）
WAIT_ELEMENT = 20
WAIT_AFTER_CLICK = 0.5
WAIT_AFTER_HOVER = 0.4
WAIT_TABLE_REFRESH = 3
WAIT_ROW_COUNT = 20
WAIT_FIRST_ROW_CHANGED = 12
