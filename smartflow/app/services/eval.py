"""
RAG 评测服务（工业化版 v3）

功能：金标集管理（多标签分级 + 不可回答负例） + 检索层离线评测 + 生成层 LLM-as-judge
      + A/B 配对显著性对比 + 分类别切片 + 生成评测异步 job
数据流：
  金标集 → eval_cases（主期望文档 + is_answerable） + eval_case_docs（grade 2=主/1=可接受，多标签）
  检索层运行 → 逐用例 hybrid_search（复用线上混合检索漏斗） → 多标签判命中
             → Hit@1 / 分数化 Recall@5 / MRR / NDCG@5 + per-case 耗时 → eval_runs + eval_results
             → 负例（is_answerable=0）跳过排名指标（存 NULL），retrieved 照存供调试
             → 排名指标分母 = answerable_count（负例混入会稀释 hit1）
  生成层运行 → 同一份检索 → 拼上下文（同 kb_gate 口径） → call_llm 生成答案
             → LLM-as-judge：正例打 faithfulness/relevance（1-5）；负例判 refused（拒答 vs 幻觉）
             → refusal_rate = 负例中拒答正确比例；负例的 F/R 恒 NULL（拒答没有忠实度可言）
  异步 job → start_generation_job 起 daemon 线程跑 _run_generation_core
           → 内存 _GEN_JOBS 记进度，GET /eval/job/{id} 轮询；单进程专用，多 worker 要换 DB/Redis
  切片 → get_run_detail 读时 LEFT JOIN eval_cases 按 category 聚合，不落库
  显著性对比 → GET /eval/compare 读时计算：Hit@1/拒答正确 走 exact 不适用（拒答走 bootstrap），
             连续指标走 paired bootstrap；95% CI 不含 0 = 显著
指标定义（多标签，E=期望文档集，rank(d)=文档首次出现名次）：
  best_rank = min rank(d)（d∈E，无命中=None）
  Hit@1 = best_rank==1（首位引到任一正确文档）
  MRR   = 1/best_rank
  Recall@5 = |{d∈E: rank(d)≤5}| / |E|（分数化；单标签用例数值恒等于旧 0/1 定义）
  NDCG@5 = DCG@5/IDCG@5，rel=grade∈{1,2} 线性增益，log2 折扣
  RefusalRate = 负例中 judge 判 refused=true 的比例（生成层独有）
设计要点：
  - 期望文档按 filename 匹配，运行时解析 is_latest=1 的 doc_id；fail-fast 一个解析不到直接 400
  - kb_snapshot 拍 filename→version 指纹；eval_results 冗余 question/expected_doc 不建外键
  - 生成层串行不并行：ThreadPoolExecutor 不继承 ContextVar，且 reranker 线程安全无保证
  - judge 走 task_type="json_extract"（模型路由 fast 档省成本）；解析失败重试 1 次仍败则剔除出均值
  - 连接关闭只在最外层一个 finally（pymysql 二次 close 会抛 Already closed）
  - 负例 eval_results.hit 存 0（列 NOT NULL），但 hit 只在 answerable 分母上统计，不污染指标
"""
import json
import math
import threading
import time
import uuid
from fastapi import HTTPException
from app.database import get_db
from app.services.retriever import hybrid_search, ab_variant_var
from app.services.eval_stats import mcnemar_exact, paired_bootstrap, percentile_nearest_rank

TOP_K = 5  # 评测固定口径，存进 eval_runs.top_k

# 生成层答案 prompt：对齐 faq_agent 的 kb_gate 口径（同样的上下文格式和回答要求）
ANSWER_SYSTEM = """你是SmartFlow AI智能客服。请根据参考资料准确回答用户问题。
如果参考资料不相关，请如实告知并建议联系人工客服。

回答要求：
1. 回答末尾标注引用来源，格式：来源：[1] [2]（只标注实际用到的编号）
2. 没有参考资料时不标注

参考资料：
{context}"""

# LLM-as-judge 评分口径（Ragas 无参考范式；v3 加 case_type 分支：正例打分 / 负例判拒答）
# 注意：JSON 花括号在 .format() 里必须写 {{ }}，否则被当成占位符 KeyError（⑪ 摔过的坑）
JUDGE_PROMPT = """你是严格的 RAG 评测评分员。用例类型：{case_type}（positive=知识库有答案，negative=知识库无答案）。

【用户问题】{question}
【检索资料】{context}
【候选答案】{answer}

若 case_type=positive：按 1-5 打分——faithfulness（答案事实能否被检索资料逐句支撑；5=全部可对应，3=主体正确有1-2处细节无法核实，1=与资料矛盾或关键事实无支撑）与 relevance（是否直接充分回答问题；5=精准完整，3=回答了但冗长或遗漏，1=答非所问）。输出：
{{"faithfulness": <1-5>, "relevance": <1-5>, "reason": "<50字以内理由>"}}

若 case_type=negative：判断候选答案是否明确拒答（告知无相关资料/建议联系人工/不编造具体条款数字）。如实说明无答案=拒答正确（refused=true）；给出任何具体答案要点=幻觉（refused=false）。输出：
{{"refused": true/false, "reason": "<50字以内理由>"}}

只输出一行 JSON，不要输出任何其他内容。"""


