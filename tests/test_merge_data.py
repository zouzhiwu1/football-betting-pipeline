import datetime
import os

import pandas as pd

import logging

from merge_data import (
    parse_filename,
    _time_point_to_datetime,
    _collect_files_in_range,
    read_xls_data,
    get_csv_headers,
    DATA_START_ROW,
)


def test_parse_filename_normal():
    home, away, tp = parse_filename("TeamA VS TeamB2026030812.xls")
    assert home == "TeamA"
    assert away == "TeamB"
    assert tp == "2026030812"


def test_parse_filename_invalid_returns_none():
    assert parse_filename("invalid_name.xls") is None


def test_time_point_to_datetime_ok():
    dt = _time_point_to_datetime("2026030812")
    assert isinstance(dt, datetime.datetime)
    assert dt.year == 2026 and dt.month == 3 and dt.day == 8 and dt.hour == 12


def test_time_point_to_datetime_invalid():
    assert _time_point_to_datetime("bad") is None


def test_time_point_to_datetime_value_error_returns_none():
    """无效日期（如 2 月 30 日）会触发 ValueError，应返回 None。"""
    assert _time_point_to_datetime("2026023012") is None


def test_time_point_to_datetime_short_or_non_digit():
    assert _time_point_to_datetime("") is None
    assert _time_point_to_datetime("123456789") is None


def test_get_csv_headers_reads_template(tmp_path, monkeypatch):
    # 在临时目录下创建 template.xlsx，并验证能够读取两行表头
    project_dir = tmp_path
    template_path = os.path.join(project_dir, "template.xlsx")
    # 两行表头 + 一些多余列
    df = pd.DataFrame(
        [
            [f"H1_{i}" for i in range(15)],
            [f"H2_{i}" for i in range(15)],
        ]
    )
    df.to_excel(template_path, header=False, index=False)

    header1, header2 = get_csv_headers(str(project_dir))
    # merge_data.NUM_COLUMNS == 12
    assert len(header1) == 12
    assert len(header2) == 12
    assert header1[0] == "H1_0"
    assert header2[0] == "H2_0"


def test_get_csv_headers_missing_template_raises():
    import pytest
    with pytest.raises(FileNotFoundError, match="template.xlsx"):
        get_csv_headers("/nonexistent_project_dir_xyz")


def test_get_csv_headers_template_only_one_row_raises(tmp_path):
    import pytest
    one_row = tmp_path / "template.xlsx"
    pd.DataFrame([["H1"] * 12]).to_excel(one_row, header=False, index=False)
    with pytest.raises(ValueError, match="至少需要 2 行"):
        get_csv_headers(str(tmp_path))


def test_collect_files_in_range_finds_xls_in_range(tmp_path, monkeypatch):
    """在指定时间区间内应收集到匹配的 .xls 文件。"""
    monkeypatch.setattr("merge_data.DOWNLOAD_DIR", str(tmp_path))
    date_dir = tmp_path / "20260308"
    date_dir.mkdir()
    (date_dir / "A VS B2026030812.xls").write_text("dummy")
    log = logging.getLogger("test")
    start_dt = datetime.datetime(2026, 3, 8, 12, 0, 0)
    end_dt = datetime.datetime(2026, 3, 8, 13, 0, 0)
    files = _collect_files_in_range(start_dt, end_dt, log)
    assert len(files) == 1
    assert files[0][2] == "A" and files[0][3] == "B" and files[0][4] == "2026030812"


def test_collect_files_in_range_skips_non_xls_and_unparseable(tmp_path, monkeypatch):
    """跳过非 .xls、文件名无法解析、时间点无效的文件。"""
    monkeypatch.setattr("merge_data.DOWNLOAD_DIR", str(tmp_path))
    date_dir = tmp_path / "20260308"
    date_dir.mkdir()
    (date_dir / "other.txt").write_text("x")
    (date_dir / "badname.xls").write_text("x")  # 无法解析为 主队 VS 客队YYYYMMDDHH
    (date_dir / "A VS B2026023012.xls").write_text("x")  # 无效日期 2月30日
    (date_dir / "A VS B2026030812.xls").write_text("x")  # 有效
    log = logging.getLogger("test")
    start_dt = datetime.datetime(2026, 3, 8, 12, 0, 0)
    end_dt = datetime.datetime(2026, 3, 8, 13, 0, 0)
    files = _collect_files_in_range(start_dt, end_dt, log)
    assert len(files) == 1
    assert files[0][4] == "2026030812"


