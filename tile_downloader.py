import os
import math
import urllib.request
import time
import sys

# 1. 定义云浮市的地理范围 (经纬度)
# 东经 111.05 至 112.52，北纬 22.36 至 23.32
LON_MIN, LON_MAX = 111.05, 112.52
LAT_MIN, LAT_MAX = 22.36, 23.32

# 2. 地图数据源模板
SOURCES = {
    "osm": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    "gaode": "https://wprd01.is.autonavi.com/appmaptile?lang=zh_cn&size=1&style=7&x={x}&y={y}&z={z}",
    "gaode_satellite": "https://wprd01.is.autonavi.com/appmaptile?lang=zh_cn&size=1&style=6&x={x}&y={y}&z={z}"
}

# 3. 经纬度转 XYZ 瓦片坐标公式
def lonlat_to_tile(lon, lat, zoom):
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    xtile = int((lon + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.log(math.tan(lat_rad) + (1.0 / math.cos(lat_rad))) / math.pi) / 2.0 * n)
    return xtile, ytile

# 4. 下载核心逻辑
def download_tiles(output_dir, min_zoom, max_zoom, source_type):
    tile_url_template = SOURCES.get(source_type, SOURCES["osm"])
    print(f"==========================================")
    print(f" 开始下载云浮市离线底图瓦片")
    print(f" 经度范围: {LON_MIN} ~ {LON_MAX}")
    print(f" 纬度范围: {LAT_MIN} ~ {LAT_MAX}")
    print(f" 数据源类型: {source_type}")
    print(f" 模板地址: {tile_url_template}")
    print(f"==========================================")

    total_downloaded = 0
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }

    for zoom in range(min_zoom, max_zoom + 1):
        x_min, y_max = lonlat_to_tile(LON_MIN, LAT_MIN, zoom)
        x_max, y_min = lonlat_to_tile(LON_MAX, LAT_MAX, zoom)

        x_start, x_end = min(x_min, x_max), max(x_min, x_max)
        y_start, y_end = min(y_min, y_max), max(y_min, y_max)

        x_count = x_end - x_start + 1
        y_count = y_end - y_start + 1
        zoom_total = x_count * y_count
        print(f"\n[层级 {zoom}] 范围: X({x_start} ~ {x_end}), Y({y_start} ~ {y_end}) | 总计: {zoom_total} 张瓦片")

        for x in range(x_start, x_end + 1):
            for y in range(y_start, y_end + 1):
                url = tile_url_template.format(z=zoom, x=x, y=y)
                
                # 按照数据源分目录保存，避免混淆
                dest_dir = os.path.join(output_dir, source_type, str(zoom), str(x))
                os.makedirs(dest_dir, exist_ok=True)
                dest_file = os.path.join(dest_dir, f"{y}.png")

                # 若文件已存在，则跳过
                if os.path.exists(dest_file) and os.path.getsize(dest_file) > 0:
                    continue

                try:
                    req = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req, timeout=10) as response, open(dest_file, 'wb') as out_file:
                        out_file.write(response.read())
                    total_downloaded += 1
                    sys.stdout.write(f"\r  下载进度: 已下载 {total_downloaded} 张...")
                    sys.stdout.flush()
                    # 适当延时，高德防爬较严，延时设置0.15秒
                    time.sleep(0.15)
                except Exception as e:
                    print(f"\n  ⚠️ 瓦片 {zoom}/{x}/{y} 下载失败: {e}")
                    time.sleep(1)

    print(f"\n\n🎉 下载完成！共成功下载 {total_downloaded} 张新增瓦片。")
    print(f"📂 瓦片保存于: {os.path.join(output_dir, source_type)}")

if __name__ == "__main__":
    # 默认下载保存路径
    default_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tiles")
    
    # 默认配置
    min_z = 7
    max_z = 11
    src = "osm" # 默认数据源

    if len(sys.argv) > 1:
        try:
            min_z = int(sys.argv[1])
            max_z = int(sys.argv[2])
        except ValueError:
            print("参数有误，将使用默认层级 7-11 级下载")

    if len(sys.argv) > 3:
        # 如果是路径
        if sys.argv[3].lower() in ["osm", "gaode", "gaode_satellite"]:
            src = sys.argv[3].lower()
        else:
            default_dir = sys.argv[3]

    if len(sys.argv) > 4:
        src = sys.argv[4].lower()

    download_tiles(default_dir, min_z, max_z, src)
