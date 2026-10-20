"""
限流与配额服务

功能：
  1. 令牌桶限流：普通用户 10次/分钟，防止刷接口
  2. 日配额：普通用户 50次/天，客服/管理员不限

数据流：
  请求进来 → middleware 调 check_rate_limit(user_id, role)
    → Redis 里检查当前分钟的请求次数 + 当天的请求次数
    → 超限返回 False，正常返回 True 并记录次数
"""
import time
import redis
from app.config import REDIS_HOST, REDIS_PORT, REDIS_DB

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)

# ========== 配置 ==========
RATE_LIMIT_PER_MINUTE = 10  # 普通用户每分钟最多10次
DAILY_QUOTA = 50  # 普通用户每天50次
UNLIMITED_ROLES = ("admin", "customer_service")  # 不限次数的角色


def check_rate_limit(user_id: int, role: str) -> dict:
    """
        检查用户是否超过限流/配额。

        返回：
            {"allowed": True, "remaining": 8}   → 正常，剩余8次
            {"allowed": False, "remaining": 0}  → 超限
        """
    # admin / customer_service 完全不限流
    if role in UNLIMITED_ROLES:
        return {"allowed": True, "remaining": 999}

    now = time.time()
    minute_key = f"rate:{user_id}:{int(now // 60)}"  # 每分钟一个key
    day_key = f"quota:{user_id}:{time.strftime('%Y%m%d')}"  # 每天一个key

    # 1. 分钟限流
    minute_count = r.incr(minute_key)
    r.expire(minute_key, 60)  # 60秒后自动过期
    if minute_count > RATE_LIMIT_PER_MINUTE:
        return {"allowed": False, "remaining": 0, "reason": "minute"}

    # 2. 日配额
    day_count = r.incr(day_key)
    r.expire(day_key, 86400)  # 24小时后过期
    if day_count > DAILY_QUOTA:
        return {"allowed": False, "remaining": 0, "reason": "daily"}

    remaining = min(
        RATE_LIMIT_PER_MINUTE - minute_count,
        DAILY_QUOTA - day_count
    )

    return {"allowed": True, "remaining": max(remaining, 0)}
