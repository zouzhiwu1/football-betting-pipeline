# -*- coding: utf-8 -*-
"""
批处理1（与批处理2 calc_car.py 分开）：将指定时间段内的 .xls 数据文件
按文件名排序后合并为一个一览表，输出文件名为 Master{YYYYMMDD}.csv。

新版本约定：
- crawl.py 下载文件时只按“自然日”建目录（YYYYMMDD），与临界点无关。
- merge_data.py 不再按“整天目录”处理，而是接收两个时间点参数：
    * 起始时间点（含），格式 YYYYMMDDHH
    * 终止时间点（含），格式 YYYYMMDDHH
  例如: merge_data.py 2026030812 2026030911
  在这两个时间点覆盖的日期目录中查找所有时间戳在区间内的 .xls 文件，
  并合并为一个一览表。
详细日志写入 logs/merge_data{YYYYMMDDHH}.log。

用法（仅接收两个时间点参数，与其它批处理脚本保持一致）:
  python merge_data.py <起始时间YYYYMMDDHH> <终止时间YYYYMMDDHH>

例如:
  python merge_data.py 2026030812 2026030911

工程目录下必须有 template.xlsx，以其第 1 行和第 2 行作为 CSV 的表头（两行表头）。
"""
import csv
import datetime
import io
import logging
import os
import re
import sys
import traceback
import unicodedata

import pandas as pd

from config import DOWNLOAD_DIR, DEBUG_LOG_DIR, LOG_RETENTION_DAYS
from log_cleanup import delete_old_logs


# 一览表列数（主队、客队、时间点 + 数据列 C/D/E/F/G/H/L/M/N）
NUM_COLUMNS = 12

# 数据文件从第 6 行开始为数据（0-based 为第 5 行）
DATA_START_ROW = 5

# 数据文件列到一览表列的映射：源表列 C,D,E,F,G,H,L,M,N -> 一览表 D,E,F,G,H,I,J,K,L（0-based）
# 即源列索引 2,3,4,5,6,7,11,12,13
SOURCE_COL_INDICES = [2, 3, 4, 5, 6, 7, 11, 12, 13]

# 文件名正则：{主队} VS {客队}{YYYYMMDDHH}.xls，末尾为 10 位数字（年月日时）
# 客队用贪婪 (.+) 以便队名含数字（如 U19、U20）时仍能正确截出末尾 10 位时间
FILENAME_PATTERN = re.compile(r"^(.+?)\s+VS\s+(.+)(\d{10})\.xls$", re.IGNORECASE)


def _setup_logging():
    """配置详细日志到独立文件：merge_data_{YYYYMMDDHH}.log。"""
    os.makedirs(DEBUG_LOG_DIR, exist_ok=True)
    time_suffix = datetime.datetime.now().strftime("%Y%m%d%H")
    log_path = os.path.join(DEBUG_LOG_DIR, f"merge_data_{time_suffix}.log")
    logger = logging.getLogger("merge_data")
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


def parse_filename(basename: str):
    """解析文件名，返回 (主队, 客队, 时间点)。时间点为 YYYYMMDDHH（10 位）。无法解析时返回 None。"""
    # macOS 可能返回 NFD 形式，统一规范为 NFC 再匹配
    name = unicodedata.normalize("NFC", basename.strip())
    m = FILENAME_PATTERN.match(name)
    if not m:
        return None
    home = m.group(1).strip()
    away = m.group(2).strip()
    yyyymmddhh = m.group(3)
    time_point = yyyymmddhh  # YYYYMMDDHH（10 位）
    return home, away, time_point


def _time_point_to_datetime(time_point: str):
    """将 YYYYMMDDHH 转为 datetime；解析失败返回 None。"""
    if not time_point or len(time_point) < 10 or not time_point.isdigit():
        return None
    try:
        y = int(time_point[0:4])
        m = int(time_point[4:6])
        d = int(time_point[6:8])
        h = int(time_point[8:10])
        return datetime.datetime(y, m, d, h, 0, 0)
    except ValueError:
        return None


def _parse_time_arg(arg: str, name: str, log: logging.Logger):
    """解析命令行时间参数 YYYYMMDDHH，解析失败则退出。"""
    if not arg or len(arg) != 10 or not arg.isdigit():
        log.error("参数 %s 格式错误，应为 10 位数字 YYYYMMDDHH: %s", name, arg)
        sys.exit(1)
    dt = _time_point_to_datetime(arg)
    if dt is None:
        log.error("参数 %s 无法解析为有效时间: %s", name, arg)
        sys.exit(1)
    return dt


