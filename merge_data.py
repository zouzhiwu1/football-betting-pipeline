# -*- coding: utf-8 -*-
"""
批处理：将指定目录下的所有 .xls 数据文件按文件名排序后合并为一个一览 CSV。
用法: python merge_data.py <数据目录或相对子目录>
  - 相对路径（如 20260307）会相对于 config.DOWNLOAD_DIR（下载目录）解析
  - 绝对路径则直接使用
例如: python merge_data.py 20260307
     python merge_data.py /Users/zhiwuzou/Documents/足球彩票/北单/20260307
工程目录下必须有 template.xlsx，以其第 1 行和第 2 行作为 CSV 的表头（两行表头）。
"""
import csv
import os
import re
import sys
import traceback
import unicodedata

import pandas as pd

from config import DOWNLOAD_DIR


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


def parse_filename(basename: str):
    """解析文件名，返回 (主队, 客队, 时间点)。无法解析时返回 None。"""
    # macOS 可能返回 NFD 形式，统一规范为 NFC 再匹配
    name = unicodedata.normalize("NFC", basename.strip())
    m = FILENAME_PATTERN.match(name)
    if not m:
        return None
    home = m.group(1).strip()
    away = m.group(2).strip()
    yyyymmddhh = m.group(3)
    time_point = yyyymmddhh[-2:]  # HH
    return home, away, time_point


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
            tables = pd.read_html(html)
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
    if df is None:
        for encoding in ("gb18030", "gbk", "utf-8"):
            try:
                html = raw.decode(encoding)
                tables = pd.read_html(html, flavor="lxml")
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
    if df is None:
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
    except Exception as e:
        raise RuntimeError(f"无法读取 template.xlsx: {e}") from e
    if len(tmpl) < 2:
        raise ValueError("template.xlsx 至少需要 2 行作为表头")
    row1 = [str(tmpl.iloc[0, i]) if i < tmpl.shape[1] else "" for i in range(NUM_COLUMNS)]
    row2 = [str(tmpl.iloc[1, i]) if i < tmpl.shape[1] else "" for i in range(NUM_COLUMNS)]
    return row1, row2


def main():
    # 确认实际执行的脚本路径（若看不到“原因”等输出，请检查是否运行了其他目录下的脚本）
    _script_path = os.path.abspath(__file__)
    print(f"[merge_data] 正在执行: {_script_path}", flush=True)

    if len(sys.argv) < 2:
        print("用法: python merge_data.py <数据目录或相对子目录>")
        print("  相对路径（如 20260307）会基于下载目录 DOWNLOAD_DIR 解析")
        print("例如: python merge_data.py 20260307")
        sys.exit(1)

    raw_arg = sys.argv[1].strip().rstrip(os.sep)
    if os.path.isabs(raw_arg):
        data_dir = os.path.abspath(raw_arg)
    else:
        data_dir = os.path.abspath(os.path.join(DOWNLOAD_DIR, raw_arg))
    if not os.path.isdir(data_dir):
        print(f"错误: 目录不存在: {data_dir}")
        sys.exit(1)

    # 日志写到数据目录，便于在 xls 同目录下查看
    error_log_path = os.path.join(data_dir, "merge_data_first_error.log")
    try:
        with open(error_log_path, "w", encoding="utf-8") as f:
            f.write(f"脚本: {_script_path}\n")
    except Exception:
        error_log_path = None

    # 工程目录：本脚本所在目录
    project_dir = os.path.dirname(os.path.abspath(__file__))

    xls_files = sorted(
        [f for f in os.listdir(data_dir) if f.lower().endswith(".xls")],
        key=lambda x: x,
    )
    if not xls_files:
        print(f"该目录下没有 .xls 文件: {data_dir}")
        sys.exit(0)

    folder_name = os.path.basename(data_dir)
    output_path = os.path.join(data_dir, f"{folder_name}.csv")

    try:
        header_row1, header_row2 = get_csv_headers(project_dir)
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        print(f"错误: {e}")
        sys.exit(1)

    rows = []
    first_fail_done = False
    for fname in xls_files:
        parsed = parse_filename(fname)
        if not parsed:
            print(f"跳过（文件名无法解析）: {fname}")
            continue
        home, away, time_point = parsed
        path = os.path.join(data_dir, fname)
        data_df, err_msg, tb = read_xls_data(path)
        if data_df is None:
            err = err_msg or "未知错误"
            print(f"跳过（读取失败）: {fname}", flush=True)
            print(f"  [原因] {err}", flush=True)
            if tb:
                print("  [异常日志]", flush=True)
                for line in tb.rstrip().split("\n"):
                    print(f"    {line}", flush=True)
            # 第一个失败时写入数据目录下的日志文件（不依赖终端输出）
            if not first_fail_done:
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
                print(block, flush=True)
                if error_log_path:
                    try:
                        with open(error_log_path, "a", encoding="utf-8") as f:
                            f.write(block)
                        print(f"  错误已追加到: {error_log_path}\n", flush=True)
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
    print(f"已合并 {len(xls_files)} 个文件，共 {len(rows)} 行 -> {output_path}")


if __name__ == "__main__":
    main()
