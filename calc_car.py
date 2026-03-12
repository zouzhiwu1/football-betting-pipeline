# -*- coding: utf-8 -*-
"""
批处理2（与批处理1 merge_data.py 分开）：按《算法概要》2.2 节，
在一览文件基础上按「主队、客队、时间点」分组，对 D～L 列计算综合评估值：
D～I 列用 (MAX-MIN)/AVERAGE，J、K、L 列用 VARP(列)*100。输出 CAR{YYYYMMDD}.xlsx。
详细日志写入 logs/calc_car{YYYYMMDDHH}.log。
依赖：需先对同一目录执行批处理1（merge_data.py）生成一览 CSV。

用法（与 merge_data.py 参数形式保持一致，仅接收两个时间点参数）:
  python calc_car.py <起始时间YYYYMMDDHH> <终止时间YYYYMMDDHH>

说明：
- 实际计算的逻辑日期与 merge_data.py 一致：使用起始时间所在日期 YYYYMMDD。
"""
import datetime
import logging
import os
import sys

import pandas as pd

from config import DOWNLOAD_DIR, REPORT_DIR, DEBUG_LOG_DIR, LOG_RETENTION_DAYS
from log_cleanup import delete_old_logs

# 与 merge_data 一致：一览表 12 列，A/B/C=主队/客队/时间点，D～L=数据列（索引 3～11）
NUM_COLUMNS = 12
COL_KEYS = [0, 1, 2]  # A,B,C: 主队, 客队, 时间点
COL_VALUE_START = 3   # D 列
COL_VALUE_END = 11    # L 列（含）
# D～I 列（索引 3～8）用 (MAX-MIN)/AVERAGE；J、K、L 列（索引 9～11）用 VARP*100
COL_RANGE_MAX_MIN_AVG = (3, 8)   # D～I
COL_RANGE_VARP = (9, 11)         # J～L


def _setup_logging():
    """配置详细日志到独立文件：calc_car_{YYYYMMDDHH}.log。"""
    os.makedirs(DEBUG_LOG_DIR, exist_ok=True)
    time_suffix = datetime.datetime.now().strftime("%Y%m%d%H")
    log_path = os.path.join(DEBUG_LOG_DIR, f"calc_car_{time_suffix}.log")
    logger = logging.getLogger("calc_car")
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


def _to_numeric(series: pd.Series) -> pd.Series:
    """将一列转为数值，无效的变为 NaN。"""
    return pd.to_numeric(series, errors="coerce")


def compute_max_min_avg(series: pd.Series) -> float:
    """
    按 2.2 节：综合评估值 = (MAX - MIN) / AVERAGE。用于 D～I 列。
    若 AVERAGE 为 0 或全为空，返回 0。
    """
    s = _to_numeric(series).dropna()
    if s.empty or s.mean() == 0:
        return 0.0
    return float((s.max() - s.min()) / s.mean())


def compute_varp_100(series: pd.Series) -> float:
    """
    按 2.2 节：J、K、L 列用 VARP(列)*100。
    VARP 为总体方差（ddof=0），空或单值返回 0。
    """
    s = _to_numeric(series).dropna()
    if s.empty or len(s) < 2:
        return 0.0
    return float(s.var(ddof=0) * 100)


