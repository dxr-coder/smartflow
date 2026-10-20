"""
查询设备状态工具

功能：查询当前用户的 IT 设备资产状态。
数据流：execute() → get_current_user() → MySQL it_assets 表 → 返回设备列表
"""

from app.database import get_db

SCHEMA = {
    "description": "查询用户的IT设备资产状态（电脑、手机、显示器等）",
    "parameters": {
        "type": "object",
        "properties": {},
        "required": []
    }
}


def execute(request=None) -> dict:
    """查询当前用户设备"""
    user_id = getattr(request.state, "user_id", None) if request else None  # 从 request 拿登录用户
    if not user_id:
        return {"error": "未获取到用户信息"}

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(  # 只查这个用户名下的资产
                """SELECT asset_type, asset_name, asset_tag, status
                   FROM it_assets WHERE user_id = %s""",
                (user_id,)
            )
            rows = cur.fetchall()

            result = []
            for r in rows:
                result.append({  # 字段名改成短的，LLM 好读
                    "type": r["asset_type"],
                    "name": r["asset_name"],
                    "tag": r["asset_tag"],
                    "status": r["status"],
                })

            return {"devices": result}
    finally:
        db.close()
