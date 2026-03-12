import os
import time

from log_cleanup import delete_old_logs


def test_delete_old_logs_non_dir_returns_empty():
    """当 log_dir 不是目录时直接返回空列表。"""
    assert delete_old_logs("/nonexistent_path_xyz", days=7) == []


def test_delete_old_logs_skips_subdirectories(tmp_path):
    """子目录不是文件，应被跳过不删除。"""
    (tmp_path / "subdir").mkdir()
    (tmp_path / "a.log").write_text("a")
    ten_days_ago = time.time() - 10 * 86400
    os.utime(tmp_path / "a.log", (ten_days_ago, ten_days_ago))
    deleted = delete_old_logs(str(tmp_path), days=7)
    assert "a.log" in deleted
    assert (tmp_path / "subdir").exists()


def test_delete_old_logs_removes_older_files(tmp_path):
    log_dir = tmp_path
    old_file = log_dir / "old.log"
    new_file = log_dir / "new.log"
    old_file.write_text("old")
    new_file.write_text("new")

    # 将 old_file 的修改时间设置为 10 天前
    ten_days_ago = time.time() - 10 * 86400
    os.utime(old_file, (ten_days_ago, ten_days_ago))

    deleted = delete_old_logs(str(log_dir), days=7)
    assert old_file.name in deleted
    assert not new_file.name in deleted
    assert not old_file.exists()
    assert new_file.exists()

