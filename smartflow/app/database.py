"""
数据库连接

功能：提供统一的数据库连接函数，其他模块需要连数据库就调 get_db()。
"""

import pymysql
from app.config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME


def get_db():
    """
    创建一个 MySQL 连接

    返回：pymysql.Connection 对象
    调用方用完必须 close()
    """
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset='utf8mb4',
        # 返回字典而不是元组，查询结果可以直接 row["username"] 取值
        cursorclass=pymysql.cursors.DictCursor,
    )
