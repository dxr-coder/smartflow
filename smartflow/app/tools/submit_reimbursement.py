"""
提交报销工具

功能：帮用户提交报销单。
数据流：execute() → INSERT reimbursements → 返回报销单ID
"""

from app.database import get_db

SCHEMA = {
    "description": "帮用户提交报销申请",
    "parameters": {
        "type": "object",
        "properties": {
            "amount": {"type": "number", "description": "报销金额（元）"},
            "category": {
                "type": "string",
                "enum": ["travel", "meal", "office", "training", "other"],
                "description": "报销类别：travel=差旅, meal=餐饮, office=办公, training=培训, other=其他"
            },
            "description": {"type": "string", "description": "报销说明"}
        },
        "required": ["amount", "category", "description"]
    }
}


def execute(amount: float, category: str, description: str, request=None) -> dict:
    """提交报销"""
    user_id = getattr(request.state, "user_id", None) if request else None  # 从 request 拿登录用户
    if not user_id:
        return {"error": "未获取到用户信息"}

    if amount <= 0:
        return {"error": "金额必须大于0"}  # 挡掉脏数据

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(  # 初始状态 pending，等审批流处理
                """INSERT INTO reimbursements (user_id, amount, category, description, status)
                   VALUES (%s, %s, %s, %s, 'pending')""",
                (user_id, amount, category, description)
            )
            reimburse_id = cur.lastrowid  # 刚插入行的自增ID
            db.commit()

            return {  # 把单号和状态回给 LLM 组织回复
                "reimburse_id": reimburse_id,
                "amount": amount,
                "status": "pending",
                "message": f"已提交{amount}元{category}报销，等待审批"
            }
    finally:
        db.close()
