"""
认证业务逻辑

功能：密码加密/校验、JWT Token 生成/解析、注册/登录核心逻辑。
不碰 HTTP 请求，纯函数。

数据流：
  hash_password(明文) → 哈希字符串
  verify_password(明文, 哈希) → True/False
  create_token(user_id, username) → token字符串
  decode_token(token) → payload字典
  register(username, password) → 成功/失败
  login(username, password) → token字典
"""

import jwt
import bcrypt
from datetime import datetime, timedelta
from fastapi import HTTPException

from app.config import JWT_SECRET, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS
from app.database import get_db


def hash_password(password: str) -> str:
    # bcrypt 会自动加随机盐，同一个密码两次哈希结果也不同
    hashword = bcrypt.hashpw(password.encode(encoding='utf8'), bcrypt.gensalt())
    return hashword.decode('utf8')


def verify_password(password: str, password_hash: str) -> bool:
    # 拿明文和库里存的哈希做校验，库里不存明文
    return bcrypt.checkpw(password.encode(encoding='utf8'), password_hash.encode(encoding='utf8'))


def create_token(user_id: int, username: str, token_type: str = "access", ver: int = 0) -> str:
    # 把用户信息打包塞进 JWT，签名后返回 token 字符串
    payload = {
        "user_id": user_id, "username": username
    }
    # access 短期（分钟级），refresh 长期（天级），过期时间写进 payload 的 exp 字段
    if token_type == 'access':
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        payload['exp'] = expire
    else:
        # refresh 要带当前用户的 token_version，刷新时用它判断是不是最新一代
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        payload['exp'] = expire
        payload['ver'] = ver
        payload['token_type'] = 'refresh'

    # 用密钥签名，防伪造；算法用 config 里配的
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token



def decode_token(token: str) -> dict:
    # 解签名验真伪 + 查过期时间，两种失败分开报错方便前端区分
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token 已过期")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token 无效")


def register(username: str, password: str):
    db = get_db()
    try:
        with db.cursor() as cur:
            # 先查用户名是否被占用，撞车直接打回
            cur.execute("SELECT id FROM users WHERE username = %s", (username,))
            if cur.fetchone():
                raise HTTPException(status_code=400, detail="用户名已存在")

            # 密码哈希后再入库，库里永远见不到明文
            password_h = hash_password(password)
            cur.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s) ", (username, password_h))
        db.commit()
        return {"msg": "注册成功", "username": username}
    finally:
        db.close()


def login(username: str, password: str):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE username = %s", (username,))
            user = cur.fetchone()

        # 用户不存在和密码错误报同一句话，防用户名枚举攻击
        if not user:
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        if not verify_password(password, user['password_hash']):
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        # 同时发两个 token：短的日常用，长的用来换新的短的
        # refresh 带上用户当前 token_version，刷新时判断是否最新一代
        ver = user.get('token_version', 0)
        access_token = create_token(user['id'], user['username'], token_type='access')
        refresh_token = create_token(user['id'], user['username'], token_type='refresh', ver=ver)
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",  # 前端 Authorization 头要拼成 "Bearer <token>"
        }
    finally:
        db.close()

def refresh_access(refresh_token: str):
    """
    用 refresh token 换新的 access + refresh（轮换 + 复用检测）
    核心：refresh 里带 ver，与库里 token_version 对比。
      对得上 → 递增版本（作废旧 refresh），发新 access + 新 refresh
      对不上 → 该 refresh 已作废还在用，可能被盗，强制吊销所有 token
    """
    # decode_token 会校验签名和过期，失败抛 401；取出 user_id 和 ver
    payload = decode_token(refresh_token)
    if payload.get('token_type') != 'refresh':
        raise HTTPException(status_code=401, detail="非 refresh token")
    user_id = payload['user_id']
    ver = payload.get('ver', 0)

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id, username, token_version FROM users WHERE id = %s", (user_id,))
            user = cur.fetchone()
            if not user:
                raise HTTPException(status_code=401, detail="用户不存在")

            if ver != user['token_version']:
                # 复用检测：这个 refresh 已作废还在用，强制递增吊销所有 token
                cur.execute("UPDATE users SET token_version = token_version + 1 WHERE id = %s", (user_id,))
                db.commit()
                raise HTTPException(status_code=401, detail="refresh token 已失效，请重新登录")

            # 合法：递增版本号，作废旧 refresh
            new_ver = user['token_version'] + 1
            cur.execute("UPDATE users SET token_version = %s WHERE id = %s", (new_ver, user_id))
        db.commit()

        # 发新 access + 新 refresh（新 refresh 带新 ver，旧的因版本对不上而作废）
        access_token = create_token(user['id'], user['username'], token_type='access')
        refresh_token_new = create_token(user['id'], user['username'], token_type='refresh', ver=new_ver)
        return {
            "access_token": access_token,
            "refresh_token": refresh_token_new,
            "token_type": "bearer",
        }
    finally:
        db.close()


