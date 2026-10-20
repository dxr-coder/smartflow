"""
查询报销状态工具

功能：查询当前用户的报销单列表。
数据流：execute() → get_current_user() → MySQL reimbursements 表 → 返回列表
"""

from app.database import get_db

SCHEMA = {
    "description": "查询用户的报销单列表和状态",
    "parameters": {
        "type": "object",
        "properties": {},
        "required": []
    }
}


def execute(request=None) -> dict:
    """查询当前用户报销单"""
    user_id = getattr(request.state, "user_id", None) if request else None  # 从 request 拿登录用户
    if not user_id:
        return {"error": "未获取到用户信息"}  # 没登录就不查了

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(  # 只看自己的单，最近10条按时间倒序
                """SELECT id, amount, category, description, status, created_at
                   FROM reimbursements
                   WHERE user_id = %s
                   ORDER BY created_at DESC LIMIT 10""",
                (user_id,)
            )
            rows = cur.fetchall()

            result = []
            for r in rows:
                result.append({  # Decimal/日期转成 JSON 友好的类型
                    "id": r["id"],
                    "amount": float(r["amount"]),
                    "category": r["category"],
                    "description": r["description"],
                    "status": r["status"],
                    "created_at": str(r["created_at"]),
                })

            return {"reimbursements": result}
    finally:
        db.close()
