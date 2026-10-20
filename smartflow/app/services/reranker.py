"""
Reranking 服务

功能：用 cross-encoder 模型对检索结果精排，提高相关性。
"""
from sentence_transformers import CrossEncoder

_model = None  # 模型单例，全局只加载一次
MODEL_NAME = 'BAAI/bge-reranker-base'
SCORE_THRESHOLD = 0.3  # 低于此分数的片段丢弃


def _get_model():
    """懒加载 cross-encoder 模型：首次慢，之后直接复用。"""
    global _model
    if _model is None:
        _model = CrossEncoder(MODEL_NAME)  # 首次下载/加载较慢
    return _model


def rerank(query: str, documents: list[dict], top_k: int = 5) -> list[dict]:
    """
        对检索结果精排。

        参数:
            query: 用户问题
            documents: hybrid_search 返回的 hit 列表
            top_k: 返回前几个结果

        返回:
            精排后的 hit 列表，每个 hit 新增 rerank_score 字段
    """
    if not documents:
        return []

    model = _get_model()

    #构造query-document对
    pairs=[(query,doc['content']) for doc in documents]

    # cross-encoder 打分
    scores = model.predict(pairs)

    # 附加分数并排序
    for doc,score in zip(documents, scores):
        doc['rerank_score'] = float(score)

    # 按 rerank_score 降序排序，过滤低分
    reranked=sorted(documents, key=lambda doc: doc['rerank_score'], reverse=True)
    reranked = [d for d in reranked if d["rerank_score"] >= SCORE_THRESHOLD]

    return reranked[:top_k]
