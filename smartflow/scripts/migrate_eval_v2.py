# -*- coding: utf-8 -*-
"""
⑪ 评测生产级升级迁移
数据流：新建 eval_case_docs（多标签期望文档，grade 2=主/1=可接受）→ 回填 51 条主文档
       → 合并 #16/#51 多标签陷阱对 → eval_runs/eval_results 加新列 → 旧 run recall5 等价回填
幂等：重复执行时 CREATE/ALTER 报 1060/1050 跳过，UPDATE 幂等
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
    # ---------- 1. 多标签期望文档表 ----------
    ok = safe_execute("""
        CREATE TABLE IF NOT EXISTS eval_case_docs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            case_id INT NOT NULL COMMENT 'eval_cases.id',
            doc_filename VARCHAR(200) NOT NULL COMMENT 'documents.filename',
            grade TINYINT NOT NULL COMMENT '2=主期望 1=可接受',
            KEY idx_case (case_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    print(f"[1/6] eval_case_docs 建表：{'新建' if ok else '已存在'}")

    # ---------- 2. 回填主文档（只在表为空时跑，防重复执行重复插） ----------
    cur.execute("SELECT COUNT(*) AS c FROM eval_case_docs")
    if cur.fetchone()["c"] == 0:
        cur.execute("INSERT INTO eval_case_docs (case_id, doc_filename, grade) SELECT id, expect_doc, 2 FROM eval_cases")
        print(f"[2/6] 回填主文档：{cur.rowcount} 行")
    else:
        print("[2/6] 回填主文档：跳过（表已有数据）")

    # ---------- 3. 合并 #16/#51 为一条多标签用例 ----------
    cur.execute("SELECT id FROM eval_cases WHERE id=51")
    if cur.fetchone():
        cur.execute("DELETE FROM eval_cases WHERE id=51")
        cur.execute("DELETE FROM eval_case_docs WHERE case_id=51")
        cur.execute("UPDATE eval_cases SET expect_doc='培训与发展管理办法.md' WHERE id=16")
        cur.execute("UPDATE eval_case_docs SET doc_filename='培训与发展管理办法.md', grade=2 WHERE case_id=16 AND grade=2")
        cur.execute("INSERT INTO eval_case_docs (case_id, doc_filename, grade) VALUES (16,'培训与发展管理办法.md',2)")
        cur.execute("UPDATE eval_case_docs SET grade=1 WHERE case_id=16 AND doc_filename='HR员工手册.md'")
        print("[3/6] #16/#51 合并：case16 = 培训办法(主) + HR手册(可接受)")
    else:
        print("[3/6] #16/#51 合并：跳过（#51 已删）")

    # ---------- 4. eval_runs 新列 ----------
    new_run_cols = [
        ("mode", "VARCHAR(16) NOT NULL DEFAULT 'retrieval' COMMENT 'retrieval|generation'"),
        ("ndcg5", "DECIMAL(5,4) NULL"),
        ("faithfulness", "DECIMAL(5,4) NULL COMMENT '生成层评审均值/5归一'"),
        ("relevance", "DECIMAL(5,4) NULL"),
        ("lat_p50_ms", "INT NULL"),
        ("lat_p95_ms", "INT NULL"),
    ]
    added = 0
    for col, decl in new_run_cols:
        if safe_execute(f"ALTER TABLE eval_runs ADD COLUMN {col} {decl}"):
            added += 1
    print(f"[4/6] eval_runs 新列：+{added}（已存在则跳过）")

    # ---------- 5. eval_results 新列 ----------
    new_res_cols = [
        ("recall5", "DECIMAL(5,4) NULL COMMENT 'per-case 分数化, NULL=旧run'"),
        ("ndcg5", "DECIMAL(5,4) NULL"),
        ("expected_docs", "JSON NULL COMMENT '运行时期望快照 [{doc,grade}]'"),
        ("duration_ms", "INT NULL COMMENT 'per-case 管线耗时'"),
        ("answer", "MEDIUMTEXT NULL COMMENT 'generation 模式生成答案'"),
        ("judge", "JSON NULL COMMENT 'generation 评审 {faithfulness,relevance,reason}'"),
    ]
    added = 0
    for col, decl in new_res_cols:
        if safe_execute(f"ALTER TABLE eval_results ADD COLUMN {col} {decl}"):
            added += 1
    print(f"[5/6] eval_results 新列：+{added}（已存在则跳过）")

    # ---------- 6. 旧 run recall5 等价回填（单标签下分数化定义值恒等） ----------
    cur.execute("""
        UPDATE eval_results
           SET recall5 = CASE WHEN first_rank IS NOT NULL AND first_rank <= 5 THEN 1.0 ELSE 0.0 END
         WHERE recall5 IS NULL
    """)
    print(f"[6/6] recall5 等价回填：{cur.rowcount} 行")

    db.commit()

    # ---------- 验证 ----------
    cur.execute("SELECT COUNT(*) AS c FROM eval_case_docs")
    n_docs = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) AS c FROM eval_cases")
    n_cases = cur.fetchone()["c"]
    cur.execute("SELECT case_id, doc_filename, grade FROM eval_case_docs WHERE case_id=16")
    case16 = cur.fetchall()
    cur.execute("SHOW COLUMNS FROM eval_runs LIKE 'ndcg5'")
    has_ndcg_run = bool(cur.fetchone())
    cur.execute("SHOW COLUMNS FROM eval_results LIKE 'judge'")
    has_judge = bool(cur.fetchone())
    cur.execute("SELECT COUNT(*) AS c FROM eval_results WHERE recall5 IS NULL")
    null_recall = cur.fetchone()["c"]
    print("\n=== 验证 ===")
    print(f"eval_cases: {n_cases} 条 | eval_case_docs: {n_docs} 行")
    print(f"case16 期望: {[(r['doc_filename'], r['grade']) for r in case16]}")
    print(f"eval_runs.ndcg5 存在: {has_ndcg_run} | eval_results.judge 存在: {has_judge}")
    print(f"recall5 NULL 残留: {null_recall}")
finally:
    db.close()
