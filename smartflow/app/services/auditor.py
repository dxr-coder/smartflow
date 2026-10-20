"""
审计服务

功能：敏感词检测 + 审计日志记录。
"""
from app.database import get_db

SENSITIVE_WORDS = ["辞职", "裁员", "劳动仲裁", "投诉老板", "泄露", "黑客", "病毒"]


def check_sensitive(text: str):
    """检测敏感词，命中返回词，未命中返回 None"""
    for word in SENSITIVE_WORDS:
        if word in text:
            return word
    return None

def log_audit(user_id: int, action: str, detail: str, ip: str = None):
    """写审计日志"""
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO audit_logs (user_id, action, detail, ip) VALUES (%s, %s, %s, %s)",
                (user_id, action, detail, ip),
            )
        db.commit()
    finally:
        db.close()

def get_audit_logs(page: int = 1, page_size: int = 50):
    """查询审计日志（管理员）"""
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS total FROM audit_logs")
            total = cur.fetchone()["total"]
            offset = (page - 1) * page_size
            cur.execute(
                "SELECT id, user_id, action, detail, ip, created_at FROM audit_logs ORDER BY created_at DESC LIMIT %s OFFSET %s",
                (page_size, offset),
            )
            items = cur.fetchall()
            return {"total": total, "items": items}
    finally:
        db.close()