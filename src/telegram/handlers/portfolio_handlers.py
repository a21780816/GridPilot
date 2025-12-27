"""
持股查詢 Telegram 指令處理器
"""

import logging
from typing import TYPE_CHECKING, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from src.brokers import get_broker

if TYPE_CHECKING:
    from src.core.user_manager import UserManager

logger = logging.getLogger('PortfolioHandlers')


class PortfolioHandlers:
    """持股查詢指令處理器"""

    def __init__(self, user_manager: 'UserManager'):
        """
        初始化處理器

        Args:
            user_manager: 用戶管理器
        """
        self.user_manager = user_manager

    def _get_back_to_menu_keyboard(self) -> InlineKeyboardMarkup:
        """取得返回主選單按鈕"""
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("↩️ 返回主選單", callback_data="menu_main")]
        ])

    def _format_currency(self, value: float) -> str:
        """格式化金額"""
        if value >= 0:
            return f"{value:,.0f}"
        else:
            return f"-{abs(value):,.0f}"

    def _format_pnl(self, value: float, percent: Optional[float] = None) -> str:
        """格式化損益"""
        if value >= 0:
            icon = "📈"
            sign = "+"
        else:
            icon = "📉"
            sign = ""

        if percent is not None:
            return f"{icon} {sign}{value:,.0f} ({sign}{percent:.2f}%)"
        else:
            return f"{icon} {sign}{value:,.0f}"

    def _get_broker(self, chat_id: int, broker_name: Optional[str] = None):
        """取得券商實例"""
        if not broker_name:
            brokers = self.user_manager.get_broker_names(chat_id)
            broker_name = brokers[0] if brokers else None

        if not broker_name:
            return None

        # 取得券商設定
        broker_config = self.user_manager.get_broker_config(chat_id, broker_name)
        if not broker_config:
            return None

        # 建立券商實例
        try:
            return get_broker(broker_name, broker_config)
        except Exception as e:
            logger.error(f"建立券商實例失敗: {e}")
            return None

    # ========== 指令處理 ==========

    async def holdings_command(self, update: Update,
                               context: ContextTypes.DEFAULT_TYPE):
        """處理 /holdings 指令 - 查詢持股"""
        chat_id = update.effective_chat.id

        # 檢查是否有設定券商
        brokers = self.user_manager.get_broker_names(chat_id)
        if not brokers:
            await update.message.reply_text(
                "請先使用 /broker 設定券商 API\n"
                "設定完成後才能查詢持股"
            )
            return

        await update.message.reply_text("正在查詢持股資料...")

        try:
            broker = self._get_broker(chat_id)
            if not broker:
                await update.message.reply_text(
                    "無法連接券商\n"
                    "請確認券商設定是否正確"
                )
                return

            positions = broker.get_all_positions()

            if not positions:
                await update.message.reply_text(
                    "目前沒有持股",
                    reply_markup=self._get_back_to_menu_keyboard()
                )
                return

            # 計算總計
            total_market_value = sum(p.market_value for p in positions)
            total_cost_value = sum(p.cost_value for p in positions)
            total_unrealized_pnl = total_market_value - total_cost_value
            total_pnl_percent = (
                (total_unrealized_pnl / total_cost_value * 100)
                if total_cost_value > 0 else 0
            )

            # 格式化訊息
            msg = "<b>📊 我的持股</b>\n\n"

            for p in positions[:15]:  # 最多顯示 15 筆
                pnl_icon = "📈" if p.unrealized_pnl >= 0 else "📉"
                pnl_sign = "+" if p.unrealized_pnl >= 0 else ""

                msg += (
                    f"<b>{p.symbol}</b> {p.symbol_name}\n"
                    f"   持有: {p.quantity}張 @ {p.avg_price:.2f}\n"
                    f"   現價: {p.current_price:.2f} | 市值: {self._format_currency(p.market_value)}\n"
                    f"   {pnl_icon} {pnl_sign}{p.unrealized_pnl:,.0f} ({pnl_sign}{p.unrealized_pnl_percent:.2f}%)\n\n"
                )

            if len(positions) > 15:
                msg += f"... 還有 {len(positions) - 15} 檔\n\n"

            # 總計
            msg += (
                f"<b>總計</b>\n"
                f"持股數: {len(positions)} 檔\n"
                f"總市值: {self._format_currency(total_market_value)}\n"
                f"總成本: {self._format_currency(total_cost_value)}\n"
                f"未實現損益: {self._format_pnl(total_unrealized_pnl, total_pnl_percent)}"
            )

            await update.message.reply_text(
                msg.strip(),
                parse_mode='HTML',
                reply_markup=self._get_back_to_menu_keyboard()
            )

        except Exception as e:
            logger.error(f"查詢持股失敗: {e}")
            await update.message.reply_text(
                f"查詢持股失敗: {str(e)}",
                reply_markup=self._get_back_to_menu_keyboard()
            )

    async def balance_command(self, update: Update,
                              context: ContextTypes.DEFAULT_TYPE):
        """處理 /balance 指令 - 查詢帳戶餘額"""
        chat_id = update.effective_chat.id

        # 檢查是否有設定券商
        brokers = self.user_manager.get_broker_names(chat_id)
        if not brokers:
            await update.message.reply_text(
                "請先使用 /broker 設定券商 API\n"
                "設定完成後才能查詢餘額"
            )
            return

        await update.message.reply_text("正在查詢帳戶餘額...")

        try:
            broker = self._get_broker(chat_id)
            if not broker:
                await update.message.reply_text(
                    "無法連接券商\n"
                    "請確認券商設定是否正確"
                )
                return

            balance = broker.get_balance()

            if not balance:
                await update.message.reply_text(
                    "無法取得帳戶餘額",
                    reply_markup=self._get_back_to_menu_keyboard()
                )
                return

            msg = (
                f"<b>💰 帳戶餘額</b>\n\n"
                f"可用餘額: {self._format_currency(balance.available_balance)}\n"
                f"帳戶總額: {self._format_currency(balance.total_balance)}\n"
                f"已交割: {self._format_currency(balance.settled_balance)}\n"
                f"未交割: {self._format_currency(balance.unsettled_amount)}\n"
            )

            if balance.margin_available > 0:
                msg += f"融資額度: {self._format_currency(balance.margin_available)}\n"

            if balance.short_available > 0:
                msg += f"融券額度: {self._format_currency(balance.short_available)}\n"

            await update.message.reply_text(
                msg.strip(),
                parse_mode='HTML',
                reply_markup=self._get_back_to_menu_keyboard()
            )

        except Exception as e:
            logger.error(f"查詢餘額失敗: {e}")
            await update.message.reply_text(
                f"查詢餘額失敗: {str(e)}",
                reply_markup=self._get_back_to_menu_keyboard()
            )

    async def orders_command(self, update: Update,
                             context: ContextTypes.DEFAULT_TYPE):
        """處理 /orders 指令 - 查詢今日委託"""
        chat_id = update.effective_chat.id

        # 檢查是否有設定券商
        brokers = self.user_manager.get_broker_names(chat_id)
        if not brokers:
            await update.message.reply_text(
                "請先使用 /broker 設定券商 API\n"
                "設定完成後才能查詢委託"
            )
            return

        await update.message.reply_text("正在查詢今日委託...")

        try:
            broker = self._get_broker(chat_id)
            if not broker:
                await update.message.reply_text(
                    "無法連接券商\n"
                    "請確認券商設定是否正確"
                )
                return

            orders = broker.get_orders()

            if not orders:
                await update.message.reply_text(
                    "今日尚無委託記錄",
                    reply_markup=self._get_back_to_menu_keyboard()
                )
                return

            status_icons = {
                'pending': '⏳',
                'partial': '🔄',
                'filled': '✅',
                'cancelled': '⚫',
                'failed': '❌'
            }

            msg = "<b>📋 今日委託</b>\n\n"

            for o in orders[:15]:  # 最多顯示 15 筆
                icon = status_icons.get(o.status, '⚪')
                side = "買" if o.side == "buy" else "賣"
                time_str = o.order_time.strftime('%H:%M') if o.order_time else ""

                msg += (
                    f"{icon} <b>{o.symbol}</b> {o.symbol_name}\n"
                    f"   {side} {o.quantity}張 @ {o.price:.2f}"
                )

                if o.filled_qty > 0:
                    msg += f" (成交: {o.filled_qty}張"
                    if o.filled_price > 0:
                        msg += f" @ {o.filled_price:.2f}"
                    msg += ")"

                if time_str:
                    msg += f" | {time_str}"

                msg += "\n\n"

            if len(orders) > 15:
                msg += f"... 還有 {len(orders) - 15} 筆\n"

            await update.message.reply_text(
                msg.strip(),
                parse_mode='HTML',
                reply_markup=self._get_back_to_menu_keyboard()
            )

        except Exception as e:
            logger.error(f"查詢委託失敗: {e}")
            await update.message.reply_text(
                f"查詢委託失敗: {str(e)}",
                reply_markup=self._get_back_to_menu_keyboard()
            )

    async def trades_command(self, update: Update,
                             context: ContextTypes.DEFAULT_TYPE):
        """處理 /trades 指令 - 查詢今日成交"""
        chat_id = update.effective_chat.id

        # 檢查是否有設定券商
        brokers = self.user_manager.get_broker_names(chat_id)
        if not brokers:
            await update.message.reply_text(
                "請先使用 /broker 設定券商 API\n"
                "設定完成後才能查詢成交"
            )
            return

        await update.message.reply_text("正在查詢今日成交...")

        try:
            broker = self._get_broker(chat_id)
            if not broker:
                await update.message.reply_text(
                    "無法連接券商\n"
                    "請確認券商設定是否正確"
                )
                return

            transactions = broker.get_transactions()

            if not transactions:
                await update.message.reply_text(
                    "今日尚無成交記錄",
                    reply_markup=self._get_back_to_menu_keyboard()
                )
                return

            msg = "<b>💹 今日成交</b>\n\n"

            total_amount = 0
            total_fee = 0
            total_tax = 0

            for t in transactions[:15]:  # 最多顯示 15 筆
                side = "買" if t.side == "buy" else "賣"
                side_icon = "🔴" if t.side == "buy" else "🟢"
                time_str = t.trade_time.strftime('%H:%M') if t.trade_time else ""

                msg += (
                    f"{side_icon} <b>{t.symbol}</b> {t.symbol_name}\n"
                    f"   {side} {t.quantity}張 @ {t.price:.2f}\n"
                    f"   金額: {self._format_currency(t.amount)}"
                )

                if t.fee > 0:
                    msg += f" | 手續費: {t.fee:.0f}"
                if t.tax > 0:
                    msg += f" | 稅: {t.tax:.0f}"
                if time_str:
                    msg += f" | {time_str}"

                msg += "\n\n"

                total_amount += t.amount
                total_fee += t.fee
                total_tax += t.tax

            if len(transactions) > 15:
                msg += f"... 還有 {len(transactions) - 15} 筆\n\n"

            # 總計
            msg += (
                f"<b>總計</b>\n"
                f"成交筆數: {len(transactions)}\n"
                f"成交金額: {self._format_currency(total_amount)}\n"
                f"手續費: {self._format_currency(total_fee)}\n"
                f"交易稅: {self._format_currency(total_tax)}"
            )

            await update.message.reply_text(
                msg.strip(),
                parse_mode='HTML',
                reply_markup=self._get_back_to_menu_keyboard()
            )

        except Exception as e:
            logger.error(f"查詢成交失敗: {e}")
            await update.message.reply_text(
                f"查詢成交失敗: {str(e)}",
                reply_markup=self._get_back_to_menu_keyboard()
            )

    # ========== 主選單回調方法 ==========

    async def show_portfolio_summary(self, query, context: ContextTypes.DEFAULT_TYPE):
        """從主選單顯示投資組合摘要 (我的持股)"""
        chat_id = query.message.chat_id

        # 檢查是否有設定券商
        brokers = self.user_manager.get_broker_names(chat_id)
        if not brokers:
            await query.edit_message_text(
                "請先使用券商設定功能設定券商 API\n"
                "設定完成後才能查詢持股",
                reply_markup=self._get_back_to_menu_keyboard()
            )
            return

        await query.edit_message_text("正在查詢持股資料...")

        try:
            broker = self._get_broker(chat_id)
            if not broker:
                await query.edit_message_text(
                    "無法連接券商\n"
                    "請確認券商設定是否正確",
                    reply_markup=self._get_back_to_menu_keyboard()
                )
                return

            positions = broker.get_all_positions()
            balance = broker.get_balance()

            # 計算總計
            total_market_value = sum(p.market_value for p in positions)
            total_cost_value = sum(p.cost_value for p in positions)
            total_unrealized_pnl = total_market_value - total_cost_value
            total_pnl_percent = (
                (total_unrealized_pnl / total_cost_value * 100)
                if total_cost_value > 0 else 0
            )
            available_balance = balance.available_balance if balance else 0
            total_assets = total_market_value + available_balance

            # 格式化訊息
            msg = "<b>📊 投資組合總覽</b>\n\n"

            msg += (
                f"<b>資產摘要</b>\n"
                f"總資產: {self._format_currency(total_assets)}\n"
                f"持股市值: {self._format_currency(total_market_value)}\n"
                f"可用餘額: {self._format_currency(available_balance)}\n"
                f"未實現損益: {self._format_pnl(total_unrealized_pnl, total_pnl_percent)}\n\n"
            )

            if positions:
                msg += f"<b>持股明細</b> ({len(positions)} 檔)\n"
                for p in positions[:8]:  # 最多顯示 8 筆
                    pnl_sign = "+" if p.unrealized_pnl >= 0 else ""
                    msg += (
                        f"• {p.symbol} {p.symbol_name}: {p.quantity}張\n"
                        f"  {p.current_price:.2f} | {pnl_sign}{p.unrealized_pnl_percent:.1f}%\n"
                    )

                if len(positions) > 8:
                    msg += f"  ... 還有 {len(positions) - 8} 檔\n"
            else:
                msg += "目前沒有持股\n"

            # 建立功能按鈕
            keyboard = [
                [
                    InlineKeyboardButton("📊 持股明細", callback_data="portfolio_holdings"),
                    InlineKeyboardButton("💰 帳戶餘額", callback_data="portfolio_balance")
                ],
                [
                    InlineKeyboardButton("📋 今日委託", callback_data="portfolio_orders"),
                    InlineKeyboardButton("💹 今日成交", callback_data="portfolio_trades")
                ],
                [InlineKeyboardButton("🔄 重新整理", callback_data="portfolio_refresh")],
                [InlineKeyboardButton("↩️ 返回主選單", callback_data="menu_main")]
            ]

            await query.edit_message_text(
                msg.strip(),
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        except Exception as e:
            logger.error(f"查詢持股失敗: {e}")
            await query.edit_message_text(
                f"查詢持股失敗: {str(e)}",
                reply_markup=self._get_back_to_menu_keyboard()
            )

    async def show_holdings_detail(self, query, context: ContextTypes.DEFAULT_TYPE):
        """顯示持股明細"""
        chat_id = query.message.chat_id

        try:
            broker = self._get_broker(chat_id)
            if not broker:
                await query.edit_message_text(
                    "無法連接券商",
                    reply_markup=self._get_back_to_menu_keyboard()
                )
                return

            positions = broker.get_all_positions()

            if not positions:
                keyboard = [
                    [InlineKeyboardButton("↩️ 返回總覽", callback_data="menu_portfolio")]
                ]
                await query.edit_message_text(
                    "目前沒有持股",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                return

            # 計算總計
            total_market_value = sum(p.market_value for p in positions)
            total_cost_value = sum(p.cost_value for p in positions)
            total_unrealized_pnl = total_market_value - total_cost_value
            total_pnl_percent = (
                (total_unrealized_pnl / total_cost_value * 100)
                if total_cost_value > 0 else 0
            )

            # 格式化訊息
            msg = "<b>📊 持股明細</b>\n\n"

            for p in positions[:12]:  # 最多顯示 12 筆
                pnl_icon = "📈" if p.unrealized_pnl >= 0 else "📉"
                pnl_sign = "+" if p.unrealized_pnl >= 0 else ""

                msg += (
                    f"<b>{p.symbol}</b> {p.symbol_name}\n"
                    f"   持有: {p.quantity}張 @ {p.avg_price:.2f}\n"
                    f"   現價: {p.current_price:.2f} | 市值: {self._format_currency(p.market_value)}\n"
                    f"   {pnl_icon} {pnl_sign}{p.unrealized_pnl:,.0f} ({pnl_sign}{p.unrealized_pnl_percent:.2f}%)\n\n"
                )

            if len(positions) > 12:
                msg += f"... 還有 {len(positions) - 12} 檔\n\n"

            msg += (
                f"<b>總計</b>\n"
                f"持股數: {len(positions)} 檔\n"
                f"總市值: {self._format_currency(total_market_value)}\n"
                f"未實現損益: {self._format_pnl(total_unrealized_pnl, total_pnl_percent)}"
            )

            keyboard = [
                [InlineKeyboardButton("↩️ 返回總覽", callback_data="menu_portfolio")]
            ]

            await query.edit_message_text(
                msg.strip(),
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        except Exception as e:
            logger.error(f"查詢持股明細失敗: {e}")
            await query.edit_message_text(
                f"查詢失敗: {str(e)}",
                reply_markup=self._get_back_to_menu_keyboard()
            )

    async def show_balance_detail(self, query, context: ContextTypes.DEFAULT_TYPE):
        """顯示帳戶餘額"""
        chat_id = query.message.chat_id

        try:
            broker = self._get_broker(chat_id)
            if not broker:
                await query.edit_message_text(
                    "無法連接券商",
                    reply_markup=self._get_back_to_menu_keyboard()
                )
                return

            balance = broker.get_balance()

            if not balance:
                keyboard = [
                    [InlineKeyboardButton("↩️ 返回總覽", callback_data="menu_portfolio")]
                ]
                await query.edit_message_text(
                    "無法取得帳戶餘額",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                return

            msg = (
                f"<b>💰 帳戶餘額</b>\n\n"
                f"可用餘額: {self._format_currency(balance.available_balance)}\n"
                f"帳戶總額: {self._format_currency(balance.total_balance)}\n"
                f"已交割: {self._format_currency(balance.settled_balance)}\n"
                f"未交割: {self._format_currency(balance.unsettled_amount)}\n"
            )

            if balance.margin_available > 0:
                msg += f"融資額度: {self._format_currency(balance.margin_available)}\n"

            if balance.short_available > 0:
                msg += f"融券額度: {self._format_currency(balance.short_available)}\n"

            keyboard = [
                [InlineKeyboardButton("↩️ 返回總覽", callback_data="menu_portfolio")]
            ]

            await query.edit_message_text(
                msg.strip(),
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        except Exception as e:
            logger.error(f"查詢餘額失敗: {e}")
            await query.edit_message_text(
                f"查詢失敗: {str(e)}",
                reply_markup=self._get_back_to_menu_keyboard()
            )

    async def show_orders_detail(self, query, context: ContextTypes.DEFAULT_TYPE):
        """顯示今日委託"""
        chat_id = query.message.chat_id

        try:
            broker = self._get_broker(chat_id)
            if not broker:
                await query.edit_message_text(
                    "無法連接券商",
                    reply_markup=self._get_back_to_menu_keyboard()
                )
                return

            orders = broker.get_orders()

            if not orders:
                keyboard = [
                    [InlineKeyboardButton("↩️ 返回總覽", callback_data="menu_portfolio")]
                ]
                await query.edit_message_text(
                    "今日尚無委託記錄",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                return

            status_icons = {
                'pending': '⏳',
                'partial': '🔄',
                'filled': '✅',
                'cancelled': '⚫',
                'failed': '❌'
            }

            msg = "<b>📋 今日委託</b>\n\n"

            for o in orders[:12]:  # 最多顯示 12 筆
                icon = status_icons.get(o.status, '⚪')
                side = "買" if o.side == "buy" else "賣"
                time_str = o.order_time.strftime('%H:%M') if o.order_time else ""

                msg += (
                    f"{icon} <b>{o.symbol}</b> {o.symbol_name}\n"
                    f"   {side} {o.quantity}張 @ {o.price:.2f}"
                )

                if o.filled_qty > 0:
                    msg += f" (成交: {o.filled_qty}張)"

                if time_str:
                    msg += f" | {time_str}"

                msg += "\n\n"

            if len(orders) > 12:
                msg += f"... 還有 {len(orders) - 12} 筆\n"

            keyboard = [
                [InlineKeyboardButton("↩️ 返回總覽", callback_data="menu_portfolio")]
            ]

            await query.edit_message_text(
                msg.strip(),
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        except Exception as e:
            logger.error(f"查詢委託失敗: {e}")
            await query.edit_message_text(
                f"查詢失敗: {str(e)}",
                reply_markup=self._get_back_to_menu_keyboard()
            )

    async def show_trades_detail(self, query, context: ContextTypes.DEFAULT_TYPE):
        """顯示今日成交"""
        chat_id = query.message.chat_id

        try:
            broker = self._get_broker(chat_id)
            if not broker:
                await query.edit_message_text(
                    "無法連接券商",
                    reply_markup=self._get_back_to_menu_keyboard()
                )
                return

            transactions = broker.get_transactions()

            if not transactions:
                keyboard = [
                    [InlineKeyboardButton("↩️ 返回總覽", callback_data="menu_portfolio")]
                ]
                await query.edit_message_text(
                    "今日尚無成交記錄",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                return

            msg = "<b>💹 今日成交</b>\n\n"

            total_amount = 0
            total_fee = 0
            total_tax = 0

            for t in transactions[:12]:  # 最多顯示 12 筆
                side = "買" if t.side == "buy" else "賣"
                side_icon = "🔴" if t.side == "buy" else "🟢"
                time_str = t.trade_time.strftime('%H:%M') if t.trade_time else ""

                msg += (
                    f"{side_icon} <b>{t.symbol}</b> {t.symbol_name}\n"
                    f"   {side} {t.quantity}張 @ {t.price:.2f}\n"
                    f"   金額: {self._format_currency(t.amount)}"
                )

                if time_str:
                    msg += f" | {time_str}"

                msg += "\n\n"

                total_amount += t.amount
                total_fee += t.fee
                total_tax += t.tax

            if len(transactions) > 12:
                msg += f"... 還有 {len(transactions) - 12} 筆\n\n"

            msg += (
                f"<b>總計</b>\n"
                f"成交筆數: {len(transactions)}\n"
                f"成交金額: {self._format_currency(total_amount)}\n"
                f"手續費: {self._format_currency(total_fee)} | 交易稅: {self._format_currency(total_tax)}"
            )

            keyboard = [
                [InlineKeyboardButton("↩️ 返回總覽", callback_data="menu_portfolio")]
            ]

            await query.edit_message_text(
                msg.strip(),
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        except Exception as e:
            logger.error(f"查詢成交失敗: {e}")
            await query.edit_message_text(
                f"查詢失敗: {str(e)}",
                reply_markup=self._get_back_to_menu_keyboard()
            )

    # ========== 回調處理 ==========

    async def handle_callback(self, update: Update,
                              context: ContextTypes.DEFAULT_TYPE) -> bool:
        """
        處理持股相關的回調

        Returns:
            bool: 是否已處理
        """
        query = update.callback_query
        data = query.data

        # 檢查是否是持股相關的回調
        if not data.startswith('portfolio_'):
            return False

        await query.answer()

        if data == "portfolio_holdings":
            await self.show_holdings_detail(query, context)
            return True

        elif data == "portfolio_balance":
            await self.show_balance_detail(query, context)
            return True

        elif data == "portfolio_orders":
            await self.show_orders_detail(query, context)
            return True

        elif data == "portfolio_trades":
            await self.show_trades_detail(query, context)
            return True

        elif data == "portfolio_refresh":
            await self.show_portfolio_summary(query, context)
            return True

        return False
