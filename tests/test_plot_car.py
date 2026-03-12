import os
import sys

import pandas as pd
import pytest

from plot_car import (
    _safe_filename,
    _to_float,
    _resolve_data_dir,
    _setup_logging,
    _setup_chinese_font,
    plot_match_curves,
    main,
)


def test_safe_filename_empty_or_blank_returns_match():
    """空串或仅空白经 strip 后为空，返回 'match'。"""
    assert _safe_filename("") == "match"
    assert _safe_filename("  ") == "match"


def test_safe_filename_replaces_illegal_chars():
    name = 'A<B>:C/"D"|E?*'
    safe = _safe_filename(name)
    assert "<" not in safe
    assert ">" not in safe
    assert ":" not in safe
    assert '"' not in safe
    assert "/" not in safe
    assert "\\" not in safe
    assert "|" not in safe
    assert "?" not in safe
    assert "*" not in safe
    assert safe  # 非空


def test_to_float_converts_and_preserves_nan():
    s = pd.Series(["1.5", "2", "bad"])
    out = _to_float(s)
    assert list(out[:2]) == [1.5, 2.0]
    assert pd.isna(out.iloc[2])


def test_resolve_data_dir_absolute():
    abs_path = os.path.abspath("/tmp/some_date")
    assert _resolve_data_dir(abs_path) == abs_path


def test_resolve_data_dir_relative(monkeypatch):
    monkeypatch.setattr("plot_car.DOWNLOAD_DIR", "/data")
    assert _resolve_data_dir("20260308") == os.path.abspath("/data/20260308")


def test_setup_logging_returns_logger(monkeypatch, tmp_path):
    monkeypatch.setattr("plot_car.DEBUG_LOG_DIR", str(tmp_path))
    log = _setup_logging()
    assert log is not None
    assert log.name == "plot_car"


def test_setup_chinese_font_runs():
    _setup_chinese_font()


def test_plot_match_curves_generates_images(tmp_path, monkeypatch):
    """有 CAR xlsx 时 plot_match_curves 生成曲线图。"""
    monkeypatch.setattr("plot_car.REPORT_DIR", str(tmp_path / "report"))
    data_dir = tmp_path / "20260308"
    data_dir.mkdir()
    report_dir = tmp_path / "report" / "20260308"
    report_dir.mkdir(parents=True)
    # CAR: 2 行表头 + 2 行数据（同一场比赛两个时间点）
    car = report_dir / "CAR20260308.xlsx"
    df = pd.DataFrame([
        ["主队", "客队", "时间", "D", "E", "F", "G", "H", "I", "J", "K", "L"],
        ["", "", "", "", "", "", "", "", "", "", "", ""],
        ["主", "客", "2026030812", 1.5, 2.0, 2.5, 1.6, 2.1, 2.4, 0.1, 0.2, 0.3],
        ["主", "客", "2026030813", 1.6, 2.0, 2.4, 1.55, 2.05, 2.45, 0.12, 0.18, 0.28],
    ])
    df.to_excel(car, header=False, index=False)
    n = plot_match_curves(str(data_dir), str(tmp_path))
    assert n == 1
    imgs = list(report_dir.glob("*_曲线.png"))
    assert len(imgs) == 1


def test_plot_match_curves_no_data_returns_zero(tmp_path, monkeypatch):
    monkeypatch.setattr("plot_car.REPORT_DIR", str(tmp_path))
    (tmp_path / "20260308").mkdir(parents=True)
    report_dir = tmp_path / "20260308"
    car = report_dir / "CAR20260308.xlsx"
    pd.DataFrame([["H1"] * 12, ["H2"] * 12]).to_excel(car, header=False, index=False)  # 仅表头
    n = plot_match_curves(str(tmp_path / "20260308"), str(tmp_path))
    assert n == 0


def test_plot_match_curves_missing_car_raises(tmp_path, monkeypatch):
    monkeypatch.setattr("plot_car.REPORT_DIR", str(tmp_path))
    (tmp_path / "empty").mkdir()
    with pytest.raises(FileNotFoundError, match="综合评估表不存在"):
        plot_match_curves(str(tmp_path / "empty"), str(tmp_path))


def test_main_exits_when_args_invalid(monkeypatch, tmp_path):
    monkeypatch.setattr("plot_car.DEBUG_LOG_DIR", str(tmp_path))
    monkeypatch.setattr("sys.argv", ["plot_car.py", "x", "y"])
    with pytest.raises(SystemExit):
        main()


def test_main_exits_when_dir_not_exist(monkeypatch, tmp_path):
    monkeypatch.setattr("plot_car.DEBUG_LOG_DIR", str(tmp_path))
    monkeypatch.setattr("plot_car.DOWNLOAD_DIR", str(tmp_path))
    monkeypatch.setattr("sys.argv", ["plot_car.py", "2026030812", "2026030911"])
    with pytest.raises(SystemExit):
        main()


def test_main_success_generates_curves(monkeypatch, tmp_path):
    """main() 在 CAR 存在时调用 plot_match_curves 并完成。"""
    monkeypatch.setattr("plot_car.DEBUG_LOG_DIR", str(tmp_path))
    monkeypatch.setattr("plot_car.DOWNLOAD_DIR", str(tmp_path))
    monkeypatch.setattr("plot_car.REPORT_DIR", str(tmp_path / "report"))
    monkeypatch.setattr("plot_car.__file__", str(tmp_path / "plot_car.py"))
    data_dir = tmp_path / "20260308"
    data_dir.mkdir()
    report_dir = tmp_path / "report" / "20260308"
    report_dir.mkdir(parents=True)
    car = report_dir / "CAR20260308.xlsx"
    pd.DataFrame([
        ["主队", "客队", "时间", "D", "E", "F", "G", "H", "I", "J", "K", "L"],
        ["", "", "", "", "", "", "", "", "", "", "", ""],
        ["主", "客", "2026030812", 1.5, 2.0, 2.5, 1.6, 2.1, 2.4, 0.1, 0.2, 0.3],
    ]).to_excel(car, header=False, index=False)
    monkeypatch.setattr("sys.argv", ["plot_car.py", "2026030812", "2026030911"])
    main()
    assert len(list(report_dir.glob("*_曲线.png"))) == 1

