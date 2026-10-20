"""
创建工单工具

功能：AI 主动创建工单（转人工时用）。
数据流：execute() → INSERT tickets → 返回工单号
"""

from app.database import get_db
import time

SCHEMA = {
    "description": "创建工单，当AI无法解决问题需要转人工时使用",
    "parameters": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "工单标题"},
            "description": {"type": "string", "description": "问题描述"},
            "category": {
                "type": "string",
                "enum": ["it", "hr", "finance", "admin"],
                "description": "所属部门：it=IT, hr=人事, finance=财务, admin=行政"
            },
            "priority": {
                "type": "string",
                "enum": ["low", "normal", "high", "urgent"],
                "description": "优先级，默认normal"
            }
        },
        "required": ["title", "description", "category"]
    }
}


def execute(title: str, description: str, category: str, priority: str = "normal", request=None) -> dict:
    """创建工单"""
    user_id = getattr(request.state, "user_id", None) if request else None  # 从 request 拿登录用户
    if not user_id:
        return {"error": "未获取到用户信息"}

    # 计算 SLA 截止时间
    sla_hours = {"urgent": 4, "high": 8, "normal": 24, "low": 48}  # 优先级→响应时限小时数
    hours = sla_hours.get(priority, 24)  # 没匹配上按 normal 24小时
    sla_deadline = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() + hours * 3600))  # 当前时间+小时数

    from app.services.ticket_approval import build_approval_chain  # 建完单顺手挂审批链

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(  # 写 tickets 表；category 和 department 都填同一个部门值
                """INSERT INTO tickets (user_id, title, content, category, department, priority, sla_deadline)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (user_id, title, description, category, category, priority, sla_deadline)
            )
            ticket_id = cur.lastrowid  # 刚插入行的自增ID
            build_approval_chain(cur, ticket_id, priority)
            db.commit()

            return {  # 把 SLA 信息一并告诉调用方
                "ticket_id": ticket_id,
                "priority": priority,
                "sla_deadline": sla_deadline,
                "message": f"已创建{category}工单（#{ticket_id}），优先级{priority}，{hours}小时内响应"
            }
    finally:
        db.close()
