import os
import sys

import pandas as pd
import pytest

from calc_car import (
    compute_max_min_avg,
    compute_varp_100,
    _resolve_data_dir,
    run,
    _setup_logging,
    main,
)


def test_compute_max_min_avg_basic():
    s = pd.Series([1, 2, 3, 4])
    value = compute_max_min_avg(s)
    # (4 - 1) / average(1,2,3,4) = 3 / 2.5 = 1.2
    assert abs(value - 1.2) < 1e-6


def test_compute_max_min_avg_empty_or_zero_returns_zero():
    assert compute_max_min_avg(pd.Series([])) == 0.0
    assert compute_max_min_avg(pd.Series([0, 0])) == 0.0


def test_compute_varp_100_basic():
    s = pd.Series([1, 2, 3])
    # population variance: mean=2, squared diffs=(1,0,1) => var=2/3, *100
    value = compute_varp_100(s)
    assert abs(value - (2.0 / 3.0 * 100.0)) < 1e-6


def test_compute_varp_100_insufficient_data_returns_zero():
    assert compute_varp_100(pd.Series([])) == 0.0
    assert compute_varp_100(pd.Series([5])) == 0.0


def test_resolve_data_dir_absolute():
    abs_path = os.path.abspath("/tmp/some_date")
    assert _resolve_data_dir(abs_path) == abs_path


def test_resolve_data_dir_relative(monkeypatch):
    monkeypatch.setattr("calc_car.DOWNLOAD_DIR", "/data")
    assert _resolve_data_dir("20260308") == os.path.abspath("/data/20260308")


def test_setup_logging_returns_logger(monkeypatch, tmp_path):
    monkeypatch.setattr("calc_car.DEBUG_LOG_DIR", str(tmp_path))
    log = _setup_logging()
    assert log is not None
    assert log.name == "calc_car"


def test_run_produces_car_xlsx(tmp_path, monkeypatch):
    """run() 读取 Master CSV 和 template，写出 CAR xlsx。"""
    data_dir = tmp_path / "20260308"
    data_dir.mkdir()
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    report_dir = tmp_path / "report" / "20260308"
    report_dir.mkdir(parents=True)

    # Master20260308.csv: 两行表头 + 一行数据（主队、客队、时间点、D～L 共 12 列）
    master = data_dir / "Master20260308.csv"
    master.write_text(
        "H1,H2,H3,H4,H5,H6,H7,H8,H9,H10,H11,H12\n"
        "h1,h2,h3,h4,h5,h6,h7,h8,h9,h10,h11,h12\n"
        "A,B,2026030812,1,2,3,4,5,6,0.1,0.2,0.3\n",
        encoding="utf-8-sig",
    )
    template_path = project_dir / "template.xlsx"
    pd.DataFrame([["H1"] * 12, ["h1"] * 12]).to_excel(template_path, header=False, index=False)

    monkeypatch.setattr("calc_car.REPORT_DIR", str(tmp_path / "report"))
    run(str(data_dir), str(project_dir))
    out = report_dir / "CAR20260308.xlsx"
    assert out.exists()
    df = pd.read_excel(out, header=None)
    assert len(df) >= 2


def test_run_missing_master_raises(tmp_path, monkeypatch):
    monkeypatch.setattr("calc_car.REPORT_DIR", str(tmp_path))
    (tmp_path / "empty").mkdir()
    with pytest.raises(FileNotFoundError, match="一览表不存在"):
        run(str(tmp_path / "empty"), str(tmp_path))


def test_main_exits_when_args_invalid(monkeypatch, tmp_path):
    monkeypatch.setattr("calc_car.DEBUG_LOG_DIR", str(tmp_path))
    monkeypatch.setattr("sys.argv", ["calc_car.py", "x", "y"])
    with pytest.raises(SystemExit):
        main()


def test_main_exits_when_dir_not_exist(monkeypatch, tmp_path):
    monkeypatch.setattr("calc_car.DEBUG_LOG_DIR", str(tmp_path))
    monkeypatch.setattr("calc_car.DOWNLOAD_DIR", str(tmp_path))
    monkeypatch.setattr("sys.argv", ["calc_car.py", "2026030812", "2026030911"])
    with pytest.raises(SystemExit):
        main()


def test_main_success_calls_run(monkeypatch, tmp_path):
    """main() 在目录和 Master/template 齐全时调用 run() 并完成。"""
    monkeypatch.setattr("calc_car.DEBUG_LOG_DIR", str(tmp_path))
    monkeypatch.setattr("calc_car.DOWNLOAD_DIR", str(tmp_path))
    monkeypatch.setattr("calc_car.REPORT_DIR", str(tmp_path / "report"))
    data_dir = tmp_path / "20260308"
    data_dir.mkdir()
    (data_dir / "Master20260308.csv").write_text(
        "H1,H2,H3,H4,H5,H6,H7,H8,H9,H10,H11,H12\n"
        "h1,h2,h3,h4,h5,h6,h7,h8,h9,h10,h11,h12\n"
        "A,B,2026030812,1,2,3,4,5,6,0.1,0.2,0.3\n",
        encoding="utf-8-sig",
    )
    proj = tmp_path / "proj"
    proj.mkdir()
    pd.DataFrame([["H1"] * 12, ["h1"] * 12]).to_excel(proj / "template.xlsx", header=False, index=False)
    monkeypatch.setattr("calc_car.__file__", str(proj / "calc_car.py"))
    monkeypatch.setattr("sys.argv", ["calc_car.py", "2026030812", "2026030911"])
    main()
    assert (tmp_path / "report" / "20260308" / "CAR20260308.xlsx").exists()

