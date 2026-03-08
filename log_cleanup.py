# -*- coding: utf-8 -*-
"""
删除指定目录下超过指定天数的日志文件，避免占用过多磁盘空间。
供 crawl.py、merge_data.py、calc_car.py、plot_car.py 在执行前调用。
"""
import os
import time


def delete_old_logs(log_dir: str, days: int = 7) -> list:
    """
    删除 log_dir 下最后修改时间早于 days 天的文件。
    :param log_dir: 日志目录路径
    :param days: 保留最近多少天，超过此天数的文件将被删除
    :return: 被删除的文件名列表
    """
    if not os.path.isdir(log_dir):
        return []
    now = time.time()
    threshold = now - days * 86400
    deleted = []
    for fname in os.listdir(log_dir):
        path = os.path.join(log_dir, fname)
        if not os.path.isfile(path):
            continue
        try:
            if os.path.getmtime(path) < threshold:
                os.remove(path)
                deleted.append(fname)
        except OSError:
            pass
    return deleted
