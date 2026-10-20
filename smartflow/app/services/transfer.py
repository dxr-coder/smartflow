"""
转接业务逻辑

功能：工单转接的发起、查询、接受、拒绝、候选坐席。
状态机：waiting（待接受）→ connected（已接受）/ declined（已拒绝），后两者是终态。
数据流：
  发起 → 校验工单在办 + 接收人是坐席 + 无重复待接受 → INSERT
  查询 → JOIN 工单标题/状态 + 转出人/接收人姓名，scope=mine|out|all
  接受 → 抢锁式 UPDATE（WHERE status='waiting' AND agent_id=我），防并发双接
  拒绝 → 同上，落终态 declined
"""
from fastapi import HTTPException
from app.database import get_db

# 这些状态的工单没有在办意义，不允许再转接
CLOSED_TICKET = ("resolved", "closed", "rejected")


def _get_ticket(cur, ticket_id):
    cur.execute("SELECT id, title, status FROM tickets WHERE id=%s", (ticket_id,))
    return cur.fetchone()


def create_transfer(ticket_id, user_id, target_agent_id, reason=""):
    if not target_agent_id:
        raise HTTPException(400, "请选择接收人")
    db = get_db()
    try:
        with db.cursor() as cur:
            ticket = _get_ticket(cur, ticket_id)
            if not ticket:
                raise HTTPException(404, "工单不存在")
            if ticket["status"] in CLOSED_TICKET:
                raise HTTPException(400, "工单已结束，无需转接")
            if target_agent_id == user_id:
                raise HTTPException(400, "不能转接给自己")
            # 接收人必须是坐席或管理员
            cur.execute(
                """SELECT u.id FROM users u JOIN roles r ON u.role_id = r.id
                   WHERE u.id = %s AND r.name IN ('agent','admin')""",
                (target_agent_id,),
            )
            if not cur.fetchone():
                raise HTTPException(400, "接收人必须是坐席或管理员")
            # 同一张工单只允许一条待接受的转接，防重复发起
            cur.execute(
                "SELECT id FROM transfer_sessions WHERE ticket_id = %s AND status = 'waiting'",
                (ticket_id,),
            )
            if cur.fetchone():
                raise HTTPException(409, "该工单已有一条待接受的转接")
            cur.execute(
                "INSERT INTO transfer_sessions (ticket_id, user_id, agent_id, reason) VALUES (%s,%s,%s,%s)",
                (ticket_id, user_id, target_agent_id, reason),
            )
            transfer_id = cur.lastrowid
        db.commit()
        return {"msg": "转接请求已提交", "transfer_id": transfer_id}
    finally:
        db.close()


def get_transfers(user, scope="mine", status=""):
    """scope: mine=转给我的（默认） / out=我发起的 / all=全部（仅坐席/管理员）"""
    db = get_db()
    try:
        with db.cursor() as cur:
            sql = """SELECT t.id, t.ticket_id, t.reason, t.status, t.created_at, t.updated_at,
                            tk.title AS ticket_title, tk.status AS ticket_status,
                            fu.username AS from_name, tu.username AS to_name
                     FROM transfer_sessions t
                     JOIN tickets tk ON t.ticket_id = tk.id
                     LEFT JOIN users fu ON t.user_id = fu.id
                     LEFT JOIN users tu ON t.agent_id = tu.id
                     WHERE 1=1"""
            args = []
            if scope == "mine":
                sql += " AND t.agent_id = %s"
                args.append(user["user_id"])
            elif scope == "out":
                sql += " AND t.user_id = %s"
                args.append(user["user_id"])
            elif scope == "all":
                if user["role"] not in ("agent", "admin"):
                    raise HTTPException(403, "权限不足")
            else:
                raise HTTPException(400, "scope 只支持 mine/out/all")
            if status:
                sql += " AND t.status = %s"
                args.append(status)
            # 待接受排最前面，方便马上处理
            sql += " ORDER BY FIELD(t.status,'waiting','connected','declined'), t.id DESC"
            cur.execute(sql, args)
            return cur.fetchall()
    finally:
        db.close()


def get_transfer_agents(user):
    """转接弹窗的候选接收人：坐席 + 管理员，排除自己"""
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                """SELECT u.id, u.username, r.name AS role_name
                   FROM users u JOIN roles r ON u.role_id = r.id
                   WHERE r.name IN ('agent','admin') AND u.id != %s
                   ORDER BY r.name, u.id""",
                (user["user_id"],),
            )
            return cur.fetchall()
    finally:
        db.close()


def _raise_not_acceptable(cur, transfer_id, user, action):
    """抢锁没抢到时，把真实原因翻译成中文：不存在 / 不归你 / 已被处理"""
    cur.execute("SELECT status, agent_id FROM transfer_sessions WHERE id = %s", (transfer_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "转接记录不存在")
    if row["agent_id"] != user["user_id"]:
        raise HTTPException(403, "这不是转接给你的工单")
    raise HTTPException(400, f"这条转接已经被处理过了，没法再{action}")


def accept_transfer(transfer_id, user):
    """仅接收人本人可接受。抢锁式 UPDATE：谁影响 1 行谁接成，防并发双接。"""
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                """UPDATE transfer_sessions SET status = 'connected', updated_at = NOW()
                   WHERE id = %s AND status = 'waiting' AND agent_id = %s""",
                (transfer_id, user["user_id"]),
            )
            if cur.rowcount == 0:
                _raise_not_acceptable(cur, transfer_id, user, "接受")
        db.commit()
        return {"msg": "已接受转接"}
    finally:
        db.close()


def decline_transfer(transfer_id, user):
    """仅接收人本人可拒绝，和接受同一套抢锁。"""
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                """UPDATE transfer_sessions SET status = 'declined', updated_at = NOW()
                   WHERE id = %s AND status = 'waiting' AND agent_id = %s""",
                (transfer_id, user["user_id"]),
            )
            if cur.rowcount == 0:
                _raise_not_acceptable(cur, transfer_id, user, "拒绝")
        db.commit()
        return {"msg": "已拒绝该转接"}
    finally:
        db.close()
