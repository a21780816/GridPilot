"""
投資組合路由
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.brokers import get_broker as create_broker

from ..dependencies import (
    get_user_manager,
    get_authenticated_user,
    require_broker_config
)
from ..models.responses import (
    PositionResponse,
    PositionListResponse,
    AccountBalanceResponse,
    OrderInfoResponse,
    OrderListResponse,
    TransactionResponse,
    TransactionListResponse,
    SettlementResponse,
    SettlementListResponse,
    PortfolioSummaryResponse
)

router = APIRouter(prefix="/api/v1/portfolio", tags=["Portfolio"])


def _get_broker(user_id: str, user_manager, broker_name: Optional[str] = None):
    """取得券商實例"""
    if not broker_name:
        brokers = user_manager.get_broker_names(user_id)
        broker_name = brokers[0] if brokers else None

    if not broker_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="請先在 Telegram 使用 /broker 設定券商"
        )

    # 取得券商設定
    broker_config = user_manager.get_broker_config(user_id, broker_name)
    if not broker_config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"找不到券商設定: {broker_name}"
        )

    # 建立券商實例
    try:
        broker = create_broker(broker_name, broker_config)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"無法連接券商 {broker_name}: {str(e)}"
        )

    if not broker:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"無法連接券商: {broker_name}"
        )

    return broker


@router.get("/summary", response_model=PortfolioSummaryResponse)
async def get_portfolio_summary(
    broker_name: Optional[str] = Query(None, description="券商名稱"),
    user_id: str = Depends(require_broker_config),
    user_manager=Depends(get_user_manager)
):
    """
    取得投資組合摘要

    Returns:
        PortfolioSummaryResponse: 投資組合摘要
    """
    try:
        broker = _get_broker(user_id, user_manager, broker_name)

        positions = broker.get_all_positions()
        balance = broker.get_balance()

        total_market_value = sum(p.market_value for p in positions)
        total_cost_value = sum(p.cost_value for p in positions)
        total_unrealized_pnl = total_market_value - total_cost_value
        total_unrealized_pnl_percent = (
            (total_unrealized_pnl / total_cost_value * 100) if total_cost_value > 0 else 0
        )
        available_balance = balance.available_balance if balance else 0

        return PortfolioSummaryResponse(
            total_market_value=total_market_value,
            total_cost_value=total_cost_value,
            total_unrealized_pnl=total_unrealized_pnl,
            total_unrealized_pnl_percent=round(total_unrealized_pnl_percent, 2),
            available_balance=available_balance,
            total_assets=total_market_value + available_balance,
            position_count=len(positions)
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"取得投資組合摘要失敗: {str(e)}"
        )


@router.get("/positions", response_model=PositionListResponse)
async def list_positions(
    broker_name: Optional[str] = Query(None, description="券商名稱"),
    user_id: str = Depends(require_broker_config),
    user_manager=Depends(get_user_manager)
):
    """
    取得所有持倉

    Returns:
        PositionListResponse: 持倉列表
    """
    try:
        broker = _get_broker(user_id, user_manager, broker_name)
        positions = broker.get_all_positions()

        total_market_value = sum(p.market_value for p in positions)
        total_cost_value = sum(p.cost_value for p in positions)
        total_unrealized_pnl = total_market_value - total_cost_value
        total_unrealized_pnl_percent = (
            (total_unrealized_pnl / total_cost_value * 100) if total_cost_value > 0 else 0
        )

        items = [
            PositionResponse(
                symbol=p.symbol,
                symbol_name=p.symbol_name,
                quantity=p.quantity,
                avg_price=p.avg_price,
                current_price=p.current_price,
                unrealized_pnl=p.unrealized_pnl,
                unrealized_pnl_percent=p.unrealized_pnl_percent,
                market_value=p.market_value,
                cost_value=p.cost_value,
                today_pnl=p.today_pnl
            )
            for p in positions
        ]

        return PositionListResponse(
            total=len(positions),
            total_market_value=total_market_value,
            total_cost_value=total_cost_value,
            total_unrealized_pnl=total_unrealized_pnl,
            total_unrealized_pnl_percent=round(total_unrealized_pnl_percent, 2),
            items=items
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"取得持倉失敗: {str(e)}"
        )


@router.get("/positions/{symbol}", response_model=PositionResponse)
async def get_position(
    symbol: str,
    broker_name: Optional[str] = Query(None, description="券商名稱"),
    user_id: str = Depends(require_broker_config),
    user_manager=Depends(get_user_manager)
):
    """
    取得單一持倉

    Args:
        symbol: 股票代號

    Returns:
        PositionResponse: 持倉資訊
    """
    try:
        broker = _get_broker(user_id, user_manager, broker_name)
        symbol = symbol.upper()

        position = broker.get_position(symbol)

        if not position:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"找不到持倉: {symbol}"
            )

        return PositionResponse(
            symbol=position.symbol,
            symbol_name=position.symbol_name,
            quantity=position.quantity,
            avg_price=position.avg_price,
            current_price=position.current_price,
            unrealized_pnl=position.unrealized_pnl,
            unrealized_pnl_percent=position.unrealized_pnl_percent,
            market_value=position.market_value,
            cost_value=position.cost_value,
            today_pnl=position.today_pnl
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"取得持倉失敗: {str(e)}"
        )


@router.get("/balance", response_model=AccountBalanceResponse)
async def get_balance(
    broker_name: Optional[str] = Query(None, description="券商名稱"),
    user_id: str = Depends(require_broker_config),
    user_manager=Depends(get_user_manager)
):
    """
    取得帳戶餘額

    Returns:
        AccountBalanceResponse: 帳戶餘額
    """
    try:
        broker = _get_broker(user_id, user_manager, broker_name)
        balance = broker.get_balance()

        if not balance:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="無法取得帳戶餘額"
            )

        return AccountBalanceResponse(
            available_balance=balance.available_balance,
            total_balance=balance.total_balance,
            settled_balance=balance.settled_balance,
            unsettled_amount=balance.unsettled_amount,
            margin_available=balance.margin_available,
            short_available=balance.short_available,
            currency=balance.currency
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"取得帳戶餘額失敗: {str(e)}"
        )


@router.get("/orders", response_model=OrderListResponse)
async def list_orders(
    status_filter: Optional[str] = Query(
        None,
        description="狀態篩選 (pending, partial, filled, cancelled, failed)"
    ),
    broker_name: Optional[str] = Query(None, description="券商名稱"),
    user_id: str = Depends(require_broker_config),
    user_manager=Depends(get_user_manager)
):
    """
    取得今日委託單

    Args:
        status_filter: 狀態篩選

    Returns:
        OrderListResponse: 委託單列表
    """
    try:
        broker = _get_broker(user_id, user_manager, broker_name)
        orders = broker.get_orders()

        # 狀態篩選
        if status_filter:
            orders = [o for o in orders if o.status == status_filter]

        items = [
            OrderInfoResponse(
                order_no=o.order_no,
                symbol=o.symbol,
                symbol_name=o.symbol_name,
                side=o.side,
                price=o.price,
                quantity=o.quantity,
                filled_qty=o.filled_qty,
                filled_price=o.filled_price,
                status=o.status,
                order_time=o.order_time,
                trade_type=o.trade_type
            )
            for o in orders
        ]

        return OrderListResponse(
            total=len(orders),
            items=items
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"取得委託單失敗: {str(e)}"
        )


@router.get("/transactions", response_model=TransactionListResponse)
async def list_transactions(
    start_date: Optional[str] = Query(None, description="開始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="結束日期 (YYYY-MM-DD)"),
    broker_name: Optional[str] = Query(None, description="券商名稱"),
    user_id: str = Depends(require_broker_config),
    user_manager=Depends(get_user_manager)
):
    """
    取得成交紀錄

    Args:
        start_date: 開始日期
        end_date: 結束日期

    Returns:
        TransactionListResponse: 成交紀錄列表
    """
    try:
        broker = _get_broker(user_id, user_manager, broker_name)
        transactions = broker.get_transactions(start_date, end_date)

        total_amount = sum(t.amount for t in transactions)
        total_fee = sum(t.fee for t in transactions)
        total_tax = sum(t.tax for t in transactions)

        items = [
            TransactionResponse(
                trade_no=t.trade_no,
                order_no=t.order_no,
                symbol=t.symbol,
                symbol_name=t.symbol_name,
                side=t.side,
                price=t.price,
                quantity=t.quantity,
                amount=t.amount,
                fee=t.fee,
                tax=t.tax,
                net_amount=t.net_amount,
                trade_time=t.trade_time,
                trade_type=t.trade_type
            )
            for t in transactions
        ]

        return TransactionListResponse(
            total=len(transactions),
            total_amount=total_amount,
            total_fee=total_fee,
            total_tax=total_tax,
            items=items
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"取得成交紀錄失敗: {str(e)}"
        )


@router.get("/settlements", response_model=SettlementListResponse)
async def list_settlements(
    broker_name: Optional[str] = Query(None, description="券商名稱"),
    user_id: str = Depends(require_broker_config),
    user_manager=Depends(get_user_manager)
):
    """
    取得交割資訊

    Returns:
        SettlementListResponse: 交割資訊列表
    """
    try:
        broker = _get_broker(user_id, user_manager, broker_name)
        settlements = broker.get_settlements()

        items = [
            SettlementResponse(
                date=s.date,
                amount=s.amount,
                status=s.status
            )
            for s in settlements
        ]

        return SettlementListResponse(
            total=len(settlements),
            items=items
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"取得交割資訊失敗: {str(e)}"
        )
