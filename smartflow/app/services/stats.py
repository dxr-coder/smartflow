"""
数据统计服务

功能：聚合对话、工单等数据，供管理后台看板使用。
"""
from app.database import get_db


def get_overview():
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS cnt FROM conversations")
            total_conversations = cur.fetchone()['cnt']

            cur.execute("SELECT COUNT(*) AS cnt FROM tickets")
            total_tickets = cur.fetchone()['cnt']

            cur.execute("SELECT COUNT(*) AS cnt FROM users")
            total_users = cur.fetchone()['cnt']

            cur.execute("SELECT COUNT(*) AS cnt FROM documents")
            total_documents = cur.fetchone()['cnt']

            cur.execute("""
                        SELECT ROUND(
                                       COUNT(CASE WHEN status = 'resolved' THEN 1 END) * 100.0
                                           / NULLIF(COUNT(*), 0), 1
                               ) AS rate
                        FROM tickets
                        """)
            ai_resolve_rate = cur.fetchone()['rate'] or 0

            cur.execute("SELECT COUNT(*) AS cnt FROM conversations WHERE DATE(created_at) = CURDATE()")
            today_conversations = cur.fetchone()['cnt']

            cur.execute("SELECT COUNT(*) AS cnt FROM tickets WHERE DATE(created_at) = CURDATE()")
            today_tickets = cur.fetchone()['cnt']
        return {
            "total_conversations": total_conversations,
            "total_tickets": total_tickets,
            "total_users": total_users,
            "total_documents": total_documents,
            "ai_resolve_rate": float(ai_resolve_rate),
            "today_conversations": today_conversations,
            "today_tickets": today_tickets,
        }
    finally:
        db.close()


def get_trends(days: int = 7):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""
                        SELECT DATE(created_at) AS dt, COUNT(*) AS cnt
                        FROM conversations
                        WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                        GROUP BY dt
                        ORDER BY dt
                        """, (days - 1,))
            conv_rows = cur.fetchall()

            cur.execute("""
                        SELECT DATE(created_at) AS dt, COUNT(*) AS cnt
                        FROM tickets
                        WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                        GROUP BY dt
                        ORDER BY dt
                        """, (days - 1,))
            ticket_rows = cur.fetchall()

        # 转成前端方便用的格式
        conv_map = {str(r['dt']): r['cnt'] for r in conv_rows}
        ticket_map = {str(r['dt']): r['cnt'] for r in ticket_rows}

        from datetime import date, timedelta
        today = date.today()
        dates = [(today - timedelta(days=days - 1 - i)).isoformat() for i in range(days)]

        return {
            "dates": dates,
            "conversations": [conv_map.get(d, 0) for d in dates],
            "tickets": [ticket_map.get(d, 0) for d in dates],
        }
    finally:
        db.close()
