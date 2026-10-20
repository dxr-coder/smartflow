"""
反馈服务

功能：保存用户对 AI 回复的点赞/点踩，统计反馈数据。
"""
from app.database import get_db

def save_feedback(conversation_id: int, user_id: int, rating: int, agent_name: str, message_id: int = None):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO feedback (conversation_id, message_id, user_id, rating, agent_name) VALUES (%s, %s, %s, %s, %s)",
                (conversation_id, message_id, user_id, rating, agent_name),
            )
        db.commit()
        return {"msg": "反馈已保存"}
    finally:
        db.close()


def get_feedback_stats():
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) AS total, SUM(rating=1) AS likes, SUM(rating=0) AS dislikes
                FROM feedback
            """)
            overall = cur.fetchone()

            cur.execute("""
                SELECT agent_name, COUNT(*) AS total, SUM(rating=1) AS likes, SUM(rating=0) AS dislikes
                FROM feedback GROUP BY agent_name ORDER BY total DESC
            """)
            by_agent = cur.fetchall()

            return {"overall": overall, "by_agent": by_agent}
    finally:
        db.close()
