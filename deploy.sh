#!/bin/bash

# 云浮市公安立体巡防管控平台 - 内网一键部署脚本

echo "=========================================="
echo "   开始部署云浮市公安立体巡防管控平台"
echo "=========================================="

# 1. 导入离线镜像
if [ -f "yf-map-latest.tar" ]; then
    echo "[1/3] 正在载入离线 Docker 镜像 (yf-map:latest)..."
    docker load -i yf-map-latest.tar
else
    echo "❌ 错误: 未能在当前目录下找到 yf-map-latest.tar 镜像文件！"
    exit 1
fi

# 2. 底图已拆到 zhian-tiles :5099，本容器只挂数据文件
echo "[2/3] 检查 map-config.json（底图 URL）..."
if [ ! -f "map-config.json" ]; then
    echo '{"tileUrl":"http://{host}:5099/tiles/gaode/{z}/{x}/{y}.png"}' > map-config.json
    echo "已生成默认 map-config.json，指向本机 :5099 的 zhian-tiles"
fi
echo "💡 底图服务必须已部署：zhian-tiles 端口 5099。改 IP 只改 map-config.json 后刷新页面即可。"

# 3. 运行容器
echo "[3/3] 启动 Docker 运行容器..."

# 检查是否有同名容器正在运行，有则先删除
if docker ps -a --format '{{.Names}}' | grep -q "^yf-map-system$"; then
    echo "ℹ️  检测到已存在同名容器 yf-map-system，正在停止并删除旧容器..."
    docker stop yf-map-system
    docker rm yf-map-system
fi

docker run -d \
  --name yf-map-system \
  -p 5007:80 \
  -v "$(pwd)/incidents.json:/usr/share/nginx/html/incidents.json" \
  -v "$(pwd)/case_type_config.json:/usr/share/nginx/html/case_type_config.json" \
  -v "$(pwd)/map-config.json:/usr/share/nginx/html/map-config.json" \
  --restart always \
  yf-map:latest

echo "=========================================="
echo "🎉 部署指令执行完成！"
echo "👉 访问系统：http://[服务器内网IP]:5007"
echo "🗺️  底图：zhian-tiles :5099（map-config.json）"
echo "📝 查看日志：docker logs -f yf-map-system"
echo "=========================================="
