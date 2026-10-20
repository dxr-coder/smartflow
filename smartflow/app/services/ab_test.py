"""
A/B 测试服务

功能：用户分组（读活跃实验、50/50 分流、落库幂等）、实验指标统计。
指标口径：rating 粒度——每条 CSAT 评分计入，按评分人的分组归到 A/B 组；
  csat_pct = top-2-box（4-5 星占比）。
数据流：
  get_variant()        → 查 ab_experiments WHERE is_active=1 取实验 id → 分组
  get_my_variant()     → 给前端展示"你在哪个组"
  get_experiment_stats() → ab_assignments JOIN csat_ratings 按 variant 聚合
"""
import random
from app.database import get_db


def _active_experiment(cur):
    """查当前活跃实验，没有就 fallback 到 id=1（老数据兼容）"""
    cur.execute("SELECT id, name, variant_a, variant_b FROM ab_experiments WHERE is_active=1 LIMIT 1")
    row = cur.fetchone()
    if row:
        return row
    cur.execute("SELECT id, name, variant_a, variant_b FROM ab_experiments WHERE id=1")
    return cur.fetchone()


def get_variant(user_id: int) -> str:
    """获取用户所属分组，已分配过就返回固定值，保证同一用户始终同一组"""
    db = get_db()
    try:
        with db.cursor() as cur:
            exp = _active_experiment(cur)
            if not exp:
                return "A"  # 还没有任何实验，全员对照组
            experiment_id = exp["id"]
            cur.execute(
                "SELECT variant FROM ab_assignments WHERE experiment_id = %s AND user_id = %s",
                (experiment_id, user_id),
            )
            row = cur.fetchone()
            if row:
                return row["variant"]
            variant = random.choice(["A", "B"])
            cur.execute(
                "INSERT INTO ab_assignments (experiment_id, user_id, variant) VALUES (%s, %s, %s)",
                (experiment_id, user_id, variant),
            )
            db.commit()
            return variant
    finally:
        db.close()


def get_my_variant(user_id: int):
    """给当前用户看自己在哪个组（含实验元信息）"""
    db = get_db()
    try:
        with db.cursor() as cur:
            exp = _active_experiment(cur)
            if not exp:
                return None
            cur.execute(
                "SELECT variant FROM ab_assignments WHERE experiment_id=%s AND user_id=%s",
                (exp["id"], user_id),
            )
            row = cur.fetchone()
            return {
                "experiment_id": exp["id"],
                "name": exp["name"],
                "variant": row["variant"] if row else None,  # null = 还没聊过天，未分流
                "variant_a": exp["variant_a"],
                "variant_b": exp["variant_b"],
            }
    finally:
        db.close()


def get_experiment_stats():
    """各组 CSAT 指标：rating 粒度（每条评分计入），按评分人分组归组"""
    db = get_db()
    try:
        with db.cursor() as cur:
            exp = _active_experiment(cur)
            if not exp:
                return {"experiment": None, "variants": []}
            # 主指标：n / 均分 / top-2-box%
            cur.execute("""
                SELECT a.variant,
                       COUNT(*) AS n,
                       AVG(c.score) AS avg_score,
                       SUM(c.score >= 4) AS top2_count
                FROM ab_assignments a
                JOIN csat_ratings c ON c.user_id = a.user_id
                WHERE a.experiment_id = %s
                GROUP BY a.variant
            """, (exp["id"],))
            by_variant = {r["variant"]: r for r in cur.fetchall()}
            # 1-5 分布
            cur.execute("""
                SELECT a.variant, c.score, COUNT(*) AS n
                FROM ab_assignments a
                JOIN csat_ratings c ON c.user_id = a.user_id
                WHERE a.experiment_id = %s
                GROUP BY a.variant, c.score
            """, (exp["id"],))
            dist = {}
            for r in cur.fetchall():
                dist.setdefault(r["variant"], {1: 0, 2: 0, 3: 0, 4: 0, 5: 0})[r["score"]] = r["n"]

            variants = []
            for v, label in (("A", exp["variant_a"]), ("B", exp["variant_b"])):
                row = by_variant.get(v)
                n = row["n"] if row else 0
                variants.append({
                    "variant": v,
                    "label": label,
                    "n": n,
                    "avg": round(float(row["avg_score"]), 2) if row and row["avg_score"] is not None else None,
                    "csat_pct": round(row["top2_count"] / n * 100, 1) if n else 0,
                    "dist": dist.get(v, {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}),
                })
            return {
                "experiment": {
                    "id": exp["id"],
                    "name": exp["name"],
                    "variant_a": exp["variant_a"],
                    "variant_b": exp["variant_b"],
                },
                "variants": variants,
            }
    finally:
        db.close()
