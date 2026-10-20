"""
Embedding 服务

功能：加载 bge-small-zh 模型，将文本转为向量。
"""
from sentence_transformers import SentenceTransformer
from app.config import EMBEDDING_MODEL

_model = None


def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def embed_text(text: str) -> list[float]:
    """单条文本向量化"""
    model = get_model()
    return model.encode(text, normalize_embeddings=True).tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """批量文本向量化"""
    model = get_model()
    return model.encode(texts, normalize_embeddings=True).tolist()
