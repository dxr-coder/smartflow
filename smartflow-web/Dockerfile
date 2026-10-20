# ========== SmartFlow 前端镜像（多阶段构建） ==========
#
# 功能：Vue3 前端构建 + nginx 静态服务 + API 反代
# 用法：docker build -t smartflow-frontend .
# 数据流：npm run build 产出 dist/ → nginx 托管静态文件 + 把 API 前缀反代到 backend

# ---------- Stage 1: 构建 ----------
FROM node:20-alpine AS builder

WORKDIR /app

# 先拷依赖清单（利用缓存）
COPY package.json package-lock.json ./
RUN npm ci

# 拷源码并构建
COPY index.html vite.config.js ./
COPY public/ ./public/
COPY src/ ./src/
RUN npm run build

# ---------- Stage 2: nginx 静态服务 ----------
FROM nginx:alpine

# 拷构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# 拷 nginx 配置（SPA fallback + API 反代 + SSE）
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
