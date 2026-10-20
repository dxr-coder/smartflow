"""
配置管理

功能：从 .env 读取所有环境变量，集中定义项目常量。
其他模块需要配置时，统一从这里 import。
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ========== 数据库 ==========
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("MYSQL_PASSWORD")
DB_NAME = os.getenv("DB_NAME", "mianshi")

# ========== JWT ==========
JWT_SECRET = os.getenv("JWT_SECRET", "smartflow-jwt-secret-key-2026-xK9mP2vL8nQ4wR7tY3bJ6hF1")

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# ========== LLM ==========
XIAOMI_API_KEY = os.getenv("XIAOMI_API_KEY")
XIAOMI_BASE_URL = os.getenv("XIAOMI_BASE_URL")

# ========== Embedding ==========
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

# ========== 限流 ==========
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", 10))
DAILY_QUOTA = int(os.getenv("DAILY_QUOTA", 50))

# ========== 模型路由 ==========
# 三档模型默认都指向 mimo-v2.5（当前只有小米端点）；
# 以后接入别的供应商，改对应环境变量即可，代码零改动。
# 例：ROUTER_FAST_MODEL=MiMo-7B-RL  ROUTER_SMART_MODEL=mimo-v2.5
ROUTER_FAST_MODEL = os.getenv("ROUTER_FAST_MODEL", "mimo-v2.5")
ROUTER_SMART_MODEL = os.getenv("ROUTER_SMART_MODEL", "mimo-v2.5")
ROUTER_BACKUP_MODEL = os.getenv("ROUTER_BACKUP_MODEL", "mimo-v2.5")

# 每档可覆盖 base_url / api_key，不填则复用小米配置
ROUTER_FAST_BASE_URL = os.getenv("ROUTER_FAST_BASE_URL", XIAOMI_BASE_URL)
ROUTER_SMART_BASE_URL = os.getenv("ROUTER_SMART_BASE_URL", XIAOMI_BASE_URL)
ROUTER_BACKUP_BASE_URL = os.getenv("ROUTER_BACKUP_BASE_URL", XIAOMI_BASE_URL)

ROUTER_FAST_API_KEY = os.getenv("ROUTER_FAST_API_KEY", XIAOMI_API_KEY)
ROUTER_SMART_API_KEY = os.getenv("ROUTER_SMART_API_KEY", XIAOMI_API_KEY)
ROUTER_BACKUP_API_KEY = os.getenv("ROUTER_BACKUP_API_KEY", XIAOMI_API_KEY)

