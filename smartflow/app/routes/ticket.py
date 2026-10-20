"""
工单路由

功能：定义工单相关的 HTTP 接口。
"""
from fastapi import APIRouter, Depends
from app.deps import get_current_user, require_role
from app.services.ticket import (
    create_ticket, get_ticket, get_ticket_detail,
    update_ticket_status, get_sla_status, trigger_sla_check
)
from app.services.ticket_approval import get_pending_approvals, decide_approval

router = APIRouter(prefix="/tickets", tags=["工单"])


@router.get('')
def get_ticket_route(user=Depends(get_current_user)):
    return get_ticket(user['user_id'], user['role'])


@router.post("/sla/check")  # 注意：要放在 /{ticket_id} 前面，否则 "sla" 会被当成 ticket_id
def sla_check_route(user=Depends(require_role('admin'))):
    return trigger_sla_check()


@router.post('')
def create_ticket_route(title: str, content: str = '', category: str = None,
                        priority: str = 'normal', user=Depends(get_current_user)):
    return create_ticket(user['user_id'], title, content, category=category, priority=priority)


@router.get("/approvals/pending")  # 固定路径，必须在 /{ticket_id} 前面
def pending_approvals_route(user=Depends(get_current_user)):
    """待审批列表。agent/admin 都能进（admin 要有 agent 角色之外的路径，
    实际按 token 里的 role 过滤级别），角色不匹配的级根本查不出来。"""
    return get_pending_approvals(user["role"])


@router.get("/{ticket_id}")
def get_ticket_detail_route(ticket_id: int, user=Depends(get_current_user)):
    return get_ticket_detail(ticket_id, user["user_id"], user["role"])


@router.put("/{ticket_id}/status")
def update_status_route(ticket_id: int, new_status: str, user=Depends(require_role('agent'))):
    return update_ticket_status(ticket_id, new_status)


@router.get("/{ticket_id}/sla")
def get_sla_route(ticket_id: int, user=Depends(get_current_user)):
    return get_sla_status(ticket_id, user["user_id"], user["role"])


@router.post("/{ticket_id}/approvals/{level}/approve")
def approve_route(ticket_id: int, level: int, comment: str = '', user=Depends(get_current_user)):
    # 用 get_current_user 不锁角色：agent 和 admin 都要用，权限在 decide_approval 里按级校验
    return decide_approval(ticket_id, level, user, "approve", comment)


@router.post("/{ticket_id}/approvals/{level}/reject")
def reject_route(ticket_id: int, level: int, comment: str = '', user=Depends(get_current_user)):
    return decide_approval(ticket_id, level, user, "reject", comment)