def _loads(v):
    """JSON 列读出可能是 str 也可能是已解析对象，统一兜底"""
    if v is None:
        return None
    if isinstance(v, (dict, list)):
        return v
    try:
        return json.loads(v)
    except (ValueError, TypeError):
        return None


def list_cases():
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""SELECT id, question, expect_doc, category, is_answerable, is_active, created_at
                           FROM eval_cases ORDER BY id""")
            cases = cur.fetchall()
            cur.execute("SELECT case_id, doc_filename, grade FROM eval_case_docs")
            by_case = {}
            for r in cur.fetchall():
                by_case.setdefault(r["case_id"], []).append(
                    {"doc_filename": r["doc_filename"], "grade": r["grade"]})
            for c in cases:
                docs = sorted(by_case.get(c["id"], []), key=lambda d: -d["grade"])
                if not docs and c["is_answerable"]:
                    # 兜底：迁移前老数据没有关联行；负例本来就没有文档，不用兜底
                    docs = [{"doc_filename": c["expect_doc"], "grade": 2}]
                c["docs"] = docs
            return cases
    finally:
        db.close()


def list_documents():
    """给前端"新增用例"下拉框用：当前最新文档的 文件名+版本+部门"""
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""SELECT id, filename, version, department FROM documents
                           WHERE is_latest=1 ORDER BY filename""")
            return cur.fetchall()
    finally:
        db.close()


def add_case(payload: dict):
    """
    新增用例（v3：支持不可回答负例）
    入参：正例 {"question": str, "category": str, "is_answerable": true(可省),
               "docs": [{"filename": str, "grade": 2|1}, ...]}  恰好一个 grade=2（主文档）
          负例 {"question": str, "category": "unanswerable", "is_answerable": false, "docs": []}
    """
    question = (payload.get("question") or "").strip()
    category = (payload.get("category") or "general").strip()[:20]
    docs = payload.get("docs") or []
    is_answerable = bool(payload.get("is_answerable", True))
    if not question:
        raise HTTPException(400, "问题不能为空")

    if not is_answerable:
        # 负例：不指定期望文档，expect_doc 落 NULL
        if docs:
            raise HTTPException(400, "不可回答用例不应指定期望文档")
        db = get_db()
        try:
            with db.cursor() as cur:
                cur.execute("""INSERT INTO eval_cases (question, expect_doc, category, is_answerable)
                               VALUES (%s, NULL, %s, 0)""", (question[:200], category))
                case_id = cur.lastrowid
            db.commit()
            return {"msg": "不可回答用例已添加", "case_id": case_id}
        finally:
            db.close()

    if not (1 <= len(docs) <= 4):
        raise HTTPException(400, "期望文档要有 1-4 个")
    grades = [d.get("grade") for d in docs]
    if any(g not in (1, 2) for g in grades):
        raise HTTPException(400, "grade 只能是 2（主文档）或 1（可接受）")
    if grades.count(2) != 1:
        raise HTTPException(400, "必须恰好指定一个主文档（grade=2）")
    filenames = [(d.get("filename") or "").strip() for d in docs]
    if any(not fn for fn in filenames):
        raise HTTPException(400, "文档文件名不能为空")
    if len(set(filenames)) != len(filenames):
        raise HTTPException(400, "同一条用例里文档不能重复")
    db = get_db()
    try:
        with db.cursor() as cur:
            # 所有期望文档必须存在于最新版本，录入时就拦住手误
            for fn in filenames:
                cur.execute("SELECT id FROM documents WHERE filename=%s AND is_latest=1", (fn,))
                if not cur.fetchone():
                    raise HTTPException(400, f"知识库中不存在该文档或已非最新版本：{fn}")
            primary = filenames[grades.index(2)]
            cur.execute("""INSERT INTO eval_cases (question, expect_doc, category, is_answerable)
                           VALUES (%s, %s, %s, 1)""",
                        (question[:200], primary, category))
            case_id = cur.lastrowid
            for fn, g in zip(filenames, grades):
                cur.execute("""INSERT INTO eval_case_docs (case_id, doc_filename, grade)
                               VALUES (%s, %s, %s)""", (case_id, fn, g))
        db.commit()
        return {"msg": "用例已添加", "case_id": case_id}
    finally:
        db.close()


def delete_case(case_id: int):
    """硬删（连 eval_case_docs 一起）；历史 eval_results 冗余了 question/expected_doc，不受影响"""
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM eval_cases WHERE id=%s", (case_id,))
            if not cur.fetchone():
                raise HTTPException(404, "用例不存在")
            cur.execute("DELETE FROM eval_case_docs WHERE case_id=%s", (case_id,))
            cur.execute("DELETE FROM eval_cases WHERE id=%s", (case_id,))
        db.commit()
        return {"msg": "用例已删除"}
    finally:
        db.close()


def _kb_snapshot(cur):
    """知识库指纹：filename → version（只取 is_latest=1），回归对比的诚实性锚点"""
    cur.execute("SELECT filename, version FROM documents WHERE is_latest=1 ORDER BY filename")
    return {r["filename"]: r["version"] for r in cur.fetchall()}


