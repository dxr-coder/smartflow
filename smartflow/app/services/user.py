"""
用户管理服务

功能：管理员查看和管理用户。
"""
from app.database import get_db


def get_users():
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT u.id, u.username, r.name as role_name, u.status, u.created_at
                FROM users u
                         LEFT JOIN roles r ON u.role_id = r.id
                ORDER BY u.created_at DESC
                """
            )
            rows = cur.fetchall()
            return rows
    finally:
        db.close()


def update_user_role(user_id: int, role_name: str):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM roles WHERE name = %s", (role_name,))
            role = cur.fetchone()
            if not role:
                return {"error": f"角色 {role_name} 不存在"}
            cur.execute("UPDATE users SET role_id = %s WHERE id = %s", (role['id'], user_id))
        db.commit()
        return {"msg": f"已将用户 {user_id} 角色改为 {role_name}"}
    finally:
        db.close()


def update_user_status(user_id: int, status: str):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("UPDATE users SET status = %s WHERE id = %s", (status, user_id))
        db.commit()
        return {"msg": f"用户状态已更新为 {status}"}
    finally:
        db.close()
