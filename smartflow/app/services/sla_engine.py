"""
SLA 引擎

功能：监控工单 SLA 截止时间，临期预警、超时自动升级优先级。
数据流：
  后台线程（每60秒） → check_sla()
    → 扫描在途工单（pending/processing）
    → 剩余<25% → 写 sla_events(warning)
    → 已超时 → 优先级升一级 + 写 sla_events(escalated)
"""
import threading
from datetime import datetime
from app.database import get_db

# 升级链：low → normal → high → urgent
ESCALATION_CHAIN = {"low": "normal", "normal": "high", "high": "urgent"}

# 已预警过的工单 ID（防止同一个工单反复写 warning）
_warning_done = set()


def check_sla() -> dict:
    """扫描一次所有在途工单的 SLA 状态。返回统计结果。"""
    now = datetime.now()
    db = get_db()
    result = {"warning": 0, "escalated": 0, "details": []}
    try:
        with db.cursor() as cur:
            cur.execute("""
                SELECT id, priority, created_at, sla_deadline, escalated
                FROM tickets
                WHERE status IN ('pending', 'processing')
                  AND sla_deadline IS NOT NULL
            """)
            tickets = cur.fetchall()

            for t in tickets:
                deadline = t["sla_deadline"]
                created = t["created_at"]
                total = (deadline - created).total_seconds()  # SLA 总时长
                remain = (deadline - now).total_seconds()  # 剩余时间

                # ① 已超时且未升级过
                if remain <= 0 and not t["escalated"]:
                    old_p = t["priority"]
                    new_p = ESCALATION_CHAIN.get(old_p)  # urgent 返回 None
                    if new_p:
                        note = f"SLA超时，优先级 {old_p} → {new_p}"
                    else:
                        note = "SLA超时，已是最高优先级，需主管介入"
                    final_p = new_p or old_p
                    cur.execute(
                        "UPDATE tickets SET priority=%s, escalated=1 WHERE id=%s",
                        (final_p, t["id"])
                    )
                    cur.execute("""
                        INSERT INTO sla_events (ticket_id, event_type, from_priority, to_priority, note)
                        VALUES (%s, 'escalated', %s, %s, %s)
                    """, (t["id"], old_p, final_p, note))
                    result["escalated"] += 1
                    result["details"].append({"ticket_id": t["id"], "event": "escalated", "note": note})

                # ② 临期预警（剩余 < 25%，且没预警过）
                elif 0 < remain < total * 0.25 and t["id"] not in _warning_done:
                    _warning_done.add(t["id"])
                    note = f"SLA临期预警：还剩 {remain / 3600:.1f} 小时"
                    cur.execute("""
                        INSERT INTO sla_events (ticket_id, event_type, note)
                        VALUES (%s, 'warning', %s)
                    """, (t["id"], note))
                    result["warning"] += 1
                    result["details"].append({"ticket_id": t["id"], "event": "warning", "note": note})

            db.commit()
            return result
    finally:
        db.close()


# ---------- 后台调度线程 ----------

_stop_event = threading.Event()
_thread = None


def _scheduler_loop(interval: int):
    """后台循环：每隔 interval 秒调一次 check_sla。"""
    while not _stop_event.is_set():
        try:
            r = check_sla()
            if r["warning"] or r["escalated"]:
                print(f"[SLA] 预警{r['warning']} 升级{r['escalated']} {r['details']}")
        except Exception as e:
            print(f"[SLA] 扫描失败: {e}")
        _stop_event.wait(interval)  # 可被 stop() 中断的 sleep


def start_sla_scheduler(interval: int = 60):
    """App 启动时调用一次，拉起后台扫描线程。"""
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop_event.clear()
    _thread = threading.Thread(target=_scheduler_loop, args=(interval,), daemon=True)
    _thread.start()
    print(f"[SLA] 引擎已启动，每 {interval} 秒扫描一次")


def stop_sla_scheduler():
    """App 关闭时调用，优雅停掉线程。"""
    _stop_event.set()