def _load_cases_with_docs(cur):
    """加载启用中的用例 + 各自的期望文档列表（grade 降序，主文档在前）；负例 docs=[]"""
    cur.execute("""SELECT id, question, expect_doc, is_answerable FROM eval_cases
                   WHERE is_active=1 ORDER BY id""")
    cases = cur.fetchall()
    if not cases:
        raise HTTPException(400, "还没有启用中的评测用例，先添加金标集")
    cur.execute("SELECT case_id, doc_filename, grade FROM eval_case_docs")
    by_case = {}
    for r in cur.fetchall():
        by_case.setdefault(r["case_id"], []).append(
            {"doc_filename": r["doc_filename"], "grade": r["grade"]})
    for c in cases:
        if not c["is_answerable"]:
            c["docs"] = []  # 负例没有期望文档，也不做 expect_doc 兜底
            continue
        docs = sorted(by_case.get(c["id"], []), key=lambda d: -d["grade"])
        if not docs:  # 兜底：迁移前老数据
            docs = [{"doc_filename": c["expect_doc"], "grade": 2}]
        c["docs"] = docs
    return cases


def _resolve_expected_docs(cur, cases):
    """fail-fast：所有期望文档（主+可接受）必须能解析到当前版本 doc_id；负例无文档自然跳过"""
    resolved, missing = set(), []
    for c in cases:
        for d in c["docs"]:
            fn = d["doc_filename"]
            if fn not in resolved:
                cur.execute("SELECT id FROM documents WHERE filename=%s AND is_latest=1", (fn,))
                if cur.fetchone():
                    resolved.add(fn)
                else:
                    missing.append(fn)
    if missing:
        raise HTTPException(400, "这些期望文档在知识库中不存在或已非最新版本：" + "、".join(sorted(set(missing))))


def _case_metrics(hits, expected_docs):
    """
    单用例多标签指标
    入参：hits=hybrid_search 返回的 chunk 列表；expected_docs=[{doc_filename, grade}]
    返回 (hit, best_rank, hit1, mrr, recall5, ndcg5)；负例（expected_docs 空）全 None
    """
    if not expected_docs:
        return None, None, None, None, None, None
    grade_by_doc = {d["doc_filename"]: d["grade"] for d in expected_docs}
    # 文档首次出现名次（同文档多 chunk 只记第一次）
    rank_by_doc = {}
    for idx, h in enumerate(hits):
        name = h.get("metadata", {}).get("document_name")
        if name not in rank_by_doc:
            rank_by_doc[name] = idx + 1
    ranks = [rank_by_doc.get(fn) for fn in grade_by_doc]
    found = [r for r in ranks if r]
    best_rank = min(found) if found else None
    hit = 1 if best_rank else 0
    hit1 = 1 if best_rank == 1 else 0
    mrr = 1.0 / best_rank if best_rank else 0.0
    # 分数化 Recall@5：期望文档有多大比例进了 top-5
    recall5 = sum(1 for r in ranks if r and r <= TOP_K) / len(expected_docs)
    # NDCG@5：按文档首次出现名次计增益（同文档多 chunk 只记一次，否则 DCG 会超过 IDCG）
    dcg = 0.0
    for name, rank in rank_by_doc.items():
        if name in grade_by_doc and rank <= TOP_K:
            dcg += grade_by_doc[name] / math.log2(rank + 1)
    ideal_grades = sorted(grade_by_doc.values(), reverse=True)[:TOP_K]
    idcg = sum(g / math.log2(i + 1) for i, g in enumerate(ideal_grades, 1))
    ndcg5 = dcg / idcg if idcg > 0 else 0.0
    return hit, best_rank, hit1, mrr, recall5, ndcg5


def _build_retrieved(query, hits):
    """检索产物快照（存 eval_results.retrieved，展开明细用）"""
    return {
        "query_used": query,   # 实际拿去检索的查询（重写后≠原话时看得见）
        "items": [
            {
                "rank": i + 1,
                "document_name": h.get("metadata", {}).get("document_name"),
                "doc_id": h.get("metadata", {}).get("doc_id"),
                "source": h.get("source"),
                "rrf_score": round(float(h.get("rrf_score", 0)), 6),
                "rerank_score": round(float(h.get("rerank_score", 0)), 4),
                "snippet": (h.get("content") or "")[:80],
            }
            for i, h in enumerate(hits)
        ],
    }


def _parse_judge(raw, case_type="positive"):
    """judge 输出 → dict；正例 {faithfulness,relevance,reason}，负例 {refused,reason}；格式不对返回 None（外层重试）"""
    if not raw:
        return None
    text = raw.strip()
    if text.startswith("```"):  # 剥 markdown 围栏
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        obj = json.loads(text)
        if case_type == "negative":
            refused = obj["refused"]
            # json.loads 出来的 true/false 就是 Python bool；字符串"true"不算
            if not isinstance(refused, bool):
                return None
            return {"refused": refused, "reason": str(obj.get("reason", ""))[:80]}
        f, r = int(obj["faithfulness"]), int(obj["relevance"])
        if 1 <= f <= 5 and 1 <= r <= 5:
            return {"faithfulness": f, "relevance": r,
                    "reason": str(obj.get("reason", ""))[:80]}
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None
    return None


