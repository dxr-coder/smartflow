"""
PDF 上传路由

功能：接收 PDF 文件，提取文本内容。
数据流：
  上传的 PDF → 存到 uploads/ → 提取纯文本 → 返回长度+前 500 字预览
"""

import os
import uuid
from fastapi import APIRouter, Depends, UploadFile, File
from app.deps import get_current_user
from app.services.pdf import extract_text_from_pdf

router = APIRouter(prefix="/pdf", tags=["PDF解析"])

UPLOAD_DIR = "uploads"


@router.post('/upload')
async def upload_pdf(file: UploadFile = File(...), user=Depends(get_current_user)):
    """上传 PDF → 存盘 → 提取文本预览"""
    if not file.filename.endswith('.pdf'):
        return {"error": "只支持 PDF 文件"}  # 只看后缀，够用但不是最严的校验

    os.makedirs(UPLOAD_DIR, exist_ok=True)  # 目录不在就建一个
    file_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}.pdf")  # 随机文件名，防覆盖

    content = await file.read()  # 异步把整个文件读进内存
    with open(file_path, 'wb') as f:
        f.write(content)  # 原样落到磁盘

    text = extract_text_from_pdf(file_path)  # 从磁盘文件里抠出纯文本

    return {"filename": file.filename, "text_length": len(text), "text_preview": text[:500]}  # 预览只回前 500 字
