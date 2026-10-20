"""
资产路由

功能：IT资产的查询、入库、领用、归还、报废、流水接口。
"""
from fastapi import APIRouter, Depends
from app.deps import get_current_user, require_role
from app.services.asset import (
    list_assets, create_asset, borrow_asset,
    return_asset, scrap_asset, get_asset_logs,
)

router = APIRouter(prefix="/assets", tags=["资产"])


@router.get('')
def list_assets_route(status: str = None, category: str = None, mine: bool = False,
                      user=Depends(get_current_user)):
    # 所有登录用户都能看台账（公司资产本来就该透明），mine 只是过滤条件
    return list_assets(user, status=status, category=category, mine=mine)


@router.post("")
def create_asset_route(
        asset_no: str,
        category: str,
        model: str = "",
        purchase_date: str = None,
        price: float = None,
        warranty_end: str = None,
        location: str = "",
        note: str = "",
        user=Depends(require_role("admin")),
):
    return create_asset(
        user, asset_no, category, model,
        purchase_date=purchase_date, price=price,
        warranty_end=warranty_end, location=location, note=note,
    )


@router.post('/{asset_id}/borrow')
def borrow_route(asset_id: int, user=Depends(get_current_user)):
    return borrow_asset(asset_id, user)


@router.post('/{asset_id}/return')
def return_route(asset_id: int, user=Depends(get_current_user)):
    # 这里不能锁 admin：本人归还是主路径。代还权限在 service 里按 is_admin 判
    is_admin = user["role"] == "admin"
    return return_asset(asset_id, user, is_admin)


@router.post('/{asset_id}/scrap')
def scrap_route(asset_id: int, reason: str = '', user=Depends(require_role('admin'))):
    return scrap_asset(asset_id, user, reason)


@router.get('/{asset_id}/logs')
def logs_route(asset_id: int, user=Depends(require_role('admin'))):
    return get_asset_logs(asset_id, user)
