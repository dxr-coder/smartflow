"""
知识库文档服务

功能：管理员管理知识库文档。
"""
from app.database import get_db
from fastapi import UploadFile
from app.services.chunk import split_text
from app.services.cleaner import clean_text
from app.services.parser import parse_file
from app.services.vector_store import add_documents, delete_by_doc_id


def get_documents():
    # 文档列表按上传时间倒序，最新的排最前
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""
                        SELECT id,
                               filename,
                               upload_time,
                               status,
                               chunk_count,
                               department,
                               version,
                               is_latest
                        FROM documents
                        ORDER BY upload_time DESC
                        """)

            return cur.fetchall()
    finally:
        db.close()


def delete_document(doc_id: int):
    # 先删 ChromaDB 向量
    delete_by_doc_id(doc_id)
    # 再删 MySQL（ON DELETE CASCADE 会自动删 document_chunks）
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
        db.commit()
        return {"msg": "文档已删除"}
    finally:
        db.close()


def upload_document(file: UploadFile, department: str = None):
    """上传文档：解析 → 清洗 → 切片 → 向量化 → 存储"""
    content = file.file.read()

    # 大小限制 300MB
    if len(content) > 300 * 1024 * 1024:
        return {"error": "文件大小不能超过 300MB"}

    # 1.解析（支持多格式）
    try:
        text = parse_file(file.filename, content)
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": f"文件解析失败：{str(e)}"}

    if not text.strip():
        return {"error": "文档内容为空"}

    # 2.数据清洗
    text = clean_text(text)

    # 3.智能切片
    chunks = split_text(text)
    if not chunks:
        return {"error": "切片后内容为空"}

    # 4. 存 MySQL + ChromaDB
    db = get_db()
    try:
        with db.cursor() as cur:
            # 查询同名文档的最新版本号（DictCursor 按键取值；MAX 为 NULL 时回落 "0"）
            cur.execute("SELECT MAX(version) AS v FROM documents WHERE filename = %s", (file.filename,))
            row = cur.fetchone()
            old_version = (row["v"] if row and row["v"] else None) or "0"
            # 版本号 +1（支持 "1.0" → "1.1" 这种格式）
            try:
                major, minor = old_version.split(".")
                new_version = f"{major}.{int(minor) + 1}"
            except ValueError:
                new_version = "1.0"

            # 收集旧版本 doc_id：置非最新后，对应向量也要从 Chroma 删除，
            # 否则旧版本文本会带着 is_latest=true 继续参与语义检索（版本污染）
            cur.execute("SELECT id FROM documents WHERE filename = %s AND is_latest = 1", (file.filename,))
            old_doc_ids = [r["id"] for r in cur.fetchall()]
            cur.execute("UPDATE documents SET is_latest = 0 WHERE filename = %s", (file.filename,))

            # 插入新版
            cur.execute(
                "INSERT INTO documents (filename, status, chunk_count, department, version, is_latest) VALUES (%s, 'processing', %s, %s, %s, 1)",
                (file.filename, len(chunks), department or 'all', new_version),
            )
            doc_id = cur.lastrowid

            for i, chunk in enumerate(chunks):
                cur.execute(
                    "INSERT INTO document_chunks (document_id, chunk_index, content) VALUES (%s, %s,%s)",
                    (doc_id, i, chunk),
                )
            cur.execute("UPDATE documents SET status = 'active' WHERE id = %s", (doc_id,))
        db.commit()
    finally:
        db.close()

    # MySQL 落定后再动 Chroma：先清旧版本向量，再写入新版向量
    for old_id in old_doc_ids:
        delete_by_doc_id(old_id)
    add_documents(doc_id, chunks, department=department)

    return {"msg": "上传成功", "doc_id": doc_id, "chunk_count": len(chunks)}


def get_document_versions(doc_id: int):
    """查询某个文档的所有历史版本"""
    db = get_db()
    try:
        with db.cursor() as cur:
            # 先查文件名
            cur.execute("SELECT filename FROM documents WHERE id = %s", (doc_id,))
            row = cur.fetchone()
            if not row:
                return []
            filename = row["filename"]
            # 查同名文档的所有版本
            cur.execute("""
                        SELECT id, filename, version, department, is_latest, upload_time
                        FROM documents
                        WHERE filename = %s
                        ORDER BY upload_time DESC
                        """, (filename,))
            return cur.fetchall()
    finally:
        db.close()
