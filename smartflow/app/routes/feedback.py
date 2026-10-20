"""
反馈路由

功能：用户提交反馈，管理员查看统计。
数据流：
  save_feedback(评分+会话id) → 一条反馈落库
  get_feedback_stats() → 点赞点踩汇总
"""
from fastapi import APIRouter, Depends
from app.deps import get_current_user, require_role
from app.services.feedback import save_feedback, get_feedback_stats

router = APIRouter(prefix="/feedback", tags=["反馈"])

@router.post("")
def submit_feedback_route(data: dict, user=Depends(get_current_user)):
    """提交一条反馈（👍/👎）"""
    return save_feedback(
        conversation_id=data.get("conversation_id"),
        user_id=user["user_id"],  # 谁点的按钮从 token 取，不信前端传的
        rating=data["rating"],  # 必填字段，缺了这里会直接报错
        agent_name=data.get("agent_name", "unknown"),
        message_id=data.get("message_id")
    )

@router.get("/stats")
def feedback_stats_route(user=Depends(require_role('admin'))):
    """反馈汇总统计，仅管理员"""
    return get_feedback_stats()