def run(data_dir: str, project_dir: str) -> None:
    """
    从 data_dir 下读取 Master{folder_name}.csv，按 (主队, 客队, 时间点) 分组计算 D～L，
    以 template.xlsx 为模板生成 CAR{YYYYMMDD}.xlsx，写入 REPORT_DIR/{YYYYMMDD}/。
    """
    folder_name = os.path.basename(data_dir.rstrip(os.sep))
    # 一览表在数据目录（crawl/merge 输出）
    csv_path = os.path.join(data_dir, f"Master{folder_name}.csv")
    if not os.path.isfile(csv_path):
        raise FileNotFoundError(f"一览表不存在，请先执行批处理1 merge_data.py: {csv_path}")

    template_path = os.path.join(project_dir, "template.xlsx")
    if not os.path.isfile(template_path):
        raise FileNotFoundError(f"工程目录下未找到 template.xlsx: {project_dir}")

    # 读一览 CSV：merge_data 写了两行表头，数据从第 3 行开始；统一按字符串读入避免混合类型告警
    df = pd.read_csv(csv_path, encoding="utf-8-sig", header=None, dtype=str)
    if len(df) <= 2:
        raise ValueError(f"一览表无数据行: {csv_path}")
    df = df.iloc[2:].reset_index(drop=True)  # 去掉两行表头，只保留数据
    df.columns = [f"C{i}" for i in range(df.shape[1])]  # 临时列名
    if df.shape[1] < NUM_COLUMNS:
        raise ValueError(f"一览表列数不足 {NUM_COLUMNS} 列: {csv_path}")

    # 分组键：主队、客队、时间点（前三列）
    group_cols = [df.columns[i] for i in COL_KEYS]
    # 计算列：D～L（索引 3～11）
    value_cols = [df.columns[i] for i in range(COL_VALUE_START, COL_VALUE_END + 1)]
    if not value_cols:
        raise ValueError("一览表需包含 D～L 数据列")

    # 按 (主队, 客队, 时间点) 分组：D～I 用 (MAX-MIN)/AVERAGE，J～L 用 VARP*100
    results = []
    for key, grp in df.groupby(group_cols, dropna=False):
        if isinstance(key, (list, tuple)):
            row_key = list(key)
        else:
            row_key = [key]
        if len(row_key) < 3:
            row_key.extend([""] * (3 - len(row_key)))
        values = []
        for i, c in enumerate(value_cols):
            col_idx = COL_VALUE_START + i
            if COL_RANGE_MAX_MIN_AVG[0] <= col_idx <= COL_RANGE_MAX_MIN_AVG[1]:
                values.append(compute_max_min_avg(grp[c]))
            elif COL_RANGE_VARP[0] <= col_idx <= COL_RANGE_VARP[1]:
                values.append(compute_varp_100(grp[c]))
            else:  # pragma: no cover - 当前列范围下不可达
                values.append(compute_max_min_avg(grp[c]))
        results.append(row_key + values)
    if not results:
        raise ValueError("没有可分组的数据行")

    # 以 template 为模板创建 CAR{YYYYMMDD}.xlsx，写入 REPORT_DIR/{YYYYMMDD}/
    report_dir = os.path.join(REPORT_DIR, folder_name)
    os.makedirs(report_dir, exist_ok=True)
    tmpl = pd.read_excel(template_path, header=None)
    col_names = [str(tmpl.iloc[0, i]) if i < tmpl.shape[1] else "" for i in range(NUM_COLUMNS)]
    out_path = os.path.join(report_dir, f"CAR{folder_name}.xlsx")
    data_df = pd.DataFrame(results, columns=col_names)
    header_df = tmpl.iloc[:2, :NUM_COLUMNS].copy()
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        header_df.to_excel(writer, sheet_name="Sheet1", index=False, header=False)
        data_df.to_excel(writer, sheet_name="Sheet1", index=False, header=False, startrow=len(header_df))
    logging.getLogger("calc_car").info("已按 2.2 节计算，共 %d 组 -> %s", len(results), out_path)


def _resolve_data_dir(raw_arg: str) -> str:
    """将参数解析为绝对数据目录（支持相对路径）。"""
    raw_arg = raw_arg.strip().rstrip(os.sep)
    if os.path.isabs(raw_arg):
        return os.path.abspath(raw_arg)
    return os.path.abspath(os.path.join(DOWNLOAD_DIR, raw_arg))


def main():
    log = _setup_logging()
    removed = delete_old_logs(DEBUG_LOG_DIR, days=LOG_RETENTION_DAYS)
    if removed:
        log.info("已删除 %d 个超过 %d 天的日志文件: %s", len(removed), LOG_RETENTION_DAYS, removed)

    args = sys.argv[1:]
    if len(args) != 2 or not all(len(a) == 10 and a.isdigit() for a in args):
        log.error(
            "用法: python calc_car.py <起始时间YYYYMMDDHH> <终止时间YYYYMMDDHH>，例如: python calc_car.py 2026031012 2026031111"
        )
        sys.exit(1)

    start_arg, end_arg = args
    logical_date = start_arg[:8]
    log.info(
        "收到时间区间参数 [%s, %s]，将按逻辑日期 %s 计算 CAR。",
        start_arg,
        end_arg,
        logical_date,
    )

    project_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = _resolve_data_dir(logical_date)
    if not os.path.isdir(data_dir):
        log.error("目录不存在: %s", data_dir)
        sys.exit(1)

    try:
        log.info("处理目录: %s", data_dir)
        run(data_dir, project_dir)
    except (FileNotFoundError, ValueError) as e:  # pragma: no cover
        log.error("[%s] %s", data_dir, e)
        sys.exit(1)


if __name__ == "__main__":
    main()
