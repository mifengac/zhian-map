# zhian-map · AGENTS.md

> **上级约定**：本项目在 `~/project/` 下，`~/project/AGENTS.md` 的全部约定同样适用，开工前先读一遍。
> 尤其是第八条 —— 动手前先扫一遍 `~/project/skills/`，有相关 skill 就**完整读完再做**。

## 运维经验（2026-09-07 从 ~/.agents/skills/zhian-map 原文迁来，一字未改）


路径 `/home/longshao/project/zhian-map`。React + Leaflet + Vite，Docker Nginx 端口 **5007**。

## 底图

底图**不是**本项目的一部分。走 `zhian-tiles` **:5099**。

运行时读 `map-config.json`：

```json
{"tileUrl":"http://{host}:5099/tiles/gaode/{z}/{x}/{y}.png"}
```

`{host}` 换成当前页面主机名。换 IP 只改这个文件（容器已挂载），刷新即可，不必重打 `yf-map` 镜像。

本地 Vite（5173）同样读 `public/map-config.json`。相对路径 `./tiles/gaode/...` 仅作配置缺失时的回退；`vite.config.ts` 仍可本地挂瓦片，但不要监视 `tiles/`。

## 坐标

库里是 CGCS2000/WGS-84，高德瓦片是 GCJ-02。落图 `wgs84ToGcj02`，地图点选回写 `gcj02ToWgs84`。不要再给瓦片做一次偏移。

**自己临时写纠偏脚本时别漏了 `-105.0 / -35.0` 的基准偏移**（`transformLat(lng-105.0, lat-35.0)`）。
漏了会算出 1700 米的离谱偏移，还以为是瓦片缺了。自检方法：天安门
WGS84 `116.3912,39.9067` 应转出约 `116.397,39.909`；云浮一带正常偏移量在 500 米上下。
`App.tsx` 里那份实现是对的，抄它。

覆盖与 zoom：min 12 **max 19**，全市框与 tiles 一致。

**19 级不能省**：高德把社区级小路名（如"西三路"）排在 19 级才画，18 级同一块地只有
店铺 POI、路是光的。改 zoom 时注意 `App.tsx` 里另有一处 `maxZoom: 15` 是
`L.heatLayer` 的参数（热力强度峰值对应的缩放级），**与瓦片层级无关，不要跟着改**。

## 数据

- `incidents.json`、`case_type_config.json` 挂进容器，改完刷新。
- `sync_police_data.py` 读金仓，内含处警清洗。

## 改完必须走完三步，少一步内网就是白改

**本机 5007 打开没问题 ≠ 内网可用。** 顺序固定：

```bash
npm run build                              # 1. 出 dist
docker build -t yf-map:latest .            # 2. 重打镜像
docker save yf-map:latest -o yf-map-latest.tar   # 3. 重导摆渡包 ← 最容易漏
```

漏了第 3 步，内网跑 `deploy.sh`（就是 `docker load -i yf-map-latest.tar`）载入的还是旧镜像，
改动一点没过去。**验收要直接解包查，别只看时间戳**：

```bash
tar -xf yf-map-latest.tar -C /tmp/tc && cd /tmp/tc
# 在 blobs 里找到含 nginx/html/assets 的层，解出 js/css 再 grep 你这次改的东西
```

2026-09-03 那次栽过：代码 8 月 26 日就改好，容器却跑着 8 周前的旧构建，
底图全黑一周没人看出来。

## 底图故障不许静默兜底

`tileerror` 用透明 1×1 GIF 兜底能防裂图，但**必须同时给可见提示**，否则故障表现是
「地图一片黑、控制台干净、没人知道为什么」。现在的做法：

- `map-config.json` 加载失败或 `tileUrl` 不合法 → `console.error` + 页面红条提示
  「底图未配置，或 zhian-tiles(:5099) 未启动」；
- 瓦片连续失败（10 秒内 ≥20 张）→ 弹同一条提示。

## 构建相关的两个坑

- **`.dockerignore` 是必需品**，必须排除 `tiles/`（几十万张 PNG、几个 GB）和 `*.tar`。
  没有它，`Dockerfile` 的 `COPY . .` 会把瓦片全吸进构建上下文，根本 build 不动。
  排干净后上下文约 5MB。注意 `.dockerignore` 里 `*.png` **不递归匹配子目录**，
  `public/` 下的资源不受影响。
- Vite 插件里给 `middlewares.use` 写死参数类型会和 Vite 实际重载类型打架，
  `tsc -b` 直接失败、整个项目 build 不过。用宽松类型标注。

## 前端布局约定

- **浮层用 `position:absolute` 时先认清它挂在哪个容器下。** `.timeline-axis-card` 在
  `<main class="map-container">` 内部，地图容器本来就已经排在两个侧栏之间了，
  再按「整屏减侧栏」写 `left:400px; right:400px` 等于又白扣 800px，
  1366 宽度下直接算成负值，卡片被压成一条竖排文字。相对地图容器写 `left/right:20px` 即可。
- **z-index 分层**（新增浮层照这个排，别随手写）：

  | 层 | z-index |
  |---|---|
  | 打标模态框 `.modal-overlay` | 2000 |
  | 窄屏右侧详情面板 | 1500 |
  | Leaflet 自带控件 | 1200 |
  | 底图故障提示条 | 1100 |
  | 地图工具栏 / 时间轴卡片 | 1000 |

  Leaflet 自己的 CSS 给 `.leaflet-top` 定了 1000，我们的覆盖规则要放在文件末尾才赢。
- 断点：≤1600px 侧栏收到 320px；≤1280px 左栏 280px、右面板转覆盖式浮层。

## 字体走本地，不许引外网 CDN

内网没有外网出口。`index.html` 曾 link 到 `fonts.googleapis.com`，内网会干等到超时
才回退系统字体。现在字体在 `public/fonts/`，`index.html` 只引 `/fonts/fonts.css`。

- Inter 只留 `latin` + `latin-ext` 分片，中文项目用不上西里尔/希腊/越南文。
- Noto Sans SC 用 unicode-range 分片版（101 个小文件），浏览器按需加载。
- **两款都是可变字体（含 `fvar` 轴），不同字重共享同一物理文件**，
  不必按字重各存一份 —— 这是总体积能压到 4.9MB 的关键。
- 回退链保留 `'Microsoft YaHei', 'PingFang SC'`，字体缺失也不会变方块。
- 副作用：只内置 400/700，CSS 里写 `font-weight:500` 会退到 400。
- 验收：`grep -rn "googleapis\|gstatic" index.html src/ public/` 必须零命中。

## 不要

- 不要把 `tiles/` 打进业务镜像或列进摆渡必须项。
- 不要占 5099。
- 不要在本项目实现统计口径（口径在 `zhian-core` / skills）。
- 不要引任何外网 CDN（字体、JS 库、CSS 都算）。
- 不要为了验证故障提示去 `docker stop zhian-tiles` —— 那是共享底图服务，
  别的项目也在用。改 `map-config.json` 里的端口来模拟即可。