def _run_judge(question, context, answer, case_type="positive"):
    """调 LLM 评审；case_type 决定走打分分支还是拒答分支；失败重试 1 次，仍失败存 error 由调用方剔除"""
    from app.services.chat import call_llm
    prompt = JUDGE_PROMPT.format(question=question, context=context,
                                 answer=answer, case_type=case_type)
    last_raw = None
    for _ in range(2):
        last_raw = call_llm([{"role": "user", "content": prompt}],
                            max_tokens=300, fallback=None, task_type="json_extract")
        parsed = _parse_judge(last_raw, case_type)
        if parsed:
            return parsed
    return {"error": "评审输出无法解析", "raw": (last_raw or "")[:120]}


def _generate_answer(question, hits):
    """按 kb_gate 同款口径拼上下文并生成答案（生成层评测专用）"""
    from app.services.chat import call_llm
    context_parts = []
    for i, h in enumerate(hits, 1):
        doc_name = h.get("metadata", {}).get("document_name", "未知文档")
        context_parts.append(f"[{i}] （来源：{doc_name}）\n{h['content']}")
    context = "\n\n".join(context_parts) if context_parts else "（本次检索无结果）"
    system_prompt = ANSWER_SYSTEM.format(context=context)
    answer = call_llm(
        [{"role": "system", "content": system_prompt},
         {"role": "user", "content": question}],
        max_tokens=4096,
        fallback="抱歉，知识库暂时无法访问，建议您联系人工客服。",
        task_type="answer",
    )
    return answer, context


def run_eval(variant: str, note: str = "", rewrite: bool = False):
    """检索层评测：只调 hybrid_search，不调 LLM（rewrite 开启时含 LLM 改写）；负例跳过排名指标"""
    if variant not in ("A", "B"):
        raise HTTPException(400, "variant 只能是 A 或 B")
    from app.services.query_rewriter import rewrite_query
    db = get_db()
    try:
        with db.cursor() as cur:
            cases = _load_cases_with_docs(cur)
            _resolve_expected_docs(cur, cases)
            kb_snapshot = _kb_snapshot(cur)

        token = ab_variant_var.set(variant)
        results = []
        hit1_sum = recall5_sum = mrr_sum = ndcg_sum = 0.0
        durations = []
        n_answerable = sum(1 for c in cases if c["is_answerable"])
        started = time.monotonic()
        try:
            for c in cases:
                t0 = time.monotonic()
                query = c["question"]
                if rewrite:
                    # 查询重写：LLM 改写成检索友好形式；挂了 fallback 回原话
                    rw = rewrite_query(c["question"])
                    query = (rw.get("rewritten") or "").strip() or c["question"]
                hits = hybrid_search(query, top_k=TOP_K)  # department=None，全库口径
                if c["is_answerable"]:
                    hit, best_rank, hit1, mrr, recall5, ndcg5 = _case_metrics(hits, c["docs"])
                    hit1_sum += hit1
                    recall5_sum += recall5
                    mrr_sum += mrr
                    ndcg_sum += ndcg5
                else:
                    # 负例：不参与排名指标（hit 存 0 是 NOT NULL 列的妥协，统计时只用 answerable 分母）
                    hit, best_rank, recall5, ndcg5 = 0, None, None, None
                dur_ms = int((time.monotonic() - t0) * 1000)
                durations.append(dur_ms)
                results.append({
                    "case_id": c["id"], "question": c["question"],
                    "expected_doc": c["expect_doc"], "hit": hit,
                    "first_rank": best_rank, "retrieved": _build_retrieved(query, hits),
                    "recall5": round(recall5, 4) if recall5 is not None else None,
                    "ndcg5": round(ndcg5, 4) if ndcg5 is not None else None,
                    "expected_docs": c["docs"], "duration_ms": dur_ms,
                })
        finally:
            ab_variant_var.reset(token)

        n = len(cases)
        duration_ms = int((time.monotonic() - started) * 1000)
        # 排名指标只在可回答用例上平均（负例混入分母会稀释 hit1——Q147）
        summary = {
            "variant": variant, "mode": "retrieval", "case_count": n,
            "answerable_count": n_answerable, "rewrite": rewrite,
            "hit1": round(hit1_sum / n_answerable, 4) if n_answerable else None,
            "recall5": round(recall5_sum / n_answerable, 4) if n_answerable else None,
            "mrr": round(mrr_sum / n_answerable, 4) if n_answerable else None,
            "ndcg5": round(ndcg_sum / n_answerable, 4) if n_answerable else None,
            "duration_ms": duration_ms,
            "lat_p50_ms": percentile_nearest_rank(durations, 0.5),
            "lat_p95_ms": percentile_nearest_rank(durations, 0.95),
        }

        # 落库：run + results 一次事务（连接统一由最外层 finally 关闭）
        with db.cursor() as cur:
            cur.execute("""INSERT INTO eval_runs
                           (variant, case_count, top_k, rewrite, mode, hit1, recall5, mrr,
                            ndcg5, lat_p50_ms, lat_p95_ms, duration_ms, kb_snapshot, note,
                            answerable_count)
                           VALUES (%s,%s,%s,%s,'retrieval',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (variant, n, TOP_K, rewrite, summary["hit1"], summary["recall5"],
                         summary["mrr"], summary["ndcg5"],
                         summary["lat_p50_ms"], summary["lat_p95_ms"], duration_ms,
                         json.dumps(kb_snapshot, ensure_ascii=False), note or "",
                         n_answerable))
            run_id = cur.lastrowid
            for r in results:
                cur.execute("""INSERT INTO eval_results
                               (run_id, case_id, question, expected_doc, hit, first_rank,
                                retrieved, recall5, ndcg5, expected_docs, duration_ms)
                               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                            (run_id, r["case_id"], r["question"], r["expected_doc"],
                             r["hit"], r["first_rank"],
                             json.dumps(r["retrieved"], ensure_ascii=False),
                             r["recall5"], r["ndcg5"],
                             json.dumps(r["expected_docs"], ensure_ascii=False),
                             r["duration_ms"]))
        db.commit()
        summary["run_id"] = run_id
        return summary
    finally:
        db.close()


