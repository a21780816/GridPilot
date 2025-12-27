"""
股票資訊查詢服務
使用公開 API 查詢台股即時資訊
"""

import asyncio
import logging
from typing import Dict, Optional
from dataclasses import dataclass

import httpx

logger = logging.getLogger('StockInfo')

# HTTP 重試設定
HTTP_MAX_RETRIES = 3
HTTP_RETRY_DELAY = 0.5  # 秒

# 台股股票名稱對照（常用）
STOCK_NAMES = {
    '2330': '台積電',
    '2317': '鴻海',
    '2454': '聯發科',
    '2412': '中華電',
    '2882': '國泰金',
    '2881': '富邦金',
    '2891': '中信金',
    '2886': '兆豐金',
    '2884': '玉山金',
    '2892': '第一金',
    '0050': '元大台灣50',
    '0056': '元大高股息',
    '00878': '國泰永續高股息',
    '00713': '元大台灣高息低波',
    '006208': '富邦台50',
}


@dataclass
class StockQuote:
    """股票報價資料"""
    symbol: str
    name: str
    price: float           # 現價
    change: float          # 漲跌
    change_percent: float  # 漲跌幅 %
    open: float            # 開盤價
    high: float            # 最高價
    low: float             # 最低價
    volume: int            # 成交量 (張)
    timestamp: str         # 更新時間


async def get_stock_quote(symbol: str) -> Optional[StockQuote]:
    """
    查詢台股即時報價

    使用 TWSE/TPEX 公開 API

    Args:
        symbol: 股票代號

    Returns:
        StockQuote 或 None
    """
    try:
        # 先嘗試上市股票 (TWSE)
        quote = await _fetch_twse_quote(symbol)
        if quote:
            return quote

        # 再嘗試上櫃股票 (TPEX)
        quote = await _fetch_tpex_quote(symbol)
        if quote:
            return quote

        return None

    except Exception as e:
        logger.error(f"查詢股價失敗 {symbol}: {e}")
        return None


async def _fetch_with_retry(url: str, max_retries: int = HTTP_MAX_RETRIES) -> Optional[dict]:
    """帶重試機制的 HTTP GET 請求"""
    last_error = None

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.json()
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.ConnectError) as e:
            last_error = e
            if attempt < max_retries - 1:
                await asyncio.sleep(HTTP_RETRY_DELAY * (attempt + 1))  # 指數退避
                logger.debug(f"HTTP 請求失敗，重試 {attempt + 2}/{max_retries}: {e}")
        except Exception as e:
            # 非網路錯誤不重試
            logger.debug(f"HTTP 請求異常: {e}")
            return None

    if last_error:
        logger.debug(f"HTTP 請求重試 {max_retries} 次後失敗: {last_error}")
    return None


async def _fetch_twse_quote(symbol: str) -> Optional[StockQuote]:
    """從 TWSE 取得上市股票報價"""
    try:
        url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_{symbol}.tw"

        data = await _fetch_with_retry(url)
        if not data or not data.get('msgArray'):
            return None

        info = data['msgArray'][0]

        # 解析資料 (處理空字串和 None)
        def safe_float(value, default=0.0):
            """安全轉換浮點數，處理空字串和 None"""
            if value is None or value == '' or value == '-':
                return default
            try:
                return float(value)
            except (ValueError, TypeError):
                return default

        price = safe_float(info.get('z')) or safe_float(info.get('y'))  # z=成交價, y=昨收
        if price == 0:
            return None

        yesterday = safe_float(info.get('y'))  # 昨收
        change = price - yesterday if yesterday else 0
        change_percent = (change / yesterday * 100) if yesterday else 0

        return StockQuote(
            symbol=symbol,
            name=info.get('n', STOCK_NAMES.get(symbol, symbol)),
            price=price,
            change=round(change, 2),
            change_percent=round(change_percent, 2),
            open=safe_float(info.get('o')),
            high=safe_float(info.get('h')),
            low=safe_float(info.get('l')),
            volume=int(safe_float(info.get('v'))),  # 成交量 (張)
            timestamp=info.get('t', '')
        )

    except Exception as e:
        logger.debug(f"TWSE 查詢失敗 {symbol}: {e}")
        return None


async def _fetch_tpex_quote(symbol: str) -> Optional[StockQuote]:
    """從 TPEX 取得上櫃股票報價"""
    try:
        url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=otc_{symbol}.tw"

        data = await _fetch_with_retry(url)
        if not data or not data.get('msgArray'):
            return None

        info = data['msgArray'][0]

        # 安全轉換浮點數
        def safe_float(value, default=0.0):
            if value is None or value == '' or value == '-':
                return default
            try:
                return float(value)
            except (ValueError, TypeError):
                return default

        price = safe_float(info.get('z')) or safe_float(info.get('y'))
        if price == 0:
            return None

        yesterday = safe_float(info.get('y'))
        change = price - yesterday if yesterday else 0
        change_percent = (change / yesterday * 100) if yesterday else 0

        return StockQuote(
            symbol=symbol,
            name=info.get('n', STOCK_NAMES.get(symbol, symbol)),
            price=price,
            change=round(change, 2),
            change_percent=round(change_percent, 2),
            open=safe_float(info.get('o')),
            high=safe_float(info.get('h')),
            low=safe_float(info.get('l')),
            volume=int(safe_float(info.get('v'))),
            timestamp=info.get('t', '')
        )

    except Exception as e:
        logger.debug(f"TPEX 查詢失敗 {symbol}: {e}")
        return None


def format_price_info(quote: StockQuote) -> str:
    """格式化股價資訊為顯示文字"""
    # 漲跌符號和顏色提示
    if quote.change > 0:
        change_str = f"+{quote.change:.2f} (+{quote.change_percent:.2f}%)"
        trend = "📈"
    elif quote.change < 0:
        change_str = f"{quote.change:.2f} ({quote.change_percent:.2f}%)"
        trend = "📉"
    else:
        change_str = "0.00 (0.00%)"
        trend = "➡️"

    return (
        f"<b>{quote.symbol} {quote.name}</b> {trend}\n"
        f"現價: <code>{quote.price:.2f}</code> {change_str}\n"
        f"今日區間: {quote.low:.2f} ~ {quote.high:.2f}\n"
        f"成交量: {quote.volume:,} 張"
    )
