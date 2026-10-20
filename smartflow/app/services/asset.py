"""
资产领用/归还服务

功能：IT资产台账的入库、领用、归还、报废与查询。
数据流：
  领用 → 一条带状态条件的 UPDATE 抢锁（防并发双领） → 写 asset_logs
  归还 → 校验持有人（本人可还，管理员可代还） → 置回在库 → 写日志
  报废 → 终态，仅管理员 → 写日志
"""
import pymysql
from fastapi import HTTPException
from app.database import get_db

# 类别白名单，前端下拉用同一组值
ASSET_CATEGORIES = ("laptop", "monitor", "phone", "badge", "other")


def _get_asset(cur, asset_id):
    cur.execute("SELECT * FROM assets WHERE id=%s", (asset_id,))
    return cur.fetchone()


def _log(cur, asset_id, user_id, operator_id, action, note=""):
    cur.execute(
        "INSERT INTO asset_logs (asset_id, user_id, operator_id, action, note) VALUES (%s,%s,%s,%s,%s)",
        (asset_id, user_id, operator_id, action, note),
    )


def list_assets(user, status=None, category=None, mine=False):
    """查资产列表。mine=True 时只看自己名下的（前端"我的领用"页签用）。"""
    db = get_db()
    try:
        with db.cursor() as cur:
            sql = """SELECT a.*, u.username AS holder_name
                     FROM assets a LEFT JOIN users u ON a.holder_user_id = u.id
                     WHERE 1=1"""
            args = []
            if status:
                sql += " AND a.status=%s"
                args.append(status)
            if category:
                sql += " AND a.category=%s"
                args.append(category)
            if mine:
                sql += " AND a.holder_user_id=%s"
                args.append(user["user_id"])
            # 在库排最前面，方便马上领；报废沉底
            sql += " ORDER BY FIELD(a.status,'available','in_use','retired'), a.id DESC"
            cur.execute(sql, args)
            return cur.fetchall()
    finally:
        db.close()


def create_asset(user, asset_no, category, model="", purchase_date=None, price=None, warranty_end=None, location="", note=""):
    """入库，仅管理员。编号撞唯一键返回 409。台账字段选填。"""
    if category not in ASSET_CATEGORIES:
        raise HTTPException(400, f"类别只支持：{'/'.join(ASSET_CATEGORIES)}")
    db = get_db()
    try:
        with db.cursor() as cur:
            try:
                cur.execute(
                    """INSERT INTO assets
                       (asset_no, category, model, purchase_date, price, warranty_end, location, note, status)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'available')""",
                    (asset_no, category, model, purchase_date, price, warranty_end, location, note),
                )
            except pymysql.err.IntegrityError:  # 唯一键冲突就是编号重复
                raise HTTPException(409, "资产编号已存在")
            asset_id = cur.lastrowid
            _log(cur, asset_id, user["user_id"], user["user_id"], "create", "入库")
        db.commit()
        return {"msg": "入库成功", "asset_id": asset_id}
    finally:
        db.close()



def borrow_asset(asset_id, user):
    """
    领用。核心是"抢锁式 UPDATE"：
    不要先 SELECT 查在库、再 UPDATE——两人同时点，两人都查到在库，后手把前手的持有人覆盖掉。
    改成一条带状态条件的 UPDATE：WHERE status='available'。谁影响 1 行谁抢到，后手 0 行直接 409。
    """
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "UPDATE assets SET status='in_use', holder_user_id=%s WHERE id=%s AND status='available'",
                (user["user_id"], asset_id),
            )
            if cur.rowcount == 0:
                row = _get_asset(cur, asset_id)
                if not row:
                    raise HTTPException(404, "资产不存在")
                raise HTTPException(409, "手慢了，这台当前不在可领用状态")
            _log(cur, asset_id, user["user_id"], user["user_id"], "borrow", "")
        db.commit()
        return {"msg": "领用成功"}
    finally:
        db.close()


def return_asset(asset_id, user, is_admin):
    """
    归还。本人可以还自己领的；管理员可以代还
    （员工离职、资产丢了让管理员兜底收回的场景）。
    """
    db = get_db()
    try:
        with db.cursor() as cur:
            row = _get_asset(cur, asset_id)
            if not row:
                raise HTTPException(404, "资产不存在")
            if row["status"] != "in_use":
                raise HTTPException(400, "这台不在领用中，没法归还")
            if row["holder_user_id"] != user["user_id"] and not is_admin:
                raise HTTPException(403, "只能归还自己领用的资产")
            cur.execute(
                "UPDATE assets SET status='available', holder_user_id=NULL WHERE id=%s AND status='in_use'",
                (asset_id,),
            )
            # 相关人记原持有人，操作人记实际点按钮的（可能是一起代还的管理员）
            _log(cur, asset_id, row["holder_user_id"], user["user_id"], "return", "")
        db.commit()
        return {"msg": "归还成功"}
    finally:
        db.close()


def scrap_asset(asset_id, user, reason=""):
    """报废，仅管理员。终态，不能复活，只能入库新资产顶替。"""
    db = get_db()
    try:
        with db.cursor() as cur:
            row = _get_asset(cur, asset_id)
            if not row:
                raise HTTPException(404, "资产不存在")
            if row["status"] == "retired":
                raise HTTPException(400, "这台已经报废过了")
            cur.execute(
                "UPDATE assets SET status='retired', holder_user_id=NULL WHERE id=%s",
                (asset_id,),
            )
            _log(cur, asset_id, row["holder_user_id"] or user["user_id"], user["user_id"], "scrap", reason)
        db.commit()
        return {"msg": "已报废"}
    finally:
        db.close()


def get_asset_logs(asset_id, user):
    """某台资产的全部流转记录，管理员后台流水页用。"""
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                """SELECT l.*, u.username AS user_name, o.username AS operator_name
                   FROM asset_logs l
                   LEFT JOIN users u ON l.user_id = u.id
                   LEFT JOIN users o ON l.operator_id = o.id
                   WHERE l.asset_id=%s ORDER BY l.id DESC""",
                (asset_id,),
            )
            return cur.fetchall()
    finally:
        db.close()
