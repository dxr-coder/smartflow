"""
查询会议室状态工具

功能：查询指定日期的会议室空闲状态。
数据流：execute(date) → MySQL meeting_rooms + room_bookings → 返回空闲列表
"""
from app.database import get_db

SCHEMA = {
    "description": "查询指定日期的会议室空闲状态",
    "parameters": {
        "type": "object",
        "properties": {
            "date": {
                "type": "string",
                "format": "date",
                "description": "查询日期，格式 YYYY-MM-DD，默认今天"
            }
        },
        "required": []
    }
}


def execute(date: str = None, request=None) -> dict:
    """查询会议室空闲状态"""
    import time  # 用到才导
    if not date:
        date = time.strftime("%Y-%m-%d")  # 没传日期就查今天

    db = get_db()
    try:
        with db.cursor() as cur:
            # 查所有会议室
            cur.execute("SELECT id, name, capacity, location FROM meeting_rooms")
            rooms = cur.fetchall()

            # 查该日期已预订的时段
            cur.execute(  # 已取消的预订不算占用
                """SELECT room_id, start_time, end_time
                   FROM room_bookings
                   WHERE book_date = %s
                     AND status != 'cancelled'""",
                (date,)
            )
            bookings = cur.fetchall()
            room_map = {}  # 按会议室ID分组，值是已订时段列表
            for b in bookings:
                rid = b['room_id']
                if rid not in room_map:
                    room_map[rid] = []
                room_map[rid].append(f"{b['start_time']}-{b['end_time']}")

            result = []
            for r in rooms:
                result.append({  # booked_slots 为空 = 这间还有空档
                    "room_id": r["id"],
                    "name": r["name"],
                    "capacity": r["capacity"],
                    "location": r["location"],
                    "booked_slots": room_map.get(r["id"], []),
                })

            return {"date": date, "rooms": result}
    finally:
        db.close()
