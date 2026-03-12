import datetime
import sys

import pytest

from main import _compute_default_time_window, _setup_logging, main


def test_setup_logging_returns_logger(monkeypatch, tmp_path):
    monkeypatch.setattr("main.DEBUG_LOG_DIR", str(tmp_path))
    log = _setup_logging()
    assert log is not None
    assert log.name == "main"


def test_compute_default_time_window_before_cutoff(monkeypatch):
    # 固定临界点，避免依赖环境变量
    monkeypatch.setattr("main.CUTOFF_HOUR", 12, raising=False)
    now = datetime.datetime(2026, 3, 8, 11, 0, 0)
    start, end = _compute_default_time_window(now)
    assert start == datetime.datetime(2026, 3, 7, 12, 0, 0)
    assert end == datetime.datetime(2026, 3, 8, 11, 0, 0)


def test_compute_default_time_window_after_cutoff(monkeypatch):
    monkeypatch.setattr("main.CUTOFF_HOUR", 12, raising=False)
    now = datetime.datetime(2026, 3, 8, 13, 0, 0)
    start, end = _compute_default_time_window(now)
    assert start == datetime.datetime(2026, 3, 8, 12, 0, 0)
    assert end == datetime.datetime(2026, 3, 9, 11, 0, 0)


def test_main_no_args_uses_default_window_and_runs_steps(monkeypatch, tmp_path):
    monkeypatch.setattr("main.DEBUG_LOG_DIR", str(tmp_path))
    monkeypatch.setattr("main.LOG_RETENTION_DAYS", 7)
    monkeypatch.setattr("sys.argv", ["main.py"])
    run_calls = []

    def fake_run(cmd, **kwargs):
        run_calls.append(cmd)
        from unittest.mock import MagicMock
        return MagicMock(returncode=0)

    monkeypatch.setattr("main.subprocess.run", fake_run)
    main()
    assert len(run_calls) == 4
    assert "crawl.py" in run_calls[0]
    assert "merge_data.py" in run_calls[1]
    assert "calc_car.py" in run_calls[2]
    assert "plot_car.py" in run_calls[3]


def test_main_two_valid_args_parses_and_runs_steps(monkeypatch, tmp_path):
    monkeypatch.setattr("main.DEBUG_LOG_DIR", str(tmp_path))
    monkeypatch.setattr("sys.argv", ["main.py", "2026030812", "2026030911"])
    run_calls = []

    def fake_run(cmd, **kwargs):
        run_calls.append(cmd)
        from unittest.mock import MagicMock
        return MagicMock(returncode=0)

    monkeypatch.setattr("main.subprocess.run", fake_run)
    main()
    assert run_calls[0][-2:] == ["2026030812", "2026030911"]


def test_main_invalid_args_exits(monkeypatch, tmp_path):
    monkeypatch.setattr("main.DEBUG_LOG_DIR", str(tmp_path))
    monkeypatch.setattr("sys.argv", ["main.py", "one", "two"])
    with pytest.raises(SystemExit):
        main()


def test_main_start_after_end_exits(monkeypatch, tmp_path):
    monkeypatch.setattr("main.DEBUG_LOG_DIR", str(tmp_path))
    monkeypatch.setattr("sys.argv", ["main.py", "2026030911", "2026030812"])
    with pytest.raises(SystemExit):
        main()


def test_main_bad_time_format_exits(monkeypatch, tmp_path):
    """时间格式 10 位但无效（如 2 月 30 日）触发 ValueError 后 exit。"""
    monkeypatch.setattr("main.DEBUG_LOG_DIR", str(tmp_path))
    monkeypatch.setattr("sys.argv", ["main.py", "2026023012", "2026023013"])  # 无效日期
    with pytest.raises(SystemExit):
        main()


def test_main_subprocess_failure_exits(monkeypatch, tmp_path):
    monkeypatch.setattr("main.DEBUG_LOG_DIR", str(tmp_path))
    monkeypatch.setattr("sys.argv", ["main.py", "2026030812", "2026030911"])
    from unittest.mock import MagicMock
    monkeypatch.setattr("main.subprocess.run", lambda *a, **k: MagicMock(returncode=1))
    with pytest.raises(SystemExit):
        main()