def _run_generation_core(variant: str, note: str = "", rewrite: bool = False, progress_cb=None):
    """
    生成层评测核心：检索 → 生成答案 → LLM-as-judge（正例 F/R，负例 refused）
    同步跑完（123 例 × 2 次 LLM 调用约 30-40 分钟）；串行不并行（ContextVar 不跨线程）
    progress_cb(done, total, phase)：异步 job 用它更新进度；同步路径传 None
    """
    if variant not in ("A", "B"):
        raise HTTPException(400, "variant 只能是 A 或 B")
    from app.services.query_rewriter import rewrite_query
    db = get_db()
    try:
        with db.cursor() as cur:
            cases = _load_cases_with_docs(cur)
            _resolve_expected_docs(cur, cases)
            kb_snapshot = _kb_snapshot(cur)

        total = len(cases)
        if progress_cb:
            progress_cb(0, total, f"{variant} 组 · 加载金标集完成")

        token = ab_variant_var.set(variant)
        results = []
        hit1_sum = recall5_sum = mrr_sum = ndcg_sum = 0.0
        faith_vals, rel_vals, refusal_vals = [], [], []
        durations = []
        n_answerable = sum(1 for c in cases if c["is_answerable"])
        started = time.monotonic()
        try:
            for i, c in enumerate(cases):
                t0 = time.monotonic()
                case_type = "positive" if c["is_answerable"] else "negative"
                query = c["question"]
                if rewrite:
                    rw = rewrite_query(c["question"])
                    query = (rw.get("rewritten") or "").strip() or c["question"]
                hits = hybrid_search(query, top_k=TOP_K)
                if c["is_answerable"]:
                    hit, best_rank, hit1, mrr, recall5, ndcg5 = _case_metrics(hits, c["docs"])
                    hit1_sum += hit1
                    recall5_sum += recall5
                    mrr_sum += mrr
                    ndcg_sum += ndcg5
                else:
                    hit, best_rank, recall5, ndcg5 = 0, None, None, None
                answer, context = _generate_answer(c["question"], hits)
                judge = _run_judge(c["question"], context, answer, case_type)
                dur_ms = int((time.monotonic() - t0) * 1000)
                durations.append(dur_ms)
                if "error" not in judge:
                    if case_type == "positive":
                        faith_vals.append(judge["faithfulness"])
                        rel_vals.append(judge["relevance"])
                    else:
                        # 拒答正确 = 1，幻觉 = 0；进 refusal_rate 的分母
                        refusal_vals.append(1 if judge["refused"] else 0)
                results.append({
                    "case_id": c["id"], "question": c["question"],
                    "expected_doc": c["expect_doc"], "hit": hit,
                    "first_rank": best_rank, "retrieved": _build_retrieved(query, hits),
                    "recall5": round(recall5, 4) if recall5 is not None else None,
                    "ndcg5": round(ndcg5, 4) if ndcg5 is not None else None,
                    "expected_docs": c["docs"], "duration_ms": dur_ms,
                    "answer": answer, "judge": judge,
                })
                if progress_cb:
                    progress_cb(i + 1, total, f"{variant} 组 · 检索→答题→评审")
        finally:
            ab_variant_var.reset(token)

        n = len(cases)
        judged = len(faith_vals)
        duration_ms = int((time.monotonic() - started) * 1000)
        summary = {
            "variant": variant, "mode": "generation", "case_count": n,
            "answerable_count": n_answerable, "rewrite": rewrite,
            "hit1": round(hit1_sum / n_answerable, 4) if n_answerable else None,
            "recall5": round(recall5_sum / n_answerable, 4) if n_answerable else None,
            "mrr": round(mrr_sum / n_answerable, 4) if n_answerable else None,
            "ndcg5": round(ndcg_sum / n_answerable, 4) if n_answerable else None,
            # 评审均值 /5 归一到 0-1；只统计评审成功的正例（judged_count 见分母）
            "faithfulness": round(sum(faith_vals) / judged / 5, 4) if judged else None,
            "relevance": round(sum(rel_vals) / judged / 5, 4) if judged else None,
            "judged_count": judged,
            # 拒答率：负例中评审成功且判 refused=true 的比例；无负例或全解析失败为 None
            "refusal_rate": round(sum(refusal_vals) / len(refusal_vals), 4) if refusal_vals else None,
            "duration_ms": duration_ms,
            "lat_p50_ms": percentile_nearest_rank(durations, 0.5),
            "lat_p95_ms": percentile_nearest_rank(durations, 0.95),
        }

        with db.cursor() as cur:
            cur.execute("""INSERT INTO eval_runs
                           (variant, case_count, top_k, rewrite, mode, hit1, recall5, mrr,
                            ndcg5, faithfulness, relevance, lat_p50_ms, lat_p95_ms,
                            duration_ms, kb_snapshot, note, refusal_rate, judged_count,
                            answerable_count)
                           VALUES (%s,%s,%s,%s,'generation',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (variant, n, TOP_K, rewrite, summary["hit1"], summary["recall5"],
                         summary["mrr"], summary["ndcg5"],
                         summary["faithfulness"], summary["relevance"],
                         summary["lat_p50_ms"], summary["lat_p95_ms"], duration_ms,
                         json.dumps(kb_snapshot, ensure_ascii=False), note or "",
                         summary["refusal_rate"], judged, n_answerable))
            run_id = cur.lastrowid
            for r in results:
                cur.execute("""INSERT INTO eval_results
                               (run_id, case_id, question, expected_doc, hit, first_rank,
                                retrieved, recall5, ndcg5, expected_docs, duration_ms,
                                answer, judge)
                               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                            (run_id, r["case_id"], r["question"], r["expected_doc"],
                             r["hit"], r["first_rank"],
                             json.dumps(r["retrieved"], ensure_ascii=False),
                             r["recall5"], r["ndcg5"],
                             json.dumps(r["expected_docs"], ensure_ascii=False),
                             r["duration_ms"], r["answer"],
                             json.dumps(r["judge"], ensure_ascii=False)))
        db.commit()
        summary["run_id"] = run_id
        return summary
    finally:
        db.close()


