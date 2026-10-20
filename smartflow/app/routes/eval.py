"""
RAG 评测路由（工业化版 v3）

数据流（全部 admin 权限）：
  GET    /eval/documents            → 新增用例的文档下拉框（filename + version）
  GET    /eval/cases                → 金标集列表（每条含 docs + is_answerable）
  POST   /eval/cases   Body 多文档版 → 新增用例；is_answerable=false 建负例（docs 须为空）
  DELETE /eval/cases/{id}           → 删除用例（级联删 eval_case_docs）
  POST   /eval/run?variant=A|B&rewrite=            → 检索层评测，同步落库返回摘要
  POST   /eval/run-generation?variant=A|B&rewrite= → 生成层评测异步启动，立即回 {job_id}
         &sync=true                                      → 同步路径（冒烟/调试用）
  GET    /eval/job/{job_id}         → 生成评测进度（前端 5s 轮询：status/done/total/phase/error）
  GET    /eval/runs                 → 历史运行列表（近 50 条，含 mode/refusal_rate/answerable_count）
  GET    /eval/runs/{id}            → 单轮明细（逐用例 retrieved + 答案 + judge + 分类别 slices）
  GET    /eval/compare?a_id=&b_id=  → 两轮配对显著性（McNemar / bootstrap，读时计算）
"""
from fastapi import APIRouter, Depends, Body
from app.deps import require_role
from app.services.eval import (
    list_cases, list_documents, add_case, delete_case,
    run_eval, run_generation_eval, start_generation_job, get_job,
    list_runs, get_run_detail, compare_runs,
)

router = APIRouter(prefix="/eval", tags=["RAG评测"])
admin = Depends(require_role('admin'))


@router.get("/documents")
def documents_route(user=admin):
    return list_documents()


@router.get("/cases")
def cases_route(user=admin):
    return list_cases()


@router.post("/cases")
def add_case_route(payload: dict = Body(...), user=admin):
    # Body: 正例 {"question", "category", "docs": [{"filename", "grade": 2|1}, ...]}
    #        负例 {"question", "category": "unanswerable", "is_answerable": false, "docs": []}
    return add_case(payload)


@router.delete("/cases/{case_id}")
def delete_case_route(case_id: int, user=admin):
    return delete_case(case_id)


@router.post("/run")
def run_route(variant: str, note: str = "", rewrite: bool = False, user=admin):
    # rewrite=True：检索前先经查询重写层（LLM 改写）；与 variant（top_k+2）正交
    # 同步循环：每用例一次 hybrid_search；首跑含 reranker 模型加载（约 1 分钟）
    # 排名指标只统计可回答用例（answerable_count），负例只落 retrieved 快照
    return run_eval(variant, note, rewrite=rewrite)


@router.post("/run-generation")
def run_generation_route(variant: str, note: str = "", rewrite: bool = False,
                         sync: bool = False, user=admin):
    # 默认异步：起 daemon 线程立即返回 {job_id}，前端轮询 /eval/job/{id} 看进度
    # 123 例 × 2 次 LLM 调用约 30-40 分钟；已有任务在跑时 409
    # sync=true 走旧同步路径（curl 冒烟小样本用；大样本别用，HTTP 会挂）
    if sync:
        return run_generation_eval(variant, note, rewrite=rewrite)
    return start_generation_job(variant, note, rewrite=rewrite)


@router.get("/job/{job_id}")
def job_route(job_id: str, user=admin):
    # {status: running|done|error, done, total, phase, run_id, error}
    # 内存表单进程专用；服务重启 → 404；running 超 45 分钟自动判 error（--reload 杀线程兜底）
    return get_job(job_id)


@router.get("/runs")
def runs_route(user=admin):
    return list_runs()


@router.get("/runs/{run_id}")
def run_detail_route(run_id: int, user=admin):
    # results 每行带 category/is_answerable（LEFT JOIN，用例删了也能看历史）
    # run.slices：{category: {n, n_answerable, n_negative, hit1, recall5, mrr, ndcg5,
    #                        faithfulness, relevance, refusal_rate}} 读时聚合
    return get_run_detail(run_id)


@router.get("/compare")
def compare_route(a_id: int, b_id: int, user=admin):
    # 配对显著性：Hit@1 用 exact McNemar，连续指标（含生成层 F/R/refusal）用 paired bootstrap
    # 回归门禁：某指标 Δ 的 95% CI 完全在 0 以下 = 显著劣化应拦截
    return compare_runs(a_id, b_id)