def _collect_files_in_range(start_dt, end_dt, log: logging.Logger):
    """
    在 [start_dt, end_dt] 区间内收集需要合并的 .xls 文件。

    遍历 DOWNLOAD_DIR 下的所有子目录（通常为自然日期 YYYYMMDD），
    仅根据文件名中的时间点 YYYYMMDDHH 判断是否落在区间内，
    不再依赖目录名与逻辑日期/自然日期的对应关系。

    返回:
      files: 列表 [(dir_path, fname, home, away, time_point), ...]
    """
    files: list[tuple[str, str, str, str, str]] = []
    root = os.path.abspath(DOWNLOAD_DIR)
    if not os.path.isdir(root):
        log.info("下载根目录不存在: %s", root)
        return files

    for name in sorted(os.listdir(root)):
        dir_path = os.path.join(root, name)
        if not os.path.isdir(dir_path):
            continue
        for fname in sorted(os.listdir(dir_path)):
            if not fname.lower().endswith(".xls"):
                continue
            parsed = parse_filename(fname)
            if not parsed:
                log.info("跳过（文件名无法解析）: %s", os.path.join(dir_path, fname))
                continue
            home, away, time_point = parsed
            dt = _time_point_to_datetime(time_point)
            if dt is None:
                log.info("跳过（时间点无法解析）: %s", os.path.join(dir_path, fname))
                continue
            if start_dt <= dt <= end_dt:
                files.append((dir_path, fname, home, away, time_point))
    return files


def read_xls_data(path: str):
    """
    读取 .xls 文件（可能是 HTML 表格），从第 6 行起取数据，返回 C,D,E,F,G,H,L,M,N 列。
    北单等导出的 .xls 多为 HTML，先按 HTML 试多种编码，失败再按 Excel 读。
    成功返回 (DataFrame, None, None)，失败返回 (None, 错误描述, 完整 traceback 或 None)。
    """
    last_err = None
    last_tb = None
    df = None
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except Exception as e:
        return None, str(e), traceback.format_exc()

    # 1) 一律先按 HTML 试（网站导出的 .xls 绝大多数是 HTML，用 read_excel 会报错）
    for encoding in ("gb18030", "gbk", "utf-8", "gb2312", "latin1"):
        try:
            html = raw.decode(encoding)
            tables = pd.read_html(io.StringIO(html))
            for t in tables:
                if t is not None and len(t) > DATA_START_ROW:
                    df = t
                    break
            if df is not None:
                break
        except UnicodeDecodeError:
            continue
        except Exception as e:
            last_err = f"read_html({encoding}): {e}"
            last_tb = traceback.format_exc()
            continue

    # 2) HTML 没解析出表时，再试 read_html 用 lxml（有时解析更稳）
    if df is None:  # pragma: no cover - 备用解析路径，常规 HTML 已在上面命中
        for encoding in ("gb18030", "gbk", "utf-8"):
            try:
                html = raw.decode(encoding)
                tables = pd.read_html(io.StringIO(html), flavor="lxml")
                for t in tables:
                    if t is not None and len(t) > DATA_START_ROW:
                        df = t
                        break
                if df is not None:
                    break
            except Exception:
                continue

    # 3) 仅当明显是二进制 Excel（OLE 头）时才用 read_excel，否则不再调用避免报错
    if df is None and raw[:8] != b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return None, last_err or "无法按 HTML 解析，且文件不是 Excel 二进制格式", last_tb
    if df is None:  # pragma: no cover - 真实二进制 .xls 少见，多为 HTML
        try:
            df = pd.read_excel(path, header=None, engine="xlrd")
        except ImportError:
            return None, "读取二进制 .xls 需要安装 xlrd，请执行: pip install xlrd", traceback.format_exc()
        except Exception as e:
            return None, str(e), traceback.format_exc()

    if df is None or len(df) <= DATA_START_ROW:
        return None, (last_err or "表为空或行数不足"), last_tb

    data_df = df.iloc[DATA_START_ROW:].copy()
    cols = []
    for i in SOURCE_COL_INDICES:
        if i < data_df.shape[1]:
            cols.append(data_df.iloc[:, i].astype(str))
        else:
            cols.append(pd.Series([""] * len(data_df)))
    return pd.concat(cols, axis=1), None, None


def get_csv_headers(project_dir: str):
    """
    工程目录下必须有 template.xlsx，以其第 1 行和第 2 行作为 CSV 的表头。
    返回 (header_row1, header_row2)，均为长度为 NUM_COLUMNS 的列表。
    """
    template_path = os.path.join(project_dir, "template.xlsx")
    if not os.path.isfile(template_path):
        raise FileNotFoundError(f"工程目录下未找到 template.xlsx: {project_dir}")
    try:
        tmpl = pd.read_excel(template_path, header=None)
    except Exception as e:  # pragma: no cover - 文件损坏等罕见情况
        raise RuntimeError(f"无法读取 template.xlsx: {e}") from e
    if len(tmpl) < 2:
        raise ValueError("template.xlsx 至少需要 2 行作为表头")
    row1 = [str(tmpl.iloc[0, i]) if i < tmpl.shape[1] else "" for i in range(NUM_COLUMNS)]
    row2 = [str(tmpl.iloc[1, i]) if i < tmpl.shape[1] else "" for i in range(NUM_COLUMNS)]
    return row1, row2


