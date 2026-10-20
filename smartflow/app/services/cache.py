"""
缓存服务（升级：精确匹配 + 语义缓存）

功能：精确匹配直接返回，语义相似问题复用缓存答案。
"""
import redis
from app.config import REDIS_HOST, REDIS_PORT, REDIS_DB

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)


EXACT_TTL = 3600  # 精确匹配缓存 1 小时
SEMANTIC_TTL = 7200  # 语义缓存 2 小时
SEMANTIC_THRESHOLD = 0.95  # 相似度阈值


def get_cached_answer(question: str):
    """精确匹配缓存"""
    return r.get(f"chat:{question}")


def set_cached_answer(question: str, answer: str):
    """精确匹配缓存"""
    r.set(f"chat:{question}", answer, ex=EXACT_TTL)


def get_semantic_cached(question: str) -> str | None:
    """语义缓存：找到相似度 > 阈值的缓存回答"""
    from app.services.embedding import embed_text
    import json

    query_vec = embed_text(question)
    # 遍历所有语义缓存key
    keys = r.keys('semantic:*')
    best_score = 0
    best_answer = None

    for key in keys:
        data = json.loads(r.get(key))
        cached_vec = data['embedding']
        # 余弦相似度
        score = sum(a * b for a, b in zip(query_vec, cached_vec))
        if score > best_score:
            best_score = score
            best_answer = data['answer']

    if best_score >= SEMANTIC_THRESHOLD:
        return best_answer
    return None


def set_semantic_cached(question: str, answer: str):
    """语义缓存：存储问题向量 + 回答"""
    from app.services.embedding import embed_text
    import json

    key = f'semantic:{question[:50]}'
    r.set(key, json.dumps({
        'question': question,
        'embedding': embed_text(question),
        'answer': answer,
    }), ex=SEMANTIC_TTL)
