"""
混合检索服务

功能：BM25 关键词检索 + 向量语义检索 + RRF 融合排序。
"""
from app.database import get_db
from app.services.reranker import rerank
from app.services.vector_store import search as semantic_search
import contextvars

ab_variant_var = contextvars.ContextVar('ab_variant', default='A')

RRF_K = 60  # RRF 常数，标准值


def keyword_search(query: str, top_k: int = 10, department: str = None) -> list[dict]:
    """MySQL FULLTEXT 关键词检索（BM25 变体）
    注意：content 的全文索引必须用 ngram 解析器，否则中文整句匹配不上：
    ALTER TABLE document_chunks ADD FULLTEXT INDEX ft_content (content) WITH PARSER ngram;
    """
    db = get_db()
    try:
        with db.cursor() as cur:
            if department:
                # department 传了就只搜本部门 + 通用（all/NULL）文档
                cur.execute("""
                            SELECT dc.id,
                                   dc.document_id,
                                   dc.content, MATCH (dc.content) AGAINST(
                                   %s IN NATURAL LANGUAGE MODE) AS score
                            FROM document_chunks dc
                                JOIN documents d
                            ON dc.document_id = d.id
                            WHERE MATCH (dc.content) AGAINST(%s IN NATURAL LANGUAGE MODE)
                              AND d.is_latest = 1
                              AND (d.department = %s
                               OR d.department = 'all'
                               OR d.department IS NULL)
                            ORDER BY score DESC
                                LIMIT %s
                            """, (query, query, department, top_k))
            else:
                # 没传部门就搜全部最新文档
                cur.execute("""
                            SELECT dc.id,
                                   dc.document_id,
                                   dc.content, MATCH (dc.content) AGAINST(
                                   %s IN NATURAL LANGUAGE MODE) AS score
                            FROM document_chunks dc
                                JOIN documents d
                            ON dc.document_id = d.id
                            WHERE MATCH (dc.content) AGAINST(%s IN NATURAL LANGUAGE MODE)
                              AND d.is_latest = 1
                            ORDER BY score DESC
                                LIMIT %s
                            """, (query, query, top_k))
            rows = cur.fetchall()
        return [
            {
                'content': r['content'],
                "metadata": {"doc_id": r["document_id"], "chunk_id": r["id"]},
                "score": float(r["score"]),
                "source": "keyword",
            }
            for r in rows
        ]
    finally:
        db.close()


def hybrid_search(query: str, top_k: int = 5, department: str = None) -> list[dict]:
    """混合检索：BM25 + 向量 + RRF 融合"""
    # 两路并行检索，各取 top_k * 2 候选
    if ab_variant_var.get() == "B":
        top_k = top_k + 2  # 实验组：检索候选更广，所有 agent 走这一个漏斗
    candidate_count = top_k * 2
    kw_results = keyword_search(query, candidate_count, department=department)
    vec_results = semantic_search(query, candidate_count, department=department)

    # RRF 融合
    rrf_scores = {}

    # rrf_scores.get(key, 0)如果关键字存在就拿到成绩，也就是另一条路的，叠加
    for rank, hit in enumerate(kw_results):
        key = hit['content'][:100]  # 用内容前100字当唯一键，判断两路是否命中同一篇
        rrf_scores[key] = rrf_scores.get(key, 0) + 1.0 / (RRF_K + rank + 1)

    for rank, hit in enumerate(vec_results):
        key = hit['content'][:100]
        rrf_scores[key] = rrf_scores.get(key, 0) + 1.0 / (RRF_K + rank + 1)  # 两路都命中就叠加加分

    # 按 RRF 分数排序，取 top_k
    # all_hits形状 = {
    #     "退货政策：7天...": {"content": "退货政策...", "metadata": {...}, "score": 0.89, "source": "semantic"},
    #     "退款流程：联系...": {"content": "退款流程...", "metadata": {...}, "score": 0.65, "source": "semantic"},
    #     "售后服务...": {"content": "售后服务...", "metadata": {...}, "score": 0.85, "source": "keyword"},
    #     "购买须知...": {"content": "购买须知...", "metadata": {...}, "score": 0.76, "source": "semantic"},
    # }
    all_hits = {hit['content'][:100]: hit for hit in kw_results + vec_results}
    # 只对key排下序，得到key列表
    sorted_keys = sorted(rrf_scores.keys(), key=lambda k: rrf_scores[k], reverse=True)

    results = []
    for key in sorted_keys[:top_k * 2]:
        hit = all_hits[key]
        hit['rrf_score'] = rrf_scores[key]
        results.append(hit)

    results = rerank(query, results, top_k=top_k)  # 再用 cross-encoder 精排，取最终 top_k

    # 批量查询文档名，用于引用溯源
    doc_ids = list(set(h['metadata'].get('doc_id') for h in results if h.get('metadata', {}).get('doc_id')))
    if doc_ids:
        db = get_db()
        # 一次查出所有 doc_id 对应的文件名，省得逐条查
        try:
            with db.cursor() as cur:
                placeholders = ','.join(['%s'] * len(doc_ids))
                cur.execute(f"SELECT id, filename FROM documents WHERE id IN ({placeholders})", doc_ids)
                name_map = {row['id']: row['filename'] for row in cur.fetchall()}
        finally:
            db.close()
        for h in results:
            doc_id = h.get('metadata', {}).get('doc_id')
            if doc_id in name_map:
                h['metadata']['document_name'] = name_map[doc_id]

    return results