def main():
    log = _setup_logging()
    removed = delete_old_logs(DEBUG_LOG_DIR, days=LOG_RETENTION_DAYS)
    if removed:
        log.info("已删除 %d 个超过 %d 天的日志文件: %s", len(removed), LOG_RETENTION_DAYS, removed)
    # 确认实际执行的脚本路径（若看不到“原因”等输出，请检查是否运行了其他目录下的脚本）
    _script_path = os.path.abspath(__file__)
    log.info("[merge_data] 正在执行: %s", _script_path)

    # 新版本：必须显式传入起始、终止时间点两个参数（YYYYMMDDHH、YYYYMMDDHH）
    if len(sys.argv) != 3:
        log.error(
            "用法: python merge_data.py <起始时间YYYYMMDDHH> <终止时间YYYYMMDDHH>，例如: python merge_data.py 2026030812 2026030911"
        )
        sys.exit(1)

    start_arg = sys.argv[1].strip()
    end_arg = sys.argv[2].strip()
    start_dt = _parse_time_arg(start_arg, "起始时间", log)
    end_dt = _parse_time_arg(end_arg, "终止时间", log)
    if start_dt > end_dt:
        log.error("起始时间晚于终止时间: %s > %s", start_arg, end_arg)
        sys.exit(1)

    files = _collect_files_in_range(start_dt, end_dt, log)
    if not files:
        log.warning("在区间 [%s, %s] 内没有匹配的 .xls 文件", start_arg, end_arg)
        sys.exit(0)

    # 输出目录和文件名：放在起始时间所在日期目录下，命名为 Master{YYYYMMDD}.csv
    logical_date = start_dt.strftime("%Y%m%d")
    output_dir = os.path.abspath(os.path.join(DOWNLOAD_DIR, logical_date))
    os.makedirs(output_dir, exist_ok=True)
    folder_label = logical_date
    error_log_path = os.path.join(output_dir, "merge_data_first_error.log")
    log.info(
        "处理区间 [%s, %s]，起始日期=%s，待处理 .xls 数量: %d",
        start_arg,
        end_arg,
        logical_date,
        len(files),
    )

    # 日志写到输出目录，便于在 xls 同目录下查看
    try:
        with open(error_log_path, "w", encoding="utf-8") as f:
            f.write(f"脚本: {_script_path}\n")
    except Exception:
        error_log_path = None

    # 工程目录：本脚本所在目录
    project_dir = os.path.dirname(os.path.abspath(__file__))

    # 一览表文件名：Master{YYYYMMDD}.csv（按起始时间所在日期命名）
    output_path = os.path.join(output_dir, f"Master{folder_label}.csv")

    try:
        header_row1, header_row2 = get_csv_headers(project_dir)
    except (FileNotFoundError, ValueError, RuntimeError) as e:  # pragma: no cover
        log.error("错误: %s", e)
        sys.exit(1)

    rows: list[list[str]] = []
    first_fail_done = False
    for dir_path, fname, home, away, time_point in files:
        path = os.path.join(dir_path, fname)
        data_df, err_msg, tb = read_xls_data(path)
        if data_df is None:  # pragma: no cover - 测试用 xls 均能解析
            err = err_msg or "未知错误"
            log.warning("跳过（读取失败）: %s", fname)
            log.info("  [原因] %s", err)
            if tb:
                log.debug("  [异常日志]\n%s", tb)
            # 第一个失败时写入数据目录下的日志文件（不依赖终端输出）
            if not first_fail_done:  # pragma: no cover - 测试用 xls 均能解析
                first_fail_done = True
                sep = "=" * 60
                block = (
                    f"\n{sep}\n【第一个读取失败的文件】\n"
                    f"  文件: {fname}\n  路径: {path}\n  原因: {err}\n"
                )
                if tb:
                    block += "  完整 traceback:\n"
                    block += "\n".join(f"    {line}" for line in tb.rstrip().split("\n"))
                block += f"\n{sep}\n\n"
                log.warning(block)
                if error_log_path:
                    try:
                        with open(error_log_path, "a", encoding="utf-8") as f:
                            f.write(block)
                        log.info("  错误已追加到: %s", error_log_path)
                    except Exception:
                        pass
            continue
        for _, r in data_df.iterrows():
            row = [home, away, time_point] + [str(r.iloc[i]) for i in range(len(SOURCE_COL_INDICES))]
            rows.append(row)

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(header_row1)
        w.writerow(header_row2)
        w.writerows(rows)
    log.info("已合并 %d 个文件，共 %d 行 -> %s", len(files), len(rows), output_path)


if __name__ == "__main__":
    main()
