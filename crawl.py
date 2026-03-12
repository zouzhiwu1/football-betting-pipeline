# -*- coding: utf-8 -*-
"""
抓取数据：创建 Chrome WebDriver，运行爬虫后退出。
执行时以当前时间点作为文件名中的小时（如 09:08 -> 09）。
详细日志写入 logs/crawl{YYYYMMDDHH}.log。
"""
import logging
import os
import sys
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from config import BASE_URL, DOWNLOAD_DIR, HEADLESS, DEBUG_LOG_DIR, LOG_RETENTION_DAYS
from log_cleanup import delete_old_logs
from scraper import ZhiyunScraper


def _setup_logging():
    """配置详细日志到独立文件：crawl_{YYYYMMDDHH}.log。"""
    os.makedirs(DEBUG_LOG_DIR, exist_ok=True)
    time_suffix = datetime.now().strftime("%Y%m%d%H")
    log_path = os.path.join(DEBUG_LOG_DIR, f"crawl_{time_suffix}.log")
    logger = logging.getLogger("crawl")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    logger.info("日志文件: %s", log_path)
    return logger


def create_driver():
    """创建 Chrome 驱动，使用 webdriver-manager 自动管理 chromedriver。"""
    options = webdriver.ChromeOptions()
    if HEADLESS:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    # 静音浏览器，避免访问比分页时进球提示音干扰本机
    options.add_argument("--mute-audio")

    prefs = {
        "download.default_directory": DOWNLOAD_DIR,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
    }
    options.add_experimental_option("prefs", prefs)

    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)


def main():
    """
    抓取当前盘口数据。

    用法（与 merge_data.py 保持一致的参数形式）:
      python crawl.py <起始时间YYYYMMDDHH> <终止时间YYYYMMDDHH>

    说明：
    - 目前 crawl.py 实际仍按「执行当下的实时盘口」抓取，不依赖传入时间点，
      这里的起始/终止时间主要用于与 merge_data.py 等脚本保持一致的调用方式，
      便于 main.py 统一管理参数，避免混淆。
    """
    log = _setup_logging()
    removed = delete_old_logs(DEBUG_LOG_DIR, days=LOG_RETENTION_DAYS)
    if removed:
        log.info("已删除 %d 个超过 %d 天的日志文件: %s", len(removed), LOG_RETENTION_DAYS, removed)

    args = sys.argv[1:]
    if len(args) != 2 or not all(len(a) == 10 and a.isdigit() for a in args):
        log.error(
            "用法: python crawl.py <起始时间YYYYMMDDHH> <终止时间YYYYMMDDHH>，例如: python crawl.py 2026031012 2026031111"
        )
        sys.exit(1)
    start_arg, end_arg = args
    log.info("收到时间区间参数: [%s, %s]（当前版本仅用于日志标记，不影响抓取行为）", start_arg, end_arg)
    driver = None
    try:
        log.info("创建 Chrome 驱动...")
        driver = create_driver()
        log.info("驱动已创建，开始执行爬虫")
        scraper = ZhiyunScraper(driver, base_url=BASE_URL)
        scraper.run()
        log.info("爬虫执行完成")
    except Exception as e:
        log.exception("执行失败: %s", e)
        raise
    finally:
        if driver:
            driver.quit()
            log.debug("驱动已关闭")


if __name__ == "__main__":
    main()
