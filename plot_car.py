# -*- coding: utf-8 -*-
"""
批处理3：根据综合评估表（CAR{YYYYMMDD}.xlsx）生成欧赔指数曲线图和凯利指数曲线图。
参见 design.md 第 3.3 节。
详细日志写入 logs/plot_car{YYYYMMDDHH}.log。

曲线节点数量由综合评估表中该场比赛的时间点数量决定，不固定。

- 欧赔指数曲线图：主、平、客三条曲线。第 1 个节点为初指（D/E/F 列），
  其余节点为各时间点即时盘（G/H/I 列），节点数 = 1 + 时间点个数。X 轴为「初指」+ 第 C 列各时间点。
- 凯利指数曲线图：主、平、客三条曲线。X 轴为时间（第 C 列），Y 轴为 J/K/L 列，节点数 = 时间点个数。

用法: python plot_car.py [数据目录或相对子目录] ...
  参数与 merge_data.py 一致：不传参数时默认为当天日期 YYYYMMDD（如 20260308）。
  相对路径相对于 config.DOWNLOAD_DIR 解析，绝对路径则直接使用。可传多个目录。
  输出图片保存在对应数据目录下，文件名：{主队}_VS_{客队}_曲线.png
"""
import datetime
import logging
import os
import re
import sys

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

from config import DOWNLOAD_DIR, REPORT_DIR, DEBUG_LOG_DIR, LOG_RETENTION_DAYS
from log_cleanup import delete_old_logs

# 综合评估表列：A=主队(0), B=客队(1), C=时间点(2), D～L=数据(3～11)
# 欧赔：初指 D/E/F(3,4,5)，即时 G/H/I(6,7,8)；凯利 J/K/L(9,10,11)
COL_HOME, COL_AWAY, COL_TIME = 0, 1, 2
COL_INIT_MAIN, COL_INIT_DRAW, COL_INIT_AWAY = 3, 4, 5   # 初指 主/平/客
COL_LIVE_MAIN, COL_LIVE_DRAW, COL_LIVE_AWAY = 6, 7, 8   # 即时 主/平/客
COL_KELLY_MAIN, COL_KELLY_DRAW, COL_KELLY_AWAY = 9, 10, 11
CAR_HEADER_ROWS = 2
NUM_COLUMNS = 12


def _setup_logging():
    """配置详细日志到独立文件：plot_car{YYYYMMDDHH}.log。"""
    os.makedirs(DEBUG_LOG_DIR, exist_ok=True)
    time_suffix = datetime.datetime.now().strftime("%Y%m%d%H")
    log_path = os.path.join(DEBUG_LOG_DIR, f"plot_car.py{time_suffix}.log")
    logger = logging.getLogger("plot_car")
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


def _safe_filename(name: str) -> str:
    """去掉或替换文件名非法字符。"""
    s = re.sub(r'[<>:"/\\|?*]', "_", name)
    return s.strip() or "match"


def _setup_chinese_font():
    """设置 matplotlib 支持中文标签，避免中文显示为方框。"""
    # 从已安装字体中选一个能显示中文的（macOS 常见：PingFang SC、Heiti SC）
    preferred = ["PingFang SC", "Heiti SC", "STHeiti", "Songti SC", "Hiragino Sans GB",
                 "SimHei", "Microsoft YaHei", "WenQuanYi Micro Hei"]
    all_names = {f.name for f in fm.fontManager.ttflist}
    chosen = None
    for name in preferred:
        if name in all_names:
            chosen = name
            break
    if not chosen:
        # 按关键字模糊匹配（字体名可能带空格或后缀）
        for f in fm.fontManager.ttflist:
            if "PingFang" in f.name or "Heiti SC" in f.name or "STHeiti" in f.name:
                chosen = f.name
                break
    plt.rcParams["font.sans-serif"] = [chosen] if chosen else preferred
    plt.rcParams["axes.unicode_minus"] = False


def _to_float(series: pd.Series):
    """转为浮点，无效为 NaN。"""
    return pd.to_numeric(series, errors="coerce")


