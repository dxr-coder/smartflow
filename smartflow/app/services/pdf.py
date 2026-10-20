"""
PDF 解析服务

功能：从 PDF 文件中提取文本内容。
"""
from pypdf import PdfReader
from io import BytesIO


def extract_text_from_pdf(file_content: bytes) -> str:
    reader = PdfReader(BytesIO(file_content))
    text = ''
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text
    return text
