# -*- coding: utf-8 -*-
"""
标注一致性：盲样导出
数据流：从金标集随机抽 25 条可回答用例 → 每条 = 主期望文档 + 3 个随机干扰文档
       → 打乱顺序生成 CSV（隐藏 grade/正确答案）→ 交给第二标注员盲选
用法：python export_annotator_sample.py [样本数]（默认 25）
输出：annotator_sample.csv（UTF-8-SIG，Excel 直接打开不乱码）
标注员填 your_choice 列（A/B/C/D），填完跑 compute_agreement.py 算一致率 + Cohen's kappa
注意：只测"主文档"选择（可接受文档对盲测者不可见）——测的是最核心的标注判断是否可复现
"""
import csv
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import get_db

N = int(sys.argv[1]) if len(sys.argv) > 1 else 25
random.seed(20261019)  # 固定种子：同一份金标多次导出盲样一致，方便复查

db = get_db()
try:
    with db.cursor() as cur:
        # 只抽可回答用例（负例没有"选对文档"可言）
        cur.execute("""SELECT id, question, expect_doc FROM eval_cases
                       WHERE is_active=1 AND is_answerable=1 ORDER BY id""")
        cases = cur.fetchall()
        cur.execute("SELECT filename FROM documents WHERE is_latest=1")
        all_docs = [r["filename"] for r in cur.fetchall()]
finally:
    db.close()

sample = random.sample(cases, min(N, len(cases)))
rows = []
for c in sample:
    # 3 个干扰文档：排除主文档和该用例的其他期望文档（可接受文档也在排除列——盲测只问主文档）
    distractors = [d for d in all_docs if d != c["expect_doc"]]
    chosen = random.sample(distractors, 3)
    candidates = chosen + [c["expect_doc"]]
    random.shuffle(candidates)
    rows.append({
        "case_id": c["id"],
        "question": c["question"],
        "candidate_A": candidates[0],
        "candidate_B": candidates[1],
        "candidate_C": candidates[2],
        "candidate_D": candidates[3],
        "your_choice": "",  # 标注员填 A/B/C/D
        "notes": "",
    })

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "annotator_sample.csv")
with open(out, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

print(f"已导出 {len(rows)} 条盲样 → {out}")
print("交给第二标注员填 your_choice 列（A/B/C/D），不要透露正确答案；填完跑 compute_agreement.py")
