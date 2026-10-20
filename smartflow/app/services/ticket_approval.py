"""
工单审批流

功能：按优先级生成多级审批链，审批决定落库，链走完自动推进工单状态。
数据流：
  建单（high/urgent） → build_approval_chain() → ticket_approvals 写待审批行
  审批人操作 → decide_approval() → 更新审批行
    → rejected：工单打成 rejected（终态）
    → approved：还有 pending 的级就等着；全通过才推 processing
  状态守卫：update_ticket_status 推 processing 前查 has_pending_approval
"""

from datetime import datetime

from fastapi import HTTPException
from app.database import get_db
from app.services.auditor import log_audit

# 审批链配置：优先级 → [(级别, 审批人角色), ...]
# low/normal 查不到，不插审批行，工单照常直接流转
APPROVAL_CHAIN = {
    "high": [(1, "agent")],
    "urgent": [(1, "agent"), (2, "admin")],
}

def build_approval_chain(cur, ticket_id: int, priority: str):
    """按优先级插待审批行。第一个参数是游标不是 db——为了和建单共用一个事务。
    low/normal 在配置里查不到，get 返回空列表，循环不执行，什么都不插。"""
    chain = APPROVAL_CHAIN.get(priority, [])
    for level, role in chain:
        cur.execute(
            """INSERT INTO ticket_approvals (ticket_id, level, approver_role)
               VALUES (%s, %s, %s)""",
            (ticket_id, level, role),
        )

def get_ticket_approvals(cur, ticket_id: int) -> list[dict]:
    """查某个工单的完整审批链，按级别排序。也传游标，方便详情接口复用。"""
    cur.execute(
        """SELECT id, ticket_id, level, approver_role, status, comment,
                  decided_by, decided_at, created_at
           FROM ticket_approvals
           WHERE ticket_id = %s
           ORDER BY level""",
        (ticket_id,),
    )
    return cur.fetchall()

def has_pending_approval(cur, ticket_id: int) -> bool:
    """这个工单还有没有没批完的级。状态守卫用。传游标同理。"""
    cur.execute(
        "SELECT COUNT(*) AS c FROM ticket_approvals WHERE ticket_id=%s AND status='pending'",
        (ticket_id,),
    )
    return cur.fetchone()["c"] > 0

def get_pending_approvals(role: str) -> list[dict]:
    """待审批列表。agent 只看自己那级（approver_role='agent'），admin 只看 admin 级。
    JOIN tickets 把工单标题/优先级带出来，前端列表直接渲染不用再查一遍。"""
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                """SELECT a.id AS approval_id, a.ticket_id, a.level, a.approver_role,
                          a.status, a.created_at AS approval_created_at,
                          t.title, t.priority, t.status AS ticket_status,
                          t.department, t.user_id AS requester_id
                   FROM ticket_approvals a
                   JOIN tickets t ON a.ticket_id = t.id
                   WHERE a.status = 'pending' AND a.approver_role = %s
                   ORDER BY FIELD(t.priority,'urgent','high','normal','low'),
                            a.created_at""",
                (role,),
            )
            return cur.fetchall()
    finally:
        db.close()

def decide_approval(ticket_id: int, level: int, user: dict, decision: str, comment: str = ""):
    """审批决定。user 是 deps 里解出来的 {'user_id':.., 'role':..}。
    四条规则：①decision 只能 approve/reject ②该级必须还是 pending
             ③审批人角色必须匹配 ④reject 打终态，approve 看链走没走完"""
    if decision not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="decision 只能是 approve 或 reject")

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                """SELECT a.*, t.status AS ticket_status, t.title
                   FROM ticket_approvals a
                   JOIN tickets t ON a.ticket_id = t.id
                   WHERE a.ticket_id = %s AND a.level = %s""",
                (ticket_id, level),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="找不到这一级审批")
            if row["status"] != "pending":
                raise HTTPException(status_code=400, detail=f"第{level}级审批已处理过，当前状态 {row['status']}")
            if user["role"] != row["approver_role"]:
                raise HTTPException(status_code=403,
                                    detail=f"第{level}级需要 {row['approver_role']} 角色审批，你是 {user['role']}")

            now = datetime.now()
            new_status = "approved" if decision == "approve" else "rejected"
            cur.execute(
                """UPDATE ticket_approvals
                   SET status=%s, comment=%s, decided_by=%s, decided_at=%s
                   WHERE id=%s""",
                (new_status, comment, user["user_id"], now, row["id"]),
            )

            if decision == "reject":
                cur.execute("UPDATE tickets SET status='rejected' WHERE id=%s", (ticket_id,))
                msg = f"第{level}级驳回，工单 #{ticket_id} 已终止"
            else:
                if has_pending_approval(cur, ticket_id):
                    msg = f"第{level}级已通过，等待上级审批"
                else:
                    # 全链通过才推进；AND status='pending' 是保险，状态被人动过就不硬推
                    cur.execute(
                        "UPDATE tickets SET status='processing' WHERE id=%s AND status='pending'",
                        (ticket_id,),
                    )
                    msg = f"第{level}级已通过，审批链完成，工单 #{ticket_id} 自动进入处理中"

        db.commit()
        # 审计放 commit 之后、独立提交：审批本身已落库，审计写失败不该把审批回滚了
        log_audit(user["user_id"],
                  f"ticket_{'approved' if decision == 'approve' else 'rejected'}",
                  f"ticket#{ticket_id} level{level}: {comment or '(无备注)'}")
        return {"msg": msg, "ticket_id": ticket_id, "level": level, "result": new_status}
    finally:
        db.close()