# -*- coding: utf-8 -*-
"""
智云比分网 竞足/北单/14场 比赛列表爬虫。
逻辑与 Java 版 ZhiyunScraperService 一致。
"""
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchWindowException,
    ElementNotInteractableException,
    ElementClickInterceptedException,
)

from config import (
    BASE_URL,
    ZUCAI_MENU_OPTIONS,
    COL_HOME,
    COL_AWAY,
    WAIT_ELEMENT,
    WAIT_AFTER_CLICK,
    WAIT_AFTER_HOVER,
    WAIT_TABLE_REFRESH,
    WAIT_ROW_COUNT,
    WAIT_FIRST_ROW_CHANGED,
)


class ZhiyunScraper:
    def __init__(self, driver, base_url=BASE_URL):
        self.driver = driver
        self.base_url = base_url

    def run(self):
        """主流程：打开页面 -> 足球 -> 即时比分 -> 足彩 -> 北单，获取列表并下载 Excel（跳过隐藏场次）。"""
        self.driver.get(self.base_url)
        wait = WebDriverWait(self.driver, WAIT_ELEMENT)

        # 1) 点击主菜单「足球」
        football_menu = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "足球")))
        self._scroll_into_view_and_click(football_menu)
        time.sleep(WAIT_AFTER_CLICK)

        # 2) 点击「即时比分」
        live_tab = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "即时比分")))
        self._scroll_into_view_and_click(live_tab)
        time.sleep(WAIT_AFTER_CLICK)

        # 3) 对 竞足、北单、14场 分别处理（当前配置里只保留了「北单」）
        for menu_option in ZUCAI_MENU_OPTIONS:
            print(f"========== 获取 [{menu_option}] 比赛列表 ==========")
            first_row_home_before = self._get_first_data_row_home_team()
            self._hover_zucai_then_click_option(wait, menu_option)
            self._ensure_zucai_mode(menu_option)
            if not self._wait_until_match_row_count_at_most(150):
                print(f"[{menu_option}] 警告：表格行数仍很多，可能未切换到当前类型")
            self._wait_until_first_row_changed(first_row_home_before)

            if not self._ensure_valid_window():
                print(f"[{menu_option}] 无可用窗口，跳过", file=__import__("sys").stderr)
                continue

            self._select_primary_matches(wait)

            match_rows = self._collect_match_rows(wait, visible_only=True)
            hidden_in_dom = self._count_hidden_rows_in_table()
            print(f"[{menu_option}] 当前列表显示: {len(match_rows)} 场，表格中隐藏行: {hidden_in_dom} 场")
            print("--- 主队 vs 客队 ---")
            for i, row in enumerate(match_rows, 1):
                home = self._get_cell_text(row, COL_HOME)
                away = self._get_cell_text(row, COL_AWAY)
                print(f"{i}. {home} vs {away}")
                self._download_excel_for_row(wait, row, i, home, away)
            print()

    def _hover_zucai_then_click_option(self, wait, option_text):
        """鼠标移到「足彩」弹出菜单，再点击指定项（竞足/北单/14场）。"""
        zucai_btn = wait.until(EC.presence_of_element_located((By.LINK_TEXT, "足彩")))
        ActionChains(self.driver).move_to_element(zucai_btn).perform()
        time.sleep(WAIT_AFTER_HOVER)
        options = self.driver.find_elements(By.LINK_TEXT, option_text)
        to_click = None
        for i in range(len(options) - 1, -1, -1):
            if options[i].is_displayed():
                to_click = options[i]
                break
        if to_click is None:
            to_click = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, option_text)))
        self._scroll_into_view_and_click(to_click)

    def _ensure_zucai_mode(self, menu_option):
        """若页面有 SetLevel，直接调用以切换到竞足(3)/北单(2)/14场(1)。"""
        level = 3 if menu_option == "竞足" else (2 if menu_option == "北单" else 1)
        try:
            ok = self.driver.execute_script(
                f"return typeof window.SetLevel === 'function' && (window.SetLevel({level}), true);"
            )
            if ok:
                print(f"已通过 SetLevel({level}) 切换到 [{menu_option}]")
        except Exception:
            pass

    def _ensure_valid_window(self):
        """若当前窗口已关闭，则切换到仍存在的任一窗口。返回是否在有效窗口上。"""
        try:
            self.driver.current_window_handle
            return True
        except NoSuchWindowException:
            handles = self.driver.window_handles
            if handles:
                self.driver.switch_to.window(handles[0])
                return True
            return False

    def _get_first_data_row_home_team(self):
        """取当前 table_live 第一行数据的主队名（非表头），无则返回空串。"""
        try:
            rows = self.driver.find_elements(By.CSS_SELECTOR, "#table_live tr")
            for row in rows:
                tds = row.find_elements(By.CSS_SELECTOR, "td")
                if len(tds) < 7:
                    continue
                home = tds[COL_HOME].text.strip()
                away = tds[COL_AWAY].text.strip()
                if home == "主队" and away == "客队":
                    continue
                if not home:
                    home = self.driver.execute_script(
                        "return arguments[0].textContent", tds[COL_HOME]
                    ) or ""
                    home = home.strip()
                return home
        except Exception:
            pass
        return ""

    def _get_match_row_count(self):
        """当前 table_live 中数据行数（不含表头）。"""
        try:
            rows = self.driver.find_elements(By.CSS_SELECTOR, "#table_live tr")
            n = 0
            for row in rows:
                tds = row.find_elements(By.CSS_SELECTOR, "td")
                if len(tds) < 7:
                    continue
                h = tds[COL_HOME].text.strip()
                a = tds[COL_AWAY].text.strip()
                if h == "主队" and a == "客队":
                    continue
                n += 1
            return n
        except Exception:
            return 999

    def _wait_until_match_row_count_at_most(self, max_count):
        """等表格行数 <= maxCount，最多等 WAIT_ROW_COUNT 秒。"""
        time.sleep(WAIT_TABLE_REFRESH)
        wait = WebDriverWait(self.driver, WAIT_ROW_COUNT)
        try:
            wait.until(lambda d: self._get_match_row_count() <= max_count and self._get_match_row_count() > 0)
            return True
        except TimeoutException:
            return False

    def _wait_until_first_row_changed(self, first_row_home_before):
        """等表格第一行数据变化，最多等 WAIT_FIRST_ROW_CHANGED 秒。"""
        time.sleep(WAIT_TABLE_REFRESH)
        wait = WebDriverWait(self.driver, WAIT_FIRST_ROW_CHANGED)
        try:
            wait.until(lambda d: (
                (now := self._get_first_data_row_home_team()) and now != first_row_home_before
            ))
            return True
        except TimeoutException:
            return False

    def _select_primary_matches(self, wait):
        """打开「赛事选择」弹窗，点击「一级赛事」，再关闭弹窗。多策略查找 + 弹窗等待 + 重试。"""
        for attempt in range(2):
            try:
                # 1) 点「赛事选择」打开弹窗（链接或可点击文字）
                choice_selectors = [
                    By.LINK_TEXT, "赛事选择",
                    By.XPATH, "//*[contains(text(),'赛事选择') and (self::a or self::span or self::button)]",
                ]
                choice_btn = None
                for i in range(0, len(choice_selectors), 2):
                    by, value = choice_selectors[i], choice_selectors[i + 1]
                    try:
                        choice_btn = WebDriverWait(self.driver, 8).until(
                            EC.element_to_be_clickable((by, value))
                        )
                        if choice_btn and choice_btn.is_displayed():
                            break
                    except Exception:
                        continue
                if not choice_btn or not choice_btn.is_displayed():
                    raise ValueError("未找到可点击的「赛事选择」")
                self._scroll_into_view_and_click(choice_btn)
                time.sleep(0.8)

                # 2) 等弹窗出现后再找「一级赛事」（支持文本含空格、子节点）
                dialog_wait = WebDriverWait(self.driver, 10)
                primary_selectors = [
                    "//*[normalize-space(text())='一级赛事']",
                    "//*[contains(text(),'一级赛事')]",
                    "//button[contains(.,'一级赛事')]",
                    "//a[contains(.,'一级赛事')]",
                    "//span[contains(.,'一级赛事')]",
                ]
                primary_btn = None
                for xpath in primary_selectors:
                    try:
                        els = self.driver.find_elements(By.XPATH, xpath)
                        for el in els:
                            if el.is_displayed() and el.is_enabled():
                                primary_btn = el
                                break
                        if primary_btn:
                            break
                    except Exception:
                        continue
                if not primary_btn:
                    raise ValueError("弹窗内未找到「一级赛事」")
                self._scroll_into_view_and_click(primary_btn)
                time.sleep(0.5)

                # 3) 点「关闭」：优先找弹窗内的（含「赛事选择」的容器内的关闭）
                close_selectors = [
                    "//div[contains(@class,'modal') or contains(@class,'dialog') or contains(@id,'dialog')]//*[normalize-space(text())='关闭']",
                    "//div[.//*[contains(text(),'一级赛事')]]//*[normalize-space(text())='关闭']",
                    "//*[normalize-space(text())='关闭']",
                ]
                close_btn = None
                for xpath in close_selectors:
                    try:
                        els = self.driver.find_elements(By.XPATH, xpath)
                        for el in els:
                            if el.is_displayed() and el.is_enabled():
                                close_btn = el
                                break
                        if close_btn:
                            break
                    except Exception:
                        continue
                if not close_btn:
                    raise ValueError("未找到「关闭」按钮")
                self._scroll_into_view_and_click(close_btn)
                time.sleep(WAIT_TABLE_REFRESH)
                print("已选「一级赛事」并关闭赛事选择")
                return
            except Exception as e:
                if attempt == 0:
                    time.sleep(1.0)
                    continue
                print(f"赛事选择/一级赛事 未应用（{e}），继续用当前列表", file=__import__("sys").stderr)
                return

    def _count_hidden_rows_in_table(self):
        """表格 #table_live 中带 index 且 display:none 的行数（与页面「隐藏 XX 场」对应，仅统计当前表内）。"""
        try:
            n = self.driver.execute_script("""
                var rows = document.querySelectorAll('#table_live tr[index]');
                var count = 0;
                for (var i = 0; i < rows.length; i++) {
                    if (rows[i].style.display === 'none') count++;
                }
                return count;
            """)
            return n if n is not None else 0
        except Exception:
            return 0

    def _collect_match_rows(self, wait, visible_only=True):
        """等待 #table_live 出现并收集数据行（非表头）。visible_only=True 时只收集当前页显示的行（style.display!='none'），与浏览器列表一致。"""
        for attempt in range(2):
            try:
                if attempt > 0 and self._ensure_valid_window():
                    wait = WebDriverWait(self.driver, WAIT_ELEMENT)
                wait.until(EC.presence_of_element_located((By.ID, "table_live")))
                table = self.driver.find_element(By.ID, "table_live")
                rows = table.find_elements(By.CSS_SELECTOR, "tr")
                match_rows = []
                for row in rows:
                    tds = row.find_elements(By.CSS_SELECTOR, "td")
                    if len(tds) < 7:
                        continue
                    home_col = tds[COL_HOME].text.strip()
                    away_col = tds[COL_AWAY].text.strip()
                    if home_col == "主队" and away_col == "客队":
                        continue
                    if visible_only:
                        try:
                            display = row.value_of_css_property("display")
                            if display == "none":
                                continue
                        except Exception:
                            pass
                    match_rows.append(row)
                return match_rows
            except (NoSuchWindowException, TimeoutException):
                if attempt == 0 and self._ensure_valid_window():
                    continue
                raise
        return []

    def _download_excel_for_row(self, wait, row, index, home, away):
        """点击当前行的「欧」链接（列表页为「析亚欧」），弹出详情页后点击「导出Excel」下载，再关闭弹窗。"""
        # 兼容「欧」「析亚欧」等，含欧字的链接或可点击元素
        europe_links = row.find_elements(By.XPATH, ".//a[contains(.,'欧')]")
        if not europe_links:
            europe_links = row.find_elements(By.XPATH, ".//*[contains(text(),'析亚欧') or contains(text(),'欧')]")
        if not europe_links:
            row_preview = self._preview_row(row)
            print(f"第 {index} 场比赛未找到「欧」链接，跳过。该行前几列: {row_preview}")
            return

        try:
            original_window = self.driver.current_window_handle
        except NoSuchWindowException:
            if not self._ensure_valid_window():
                print(f"第 {index} 场 {home} vs {away}：无有效窗口，无法下载")
                return
            original_window = self.driver.current_window_handle

        existing_windows = set(self.driver.window_handles)

        link = europe_links[0]
        self._scroll_into_view_and_click(link)

        def _find_new_window(d):
            handles = set(d.window_handles)
            handles.difference_update(existing_windows)
            return handles.pop() if len(handles) == 1 else None

        try:
            new_handle = WebDriverWait(self.driver, WAIT_ELEMENT).until(_find_new_window)
        except TimeoutException:
            print(f"第 {index} 场 {home} vs {away}：未发现新窗口，跳过")
            return

        if not new_handle:
            print(f"第 {index} 场 {home} vs {away}：新窗口句柄为空，跳过")
            return

        try:
            self.driver.switch_to.window(new_handle)
            time.sleep(0.8)
            wait_new = WebDriverWait(self.driver, WAIT_ELEMENT)
            # 导出Excel 可能是 <a> 或 <button>，多策略查找
            export_xpaths = [
                "//a[contains(.,'导出') and contains(.,'Excel')]",
                "//button[contains(.,'导出') and contains(.,'Excel')]",
                "//*[contains(text(),'导出') and contains(text(),'Excel')]",
            ]
            export_btn = None
            for xpath in export_xpaths:
                try:
                    els = self.driver.find_elements(By.XPATH, xpath)
                    for el in els:
                        if el.is_displayed() and el.is_enabled():
                            export_btn = el
                            break
                    if export_btn:
                        break
                except Exception:
                    continue
            if not export_btn:
                raise ValueError("未找到「导出Excel」按钮")
            print(f"开始下载第 {index} 场 Excel: {home} vs {away}")
            self._scroll_into_view_and_click(export_btn)
            time.sleep(2.0)
        except Exception as e:
            print(f"第 {index} 场 {home} vs {away}：下载 Excel 出错：{e}")
        finally:
            try:
                self.driver.close()
            except Exception:
                pass
            try:
                self.driver.switch_to.window(original_window)
            except Exception:
                pass

    def _get_cell_text(self, row, col_index):
        """取单元格文本；若 getText 为空则用 JS textContent。"""
        tds = row.find_elements(By.CSS_SELECTOR, "td")
        if col_index < 0 or col_index >= len(tds):
            return ""
        cell = tds[col_index]
        text = cell.text.strip()
        if not text:
            text = self.driver.execute_script("return arguments[0].textContent", cell) or ""
            text = text.strip()
        return text

    def _preview_row(self, row):
        """打印该行前几列文本，用于排查“无欧链接”的行是表头还是异常数据。"""
        tds = row.find_elements(By.CSS_SELECTOR, "td")
        texts = []
        for cell in tds[:6]:
            texts.append(cell.text.strip())
        return " | ".join(texts)

    def _scroll_into_view_and_click(self, element):
        """先滚动到元素再点击；若被遮挡或不可交互则用 JS 点击。"""
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block:'center'});", element
        )
        time.sleep(0.3)
        try:
            element.click()
        except (ElementNotInteractableException, ElementClickInterceptedException):
            self.driver.execute_script("arguments[0].click();", element)
