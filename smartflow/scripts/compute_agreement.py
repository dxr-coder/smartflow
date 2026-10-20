# -*- coding: utf-8 -*-
"""
标注一致性：算一致率 + Cohen's kappa
数据流：读 annotator_sample.csv（第二标注员已填 your_choice）
       → 金标 join 出"主文档在哪个候选位"（gold）→ 与标注员选择逐条比
       → percent agreement + Cohen's kappa（4 类：主文档在 A/B/C/D）+ 分歧清单
用法：python compute_agreement.py（默认读同目录 annotator_sample.csv）
解读：kappa > 0.75 优秀；0.6-0.75 良好；< 0.4 说明金标主文档判断主观性强，需要写清标注指引
     注意 kappa 对类别不平衡敏感（若金标主文档总被打乱到同一位置，导出脚本会打乱所以不成立）
"""
import csv
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import get_db

csv_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "annotator_sample.csv")

rows = list(csv.DictReader(open(csv_path, encoding="utf-8-sig")))
if not rows:
    sys.exit("CSV 是空的")
unfilled = [r for r in rows if (r.get("your_choice") or "").strip().upper() not in ("A", "B", "C", "D")]
if unfilled:
    sys.exit(f"还有 {len(unfilled)} 条没填 your_choice（case_id: {[r['case_id'] for r in unfilled][:10]}）")

# 金标：主文档文件名
db = get_db()
try:
    with db.cursor() as cur:
        cur.execute("SELECT id, expect_doc FROM eval_cases WHERE is_answerable=1")
        gold_doc = {r["id"]: r["expect_doc"] for r in cur.fetchall()}
finally:
    db.close()

pairs = []  # (gold_pos, annot_pos)
dissent = []
for r in rows:
    cid = int(r["case_id"])
    doc = gold_doc.get(cid)
    if not doc:
        print(f"警告：case_id={cid} 不在金标里，跳过")
        continue
    cols = ["candidate_A", "candidate_B", "candidate_C", "candidate_D"]
    gold_pos = cols.index(next(c for c in cols if r[c] == doc)) + 1  # 1=A … 4=D
    ann_pos = "ABCD".index(r["your_choice"].strip().upper()) + 1
    pairs.append((gold_pos, ann_pos))
    if gold_pos != ann_pos:
        dissent.append((cid, "ABCD"[gold_pos - 1], "ABCD"[ann_pos - 1],
                        doc, r["question"]))

n = len(pairs)
agree = sum(1 for g, a in pairs if g == a)
p_o = agree / n

# Cohen's kappa：p_e = 两位标注员边缘分布的偶然一致率
gold_marg = Counter(g for g, _ in pairs)
ann_marg = Counter(a for _, a in pairs)
p_e = sum((gold_marg[k] / n) * (ann_marg[k] / n) for k in range(1, 5))
kappa = (p_o - p_e) / (1 - p_e) if p_e < 1 else 0.0

print(f"\n=== 标注一致性（n={n}）===")
print(f"一致率 (percent agreement): {agree}/{n} = {p_o:.1%}")
print(f"Cohen's kappa: {kappa:.3f}")
verdict = ("优秀" if kappa > 0.75 else "良好" if kappa > 0.6 else
           "一般（金标主文档判断可能主观，建议补标注指引）" if kappa > 0.4 else "差（需要重新审视金标定义）")
print(f"解读：{verdict}")
if dissent:
    print(f"\n分歧 {len(dissent)} 条（金标位置 vs 标注员位置）：")
    for cid, g, a, doc, q in dissent:
        print(f"  #{cid} 金标={g} 标注={a} 主文档={doc} | {q[:40]}")
