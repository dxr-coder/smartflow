"""
文档解析服务
功能：按格式分流解析，常用格式走专用库（快），复杂格式走 Unstructured（全）。
"""
import os
from io import BytesIO


def parse_file(filename: str, content: bytes) -> str:
    # 按扩展名分流：常见格式用轻量专用库，冷门格式兜底给 Unstructured
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".pdf":
        return _parse_pdf(content)
    elif ext == ".docx":
        return _parse_docx(content)
    elif ext == ".xlsx":
        return _parse_xlsx(content)
    elif ext == ".csv":
        return _parse_csv(content)
    elif ext in (".txt", ".md"):
        return content.decode("utf-8", errors="ignore")  # 纯文本直接解码，坏字节跳过
    elif ext == ".html":
        return _parse_html(content)
    else:
        return _parse_unstructured(filename, content)

def _parse_pdf(content: bytes) -> str:
    import fitz  # PyMuPDF，解析快
    doc = fitz.open(stream=content, filetype="pdf")
    texts = [page.get_text().strip() for page in doc if page.get_text().strip()]
    doc.close()
    # 提出来不到 50 字 → 多半是扫描版 PDF（图片没文字），换 Unstructured 试试 OCR 路线
    if len("\n".join(texts)) < 50:
        return _parse_unstructured("dummy.pdf", content)
    return "\n\n".join(texts)  # 每页之间空行隔开，保留页边界

def _parse_docx(content: bytes) -> str:
    from docx import Document
    doc = Document(BytesIO(content))
    return "\n\n".join(p.text.strip() for p in doc.paragraphs if p.text.strip())


def _parse_xlsx(content: bytes) -> str:
    from openpyxl import load_workbook
    wb = load_workbook(BytesIO(content), read_only=True, data_only=True)
    texts = []
    for sheet in wb:
        for row in sheet.iter_rows(values_only=True):
            line = " | ".join(str(c) for c in row if c is not None)
            if line.strip():
                texts.append(line)
    wb.close()
    return "\n".join(texts)


def _parse_csv(content: bytes) -> str:
    import csv
    reader = csv.reader(content.decode("utf-8", errors="ignore").splitlines())
    return "\n".join(" | ".join(row) for row in reader if any(row))


def _parse_html(content: bytes) -> str:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(content.decode("utf-8", errors="ignore"), "html.parser")
    return soup.get_text(separator="\n", strip=True)


def _parse_unstructured(filename: str, content: bytes) -> str:
    from unstructured.partition.auto import partition
    elements = partition(file=BytesIO(content), metadata_filename=filename, strategy="fast")
    return "\n\n".join(str(el) for el in elements if str(el).strip())