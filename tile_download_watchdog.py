#!/usr/bin/env python3
"""瓦片下载看门狗。

下载进程在系统睡眠 / 断网后会永久挂起（所有工作线程卡在 wait_woken，
连 urlopen 的 timeout 都随 WSL 一起被冻结），自己醒不过来。
本脚本盯着它：进程没了、或状态文件超过 STALE_SEC 没更新（= 卡死），
就杀掉重启。文件数达标后自动退出。

用法：
    nohup setsid python3 tile_download_watchdog.py > tiles/watchdog.log 2>&1 &
"""
import json
import os
import signal
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
TILES = os.path.join(ROOT, "tiles", "gaode", "19")
STATUS = os.path.join(ROOT, "tiles", "download_z19_status.json")
DLOG = os.path.join(ROOT, "tiles", "download_z19.log")
TARGET = 3_251_556
STALE_SEC = 300          # 状态文件超过 5 分钟没更新就判定卡死
CHECK_EVERY = 60
PATTERN = "download_city_gaode.py --min-zoom 19"

CMD = [
    sys.executable, os.path.join(ROOT, "download_city_gaode.py"),
    "--min-zoom", "19", "--max-zoom", "19", "--workers", "12",
    "--status", STATUS,
]


def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def count_tiles():
    n = 0
    for _, _, files in os.walk(TILES):
        n += sum(1 for f in files if f.endswith(".png"))
    return n


def find_pids():
    try:
        out = subprocess.run(["pgrep", "-f", PATTERN],
                             capture_output=True, text=True).stdout
        return [int(p) for p in out.split() if p.strip().isdigit()]
    except Exception:
        return []


def status_age():
    """状态文件多久没更新了（秒）。文件不存在返回 None。"""
    try:
        return time.time() - os.path.getmtime(STATUS)
    except OSError:
        return None


def kill_all():
    for pid in find_pids():
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.kill(pid, sig)
            except ProcessLookupError:
                break
            time.sleep(3)
            if not find_pids():
                break
    # 清掉可能的半截文件
    subprocess.run(["find", os.path.join(ROOT, "tiles", "gaode"),
                    "-name", "*.part", "-delete"], capture_output=True)


def start():
    with open(DLOG, "ab") as f:
        subprocess.Popen(CMD, cwd=ROOT, stdout=f, stderr=f,
                         stdin=subprocess.DEVNULL, start_new_session=True)
    log(f"已拉起下载进程 pid={find_pids()}")


def main():
    log(f"看门狗启动，目标 {TARGET:,} 张，当前 {count_tiles():,} 张")
    restarts = 0
    while True:
        n = count_tiles()
        if n >= TARGET:
            log(f"下载完成：{n:,}/{TARGET:,}，共重启 {restarts} 次，看门狗退出")
            kill_all()
            return 0

        pids = find_pids()
        age = status_age()

        if not pids:
            log(f"进程不在（已下 {n:,}），拉起")
            start()
            restarts += 1
        elif age is not None and age > STALE_SEC:
            log(f"状态文件 {age/60:.1f} 分钟没更新，判定卡死（已下 {n:,}），重启")
            kill_all()
            time.sleep(3)
            start()
            restarts += 1

        time.sleep(CHECK_EVERY)


if __name__ == "__main__":
    sys.exit(main())
