# SmartFlow 部署指南

## 架构总览

```
用户浏览器 → Ingress (nginx) → frontend:80 (静态页面)
                             → backend:8000 (FastAPI API)
                                   ↓
                             MySQL 8.0 + Redis 7 + ChromaDB(PVC)
```

## 1. Docker Compose 本地部署

```bash
# 克隆仓库
git clone https://github.com/dxr-coder/smartflow.git
cd smartflow

# 复制环境变量模板，填入真实值
cp smartflow/.env.example smartflow/.env
# 编辑 .env：MYSQL_PASSWORD、JWT_SECRET、XIAOMI_API_KEY

# 一键启动（MySQL + Redis + Backend + Frontend）
docker compose up -d

# 验证
curl http://localhost:8000/health   # {"status":"ok"}
curl http://localhost:8000/ready    # {"status":"ready","checks":{"mysql":"ok","redis":"ok"}}
open http://localhost:8080          # 前端页面
```

### 服务说明

| 服务 | 端口 | 说明 |
|------|------|------|
| frontend | 8080→80 | nginx 静态页面 + API 反代 |
| backend | 8000 | FastAPI（RAG + Agent + 评测） |
| mysql | 3306 | 数据库（工单/用户/评测数据） |
| redis | 6379 | 缓存（语义缓存/限流/会话） |

### 常用命令

```bash
docker compose logs -f backend      # 看后端日志
docker compose restart backend      # 重启后端
docker compose down -v              # 停止并删除数据卷（慎用）
```

## 2. CI/CD（GitHub Actions）

每次 push 到 main 自动触发：

```
代码推送 → GitHub Actions
  ├─ Job 1: lint-and-build（并行）
  │    ├─ ruff lint（后端代码风格检查）
  │    └─ npm run build（前端构建，构建成功=无语法错误）
  └─ Job 2: build-and-push（依赖 Job 1，只在 main push 时跑）
       ├─ 构建后端镜像 → ghcr.io/dxr-coder/smartflow/backend:{sha} + :latest
       └─ 构建前端镜像 → ghcr.io/dxr-coder/smartflow/frontend:{sha} + :latest
```

**镜像 tag 策略**：sha 用于回滚（精确定位版本），latest 用于开发环境快速部署。

**ruff 不需要装应用依赖**：独立 linter，只读源码不跑代码，跳过 torch 等 ~2GB 包。

## 3. Kubernetes 部署（kind 本地验证）

### 前提

```bash
# 安装 kind（Kubernetes in Docker）
choco install kind    # Windows
# 或
go install sigs.k8s.io/kind@latest

# 创建集群
kind create cluster --name smartflow

# 安装 NGINX Ingress Controller（kind 专用）
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
```

### 部署步骤

```bash
# 1. 创建 namespace
kubectl apply -f k8s/namespace.yaml

# 2. 创建 Secret（敏感信息，不入库）
kubectl create secret generic smartflow-secrets \
  --from-literal=mysql-password=你的密码 \
  --from-literal=jwt-secret=你的JWT密钥 \
  --from-literal=xiaomi-api-key=你的APIKey \
  -n smartflow

# 3. 创建 ConfigMap（非敏感配置）
kubectl apply -f k8s/configmap.yaml

# 4. 部署 MySQL + Redis
kubectl apply -f k8s/mysql/deployment.yaml
kubectl apply -f k8s/redis/deployment.yaml

# 5. 构建镜像并加载到 kind
docker build -t smartflow-backend:latest ./smartflow
docker build -t smartflow-frontend:latest ./smartflow-web
kind load docker-image smartflow-backend:latest --name smartflow
kind load docker-image smartflow-frontend:latest --name smartflow

# 6. 部署 Backend + Frontend + Ingress
kubectl apply -f k8s/backend/deployment.yaml
kubectl apply -f k8s/frontend/deployment.yaml
kubectl apply -f k8s/ingress.yaml

# 7. 验证
kubectl get pods -n smartflow
kubectl port-forward svc/frontend 8080:80 -n smartflow
open http://localhost:8080
```

### 关键设计决策

| 决策 | 原因 |
|------|------|
| Backend `replicas: 1` | 内存 job 表 + SLA 线程 + Chroma 本地目录都是进程级状态 |
| `strategy: Recreate` | ChromaDB 是本地文件，滚动更新时两个 Pod 同时写会坏 |
| liveness `/health` delay=60s | 模型加载 ~2GB 需要时间，设短了会被误杀重启循环 |
| readiness `/ready` delay=30s | 比 liveness 早就绪，先能接流量再探活 |
| Ingress `proxy_buffering: off` | SSE 流式必须关缓冲，否则前端收不到逐字输出 |

### 多副本改造路径（生产演进）

1. **ChromaDB → 远程服务**（Chroma Cloud / Qdrant / Milvus）——解除 PVC 单挂载限制
2. **内存 job 表 → Redis Hash / MySQL 表**——多 worker 共享 job 状态
3. **SLA 线程 → Redis 分布式锁**（SETNX + TTL）——只有一个 Pod 执行扫描

## 4. 环境变量说明

| 变量 | 说明 | 示例 |
|------|------|------|
| DB_HOST | MySQL 地址 | localhost / mysql（compose 内） |
| DB_USER | MySQL 用户 | root |
| MYSQL_PASSWORD | MySQL 密码 | ****** |
| DB_NAME | 数据库名 | mianshi |
| JWT_SECRET | JWT 签名密钥 | 随机 64 字符 |
| XIAOMI_API_KEY | LLM API Key | ****** |
| XIAOMI_BASE_URL | LLM API 地址 | https://api.example.com/v1 |
| REDIS_HOST | Redis 地址 | localhost / redis（compose 内） |
| CHROMA_PERSIST_DIR | 向量库持久化目录 | /app/chroma_db |
| MOCK_LLM | Mock 模式开关 | 0=真实调用 1=Mock |

**安全红线**：`.env` 不入库（`.gitignore` 排除），K8s 用 `kubectl create secret` 注入，生产可用 External Secrets Operator 或 Sealed Secrets。
