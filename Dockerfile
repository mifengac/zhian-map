# 阶段一：构建前端静态资源
FROM node:20-alpine AS builder

# 设置国内 npm 镜像源以加快依赖下载
RUN npm config set registry https://registry.npmmirror.com

WORKDIR /app

# 复制依赖配置并安装
COPY package*.json ./
RUN npm install

# 复制项目代码并打包
COPY . .
RUN npm run build

# 阶段二：使用 Nginx 运行静态资源
FROM nginx:alpine

# 复制 Nginx 配置文件
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 从阶段一将打包产物复制至 Nginx html 静态目录
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
