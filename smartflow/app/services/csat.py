"""
CSAT 满意度服务

功能：工单评分的提交、查询、汇总。
规则：一单一评（csat_ratings.ticket_id UNIQUE 兜底）；评分人必须是工单
  提交人本人；只有 resolved/closed 状态的工单能评。
数据流：
  submit_csat()  → 校验 400/404/403 → INSERT（撞唯一键翻译成 409）
  get_csat()     → 返回已有评分或 None（前端"已评价"初始态）
  get_csat_stats() → 均分 + top-2-box%（4-5星占比，行业口径）+ 1-5 分布
"""
from fastapi import HTTPException
import pymysql
from app.database import get_db


def submit_csat(ticket_id: int, user: dict, score: int, comment: str = ""):
    if score not in (1, 2, 3, 4, 5):
        raise HTTPException(400, "评分必须是 1-5 的整数")
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id, status, user_id FROM tickets WHERE id=%s", (ticket_id,))
            ticket = cur.fetchone()
            if not ticket:
                raise HTTPException(404, "工单不存在")
            if ticket["status"] not in ("resolved", "closed"):
                raise HTTPException(400, "工单还没解决，暂时不能评分")
            if ticket["user_id"] != user["user_id"]:
                raise HTTPException(403, "只有工单提交人可以评分")
            try:
                cur.execute(
                    "INSERT INTO csat_ratings (ticket_id, user_id, score, comment) VALUES (%s,%s,%s,%s)",
                    (ticket_id, user["user_id"], score, comment),
                )
                rating_id = cur.lastrowid
            except pymysql.err.IntegrityError:
                # ticket_id 是 UNIQUE，撞了就是重复评分
                raise HTTPException(409, "这张工单已经评过分了")
        db.commit()
        return {"msg": "评分成功", "rating_id": rating_id}
    finally:
        db.close()


def get_csat(ticket_id: int):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT id, ticket_id, user_id, score, comment, created_at FROM csat_ratings WHERE ticket_id=%s",
                (ticket_id,),
            )
            return cur.fetchone()
    finally:
        db.close()


def get_csat_stats():
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) AS count, AVG(score) AS avg_score,
                       SUM(score >= 4) AS top2_count
                FROM csat_ratings
            """)
            row = cur.fetchone() or {"count": 0, "avg_score": None, "top2_count": 0}
            cur.execute("SELECT score, COUNT(*) AS n FROM csat_ratings GROUP BY score")
            dist = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            for r in cur.fetchall():
                dist[r["score"]] = r["n"]
            count = row["count"]
            return {
                "count": count,
                "avg": round(float(row["avg_score"]), 2) if row["avg_score"] is not None else None,
                # top-2-box：行业标准口径，4-5 星才算"满意"
                "top2_pct": round(row["top2_count"] / count * 100, 1) if count else 0,
                "dist": dist,
            }
    finally:
        db.close()
