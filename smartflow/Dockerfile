# ========== SmartFlow 后端镜像（多阶段构建） ==========
#
# 功能：把后端打包成生产级 Docker 镜像
# 用法：docker build -t smartflow-backend .
# 数据流：requirements.txt → builder 阶段装依赖 → runtime 阶段精简运行 + 预下载模型
#
# 设计决策：
# - 多阶段构建：builder 装依赖（含编译工具链），runtime 只拷 site-packages，减小镜像
# - 模型预下载：构建时拉 sentence-transformers 模型，Pod 启动 30s 内 ready（不用等下载）
# - non-root：appuser 运行，不给容器 root 权限
# - healthcheck：Docker 层面的健康检查（K8s 用 liveness/readiness 探针，不依赖这个）

# ---------- Stage 1: builder（装依赖） ----------
FROM python:3.11-slim AS builder

WORKDIR /app

# 先拷 requirements.txt（利用 Docker 层缓存：依赖不变则不重装）
COPY requirements.txt .

# 装依赖到 /install（独立目录，方便 Stage 2 整体拷贝）
# 不指定镜像源：GitHub Actions 海外服务器连不上清华镜像，用官方 PyPI
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---------- Stage 2: runtime（精简运行时） ----------
FROM python:3.11-slim

WORKDIR /app

# 建非 root 用户
RUN useradd -m appuser

# 从 builder 拷贝 Python 包（不含 pip/setuptools 本身，只拷 site-packages + bin 脚本）
COPY --from=builder /install /usr/local

# 拷贝应用代码（.dockerignore 排除 chroma_db/logs/.env 等）
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY docs/knowledge/ ./docs/knowledge/

# 预下载 Embedding 模型（~400MB）+ Reranker 模型（~1.1GB）
# 构建时下载，避免运行时冷启动等模型拉取
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-zh-v1.5')"
RUN python -c "from sentence_transformers import CrossEncoder; CrossEncoder('BAAI/bge-reranker-base')"

# 切到非 root 用户
USER appuser

EXPOSE 8000

# Docker 层健康检查（K8s 不用这个，用 liveness/readiness 探针）
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)"

# 启动命令：uvicorn 单进程
# --proxy-headers：信任反代（nginx）传来的 X-Forwarded-* 头
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
