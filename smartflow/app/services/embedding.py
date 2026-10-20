"""
Embedding 服务

功能：加载 bge-small-zh 模型，将文本转为向量。有 CUDA 用 GPU，没有自动回退 CPU。
"""
import torch
from sentence_transformers import SentenceTransformer
from app.config import EMBEDDING_MODEL

_model = None
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"  # 3050 走 GPU，没卡自动回退


def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL, device=DEVICE)
    return _model


def embed_text(text: str) -> list[float]:
    """单条文本向量化"""
    model = get_model()
    return model.encode(text, normalize_embeddings=True).tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """批量文本向量化——批量推理是 GPU 的主场"""
    model = get_model()
    return model.encode(texts, normalize_embeddings=True).tolist()