def run_generation_eval(variant: str, note: str = "", rewrite: bool = False):
    """生成层评测（同步路径，sync=true 或冒烟用）：直接跑完返回 summary"""
    return _run_generation_core(variant, note, rewrite)


# ---------------------------------------------------------------------------
# 生成评测异步 job：进程内存表 + daemon 线程
# 单进程 uvicorn 专用——多 worker 部署要换 DB/Redis 做任务表（面试主动讲的取舍）
# --reload 改文件会杀工作线程 → get_job 用 45 分钟超时兜底，防 job 永挂 running
# ---------------------------------------------------------------------------
_GEN_JOBS = {}  # job_id -> {status, done, total, phase, run_id, error, started_at}
_JOB_TIMEOUT_SECONDS = 45 * 60


def start_generation_job(variant: str, note: str = "", rewrite: bool = False):
    """起一个生成评测后台任务；已有 running 任务时 409（生成评测共用检索漏斗，跑并行没意义还互相抢 LLM 配额）"""
    # 清理 1 小时前结束的任务记录，防内存表无限增长
    now = time.time()
    for k in [k for k, j in _GEN_JOBS.items()
              if j["status"] != "running" and now - j["started_at"] > 3600]:
        del _GEN_JOBS[k]
    for j in _GEN_JOBS.values():
        if j["status"] == "running":
            raise HTTPException(409, "已有生成评测在跑，请等它完成再发起")
    job_id = uuid.uuid4().hex[:8]
    _GEN_JOBS[job_id] = {
        "status": "running", "done": 0, "total": 0,
        "phase": "线程启动中", "run_id": None, "error": None,
        "started_at": time.time(),
    }
    threading.Thread(target=_gen_job_worker, args=(job_id, variant, note, rewrite),
                     daemon=True).start()
    return {"job_id": job_id}


def _gen_job_worker(job_id: str, variant: str, note: str, rewrite: bool):
    """后台工作线程：跑生成评测核心，进度写进内存 job 表；异常落 error 状态由前端轮询发现"""
    job = _GEN_JOBS[job_id]
    try:
        def progress_cb(done, total, phase):
            job["done"] = done
            job["total"] = total
            job["phase"] = phase
        summary = _run_generation_core(variant, note, rewrite, progress_cb=progress_cb)
        job["run_id"] = summary["run_id"]
        job["status"] = "done"
        job["phase"] = "完成"
    except Exception as e:  # 后台线程的异常没人接，必须自己兜住写进 job 表
        job["status"] = "error"
        job["error"] = str(e)[:200]
        job["phase"] = "失败"


def get_job(job_id: str):
    """查任务进度（前端 5s 轮询）；服务重启后任务表清空 → 404；running 超 45 分钟判 error"""
    job = _GEN_JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "任务不存在（服务重启会清空任务表）")
    if job["status"] == "running" and time.time() - job["started_at"] > _JOB_TIMEOUT_SECONDS:
        job["status"] = "error"
        job["error"] = "超过45分钟未完成（多半是 uvicorn --reload 重启杀掉了工作线程）"
        job["phase"] = "超时"
    return dict(job)


def list_runs():
    db = get_db()
    try:
        with db.cursor() as cur:
            # 显式列清单：新列必须同步这里，否则前端拿不到字段
            cur.execute("""SELECT id, created_at, variant, case_count, top_k, rewrite, mode,
                                  hit1, recall5, mrr, ndcg5, faithfulness, relevance,
                                  lat_p50_ms, lat_p95_ms, duration_ms, kb_snapshot, note,
                                  refusal_rate, judged_count, answerable_count
                           FROM eval_runs ORDER BY id DESC LIMIT 50""")
            rows = cur.fetchall()
            for r in rows:
                r["kb_snapshot"] = _loads(r["kb_snapshot"]) or {}
            return rows
    finally:
        db.close()