def test_collect_files_in_range_skips_nonexistent_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("merge_data.DOWNLOAD_DIR", str(tmp_path))
    log = logging.getLogger("test")
    start_dt = datetime.datetime(2026, 3, 8, 12, 0, 0)
    end_dt = datetime.datetime(2026, 3, 8, 13, 0, 0)
    files = _collect_files_in_range(start_dt, end_dt, log)
    assert len(files) == 0


def test_read_xls_data_success_html(tmp_path):
    """read_xls_data 能解析最小 HTML 表格并返回数据列。"""
    # 至少 6 行（0-based 第 5 行起为数据），至少 14 列以覆盖 SOURCE_COL_INDICES
    rows = DATA_START_ROW + 2
    cols = 14
    trs = "".join(
        "<tr>" + "".join(f"<td>{i},{j}</td>" for j in range(cols)) + "</tr>"
        for i in range(rows)
    )
    table = "<table>" + trs + "</table>"
    path = tmp_path / "t.xls"
    path.write_text(table, encoding="utf-8")
    df, err, tb = read_xls_data(str(path))
    assert df is not None
    assert err is None
    assert tb is None
    assert len(df) >= 2


def test_read_xls_data_file_not_found():
    df, err, tb = read_xls_data("/nonexistent_file_xyz.xls")
    assert df is None
    assert err is not None
    assert "No such file" in err or "exist" in err or err


def test_read_xls_data_not_html_not_ole_returns_error(tmp_path):
    """既非 HTML 又非 Excel OLE 头时返回错误。"""
    path = tmp_path / "t.xls"
    path.write_bytes(b"not html and not ole magic bytes")
    df, err, tb = read_xls_data(str(path))
    assert df is None
    assert err is not None


def test_read_xls_data_table_too_small_returns_error(tmp_path):
    """表格行数不足（<= DATA_START_ROW）时返回错误。"""
    small = "<table><tr><td>1</td></tr></table>"  # 只有 1 行
    path = tmp_path / "t.xls"
    path.write_text(small, encoding="utf-8")
    df, err, tb = read_xls_data(str(path))
    assert df is None
    assert err is not None


def test_parse_time_arg_valid_returns_datetime():
    log = logging.getLogger("test")
    from merge_data import _parse_time_arg
    dt = _parse_time_arg("2026030812", "起始时间", log)
    assert dt is not None
    assert dt.year == 2026 and dt.month == 3 and dt.day == 8 and dt.hour == 12


def test_parse_time_arg_invalid_exits():
    import pytest
    log = logging.getLogger("test")
    from merge_data import _parse_time_arg
    with pytest.raises(SystemExit):
        _parse_time_arg("bad", "起始时间", log)


def test_merge_data_main_success(tmp_path, monkeypatch):
    """main() 在有效参数和已有 xls 下合并并写出 Master CSV。"""
    import merge_data
    monkeypatch.setattr(merge_data, "__file__", str(tmp_path / "merge_data.py"))
    monkeypatch.setattr(merge_data, "DOWNLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(merge_data, "DEBUG_LOG_DIR", str(tmp_path / "log"))
    (tmp_path / "log").mkdir()
    pd.DataFrame([["H1"] * 12, ["h1"] * 12]).to_excel(tmp_path / "template.xlsx", header=False, index=False)
    date_dir = tmp_path / "20260308"
    date_dir.mkdir()
    rows = DATA_START_ROW + 2
    cols = 14
    trs = "".join("<tr>" + "".join(f"<td>{i},{j}</td>" for j in range(cols)) + "</tr>" for i in range(rows))
    (date_dir / "A VS B2026030812.xls").write_text("<table>" + trs + "</table>", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["merge_data.py", "2026030812", "2026030812"])
    merge_data.main()
    master = date_dir / "Master20260308.csv"
    assert master.exists()
    content = master.read_text(encoding="utf-8-sig")
    assert "A" in content and "B" in content

