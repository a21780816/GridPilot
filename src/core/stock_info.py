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
    close: float = 0       # 收盤價 (盤中同現價)
    yesterday: float = 0   # 昨收價
    volume: int = 0        # 成交量 (張)
    amount: float = 0      # 成交金額 (元)
    bid_price: float = 0   # 買進價 (最佳買價)
    ask_price: float = 0   # 賣出價 (最佳賣價)
    limit_up: float = 0    # 漲停價
    limit_down: float = 0  # 跌停價
    amplitude: float = 0   # 振幅 %
    timestamp: str = ""    # 更新時間
    market: str = ""       # 市場 (tse/otc)


@dataclass
class StockFundamental:
    """股票基本面資料"""
    symbol: str
    name: str = ""
    pe_ratio: float = 0         # 本益比
    pb_ratio: float = 0         # 股價淨值比
    dividend_yield: float = 0   # 殖利率 %
    eps: float = 0              # 每股盈餘
    market_cap: float = 0       # 市值 (億)
    shares_outstanding: int = 0 # 流通股數


@dataclass
class InstitutionalInvestor:
    """法人買賣超資料"""
    symbol: str
    date: str = ""
    foreign_buy: int = 0        # 外資買 (張)
    foreign_sell: int = 0       # 外資賣 (張)
    foreign_net: int = 0        # 外資買賣超 (張)
    investment_trust_buy: int = 0    # 投信買 (張)
    investment_trust_sell: int = 0   # 投信賣 (張)
    investment_trust_net: int = 0    # 投信買賣超 (張)
    dealer_buy: int = 0         # 自營商買 (張)
    dealer_sell: int = 0        # 自營商賣 (張)
    dealer_net: int = 0         # 自營商買賣超 (張)
    total_net: int = 0          # 三大法人合計買賣超


@dataclass
class StockDetail:
    """股票完整資訊"""
    quote: StockQuote
    fundamental: Optional['StockFundamental'] = None
    institutional: Optional['InstitutionalInvestor'] = None


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


def _safe_float(value, default=0.0):
    """安全轉換浮點數，處理空字串和 None"""
    if value is None or value == '' or value == '-':
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _parse_best_price(price_str: str) -> float:
    """解析最佳五檔價格字串，取第一個價格"""
    if not price_str:
        return 0.0
    prices = price_str.split('_')
    return _safe_float(prices[0]) if prices else 0.0


