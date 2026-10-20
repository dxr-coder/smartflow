"""
工单转接路由

功能：转接的发起、查询（转给我/我发起/全部）、接受、拒绝、候选坐席列表。
"""
from fastapi import APIRouter, Depends
from app.deps import get_current_user
from app.services.transfer import (
    create_transfer, get_transfers, accept_transfer,
    decline_transfer, get_transfer_agents,
)

router = APIRouter(prefix='/transfer', tags=['工单转接'])


@router.post('')
def create_route(ticket_id: int, target_agent_id: int, reason: str = '',
                 user=Depends(get_current_user)):
    # 普通用户也能发起（把单转给坐席），细粒度校验在 service 里
    return create_transfer(ticket_id, user['user_id'], target_agent_id, reason)


@router.get('')
def list_route(scope: str = 'mine', status: str = '', user=Depends(get_current_user)):
    # 默认只看转给我的；all 的权限在 service 里判
    return get_transfers(user, scope=scope, status=status)


@router.get('/agents')
def agents_route(user=Depends(get_current_user)):
    return get_transfer_agents(user)


@router.put('/{transfer_id}/accept')
def accept_route(transfer_id: int, user=Depends(get_current_user)):
    # 不锁 agent 角色：权限精确到"这条是不是转给你的"
    return accept_transfer(transfer_id, user)


@router.put('/{transfer_id}/decline')
def decline_route(transfer_id: int, user=Depends(get_current_user)):
    return decline_transfer(transfer_id, user)
