"""
公共依赖

功能：跨路由复用的依赖函数，比如 get_current_user。
"""

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.services.auth import decode_token
from app.database import get_db
from starlette.requests import Request

security = HTTPBearer()


def get_current_user(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)):
    # HTTPBearer 自动从请求头取出 token（已剥掉 "Bearer " 前缀）
    token = credentials.credentials
    # 解出 payload，token 是假的/过期的会直接抛 401
    payload = decode_token(token)

    # 挂到 request 上，中间件记 trace 日志时取 user_id 用
    request.state.user_id = payload["user_id"]

    # token 里没带角色，查一次数据库补齐
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT r.name as role FROM users u JOIN roles r ON u.role_id = r.id WHERE u.id = %s",
                (payload["user_id"],)
            )
            row = cur.fetchone()
    finally:
        db.close()

    # 路由里用 user["user_id"] / user["role"] 直接取
    return {
        "user_id": payload["user_id"],
        "username": payload["username"],
        "role": row["role"],
    }


def require_role(role_name: str):
    """权限装饰器：先验登录，再比对角色，不符抛 403"""
    def check_role(user=Depends(get_current_user)):
        if user["role"] != role_name:
            raise HTTPException(status_code=403, detail="权限不足")
        return user

    return check_role
