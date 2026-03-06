"""
爬虫配置。可通过环境变量覆盖：
  CRAWLER_BASE_URL  页面地址
  CRAWLER_DOWNLOAD_DIR  下载目录
  CRAWLER_HEADLESS  设为 1 则无头模式
"""
import os

BASE_URL = os.environ.get(
    "CRAWLER_BASE_URL",
    "https://live.nowscore.com/2in1.aspx"
)
DOWNLOAD_DIR = os.environ.get(
    "CRAWLER_DOWNLOAD_DIR",
    "/Users/zhiwuzou/Documents/足球彩票/北单"
)
HEADLESS = os.environ.get("CRAWLER_HEADLESS", "1") == "1"

# 足彩子菜单：目前只抓取「北单」
ZUCAI_MENU_OPTIONS = ["北单"]

# 表格列索引（与页面一致）：选、日期、时间、状态、主队、比分、客队、…
COL_HOME = 4
COL_AWAY = 6

# 等待时间（秒）
WAIT_ELEMENT = 20
WAIT_AFTER_CLICK = 0.5
WAIT_AFTER_HOVER = 0.4
WAIT_TABLE_REFRESH = 3
WAIT_ROW_COUNT = 20
WAIT_FIRST_ROW_CHANGED = 12