def plot_match_curves(data_dir: str, project_dir: str) -> int:
    """
    读取 REPORT_DIR/{YYYYMMDD}/ 下的 CAR{YYYYMMDD}.xlsx，按（主队、客队）分组，
    为每场比赛生成一张图，包含欧赔指数曲线图与凯利指数曲线图两个子图；
    图片写入 REPORT_DIR/{YYYYMMDD}/。
    返回成功生成的图片数量。
    """
    folder_name = os.path.basename(data_dir.rstrip(os.sep))
    report_dir = os.path.join(REPORT_DIR, folder_name)
    car_path = os.path.join(report_dir, f"CAR{folder_name}.xlsx")
    if not os.path.isfile(car_path):
        raise FileNotFoundError(f"综合评估表不存在，请先执行 calc_car.py: {car_path}")

    log = logging.getLogger("plot_car")
    df = pd.read_excel(car_path, header=None, engine="openpyxl")
    if len(df) <= CAR_HEADER_ROWS:
        log.info("  [%s] 综合评估表无数据行，跳过", folder_name)
        return 0
    data = df.iloc[CAR_HEADER_ROWS:].copy()
    if data.shape[1] < NUM_COLUMNS:
        raise ValueError(f"综合评估表列数不足 {NUM_COLUMNS} 列: {car_path}")

    data.columns = [f"C{i}" for i in range(data.shape[1])]
    for j in range(COL_INIT_MAIN, NUM_COLUMNS):
        data[data.columns[j]] = _to_float(data[data.columns[j]])

    group_cols = [data.columns[COL_HOME], data.columns[COL_AWAY]]
    count = 0
    for (home, away), grp in data.groupby(group_cols, dropna=False):
        grp = grp.sort_values(by=data.columns[COL_TIME]).reset_index(drop=True)
        if len(grp) == 0:
            continue
        home_str = str(home).strip()
        away_str = str(away).strip()
        title = f"{home_str} VS {away_str}"

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
        fig.suptitle(title, fontsize=12)

        # ---------- 欧赔指数曲线图 ----------
        # 第 1 节点：初指 D/E/F；第 2～N+1 节点：即时 G/H/I（N = 该场比赛时间点数量，由表决定）
        init_main = grp.iloc[0][data.columns[COL_INIT_MAIN]]
        init_draw = grp.iloc[0][data.columns[COL_INIT_DRAW]]
        init_away = grp.iloc[0][data.columns[COL_INIT_AWAY]]
        times = grp[data.columns[COL_TIME]].astype(str).tolist()
        x_labels = ["初指"] + times
        x_pos = list(range(len(x_labels)))

        y_main = [init_main] + grp[data.columns[COL_LIVE_MAIN]].tolist()
        y_draw = [init_draw] + grp[data.columns[COL_LIVE_DRAW]].tolist()
        y_away = [init_away] + grp[data.columns[COL_LIVE_AWAY]].tolist()

        ax1.plot(x_pos, y_main, "o-", label="主", color="C0")
        ax1.plot(x_pos, y_draw, "s-", label="平", color="C1")
        ax1.plot(x_pos, y_away, "^-", label="客", color="C2")
        ax1.set_xticks(x_pos)
        ax1.set_xticklabels(x_labels, rotation=45, ha="right")
        ax1.set_ylabel("评估值")
        ax1.set_title("欧赔指数曲线图")
        ax1.legend(loc="best")
        ax1.grid(True, alpha=0.3)

        # ---------- 凯利指数曲线图 ----------
        x_kelly = list(range(len(times)))
        ax2.plot(x_kelly, grp[data.columns[COL_KELLY_MAIN]], "o-", label="主", color="C0")
        ax2.plot(x_kelly, grp[data.columns[COL_KELLY_DRAW]], "s-", label="平", color="C1")
        ax2.plot(x_kelly, grp[data.columns[COL_KELLY_AWAY]], "^-", label="客", color="C2")
        ax2.set_xticks(x_kelly)
        ax2.set_xticklabels(times, rotation=45, ha="right")
        ax2.set_xlabel("时间点")
        ax2.set_ylabel("凯利指数")
        ax2.set_title("凯利指数曲线图")
        ax2.legend(loc="best")
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()
        os.makedirs(report_dir, exist_ok=True)
        safe_name = f"{_safe_filename(home_str)}_VS_{_safe_filename(away_str)}_曲线.png"
        out_path = os.path.join(report_dir, safe_name)
        plt.savefig(out_path, dpi=120, bbox_inches="tight")
        plt.close()
        log.info("  已生成: %s", out_path)
        count += 1

    return count


def _resolve_data_dir(raw_arg: str) -> str:
    """将参数解析为绝对数据目录。"""
    raw_arg = raw_arg.strip().rstrip(os.sep)
    if os.path.isabs(raw_arg):
        return os.path.abspath(raw_arg)
    return os.path.abspath(os.path.join(DOWNLOAD_DIR, raw_arg))


def main():
    log = _setup_logging()
    removed = delete_old_logs(DEBUG_LOG_DIR, days=LOG_RETENTION_DAYS)
    if removed:
        log.info("已删除 %d 个超过 %d 天的日志文件: %s", len(removed), LOG_RETENTION_DAYS, removed)
    _setup_chinese_font()
    if len(sys.argv) < 2:
        dirs = [datetime.date.today().strftime("%Y%m%d")]
    else:
        dirs = [d for d in sys.argv[1:] if d.strip()]

    project_dir = os.path.dirname(os.path.abspath(__file__))
    if not dirs:
        log.error("请至少指定一个数据目录")
        sys.exit(1)

    log.info("待处理目录: %s", dirs)
    total = 0
    failed = 0
    for raw_arg in dirs:
        data_dir = _resolve_data_dir(raw_arg)
        if not os.path.isdir(data_dir):
            log.error("目录不存在: %s", data_dir)
            failed += 1
            continue
        try:
            log.info("处理目录: %s", data_dir)
            n = plot_match_curves(data_dir, project_dir)
            total += n
        except FileNotFoundError as e:
            log.error("[%s] %s", data_dir, e)
            failed += 1
        except ValueError as e:
            log.error("[%s] %s", data_dir, e)
            failed += 1
    if total:
        log.info("共生成 %d 张曲线图。", total)
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
