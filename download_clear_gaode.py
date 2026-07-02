import os
import math
import urllib.request
import time
import sys

# 1. 地理范围配置
# 全市范围（用于中低层级 12-13 级）
YF_LON_MIN, YF_LON_MAX = 111.05, 112.52
YF_LAT_MIN, YF_LAT_MAX = 22.36, 23.32

# 云城区市中心核心区域（用于高精度层级 14-17 级，聚焦警务巡防区域，节省空间和下载时间）
CENTER_LON_MIN, CENTER_LON_MAX = 112.01, 112.08
CENTER_LAT_MIN, CENTER_LAT_MAX = 22.91, 22.95

# 高德地图街道图源
TILE_URL_TEMPLATE = "https://wprd01.is.autonavi.com/appmaptile?lang=zh_cn&size=1&style=7&x={x}&y={y}&z={z}"

def lonlat_to_tile(lon, lat, zoom):
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    xtile = int((lon + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.log(math.tan(lat_rad) + (1.0 / math.cos(lat_rad))) / math.pi) / 2.0 * n)
    return xtile, ytile

def download_range(output_dir, zoom, lon_min, lon_max, lat_min, lat_max, headers):
    x_min, y_max = lonlat_to_tile(lon_min, lat_min, zoom)
    x_max, y_min = lonlat_to_tile(lon_max, lat_max, zoom)

    x_start, x_end = min(x_min, x_max), max(x_min, x_max)
    y_start, y_end = min(y_min, y_max), max(y_min, y_max)

    downloaded = 0
    total = (x_end - x_start + 1) * (y_end - y_start + 1)
    
    print(f"\n[层级 {zoom}] 下载范围: X({x_start} ~ {x_end}), Y({y_start} ~ {y_end}) | 共计: {total} 张瓦片")

    for x in range(x_start, x_end + 1):
        for y in range(y_start, y_end + 1):
            url = TILE_URL_TEMPLATE.format(z=zoom, x=x, y=y)
            dest_dir = os.path.join(output_dir, "gaode", str(zoom), str(x))
            os.makedirs(dest_dir, exist_ok=True)
            dest_file = os.path.join(dest_dir, f"{y}.png")

            if os.path.exists(dest_file) and os.path.getsize(dest_file) > 0:
                continue

            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=8) as response, open(dest_file, 'wb') as out_file:
                    out_file.write(response.read())
                downloaded += 1
                sys.stdout.write(f"\r  已下载 {downloaded}/{total} 张瓦片...")
                sys.stdout.flush()
                # 延时防屏蔽
                time.sleep(0.08)
            except Exception as e:
                print(f"\n  ⚠️ 瓦片 {zoom}/{x}/{y} 下载失败: {e}")
                time.sleep(0.5)
                
    return downloaded

def main():
    output_dir = sys.argv[1] if len(sys.argv) > 1 else "./tiles"
    print(f"==========================================")
    print(f" 开始下载云浮市高精高德离线瓦片")
    print(f" 保存目录: {output_dir}")
    print(f"==========================================")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    total_downloaded = 0

    # 1. 下载全市域范围的 12-13 级（县级/大局态势）
    for z in [12, 13]:
        print(f"\n>> 正在下载【全市范围】第 {z} 级瓦片...")
        total_downloaded += download_range(output_dir, z, YF_LON_MIN, YF_LON_MAX, YF_LAT_MIN, YF_LAT_MAX, headers)

    # 2. 下载云城区中心范围的 14-18 级（街道/高精巡区）
    for z in [14, 15, 16, 17, 18]:
        print(f"\n>> 正在下载【云城区市中心核心巡防区】第 {z} 级高精瓦片...")
        total_downloaded += download_range(output_dir, z, CENTER_LON_MIN, CENTER_LON_MAX, CENTER_LAT_MIN, CENTER_LAT_MAX, headers)

    print(f"\n\n🎉 任务完成！共成功下载 {total_downloaded} 张高精瓦片，已归档至 {os.path.join(output_dir, 'gaode')} 目录。")

if __name__ == "__main__":
    main()