def _build_slices(results):
    """
    分类别切片（读时计算不落库）：按 category 聚合
    排名指标只算可回答行；refusal 只算负例行；小样本类别前端要带 n 列防过度解读
    """
    buckets = {}
    for r in results:
        cat = r.get("category") or "已删除用例"
        b = buckets.setdefault(cat, {
            "n": 0, "n_answerable": 0, "n_negative": 0,
            "hit1": [], "recall5": [], "mrr": [], "ndcg5": [],
            "faithfulness": [], "relevance": [], "refusal": [],
        })
        b["n"] += 1
        judge = _loads(r.get("judge"))
        if r.get("is_answerable") == 0:
            b["n_negative"] += 1
            if judge and "refused" in judge:
                b["refusal"].append(1 if judge["refused"] else 0)
            continue
        b["n_answerable"] += 1
        if r.get("first_rank") is not None:
            b["hit1"].append(1 if r["first_rank"] == 1 else 0)
            b["mrr"].append(1.0 / r["first_rank"])
        if r.get("recall5") is not None:
            b["recall5"].append(float(r["recall5"]))
        if r.get("ndcg5") is not None:
            b["ndcg5"].append(float(r["ndcg5"]))
        if judge and "faithfulness" in judge:
            b["faithfulness"].append(judge["faithfulness"] / 5)
            b["relevance"].append(judge["relevance"] / 5)

    def _mean(vals):
        return round(sum(vals) / len(vals), 4) if vals else None

    return {
        cat: {
            "n": b["n"], "n_answerable": b["n_answerable"], "n_negative": b["n_negative"],
            "hit1": _mean(b["hit1"]), "recall5": _mean(b["recall5"]),
            "mrr": _mean(b["mrr"]), "ndcg5": _mean(b["ndcg5"]),
            "faithfulness": _mean(b["faithfulness"]), "relevance": _mean(b["relevance"]),
            "refusal_rate": _mean(b["refusal"]),
        }
        for cat, b in sorted(buckets.items())
    }


