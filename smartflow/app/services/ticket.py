"""
工单业务逻辑

功能：工单的创建、查询、状态流转。
"""
from datetime import datetime

from fastapi import HTTPException
from app.database import get_db
import time  # create_ticket 算 SLA 截止时间用
from app.services.ticket_approval import build_approval_chain, has_pending_approval, get_ticket_approvals

# 优先级 → SLA 时长（小时）
SLA_HOURS = {"urgent": 4, "high": 8, "normal": 24, "low": 48}


def create_ticket(user_id: int, title: str, content: str = "",
                  category: str = None, department: str = None, priority: str = "normal"):
    """建单：写 tickets 行 → 高优先级顺手建审批链（同一个事务）。"""
    if priority not in SLA_HOURS:
        priority = "normal"  # 防御：乱传的值按普通处理
    department = department or category  # 没单独传部门就用 category
    hours = SLA_HOURS[priority]
    sla_deadline = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() + hours * 3600))

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                """INSERT INTO tickets (user_id, title, content, category, department, priority, sla_deadline)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (user_id, title, content, category, department, priority, sla_deadline)
            )
            ticket_id = cur.lastrowid
            build_approval_chain(cur, ticket_id, priority)  # 同一个 cur，同一个事务
        db.commit()
        return {"msg": "工单创建成功", "ticket_id": ticket_id,
                "priority": priority, "sla_deadline": sla_deadline}
    finally:
        db.close()


def get_ticket(user_id: int, role: str):
    db = get_db()
    try:
        with db.cursor() as cur:
            if role == "user":
                cur.execute("SELECT * FROM tickets WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
            else:
                cur.execute("SELECT * FROM tickets ORDER BY created_at DESC")
            return cur.fetchall()
    finally:
        db.close()


def get_ticket_detail(ticket_id: int, user_id: int, role: str):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT * FROM tickets WHERE id = %s", (ticket_id,))
            ticket = cur.fetchone()
            # 审批链一起带回，前端详情页直接渲染时间线
            ticket["approvals"] = get_ticket_approvals(cur, ticket_id)
        if not ticket:
            raise HTTPException(status_code=404, detail="工单不存在")
        if role == "user" and ticket["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="无权查看此工单")

        return ticket

    finally:
        db.close()


STATUS_FLOW = {
    "pending": "processing",
    "processing": "resolved",
    "resolved": "closed",
}


def update_ticket_status(ticket_id: int, new_status: str):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT status FROM tickets WHERE id = %s", (ticket_id,))
            ticket = cur.fetchone()
            if not ticket:
                raise HTTPException(status_code=404, detail="工单不存在")

            current = ticket["status"]
            expected_next = STATUS_FLOW.get(current)
            if new_status != expected_next:
                raise HTTPException(status_code=400,
                                    detail=f"不能从 {current} 变成 {new_status}，只能变成 {expected_next}")

            # 审批守卫：想推进到处理中，但还有没批完的级 → 拦下
            if new_status == "processing" and has_pending_approval(cur, ticket_id):
                raise HTTPException(status_code=400, detail="还有审批未完成，审批通过后才能开始处理")

            cur.execute("UPDATE tickets SET status = %s WHERE id = %s", (new_status, ticket_id))
        db.commit()
        return {"msg": f"状态已更新为 {new_status}"}
    finally:
        db.close()


def _sla_summary(ticket: dict) -> dict:
    """给单个工单算 SLA 剩余时间/状态。"""
    if not ticket.get("sla_deadline"):
        return {"sla_status": "none"}
    now = datetime.now()
    deadline = ticket["sla_deadline"]
    created = ticket["created_at"]
    total = (deadline - created).total_seconds()
    remain = (deadline - now).total_seconds()

    if ticket.get("escalated"):
        status = "escalated"
    elif remain <= 0:
        status = "breached"
    elif remain < total * 0.25:
        status = "warning"
    else:
        status = "ok"

    return {
        "sla_status": status,
        "sla_remain_hours": round(remain / 3600, 1),
        "sla_deadline": str(deadline),
    }


def get_sla_status(ticket_id: int, user_id: int, role: str) -> dict:
    """查看工单 SLA 状态 + 升级事件历史。"""
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT * FROM tickets WHERE id = %s", (ticket_id,))
            ticket = cur.fetchone()
            if not ticket:
                raise HTTPException(status_code=404, detail="工单不存在")
            if role == "user" and ticket["user_id"] != user_id:
                raise HTTPException(status_code=403, detail="无权查看")

            cur.execute(
                "SELECT * FROM sla_events WHERE ticket_id = %s ORDER BY created_at",
                (ticket_id,),
            )
            events = cur.fetchall()

        return {
            "ticket_id": ticket_id,
            **_sla_summary(ticket),
            "events": events,
        }
    finally:
        db.close()


def trigger_sla_check() -> dict:
    """手动触发一次 SLA 扫描（管理后台/演示用）。"""
    from app.services.sla_engine import check_sla
    return check_sla()
