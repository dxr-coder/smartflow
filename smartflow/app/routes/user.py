"""
用户管理路由

功能：管理员查看和管理用户。
"""
from fastapi import APIRouter, Depends
from app.deps import require_role
from app.services.user import get_users, update_user_role, update_user_status

router = APIRouter(prefix="/users", tags=["用户管理"])


@router.get('')
def get_users_route(user=Depends(require_role('admin'))):
    # 全量用户列表，只有 admin 能看
    return get_users()


@router.put('/{user_id}/role')
def update_user_role_route(user_id: int, role_name: str, user=Depends(require_role('admin'))):
    # 改角色（user/agent/admin），只能 admin 操作
    return update_user_role(user_id=user_id, role_name=role_name)


@router.put('/{user_id}/status')
def update_status_route(user_id: int, status: str, user=Depends(require_role('admin'))):
    # 启用/禁用账号
    return update_user_status(user_id, status)
