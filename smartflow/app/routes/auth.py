"""
认证路由

功能：定义 HTTP 接口，接收请求，调用 service 处理，返回响应。
只管 HTTP 层，不碰业务逻辑。
数据流：
  register(username, password) → 成功/失败提示
  login(username, password) → token 字典
  get_me(token) → 当前用户的 id/用户名/角色
"""
from fastapi import APIRouter, Depends, HTTPException
from app.services.auth import register, login, refresh_access
from app.deps import get_current_user
from app.database import get_db

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register")
def register_route(username: str, password: str):
    """注册新账号"""
    return register(username, password)


@router.post("/login")
def login_route(username: str, password: str):
    """登录，成功会返回 token"""
    return login(username, password)


@router.post("/refresh")
def refresh_route(payload: dict):
    """用 refresh token 换新的 access + refresh（无感续期）"""
    refresh_token = payload.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=400, detail="缺少 refresh_token")
    return refresh_access(refresh_token)


@router.get("/me")
def get_me(user=Depends(get_current_user)):
    """查当前登录用户是谁"""
    db = get_db()  # 拿一个数据库连接
    try:
        with db.cursor() as cur:
            cur.execute("""
                        SELECT u.id, u.username, r.name as role_name
                        FROM users u
                                 LEFT JOIN roles r ON u.role_id = r.id
                        WHERE u.id = %s
                        """, (user['user_id'],))  # user_id 从 token 里解析出来，不是前端传的
            return cur.fetchone()  # 返回一行：id / 用户名 / 角色名
    finally:
        db.close()  # 不管成功失败都把连接还回去
