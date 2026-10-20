"""
数据库连接管理 — DBUtils 连接池版

功能：管理 MySQL 连接，用连接池复用连接而不是每个请求新建。
数据流向：全局 PooledDB 单例 → get_db() 从池里借连接 → 调用方 close() 归还（不真断开）。

为什么用连接池：
旧版每个请求 pymysql.connect() 新建连接、用完销毁，一个请求 2+ 次 DB 调用
= 2+ 次 TCP 握手 + 认证。压测时 MySQL 连接数直接打爆。
连接池：启动时建好 minconnections 个连接，请求来了借走、用完还回来，复用不断开。
"""
import os
from dbutils.pooled_db import PooledDB
import pymysql

_pool = None


def _get_pool():
    """懒加载连接池单例（第一次用时创建，之后复用）"""
    global _pool
    if _pool is None:
        _pool = PooledDB(
            creator=pymysql,          # 底层用 pymysql 驱动
            maxconnections=20,        # 池里最多 20 个连接（压测并发别超过这个数）
            host=os.getenv("DB_HOST", "localhost"),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("MYSQL_PASSWORD", ""),
            database=os.getenv("DB_NAME", "mianshi"),
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            blocking=True,            # 池满时等待而不是直接报错
            maxusage=None,            # 连接可无限复用（不自动断开）
            ping=1,                   # 取连接时先 SELECT 1 探活，断了自动重连
        )
    return _pool


def get_db():
    """从池里取连接；调用方必须 close() 归还（不是真断开，是还回池里）
    40+ 个调用点不用改——.cursor()/.commit()/.rollback()/.close() 接口完全兼容
    """
    return _get_pool().connection()
