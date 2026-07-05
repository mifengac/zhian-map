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

# 2. 创建瓦片挂载文件夹
echo "[2/3] 初始化本地离线瓦片挂载点..."
mkdir -p ./tiles
echo "💡 提示: 请将下载的云浮市 XYZ 瓦片数据放置在当前文件夹的 ./tiles/ 目录下。"
echo "   结构应类似于: ./tiles/{z}/{x}/{y}.png"

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
  -v "$(pwd)/tiles:/usr/share/nginx/html/tiles" \
  -v "$(pwd)/incidents.json:/usr/share/nginx/html/incidents.json" \
  -v "$(pwd)/case_type_config.json:/usr/share/nginx/html/case_type_config.json" \
  --restart always \
  yf-map:latest

echo "=========================================="
echo "🎉 部署指令执行完成！"
echo "👉 访问系统：http://[服务器内网IP]:5007"
echo "📂 瓦片目录：$(pwd)/tiles"
echo "📝 查看日志：docker logs -f yf-map-system"
echo "=========================================="
