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
    StockFundamentalResponse,
    InstitutionalInvestorResponse,
    StockDetailResponse,
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
            order_action=request.order_action.value,
            order_type=request.order_type.value,
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


# 股價查詢路由 - 放在 triggers 外避免路徑衝突
stocks_router = APIRouter(prefix="/api/v1/stocks", tags=["Stocks"])


@stocks_router.get("/{symbol}/quote", response_model=StockQuoteResponse)
async def get_stock_quote(
    symbol: str,
    user_id: str = Depends(get_authenticated_user)
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
            symbol=quote.symbol,
            name=quote.name,
            price=quote.price,
            change=quote.change,
            change_percent=quote.change_percent,
            open=quote.open,
            high=quote.high,
            low=quote.low,
            close=quote.close,
            yesterday=quote.yesterday,
            volume=quote.volume,
            amount=quote.amount,
            bid_price=quote.bid_price,
            ask_price=quote.ask_price,
            limit_up=quote.limit_up,
            limit_down=quote.limit_down,
            amplitude=quote.amplitude,
            timestamp=quote.timestamp,
            market=quote.market
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查詢股價失敗: {str(e)}"
        )


@stocks_router.get("/{symbol}/detail", response_model=StockDetailResponse)
async def get_stock_detail_info(
    symbol: str,
    user_id: str = Depends(get_authenticated_user)
):
    """
    取得股票完整資訊 (報價 + 基本面 + 法人買賣超)

    Args:
        symbol: 股票代號

    Returns:
        StockDetailResponse: 股票完整資訊
    """
    from src.core.stock_info import get_stock_detail as fetch_detail

    symbol = symbol.upper()

    try:
        detail = await fetch_detail(symbol)

        if not detail:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"找不到股票: {symbol}"
            )

        # 轉換報價
        quote_resp = StockQuoteResponse(
            symbol=detail.quote.symbol,
            name=detail.quote.name,
            price=detail.quote.price,
            change=detail.quote.change,
            change_percent=detail.quote.change_percent,
            open=detail.quote.open,
            high=detail.quote.high,
            low=detail.quote.low,
            close=detail.quote.close,
            yesterday=detail.quote.yesterday,
            volume=detail.quote.volume,
            amount=detail.quote.amount,
            bid_price=detail.quote.bid_price,
            ask_price=detail.quote.ask_price,
            limit_up=detail.quote.limit_up,
            limit_down=detail.quote.limit_down,
            amplitude=detail.quote.amplitude,
            timestamp=detail.quote.timestamp,
            market=detail.quote.market
        )

        # 轉換基本面
        fundamental_resp = None
        if detail.fundamental:
            f = detail.fundamental
            fundamental_resp = StockFundamentalResponse(
                symbol=f.symbol,
                name=f.name or None,
                pe_ratio=f.pe_ratio or None,
                pb_ratio=f.pb_ratio or None,
                dividend_yield=f.dividend_yield or None,
                eps=f.eps or None,
                market_cap=f.market_cap or None,
                shares_outstanding=f.shares_outstanding or None
            )

        # 轉換法人買賣超
        institutional_resp = None
        if detail.institutional:
            i = detail.institutional
            institutional_resp = InstitutionalInvestorResponse(
                symbol=i.symbol,
                date=i.date or None,
                foreign_buy=i.foreign_buy or None,
                foreign_sell=i.foreign_sell or None,
                foreign_net=i.foreign_net,
                investment_trust_buy=i.investment_trust_buy or None,
                investment_trust_sell=i.investment_trust_sell or None,
                investment_trust_net=i.investment_trust_net,
                dealer_buy=i.dealer_buy or None,
                dealer_sell=i.dealer_sell or None,
                dealer_net=i.dealer_net,
                total_net=i.total_net
            )

        return StockDetailResponse(
            quote=quote_resp,
            fundamental=fundamental_resp,
            institutional=institutional_resp
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查詢股票資訊失敗: {str(e)}"
        )


@stocks_router.get("/{symbol}/fundamental", response_model=StockFundamentalResponse)
async def get_stock_fundamental_info(
    symbol: str,
    user_id: str = Depends(get_authenticated_user)
):
    """
    取得股票基本面資訊 (本益比、殖利率等)

    Args:
        symbol: 股票代號

    Returns:
        StockFundamentalResponse: 基本面資訊
    """
    from src.core.stock_info import get_stock_fundamental as fetch_fundamental

    symbol = symbol.upper()

    try:
        fundamental = await fetch_fundamental(symbol)

        if not fundamental:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"找不到股票基本面資料: {symbol}"
            )

        return StockFundamentalResponse(
            symbol=fundamental.symbol,
            name=fundamental.name or None,
            pe_ratio=fundamental.pe_ratio or None,
            pb_ratio=fundamental.pb_ratio or None,
            dividend_yield=fundamental.dividend_yield or None,
            eps=fundamental.eps or None,
            market_cap=fundamental.market_cap or None,
            shares_outstanding=fundamental.shares_outstanding or None
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查詢基本面失敗: {str(e)}"
        )


@stocks_router.get("/{symbol}/institutional", response_model=InstitutionalInvestorResponse)
async def get_stock_institutional_info(
    symbol: str,
    user_id: str = Depends(get_authenticated_user)
):
    """
    取得股票法人買賣超資訊

    Args:
        symbol: 股票代號

    Returns:
        InstitutionalInvestorResponse: 法人買賣超資訊
    """
    from src.core.stock_info import get_institutional_investor as fetch_institutional

    symbol = symbol.upper()

    try:
        institutional = await fetch_institutional(symbol)

        if not institutional:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"找不到法人買賣超資料: {symbol}"
            )

        return InstitutionalInvestorResponse(
            symbol=institutional.symbol,
            date=institutional.date or None,
            foreign_buy=institutional.foreign_buy or None,
            foreign_sell=institutional.foreign_sell or None,
            foreign_net=institutional.foreign_net,
            investment_trust_buy=institutional.investment_trust_buy or None,
            investment_trust_sell=institutional.investment_trust_sell or None,
            investment_trust_net=institutional.investment_trust_net,
            dealer_buy=institutional.dealer_buy or None,
            dealer_sell=institutional.dealer_sell or None,
            dealer_net=institutional.dealer_net,
            total_net=institutional.total_net
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查詢法人買賣超失敗: {str(e)}"
        )
