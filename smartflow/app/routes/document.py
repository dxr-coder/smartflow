"""
知识库管理路由

功能：管理员管理知识库文档。
数据流：
  upload_document → 切片入库
  get_documents → 文档列表
  delete_document → 删文档
  get_document_versions → 该文档的历史版本
"""
from fastapi import APIRouter, Depends, Form
from fastapi import UploadFile, File

from app.database import get_db
from app.deps import require_role
from app.services.document import get_documents, delete_document, upload_document, get_document_versions

router = APIRouter(prefix="/documents", tags=["知识库管理"])


@router.get('')
def get_documents_route(user=Depends(require_role('admin'))):
    """看全部文档列表"""
    return get_documents()


@router.delete('/{doc_id}')
def delete_document_route(doc_id: int, user=Depends(require_role('admin'))):
    """删掉某个文档"""
    return delete_document(doc_id)


@router.post("")
async def upload_document_route(
    file: UploadFile = File(...),  # multipart 上传的文件本体
    department: str = Form(None),   # 前端表单多传一个部门字段
    user=Depends(require_role('admin'))
):
    """上传文档，service 里会自动切片入库"""
    return upload_document(file, department=department)


@router.get("/{doc_id}/chunks")
def get_chunks_route(doc_id: int, user=Depends(require_role('admin'))):
    """查看某个文档的所有切片"""
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT id, chunk_index, content FROM document_chunks WHERE document_id = %s ORDER BY chunk_index",
                (doc_id,),  # 按切片序号排好返回
            )
            return cur.fetchall()
    finally:
        db.close()

@router.get("/{doc_id}/versions")
def get_versions_route(doc_id: int, user=Depends(require_role('admin'))):
    """查看某个文档的所有历史版本"""
    return get_document_versions(doc_id)