def get_run_detail(run_id: int):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""SELECT id, created_at, variant, case_count, top_k, rewrite, mode,
                                  hit1, recall5, mrr, ndcg5, faithfulness, relevance,
                                  lat_p50_ms, lat_p95_ms, duration_ms, kb_snapshot, note,
                                  refusal_rate, judged_count, answerable_count
                           FROM eval_runs WHERE id=%s""", (run_id,))
            run = cur.fetchone()
            if not run:
                raise HTTPException(404, "评测记录不存在")
            run["kb_snapshot"] = _loads(run["kb_snapshot"]) or {}
            # LEFT JOIN 带出 category/is_answerable：用例后来被删也不影响历史明细
            cur.execute("""SELECT r.id, r.case_id, r.question, r.expected_doc, r.hit, r.first_rank,
                                  r.retrieved, r.recall5, r.ndcg5, r.expected_docs, r.duration_ms,
                                  r.answer, r.judge, c.category, c.is_answerable
                           FROM eval_results r
                           LEFT JOIN eval_cases c ON c.id = r.case_id
                           WHERE r.run_id=%s ORDER BY r.id""", (run_id,))
            results = cur.fetchall()
            for r in results:
                r["retrieved"] = _loads(r["retrieved"]) or []
                r["expected_docs"] = _loads(r["expected_docs"]) or []
                r["judge"] = _loads(r["judge"])
            run["results"] = results
            run["slices"] = _build_slices(results)
            return run
    finally:
        db.close()


def compare_runs(a_id: int, b_id: int):
    """
    A/B 两轮配对显著性对比（读时计算不落库）
    按 case_id 交集配对；Hit@1 走 exact McNemar（只看不一致对），
    分数化 Recall@5 / MRR / NDCG@5（生成层换成 faithfulness / relevance / refusal_rate）
    走 paired bootstrap；95% CI 不含 0 = 显著；n_paired<10 或口径不一致给 warnings / 400
    回归门禁语义：某指标 Δ 的 CI 完全落在 0 以下 = 显著劣化应拦截；CI 含 0 = 放行但不显著
    """
    if a_id == b_id:
        raise HTTPException(400, "请选两轮不同的评测记录做对比")
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""SELECT id, created_at, variant, rewrite, mode, case_count,
                                  hit1, recall5, mrr, ndcg5, kb_snapshot,
                                  faithfulness, relevance, refusal_rate, judged_count, answerable_count
                           FROM eval_runs WHERE id IN (%s, %s)""", (a_id, b_id))
            runs = {r["id"]: r for r in cur.fetchall()}
            if a_id not in runs or b_id not in runs:
                raise HTTPException(404, "两轮评测记录都要存在")
            a, b = runs[a_id], runs[b_id]
            warnings = []
            if a["case_count"] != b["case_count"]:
                warnings.append(f"两轮用例数不同（A={a['case_count']} / B={b['case_count']}），可能跨了金标集版本")
            if (_loads(a["kb_snapshot"]) or {}) != (_loads(b["kb_snapshot"]) or {}):
                warnings.append("两轮知识库指纹（kb_snapshot）不一致，差异可能来自文档变更而非实验本身")
            if a["mode"] != b["mode"]:
                warnings.append(f"两轮模式不同（A={a['mode']} / B={b['mode']}），指标含义不可直接比")
            cur.execute("""SELECT run_id, case_id, first_rank, recall5, ndcg5, judge
                           FROM eval_results WHERE run_id IN (%s, %s)""", (a_id, b_id))
            by_run = {a_id: {}, b_id: {}}
            for r in cur.fetchall():
                by_run[r["run_id"]][r["case_id"]] = r

        paired_ids = sorted(set(by_run[a_id]) & set(by_run[b_id]))
        if len(paired_ids) < 10:
            raise HTTPException(400, f"可配对用例只有 {len(paired_ids)} 条（<10），配对检验不可靠")

        is_gen = a["mode"] == "generation"
        metrics = {}

        def _metric_block(pairs, binary=False):
            """pairs: [(a_val, b_val)] → 显著性块"""
            va = [p[0] for p in pairs]
            vb = [p[1] for p in pairs]
            if binary:
                return mcnemar_exact(va, vb)
            return paired_bootstrap(va, vb)

        if is_gen:
            # 生成层：只配对评审双方都成功的正例（负例 judge 是 refused 形态，没有 faithfulness 键）
            pairs_f, pairs_r = [], []
            for cid in paired_ids:
                ja, jb = _loads(by_run[a_id][cid].get("judge")), _loads(by_run[b_id][cid].get("judge"))
                if not ja or not jb or "error" in ja or "error" in jb:
                    continue
                if "faithfulness" not in ja or "faithfulness" not in jb:
                    continue  # 负例行，跳过 F/R 配对
                pairs_f.append((ja["faithfulness"] / 5, jb["faithfulness"] / 5))
                pairs_r.append((ja["relevance"] / 5, jb["relevance"] / 5))
            if len(pairs_f) >= 10:
                metrics["faithfulness"] = _metric_block(pairs_f)
                metrics["relevance"] = _metric_block(pairs_r)
            else:
                metrics["faithfulness"] = {"skipped": True,
                                           "reason": f"双方评审都成功的正例配对只有 {len(pairs_f)} 条（<10）"}
                metrics["relevance"] = {"skipped": True, "reason": "同 faithfulness"}
            # 拒答正确配对（双方 judge 都含 refused 的负例）：0/1 走 paired bootstrap
            pairs_ref = []
            for cid in paired_ids:
                ja, jb = _loads(by_run[a_id][cid].get("judge")), _loads(by_run[b_id][cid].get("judge"))
                if not ja or not jb or "error" in ja or "error" in jb:
                    continue
                if "refused" not in ja or "refused" not in jb:
                    continue
                pairs_ref.append((1.0 if ja["refused"] else 0.0, 1.0 if jb["refused"] else 0.0))
            if len(pairs_ref) >= 10:
                metrics["refusal_rate"] = _metric_block(pairs_ref)
            else:
                metrics["refusal_rate"] = {"skipped": True,
                                           "reason": f"拒答可配对负例只有 {len(pairs_ref)} 条（<10）"}
        else:
            # Hit@1：从 first_rank 推逐例 0/1，exact McNemar；负例 first_rank=NULL 自动落 0/0 对（无信息）
            pairs_hit = []
            for cid in paired_ids:
                ra, rb = by_run[a_id][cid], by_run[b_id][cid]
                pairs_hit.append((1 if ra["first_rank"] == 1 else 0,
                                  1 if rb["first_rank"] == 1 else 0))
            metrics["hit1"] = _metric_block(pairs_hit, binary=True)
            # 连续指标：逐例值两边都非 NULL 才入对（负例/旧 run 缺列自动缩样）
            for key, col in (("recall5", "recall5"), ("mrr", None), ("ndcg5", "ndcg5")):
                pairs = []
                for cid in paired_ids:
                    ra, rb = by_run[a_id][cid], by_run[b_id][cid]
                    if col:
                        va, vb = ra[col], rb[col]
                        if va is None or vb is None:
                            continue
                    else:
                        # mrr 从 first_rank 推；负例的 recall5 是 NULL → 不入对；
                        # 可回答但未命中的 first_rank 也是 NULL，但 recall5=0.0 非空 → 记 0.0（1/∞ 的约定）
                        if ra["recall5"] is None or rb["recall5"] is None:
                            continue
                        va = 1.0 / ra["first_rank"] if ra["first_rank"] else 0.0
                        vb = 1.0 / rb["first_rank"] if rb["first_rank"] else 0.0
                    pairs.append((float(va), float(vb)))
                if len(pairs) >= 10:
                    metrics[key] = _metric_block(pairs)
                else:
                    metrics[key] = {"skipped": True,
                                    "reason": f"该指标可配对用例只有 {len(pairs)} 条（<10，多为负例或旧 run 缺列）"}

        summary_keys = ("id", "variant", "rewrite", "mode", "created_at", "case_count",
                        "hit1", "recall5", "mrr", "ndcg5", "faithfulness", "relevance",
                        "refusal_rate", "judged_count", "answerable_count")
        return {
            "a": {k: a[k] for k in summary_keys},
            "b": {k: b[k] for k in summary_keys},
            "n_paired": len(paired_ids),
            "warnings": warnings,
            "metrics": metrics,
        }
    finally:
        db.close()