async def _fetch_twse_quote(symbol: str) -> Optional[StockQuote]:
    """從 TWSE 取得上市股票報價"""
    try:
        url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_{symbol}.tw"

        data = await _fetch_with_retry(url)
        if not data or not data.get('msgArray'):
            return None

        info = data['msgArray'][0]

        # TWSE API 欄位說明:
        # z: 成交價, y: 昨收, o: 開盤, h: 最高, l: 最低
        # v: 成交量(張), tv: 成交量(股), a: 最佳五檔賣價, b: 最佳五檔買價
        # u: 漲停價, w: 跌停價, t: 時間, n: 股票名稱
        # tlong: 時間戳記

        price = _safe_float(info.get('z')) or _safe_float(info.get('y'))
        if price == 0:
            return None

        yesterday = _safe_float(info.get('y'))
        change = price - yesterday if yesterday else 0
        change_percent = (change / yesterday * 100) if yesterday else 0

        high = _safe_float(info.get('h'))
        low = _safe_float(info.get('l'))
        amplitude = ((high - low) / yesterday * 100) if yesterday and high and low else 0

        # 成交金額 (估算: 價格 * 成交量 * 1000)
        volume = int(_safe_float(info.get('v')))
        amount = price * volume * 1000 if price and volume else 0

        return StockQuote(
            symbol=symbol,
            name=info.get('n', STOCK_NAMES.get(symbol, symbol)),
            price=price,
            change=round(change, 2),
            change_percent=round(change_percent, 2),
            open=_safe_float(info.get('o')),
            high=high,
            low=low,
            close=price,
            yesterday=yesterday,
            volume=volume,
            amount=amount,
            bid_price=_parse_best_price(info.get('b', '')),
            ask_price=_parse_best_price(info.get('a', '')),
            limit_up=_safe_float(info.get('u')),
            limit_down=_safe_float(info.get('w')),
            amplitude=round(amplitude, 2),
            timestamp=info.get('t', ''),
            market='tse'
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

        price = _safe_float(info.get('z')) or _safe_float(info.get('y'))
        if price == 0:
            return None

        yesterday = _safe_float(info.get('y'))
        change = price - yesterday if yesterday else 0
        change_percent = (change / yesterday * 100) if yesterday else 0

        high = _safe_float(info.get('h'))
        low = _safe_float(info.get('l'))
        amplitude = ((high - low) / yesterday * 100) if yesterday and high and low else 0

        volume = int(_safe_float(info.get('v')))
        amount = price * volume * 1000 if price and volume else 0

        return StockQuote(
            symbol=symbol,
            name=info.get('n', STOCK_NAMES.get(symbol, symbol)),
            price=price,
            change=round(change, 2),
            change_percent=round(change_percent, 2),
            open=_safe_float(info.get('o')),
            high=high,
            low=low,
            close=price,
            yesterday=yesterday,
            volume=volume,
            amount=amount,
            bid_price=_parse_best_price(info.get('b', '')),
            ask_price=_parse_best_price(info.get('a', '')),
            limit_up=_safe_float(info.get('u')),
            limit_down=_safe_float(info.get('w')),
            amplitude=round(amplitude, 2),
            timestamp=info.get('t', ''),
            market='otc'
        )

    except Exception as e:
        logger.debug(f"TPEX 查詢失敗 {symbol}: {e}")
        return None


async def get_stock_fundamental(symbol: str) -> Optional[StockFundamental]:
    """
    查詢股票基本面資料

    使用 TWSE/TPEX 公開資料

    Args:
        symbol: 股票代號

    Returns:
        StockFundamental 或 None
    """
    try:
        from datetime import datetime

        # 取得當前日期
        today = datetime.now()
        date_str = today.strftime('%Y%m%d')

        # 嘗試上市股票
        url = f"https://www.twse.com.tw/exchangeReport/BWIBBU_d?response=json&date={date_str}&stockNo={symbol}"
        data = await _fetch_with_retry(url)

        if data and data.get('data'):
            row = data['data'][0] if data['data'] else None
            if row:
                return StockFundamental(
                    symbol=symbol,
                    name=row[0] if len(row) > 0 else "",
                    dividend_yield=_safe_float(row[2]) if len(row) > 2 else 0,
                    pe_ratio=_safe_float(row[4]) if len(row) > 4 else 0,
                    pb_ratio=_safe_float(row[5]) if len(row) > 5 else 0,
                )

        # 嘗試上櫃股票
        url = f"https://www.tpex.org.tw/web/stock/aftertrading/peratio_analysis/pera_result.php?l=zh-tw&d={today.strftime('%Y/%m/%d')}&stkno={symbol}"
        data = await _fetch_with_retry(url)

        if data and data.get('aaData'):
            row = data['aaData'][0] if data['aaData'] else None
            if row:
                return StockFundamental(
                    symbol=symbol,
                    name=row[1] if len(row) > 1 else "",
                    pe_ratio=_safe_float(row[2]) if len(row) > 2 else 0,
                    dividend_yield=_safe_float(row[6]) if len(row) > 6 else 0,
                )

        return None

    except Exception as e:
        logger.debug(f"基本面查詢失敗 {symbol}: {e}")
        return None


async def get_institutional_investor(symbol: str) -> Optional[InstitutionalInvestor]:
    """
    查詢法人買賣超資料

    Args:
        symbol: 股票代號

    Returns:
        InstitutionalInvestor 或 None
    """
    try:
        from datetime import datetime

        today = datetime.now()
        date_str = today.strftime('%Y%m%d')

        # 上市股票法人買賣超
        url = f"https://www.twse.com.tw/fund/T86?response=json&date={date_str}&selectType=ALLBUT0999"
        data = await _fetch_with_retry(url)

        if data and data.get('data'):
            for row in data['data']:
                if row[0].strip() == symbol:
                    return InstitutionalInvestor(
                        symbol=symbol,
                        date=data.get('date', date_str),
                        foreign_buy=int(_safe_float(row[2].replace(',', ''))),
                        foreign_sell=int(_safe_float(row[3].replace(',', ''))),
                        foreign_net=int(_safe_float(row[4].replace(',', ''))),
                        investment_trust_buy=int(_safe_float(row[5].replace(',', ''))),
                        investment_trust_sell=int(_safe_float(row[6].replace(',', ''))),
                        investment_trust_net=int(_safe_float(row[7].replace(',', ''))),
                        dealer_net=int(_safe_float(row[8].replace(',', ''))) if len(row) > 8 else 0,
                        total_net=int(_safe_float(row[-1].replace(',', '')))
                    )

        return None

    except Exception as e:
        logger.debug(f"法人買賣超查詢失敗 {symbol}: {e}")
        return None


async def get_stock_detail(symbol: str) -> Optional[StockDetail]:
    """
    查詢股票完整資訊 (報價 + 基本面 + 法人)

    Args:
        symbol: 股票代號

    Returns:
        StockDetail 或 None
    """
    quote = await get_stock_quote(symbol)
    if not quote:
        return None

    # 並行查詢基本面和法人資料
    fundamental, institutional = await asyncio.gather(
        get_stock_fundamental(symbol),
        get_institutional_investor(symbol),
        return_exceptions=True
    )

    # 處理例外情況
    if isinstance(fundamental, Exception):
        fundamental = None
    if isinstance(institutional, Exception):
        institutional = None

    return StockDetail(
        quote=quote,
        fundamental=fundamental,
        institutional=institutional
    )


def format_price_info(quote: StockQuote, detailed: bool = False) -> str:
    """
    格式化股價資訊為顯示文字

    Args:
        quote: 股票報價
        detailed: 是否顯示詳細資訊

    Returns:
        格式化的字串
    """
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

    # 基本資訊
    msg = (
        f"<b>{quote.symbol} {quote.name}</b> {trend}\n"
        f"現價: <code>{quote.price:.2f}</code> {change_str}\n"
    )

    if detailed:
        # 詳細模式：顯示更多資訊
        msg += f"\n<b>價格資訊</b>\n"
        msg += f"開盤: {quote.open:.2f} | 昨收: {quote.yesterday:.2f}\n"
        msg += f"最高: {quote.high:.2f} | 最低: {quote.low:.2f}\n"
        if quote.amplitude > 0:
            msg += f"振幅: {quote.amplitude:.2f}%\n"

        if quote.bid_price > 0 and quote.ask_price > 0:
            msg += f"\n<b>買賣價</b>\n"
            msg += f"買進: {quote.bid_price:.2f} | 賣出: {quote.ask_price:.2f}\n"

        if quote.limit_up > 0 and quote.limit_down > 0:
            msg += f"漲停: {quote.limit_up:.2f} | 跌停: {quote.limit_down:.2f}\n"

        msg += f"\n<b>成交資訊</b>\n"
        msg += f"成交量: {quote.volume:,} 張\n"
        if quote.amount > 0:
            if quote.amount >= 100000000:
                msg += f"成交金額: {quote.amount/100000000:.2f} 億\n"
            else:
                msg += f"成交金額: {quote.amount/10000:.0f} 萬\n"

        if quote.timestamp:
            msg += f"\n更新時間: {quote.timestamp}"
    else:
        # 簡潔模式
        msg += f"今日區間: {quote.low:.2f} ~ {quote.high:.2f}\n"
        msg += f"成交量: {quote.volume:,} 張"

    return msg


def format_stock_detail(detail: StockDetail) -> str:
    """
    格式化完整股票資訊

    Args:
        detail: 股票完整資訊

    Returns:
        格式化的字串
    """
    msg = format_price_info(detail.quote, detailed=True)

    # 基本面資訊
    if detail.fundamental:
        f = detail.fundamental
        msg += f"\n\n<b>基本面</b>\n"
        if f.pe_ratio > 0:
            msg += f"本益比: {f.pe_ratio:.2f}\n"
        if f.pb_ratio > 0:
            msg += f"股價淨值比: {f.pb_ratio:.2f}\n"
        if f.dividend_yield > 0:
            msg += f"殖利率: {f.dividend_yield:.2f}%\n"

    # 法人買賣超
    if detail.institutional:
        i = detail.institutional
        msg += f"\n<b>法人買賣超</b> ({i.date})\n"

        def format_net(value: int) -> str:
            if value > 0:
                return f"+{value:,}"
            elif value < 0:
                return f"{value:,}"
            else:
                return "0"

        msg += f"外資: {format_net(i.foreign_net)} 張\n"
        msg += f"投信: {format_net(i.investment_trust_net)} 張\n"
        msg += f"自營: {format_net(i.dealer_net)} 張\n"
        msg += f"合計: {format_net(i.total_net)} 張"

    return msg
