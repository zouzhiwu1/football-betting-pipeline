# 足球比分爬虫（Python 版）

与 Java 版 `football-betting` 功能一致：打开智云比分页，点击「足球」→「足彩」下的 竞足/北单/14场，等待表格刷新后打印主客队列表。

## 环境

- Python 3.10+
- Chrome 浏览器

## 安装

```bash
cd football-betting-python
pip install -r requirements.txt
```

## 运行

```bash
python main.py
```

## 配置

- **config.py** 中可改 `BASE_URL`、`DOWNLOAD_DIR`、`HEADLESS`。
- 或用环境变量（无需改代码）：
  - `CRAWLER_BASE_URL`：页面地址，默认 `https://live.nowscore.com/2in1.aspx`
  - `CRAWLER_DOWNLOAD_DIR`：下载目录（若后续加下载 Excel 功能会用到）
  - `CRAWLER_HEADLESS`：设为 `1` 无头模式（默认），`0` 有界面

示例（有界面、指定下载目录）：

```bash
CRAWLER_HEADLESS=0 CRAWLER_DOWNLOAD_DIR=/path/to/excels python main.py
```

## 与 Java 版对应关系

| Java | Python |
|------|--------|
| ZhiyunScraperService | scraper.ZhiyunScraper |
| WebDriverConfig | main.create_driver + config.py |
| application.yml | config.py / 环境变量 |

Java 版保留在原项目目录，本目录为独立 Python 实现，可单独拷贝到任意位置使用。
