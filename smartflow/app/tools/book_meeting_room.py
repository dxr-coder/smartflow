"""
预订会议室工具

功能：帮用户预订会议室。
数据流：execute() → 检查冲突 → INSERT room_bookings → 返回预订ID
"""

from app.database import get_db

SCHEMA = {
    "description": "帮用户预订会议室",
    "parameters": {
        "type": "object",
        "properties": {
            "room_id": {"type": "integer", "description": "会议室ID"},
            "book_date": {"type": "string", "format": "date", "description": "预订日期 YYYY-MM-DD"},
            "start_time": {"type": "string", "description": "开始时间 HH:MM"},
            "end_time": {"type": "string", "description": "结束时间 HH:MM"},
            "purpose": {"type": "string", "description": "会议目的"}
        },
        "required": ["room_id", "book_date", "start_time", "end_time", "purpose"]
    }
}


def execute(room_id: int, book_date: str, start_time: str, end_time: str, purpose: str, request=None) -> dict:
    """预订会议室"""
    user_id = getattr(request.state, "user_id", None) if request else None  # 从 request 拿登录用户
    if not user_id:
        return {"error": "未获取到用户信息"}

    db = get_db()
    try:
        with db.cursor() as cur:
            # 检查时段冲突
            cur.execute(  # 新时段和已有预订有交叉就算冲突（含完全包含/被包含）
                """SELECT COUNT(*) as cnt FROM room_bookings
                   WHERE room_id = %s AND book_date = %s AND status != 'cancelled'
                   AND ((start_time < %s AND end_time > %s) OR (start_time < %s AND end_time > %s) OR (start_time >= %s AND end_time <= %s))""",
                (room_id, book_date, end_time, start_time, start_time, end_time, start_time, end_time)
            )
            conflict = cur.fetchone()["cnt"]

            if conflict > 0:
                return {"error": "该时段已被预订，请选择其他时间"}  # 直接拒绝，让用户换时间

            # 创建预订
            cur.execute(  # 冲突检查过了才写库，状态直接 confirmed
                """INSERT INTO room_bookings (room_id, user_id, book_date, start_time, end_time, purpose, status)
                   VALUES (%s, %s, %s, %s, %s, %s, 'confirmed')""",
                (room_id, user_id, book_date, start_time, end_time, purpose)
            )
            booking_id = cur.lastrowid  # 刚插入行的自增ID
            db.commit()

            return {  # 把预订时段回显给用户确认
                "booking_id": booking_id,
                "status": "confirmed",
                "message": f"已预订会议室{room_id}，{book_date} {start_time}-{end_time}"
            }
    finally:
        db.close()
