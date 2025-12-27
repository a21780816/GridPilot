"""
條件單路由
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..dependencies import (
    get_trigger_manager,
    get_user_manager,
    get_authenticated_user,
    require_broker_config
)
from ..models.requests import CreateTriggerOrderRequest, UpdateTriggerOrderRequest
from ..models.responses import (
    TriggerOrderResponse,
    TriggerOrderListResponse,
    StockQuoteResponse,
    SuccessResponse
)
from src.models.enums import TriggerStatus

router = APIRouter(prefix="/api/v1/triggers", tags=["Trigger Orders"])


def _trigger_to_response(trigger) -> TriggerOrderResponse:
    """將 TriggerOrder 轉換為 Response"""
    return TriggerOrderResponse(
        id=trigger.id,
        symbol=trigger.symbol,
        condition=trigger.condition.value,
        trigger_price=trigger.trigger_price,
        order_type=trigger.order_type.value,
        order_action=trigger.order_action.value,
        trade_type=trigger.trade_type.value,
        order_price=trigger.order_price,
        quantity=trigger.quantity,
        broker_name=trigger.broker_name,
        status=trigger.status.value,
        created_at=trigger.created_at,
        triggered_at=trigger.triggered_at,
        executed_at=trigger.executed_at
    )


@router.post("", response_model=TriggerOrderResponse, status_code=status.HTTP_201_CREATED)
async def create_trigger_order(
    request: CreateTriggerOrderRequest,
    user_id: str = Depends(require_broker_config),
    trigger_manager=Depends(get_trigger_manager),
    user_manager=Depends(get_user_manager)
):
    """
    建立條件單

    Args:
        request: 建立條件單請求

    Returns:
        TriggerOrderResponse: 建立的條件單
    """
    # 驗證限價單需要價格
    if request.order_type.value == "limit" and request.order_price is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="限價單必須指定 order_price"
        )

    # 取得券商名稱
    broker_name = request.broker_name
    if not broker_name:
        brokers = user_manager.get_broker_names(user_id)
        broker_name = brokers[0] if brokers else None

    if not broker_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="請指定券商或先在 Telegram 設定券商"
        )

    try:
        trigger = trigger_manager.create_trigger_order(
            user_id=user_id,
            symbol=request.symbol.upper(),
            condition=request.condition.value,
            trigger_price=request.trigger_price,
            order_type=request.order_type.value,
            order_action=request.order_action.value,
            trade_type=request.trade_type.value,
            quantity=request.quantity,
            order_price=request.order_price,
            broker_name=broker_name
        )

        return _trigger_to_response(trigger)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"建立條件單失敗: {str(e)}"
        )


@router.get("", response_model=TriggerOrderListResponse)
async def list_trigger_orders(
    status_filter: Optional[str] = Query(
        None,
        description="狀態篩選 (active, triggered, executed, failed, cancelled)"
    ),
    symbol: Optional[str] = Query(None, description="股票代號篩選"),
    limit: int = Query(50, ge=1, le=100, description="返回數量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
    user_id: str = Depends(get_authenticated_user),
    trigger_manager=Depends(get_trigger_manager)
):
    """
    列出條件單

    Args:
        status_filter: 狀態篩選
        symbol: 股票代號篩選
        limit: 返回數量限制
        offset: 偏移量

    Returns:
        TriggerOrderListResponse: 條件單列表
    """
    # 轉換狀態篩選
    trigger_status = None
    if status_filter:
        try:
            trigger_status = TriggerStatus(status_filter)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"無效的狀態: {status_filter}"
            )

    triggers = trigger_manager.get_user_triggers(user_id, trigger_status)

    # 股票代號篩選
    if symbol:
        symbol = symbol.upper()
        triggers = [t for t in triggers if t.symbol == symbol]

    total = len(triggers)

    # 分頁
    triggers = triggers[offset:offset + limit]

    return TriggerOrderListResponse(
        total=total,
        items=[_trigger_to_response(t) for t in triggers]
    )


@router.get("/{trigger_id}", response_model=TriggerOrderResponse)
async def get_trigger_order(
    trigger_id: str,
    user_id: str = Depends(get_authenticated_user),
    trigger_manager=Depends(get_trigger_manager)
):
    """
    取得條件單詳情

    Args:
        trigger_id: 條件單 ID (完整或前綴)

    Returns:
        TriggerOrderResponse: 條件單詳情
    """
    trigger = trigger_manager.get_trigger_order(trigger_id, user_id)

    if not trigger:
        # 嘗試用前綴查找
        triggers = trigger_manager.get_user_triggers(user_id)
        for t in triggers:
            if t.id.startswith(trigger_id):
                trigger = t
                break

    if not trigger:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"找不到條件單: {trigger_id}"
        )

    return _trigger_to_response(trigger)


@router.put("/{trigger_id}", response_model=TriggerOrderResponse)
async def update_trigger_order(
    trigger_id: str,
    request: UpdateTriggerOrderRequest,
    user_id: str = Depends(get_authenticated_user),
    trigger_manager=Depends(get_trigger_manager)
):
    """
    更新條件單

    只能更新 active 狀態的條件單

    Args:
        trigger_id: 條件單 ID
        request: 更新請求

    Returns:
        TriggerOrderResponse: 更新後的條件單
    """
    # 取得現有條件單
    trigger = trigger_manager.get_trigger_order(trigger_id, user_id)

    if not trigger:
        # 嘗試用前綴查找
        triggers = trigger_manager.get_user_triggers(user_id)
        for t in triggers:
            if t.id.startswith(trigger_id):
                trigger = t
                trigger_id = t.id
                break

    if not trigger:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"找不到條件單: {trigger_id}"
        )

    if trigger.status != TriggerStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"只能更新 active 狀態的條件單，當前狀態: {trigger.status.value}"
        )

    # 準備更新資料
    update_data = {}
    if request.trigger_price is not None:
        update_data['trigger_price'] = request.trigger_price
    if request.order_price is not None:
        update_data['order_price'] = request.order_price
    if request.quantity is not None:
        update_data['quantity'] = request.quantity

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="沒有提供更新資料"
        )

    try:
        updated = trigger_manager.update_trigger_order(trigger_id, user_id, update_data)

        if not updated:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="更新失敗"
            )

        return _trigger_to_response(updated)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新條件單失敗: {str(e)}"
        )


@router.delete("/{trigger_id}", response_model=SuccessResponse)
async def delete_trigger_order(
    trigger_id: str,
    user_id: str = Depends(get_authenticated_user),
    trigger_manager=Depends(get_trigger_manager)
):
    """
    刪除/取消條件單

    Args:
        trigger_id: 條件單 ID

    Returns:
        SuccessResponse: 刪除結果
    """
    # 取得現有條件單
    trigger = trigger_manager.get_trigger_order(trigger_id, user_id)

    if not trigger:
        # 嘗試用前綴查找
        triggers = trigger_manager.get_user_triggers(user_id)
        for t in triggers:
            if t.id.startswith(trigger_id):
                trigger = t
                trigger_id = t.id
                break

    if not trigger:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"找不到條件單: {trigger_id}"
        )

    success = trigger_manager.cancel_trigger_order(trigger_id, user_id)

    if success:
        return SuccessResponse(
            success=True,
            message=f"條件單 {trigger_id[:8]} 已取消"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="無法取消此條件單，可能已被觸發或執行"
        )


# 股價查詢
@router.get("/stocks/{symbol}/quote", response_model=StockQuoteResponse)
async def get_stock_quote(
    symbol: str,
    user_id: str = Depends(get_authenticated_user),
    user_manager=Depends(get_user_manager)
):
    """
    取得股票即時報價

    Args:
        symbol: 股票代號

    Returns:
        StockQuoteResponse: 股票報價
    """
    from src.core.stock_info import get_stock_quote as fetch_quote

    symbol = symbol.upper()

    try:
        quote = await fetch_quote(symbol)

        if not quote:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"找不到股票: {symbol}"
            )

        return StockQuoteResponse(
            symbol=symbol,
            name=quote.get('name'),
            price=quote.get('closePrice', 0),
            change=quote.get('change'),
            change_percent=quote.get('changePercent'),
            open=quote.get('openPrice'),
            high=quote.get('highPrice'),
            low=quote.get('lowPrice'),
            volume=quote.get('totalVolume'),
            timestamp=quote.get('lastUpdated')
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查詢股價失敗: {str(e)}"
        )
