# -*- coding: utf-8 -*-
"""
入口：创建 Chrome WebDriver，运行爬虫后退出。
"""
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from config import BASE_URL, DOWNLOAD_DIR, HEADLESS
from scraper import ZhiyunScraper


def create_driver():
    """创建 Chrome 驱动，使用 webdriver-manager 自动管理 chromedriver。"""
    options = webdriver.ChromeOptions()
    if HEADLESS:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

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
    driver = None
    try:
        driver = create_driver()
        scraper = ZhiyunScraper(driver, base_url=BASE_URL)
        scraper.run()
    finally:
        if driver:
            driver.quit()


if __name__ == "__main__":
    main()
