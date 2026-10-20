"""
CSAT 满意度路由

数据流：
  GET /csat/stats        → 管理页汇总（必须声明在 /{ticket_id} 前面！）
  GET /csat/{ticket_id}  → 单张工单已有评分（前端初始态，没有返回 null）
  POST /csat/{ticket_id}?score=&comment= → 提交评分（评分人 = 当前登录人）
"""
from fastapi import APIRouter, Depends
from app.deps import get_current_user, require_role
from app.services.csat import submit_csat, get_csat, get_csat_stats

router = APIRouter(prefix="/csat", tags=["满意度"])


# 顺序坑：stats 必须在 /{ticket_id} 前面，否则 "stats" 被当成 ticket_id 去转 int，422
@router.get("/stats")
def stats_route(user=Depends(require_role('admin'))):
    return get_csat_stats()


@router.get("/{ticket_id}")
def get_route(ticket_id: int, user=Depends(get_current_user)):
    return get_csat(ticket_id)


@router.post("/{ticket_id}")
def submit_route(ticket_id: int, score: int, comment: str = "", user=Depends(get_current_user)):
    # 简单类型参数走 query string，跟项目惯例一致
    return submit_csat(ticket_id, user, score, comment)
