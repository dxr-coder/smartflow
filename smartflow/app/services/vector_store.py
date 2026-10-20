"""
向量存储服务

功能：ChromaDB 初始化、文档向量化存储、相似度检索。
"""
import chromadb
from app.config import CHROMA_PERSIST_DIR
from app.services.embedding import embed_text, embed_texts

_client = None
_collection = None


def _get_collection():
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
        _collection = _client.get_or_create_collection(
            name='knowledge_base',
            metadata={"hnsw:space": "cosine"}
        )
    return _collection


def add_documents(doc_id: int, chunks: list[str], department: str = None):
    """将切片文档存入 ChromaDB"""
    collection = _get_collection()
    embeddings = embed_texts(chunks)
    ids = [f"doc{doc_id}_chunk{i}" for i in range(len(chunks))]
    metadatas = [{"doc_id": doc_id, "chunk_index": i, "department": department or "all", "is_latest": True} for i in range(len(chunks))]

    collection.add(
        ids=ids,
        documents=chunks,
        embeddings=embeddings,
        metadatas=metadatas
    )


def search(query: str, top_k: int = 5, department: str = None) -> list[dict]:
    """向量相似度检索，department 传了就只搜该部门的文档"""
    collection = _get_collection()
    query_embedding = embed_text(query)
    # where 条件：department 匹配 或 department='all'（通用文档）
    where = {"is_latest": True}
    if department:
        where = {"$and": [
            {"is_latest": True},
            {"$or": [{"department": department}, {"department": "all"}]}
        ]}
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
        where=where
    )
    hits = []
    for i in range(len(results['ids'][0])):
        hits.append({
            "content": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "score": 1 - results["distances"][0][i],
            "source": "semantic",
        })
    return hits


def delete_by_doc_id(doc_id: int):
    """删除某个文档的所有切片"""
    collection = _get_collection()
    results = collection.get(where={"doc_id": doc_id})
    if results["ids"]:
        collection.delete(ids=results["ids"])
