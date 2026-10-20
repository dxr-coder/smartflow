"""
批量上传知识库文档

功能：把 docs/knowledge/ 下的新文档批量上传到已运行的后端(8000)，触发真实切片+向量化入库。
数据流：读取每篇文档 → multipart POST /documents（带 department）→ 后端 parse→chunk→embed→存 MySQL+Chroma。

用法：
  1. 确保后端已在 8000 运行（uvicorn）
  2. "D:/DevCache/conda/envs/mianshi/python.exe" -X utf8 scripts/upload_kb.py
说明：只上传新文档，跳过已入库的 4 篇（HR/IT/行政/财务）。同名文档重传会自动升版本。
"""
import os
import sys
import time
import urllib.request
import json
from pathlib import Path

API = "http://localhost:8000"
DOCS_DIR = Path(__file__).resolve().parent.parent / "docs" / "knowledge"

# 已在库的 4 篇，跳过
ALREADY = {"HR员工手册.md", "IT服务指南.md", "行政管理规范.md", "财务报销制度.md"}

# 文件名 → department 字段（hr/it/admin/finance/all）
DEPT = {
    # HR 线
    "招聘与录用制度.md": "hr",
    "培训与发展管理办法.md": "hr",
    "考勤与请休假细则.md": "hr",
    "薪酬与调薪制度.md": "hr",
    "绩效考核办法.md": "hr",
    "社保与福利制度.md": "hr",
    "员工关系与奖惩制度.md": "hr",
    "入职与离职指引.md": "hr",
    "职称与资格津贴管理办法.md": "hr",
    # IT 线
    "信息安全管理制度.md": "it",
    "网络与系统运维规范.md": "it",
    "软件使用与正版化制度.md": "it",
    "数据备份与恢复管理办法.md": "it",
    # 行政线
    "会议室预订与使用规范.md": "admin",
    "办公用品与资产管理制度.md": "admin",
    "公务用车与差旅行政规范.md": "admin",
    "来访接待与安全管理制度.md": "admin",
    # 财务线
    "差旅费报销实施细则.md": "finance",
    "预算管理制度.md": "finance",
    "资金支付与审批权限办法.md": "finance",
    "发票与税务管理办法.md": "finance",
    "固定资产折旧与盘点制度.md": "finance",
    "费用报销系统操作手册.md": "finance",
    "财务报销常见问题FAQ.md": "finance",
    # 综合线
    "员工行为准则.md": "all",
    "组织架构与部门职责.md": "all",
    "合规与商业道德手册.md": "all",
    "SmartFlow助手使用指南.md": "all",
}


def login():
    """登录取 admin token（dxr 是唯一 admin）"""
    req = urllib.request.Request(
        f"{API}/auth/login?username=dxr&password=123456", method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["access_token"]


def upload_one(token, path, department):
    """单篇 multipart 上传，返回 (ok, msg)"""
    boundary = "----kbupload7f3a9c"
    filename = path.name
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="department"\r\n\r\n'
        f"{department}\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: text/markdown\r\n\r\n"
    ).encode("utf-8") + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(
        f"{API}/documents",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            out = json.loads(resp.read().decode("utf-8"))
            if "error" in out:
                return False, out["error"]
            return True, f"{out.get('chunk_count', '?')} 片 v{out.get('version', '?')}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read().decode('utf-8', 'ignore')[:120]}"
    except Exception as e:
        return False, str(e)[:120]


def main():
    if not DOCS_DIR.exists():
        print("目录不存在:", DOCS_DIR)
        sys.exit(1)
    print("登录中…")
    token = login()
    print("登录成功\n")

    files = sorted(
        f for f in DOCS_DIR.glob("*.md") if f.name not in ALREADY
    )
    print(f"待上传 {len(files)} 篇（已跳过库内 4 篇）\n")

    ok = fail = 0
    for i, f in enumerate(files, 1):
        dept = DEPT.get(f.name, "all")
        t0 = time.time()
        print(f"[{i}/{len(files)}] {f.name}  (dept={dept}) …", end=" ", flush=True)
        success, msg = upload_one(token, f, dept)
        dt = time.time() - t0
        if success:
            ok += 1
            print(f"✓ {msg}  ({dt:.1f}s)")
        else:
            fail += 1
            print(f"✗ {msg}  ({dt:.1f}s)")

    print(f"\n完成：成功 {ok}，失败 {fail}，共 {len(files)} 篇")
    if fail:
        print("有失败项，重跑本脚本会自动跳过已成功的（同名文档会升版本，注意）")


if __name__ == "__main__":
    main()
