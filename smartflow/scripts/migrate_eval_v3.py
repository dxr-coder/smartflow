# -*- coding: utf-8 -*-
"""
⑫ 评测工业化升级迁移
数据流：eval_cases 加 is_answerable（0=知识库无答案负例）+ expect_doc 放宽 NULL
       → eval_results.expected_doc 放宽 NULL（负例检索层不落期望文档）
       → eval_runs 加 refusal_rate/judged_count/answerable_count（拒答率、评审成功数、排名指标分母）
幂等：重复执行时 ALTER 报 1060/1050 跳过
"""
import os
import sys
import pymysql

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import get_db

db = get_db()
cur = db.cursor(pymysql.cursors.DictCursor)

def safe_execute(sql, args=None, skip_errors=(1060, 1050, 1061, 1062)):
    """执行 SQL，幂等错误码跳过"""
    try:
        cur.execute(sql, args)
        return True
    except pymysql.err.OperationalError as e:
        if e.args[0] in skip_errors:
            return False
        raise

try:
    # ---------- 1. eval_cases：负例标记 + expect_doc 放宽 ----------
    ok1 = safe_execute("""
        ALTER TABLE eval_cases
          ADD COLUMN is_answerable TINYINT NOT NULL DEFAULT 1 COMMENT '0=不可回答负例' AFTER category
    """)
    ok2 = safe_execute("ALTER TABLE eval_cases MODIFY expect_doc VARCHAR(200) NULL COMMENT '主期望文档；负例为 NULL'")
    print(f"[1/3] eval_cases：is_answerable {'新增' if ok1 else '已存在'} | expect_doc NULLABLE {'已改' if ok2 else '无需改'}")

    # ---------- 2. eval_results.expected_doc 放宽 ----------
    ok3 = safe_execute("ALTER TABLE eval_results MODIFY expected_doc VARCHAR(200) NULL COMMENT '负例为 NULL'")
    print(f"[2/3] eval_results.expected_doc NULLABLE：{'已改' if ok3 else '无需改'}")

    # ---------- 3. eval_runs 新列 ----------
    new_run_cols = [
        ("refusal_rate", "DECIMAL(5,4) NULL COMMENT '生成层负例拒答正确率'"),
        ("judged_count", "INT NULL COMMENT 'generation 评审成功数'"),
        ("answerable_count", "INT NULL COMMENT '可回答用例数（排名指标分母）'"),
    ]
    added = 0
    for col, decl in new_run_cols:
        if safe_execute(f"ALTER TABLE eval_runs ADD COLUMN {col} {decl}"):
            added += 1
    print(f"[3/3] eval_runs 新列：+{added}（已存在则跳过）")

    db.commit()

    # ---------- 验证 ----------
    cur.execute("SHOW COLUMNS FROM eval_cases LIKE 'is_answerable'")
    has_ans = bool(cur.fetchone())
    cur.execute("SHOW COLUMNS FROM eval_cases LIKE 'expect_doc'")
    expect_doc_row = cur.fetchone()
    cur.execute("SHOW COLUMNS FROM eval_runs LIKE 'refusal_rate'")
    has_refusal = bool(cur.fetchone())
    cur.execute("SHOW COLUMNS FROM eval_runs LIKE 'answerable_count'")
    has_answerable = bool(cur.fetchone())
    cur.execute("SHOW COLUMNS FROM eval_runs LIKE 'judged_count'")
    has_judged = bool(cur.fetchone())
    cur.execute("SELECT COUNT(*) AS c FROM eval_cases WHERE is_answerable=0")
    n_neg = cur.fetchone()["c"]
    print("\n=== 验证 ===")
    print(f"eval_cases.is_answerable: {has_ans} | expect_doc Type: {expect_doc_row['Type']} (应含 NULL)")
    print(f"eval_runs refusal_rate: {has_refusal} | judged_count: {has_judged} | answerable_count: {has_answerable}")
    print(f"当前负例数: {n_neg}（seed v3 还没插，0 正常）")
finally:
    db.close()
