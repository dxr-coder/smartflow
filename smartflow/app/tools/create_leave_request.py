"""
创建请假申请工具

功能：帮用户提交请假申请。
数据流：execute() → 检查余额 → INSERT leave_requests → 返回申请ID
"""

from app.database import get_db

SCHEMA = {
    "description": "帮用户提交请假申请",
    "parameters": {
        "type": "object",
        "properties": {
            "leave_type": {
                "type": "string",
                "enum": ["annual", "sick", "comp", "personal"],
                "description": "请假类型：annual=年假, sick=病假, comp=调休, personal=事假"
            },
            "start_date": {"type": "string", "format": "date", "description": "开始日期 YYYY-MM-DD"},
            "end_date": {"type": "string", "format": "date", "description": "结束日期 YYYY-MM-DD"},
            "reason": {"type": "string", "description": "请假原因"}
        },
        "required": ["leave_type", "start_date", "end_date", "reason"]
    }
}


def execute(leave_type: str, start_date: str, end_date: str, reason: str, request=None) -> dict:
    """创建请假申请"""
    user_id = getattr(request.state, "user_id", None) if request else None  # 从 request 拿登录用户
    if not user_id:
        return {"error": "未获取到用户信息"}

    # 计算天数
    from datetime import datetime  # 用到才导，避免顶层多占
    d1 = datetime.strptime(start_date, "%Y-%m-%d")
    d2 = datetime.strptime(end_date, "%Y-%m-%d")
    days = (d2 - d1).days + 1  # 包含首尾

    if days <= 0:
        return {"error": "结束日期必须大于等于开始日期"}  # 日期写反了

    db = get_db()
    try:
        with db.cursor() as cur:
            # 检查余额（年假和调休需要检查）
            if leave_type in ("annual", "comp"):
                cur.execute(
                    "SELECT annual_leave, comp_leave FROM leave_balances WHERE user_id = %s",
                    (user_id,)
                )
                balance = cur.fetchone()
                if balance:
                    available = balance["annual_leave"] if leave_type == "annual" else balance["comp_leave"]  # 按假种取对应余额
                    if days > float(available):
                        return {"error": f"余额不足，当前剩余{available}天，申请{days}天"}  # 余额不够直接打回

            # 创建申请
            cur.execute(  # 病假/事假不查余额，直接建单；状态 pending 等审批
                """INSERT INTO leave_requests (user_id, leave_type, start_date, end_date, days, reason, status)
                   VALUES (%s, %s, %s, %s, %s, %s, 'pending')""",
                (user_id, leave_type, start_date, end_date, days, reason)
            )
            request_id = cur.lastrowid  # 刚插入行的自增ID
            db.commit()

            return {  # 天数和状态回给 LLM 组织回复
                "request_id": request_id,
                "days": days,
                "status": "pending",
                "message": f"已提交{days}天{leave_type}假申请，等待审批"
            }
    finally:
        db.close()
