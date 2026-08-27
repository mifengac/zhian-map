#!/usr/bin/env python3
"""全市高德街道瓦片下载（style=7）。

默认覆盖现有口径：东经 111.05–112.52，北纬 22.36–23.32。
已有非空 PNG 会跳过，可断点续跑。
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

YF_LON_MIN, YF_LON_MAX = 111.05, 112.52
YF_LAT_MIN, YF_LAT_MAX = 22.36, 23.32

HOSTS = [
    "https://wprd01.is.autonavi.com/appmaptile?lang=zh_cn&size=1&style=7&x={x}&y={y}&z={z}",
    "https://wprd02.is.autonavi.com/appmaptile?lang=zh_cn&size=1&style=7&x={x}&y={y}&z={z}",
    "https://wprd03.is.autonavi.com/appmaptile?lang=zh_cn&size=1&style=7&x={x}&y={y}&z={z}",
    "https://wprd04.is.autonavi.com/appmaptile?lang=zh_cn&size=1&style=7&x={x}&y={y}&z={z}",
]

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# 高德是国内 CDN，强制直连，不走 HTTP_PROXY（本机常见 7897 Clash）
_DIRECT_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def lonlat_to_tile(lon: float, lat: float, zoom: int) -> tuple[int, int]:
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    xtile = int((lon + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.log(math.tan(lat_rad) + (1.0 / math.cos(lat_rad))) / math.pi) / 2.0 * n)
    return xtile, ytile


def tile_range(zoom: int) -> tuple[range, range]:
    x_min, y_max = lonlat_to_tile(YF_LON_MIN, YF_LAT_MIN, zoom)
    x_max, y_min = lonlat_to_tile(YF_LON_MAX, YF_LAT_MAX, zoom)
    xs = range(min(x_min, x_max), max(x_min, x_max) + 1)
    ys = range(min(y_min, y_max), max(y_min, y_max) + 1)
    return xs, ys


def iter_jobs(min_zoom: int, max_zoom: int):
    for z in range(min_zoom, max_zoom + 1):
        xs, ys = tile_range(z)
        for x in xs:
            for y in ys:
                yield z, x, y


def count_jobs(min_zoom: int, max_zoom: int) -> dict[int, int]:
    out = {}
    for z in range(min_zoom, max_zoom + 1):
        xs, ys = tile_range(z)
        out[z] = len(xs) * len(ys)
    return out


class Stats:
    def __init__(self, total: int, by_zoom: dict[int, int], status_path: str):
        self.lock = threading.Lock()
        self.total = total
        self.by_zoom = by_zoom
        self.status_path = status_path
        self.downloaded = 0
        self.skipped = 0
        self.failed = 0
        self.bytes = 0
        self.started = time.time()
        self.started_iso = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        self.current_zoom = min(by_zoom) if by_zoom else 0
        self._last_write = 0.0

    def add(self, downloaded=0, skipped=0, failed=0, nbytes=0, zoom=None):
        with self.lock:
            self.downloaded += downloaded
            self.skipped += skipped
            self.failed += failed
            self.bytes += nbytes
            if zoom is not None:
                self.current_zoom = zoom
            done = self.downloaded + self.skipped + self.failed
            now = time.time()
            if now - self._last_write >= 2.0 or done >= self.total:
                self._write_unlocked(done, now)
                self._last_write = now
            return done

    def snapshot(self) -> dict:
        with self.lock:
            done = self.downloaded + self.skipped + self.failed
            return self._payload(done, time.time())

    def _write_unlocked(self, done: int, now: float) -> None:
        payload = self._payload(done, now)
        tmp = self.status_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.status_path)
        elapsed = max(now - self.started, 0.001)
        rate = (self.downloaded + self.failed) / elapsed
        remain = self.total - done
        eta_min = (remain / rate / 60.0) if rate > 0 else None
        eta_s = f"{eta_min:.0f}min" if eta_min is not None else "?"
        sys.stdout.write(
            f"\r  z{self.current_zoom} 完成 {done}/{self.total}  "
            f"新下 {self.downloaded} 跳过 {self.skipped} 失败 {self.failed}  "
            f"{self.bytes/1024/1024:.1f}MB  {eta_s}    "
        )
        sys.stdout.flush()

    def _payload(self, done: int, now: float) -> dict:
        elapsed = max(now - self.started, 0.001)
        new_or_fail = self.downloaded + self.failed
        rate = new_or_fail / elapsed
        remain = max(self.total - done, 0)
        return {
            "started_at": self.started_iso,
            "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "current_zoom": self.current_zoom,
            "total": self.total,
            "done": done,
            "downloaded": self.downloaded,
            "skipped": self.skipped,
            "failed": self.failed,
            "bytes": self.bytes,
            "elapsed_sec": int(elapsed),
            "rate_per_sec": round(rate, 2),
            "eta_sec": int(remain / rate) if rate > 0 else None,
            "by_zoom": self.by_zoom,
            "bbox": {
                "lon": [YF_LON_MIN, YF_LON_MAX],
                "lat": [YF_LAT_MIN, YF_LAT_MAX],
            },
        }


def fetch_one(z: int, x: int, y: int, dest: str, delay: float, retries: int) -> tuple[str, int]:
    """Return ('ok'|'skip'|'fail', bytes)."""
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return "skip", 0

    os.makedirs(os.path.dirname(dest), exist_ok=True)
    last_err = None
    for attempt in range(retries):
        url = HOSTS[(x + y + attempt) % len(HOSTS)].format(z=z, x=x, y=y)
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://www.amap.com/"})
        try:
            with _DIRECT_OPENER.open(req, timeout=12) as resp:
                data = resp.read()
            if not data:
                last_err = "empty body"
                time.sleep(0.4 * (attempt + 1) + random.random() * 0.2)
                continue
            tmp = dest + ".part"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, dest)
            if delay > 0:
                time.sleep(delay)
            return "ok", len(data)
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}"
            if e.code in (403, 429, 503):
                time.sleep(1.5 * (attempt + 1) + random.random())
            else:
                time.sleep(0.3 * (attempt + 1))
        except Exception as e:
            last_err = str(e)
            time.sleep(0.5 * (attempt + 1) + random.random() * 0.3)
    sys.stderr.write(f"\n  fail {z}/{x}/{y}: {last_err}\n")
    return "fail", 0


def parse_args():
    p = argparse.ArgumentParser(description="下载云浮全市高德街道瓦片")
    p.add_argument("--min-zoom", type=int, default=14)
    p.add_argument("--max-zoom", type=int, default=18)
    p.add_argument("--workers", type=int, default=12)
    p.add_argument("--delay", type=float, default=0.02, help="每张成功请求后的间隔秒")
    p.add_argument("--retries", type=int, default=3)
    p.add_argument("--output", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "tiles"))
    p.add_argument("--status", default=None, help="进度 JSON 路径")
    return p.parse_args()


def main():
    args = parse_args()
    out_root = os.path.join(args.output, "gaode")
    os.makedirs(out_root, exist_ok=True)
    status_path = args.status or os.path.join(args.output, "download_city_status.json")

    by_zoom = count_jobs(args.min_zoom, args.max_zoom)
    total = sum(by_zoom.values())
    print("==========================================")
    print(" 云浮全市高德街道瓦片")
    print(f" 范围: {YF_LON_MIN}–{YF_LON_MAX}E, {YF_LAT_MIN}–{YF_LAT_MAX}N")
    print(f" 层级: {args.min_zoom}–{args.max_zoom}")
    print(f" 张数: {total:,}  " + " ".join(f"z{z}={n:,}" for z, n in by_zoom.items()))
    print(f" 并发: {args.workers}  间隔: {args.delay}s")
    print(f" 目录: {out_root}")
    print(f" 进度: {status_path}")
    print("==========================================")

    stats = Stats(total, by_zoom, status_path)
    stats.add()  # write initial status

    inflight_limit = max(args.workers * 8, 64)
    for z in range(args.min_zoom, args.max_zoom + 1):
        xs, ys = tile_range(z)
        zoom_total = len(xs) * len(ys)
        print(f"\n>> 层级 {z}: X({xs.start}–{xs.stop - 1}) Y({ys.start}–{ys.stop - 1}) 共 {zoom_total:,} 张")
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futs = set()
            for x in xs:
                for y in ys:
                    dest = os.path.join(out_root, str(z), str(x), f"{y}.png")
                    futs.add(pool.submit(fetch_one, z, x, y, dest, args.delay, args.retries))
                    if len(futs) >= inflight_limit:
                        done = next(as_completed(futs))
                        futs.remove(done)
                        kind, nbytes = done.result()
                        if kind == "ok":
                            stats.add(downloaded=1, nbytes=nbytes, zoom=z)
                        elif kind == "skip":
                            stats.add(skipped=1, zoom=z)
                        else:
                            stats.add(failed=1, zoom=z)
            for fut in as_completed(futs):
                kind, nbytes = fut.result()
                if kind == "ok":
                    stats.add(downloaded=1, nbytes=nbytes, zoom=z)
                elif kind == "skip":
                    stats.add(skipped=1, zoom=z)
                else:
                    stats.add(failed=1, zoom=z)

    snap = stats.snapshot()
    print("\n\n完成。")
    print(
        f"新下 {snap['downloaded']:,}  跳过 {snap['skipped']:,}  失败 {snap['failed']:,}  "
        f"体积 {snap['bytes']/1024/1024:.1f}MB  耗时 {snap['elapsed_sec']//60}min"
    )
    if snap["failed"]:
        sys.exit(2)


if __name__ == "__main__":
    main()
