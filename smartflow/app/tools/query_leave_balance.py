"""
查询假期余额工具

功能：查询当前登录用户的年假、病假、调休余额。
数据流：execute() → get_current_user() → MySQL leave_balances 表 → 返回余额
"""
from app.database import get_db
from app.deps import get_current_user
from fastapi import Request

SCHEMA = {
    "description": "查询用户的年假、病假、调休余额",
    "parameters": {
        "type": "object",
        "properties": {},
        "required": []
    }
}


def execute(request: Request = None) -> dict:
    """查询当前用户假期余额"""
    # 这里简化处理：从 request 或全局获取 user_id
    # 实际项目中可以通过上下文传递
    user_id = getattr(request.state, "user_id", None) if request else None  # 从注入的 request 拿登录用户
    if not user_id:
        return {"error": "未获取到用户信息"}  # 没登录就不查了

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(  # 按 user_id 查余额表
                "SELECT annual_leave, sick_leave, comp_leave FROM leave_balances WHERE user_id = %s",
                (user_id,)
            )
            row = cur.fetchone()
            if row:
                return {  # Decimal 转 float，方便 JSON 序列化
                    "annual_leave": float(row["annual_leave"]),
                    "sick_leave": float(row["sick_leave"]),
                    "comp_leave": float(row["comp_leave"]),
                }
            else:
                # 没有记录，返回默认值
                return {"annual_leave": 0, "sick_leave": 0, "comp_leave": 0}
    finally:
        db.close()
