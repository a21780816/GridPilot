"""
條件單 Telegram 指令處理器
"""

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

if TYPE_CHECKING:
    from src.core.trigger_order_manager import TriggerOrderManager
    from src.core.user_manager import UserManager, UserStateManager

from src.models.enums import TriggerStatus

logger = logging.getLogger('TriggerHandlers')


class TriggerSetupState:
    """條件單設定狀態"""
    IDLE = 'idle'
    WAITING_SYMBOL = 'waiting_trigger_symbol'
    WAITING_CONDITION = 'waiting_trigger_condition'
    WAITING_TRIGGER_PRICE = 'waiting_trigger_price'
    WAITING_ACTION = 'waiting_trigger_action'
    WAITING_TRADE_TYPE = 'waiting_trade_type'
    WAITING_ORDER_TYPE = 'waiting_order_type'
    WAITING_ORDER_PRICE = 'waiting_order_price'
    WAITING_QUANTITY = 'waiting_trigger_quantity'
    WAITING_CONFIRM = 'waiting_trigger_confirm'
    WAITING_PIN = 'waiting_trigger_pin'
    WAITING_SET_PIN = 'waiting_set_pin'
    WAITING_SET_PIN_CONFIRM = 'waiting_set_pin_confirm'


class TriggerHandlers:
    """條件單指令處理器"""

    def __init__(self,
                 trigger_manager: 'TriggerOrderManager',
                 user_manager: 'UserManager',
                 state_manager: 'UserStateManager'):
        """
        初始化處理器

        Args:
            trigger_manager: 條件單管理器
            user_manager: 用戶管理器
            state_manager: 狀態管理器
        """
        self.trigger_manager = trigger_manager
        self.user_manager = user_manager
        self.state_manager = state_manager

    def _get_back_to_menu_keyboard(self) -> InlineKeyboardMarkup:
        """取得返回主選單按鈕"""
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("↩️ 返回主選單", callback_data="menu_main")]
        ])

    # ========== 指令處理 ==========

    async def trigger_command(self, update: Update,
                              context: ContextTypes.DEFAULT_TYPE):
        """
        處理 /trigger 指令 - 新增條件單

        流程:
        1. 輸入股票代號
        2. 選擇觸發條件 (>=, <=)
        3. 輸入觸發價格
        4. 選擇買/賣
        5. 選擇市價單/限價單
        6. (限價單) 輸入委託價格
        7. 輸入張數
        8. 確認並輸入 PIN 碼
        """
        chat_id = update.effective_chat.id

        # 確保用戶已註冊
        if not self.user_manager.user_exists(chat_id):
            self.user_manager.create_user(
                chat_id,
                username=update.effective_user.username,
                first_name=update.effective_user.first_name
            )

        # 檢查是否有設定券商
        brokers = self.user_manager.get_broker_names(chat_id)
        if not brokers:
            await update.message.reply_text(
                "請先使用 /broker 設定券商 API\n"
                "設定完成後才能建立條件單"
            )
            return

        # 檢查是否已設定 PIN 碼
        if not self.user_manager.has_pin_code(chat_id):
            await update.message.reply_text(
                "請先使用 /setpin 設定 PIN 碼\n"
                "PIN 碼用於驗證敏感操作"
            )
            return

        self.state_manager.clear_state(chat_id)

        await update.message.reply_text(
            "<b>新增條件單</b>\n\n"
            "請輸入股票代號：\n"
            "例如: <code>2330</code> (台積電)",
            parse_mode='HTML'
        )
        self.state_manager.set_state(chat_id, TriggerSetupState.WAITING_SYMBOL)

    async def triggers_command(self, update: Update,
                               context: ContextTypes.DEFAULT_TYPE):
        """處理 /triggers 指令 - 列出條件單"""
        chat_id = update.effective_chat.id

        triggers = self.trigger_manager.get_user_triggers(str(chat_id))

        if not triggers:
            await update.message.reply_text(
                "尚未設定任何條件單\n\n"
                "使用 /trigger 新增條件單"
            )
            return

        status_icons = {
            'active': '🟢',
            'triggered': '🟡',
            'executed': '✅',
            'failed': '❌',
            'cancelled': '⚫',
            'expired': '⏰'
        }

        trade_type_map = {
            'cash': '現股',
            'day_trade': '現沖',
            'margin_buy': '融資',
            'short_sell': '融券',
        }

        msg = "<b>條件單列表</b>\n\n"

        for t in triggers[:15]:  # 最多顯示 15 筆
            icon = status_icons.get(t.status.value, '⚪')
            action = "買" if t.order_action.value == "buy" else "賣"
            order_type = "市" if t.order_type.value == "market" else "限"
            trade_type = trade_type_map.get(t.trade_type.value, '現股')

            msg += (
                f"{icon} <code>{t.symbol}</code> | "
                f"價格 {t.condition.value} {t.trigger_price}\n"
                f"   → {trade_type} {order_type}價{action} {t.quantity}張 | "
                f"ID: <code>{t.id[:8]}</code>\n"
            )

        if len(triggers) > 15:
            msg += f"\n... 還有 {len(triggers) - 15} 筆\n"

        msg += "\n使用 /deltrigger [ID] 刪除條件單"
        await update.message.reply_text(msg.strip(), parse_mode='HTML')

    async def delete_trigger_command(self, update: Update,
                                     context: ContextTypes.DEFAULT_TYPE):
        """處理 /deltrigger 指令 - 刪除條件單"""
        chat_id = update.effective_chat.id

        if not context.args:
            # 顯示可刪除的條件單列表
            triggers = self.trigger_manager.get_user_triggers(
                str(chat_id), TriggerStatus.ACTIVE
            )

            if not triggers:
                await update.message.reply_text(
                    "沒有可刪除的條件單\n\n"
                    "使用 /triggers 查看所有條件單"
                )
                return

            keyboard = []
            for t in triggers[:10]:
                # 使用 12 字元前綴減少碰撞機率 (8 字元可能不夠唯一)
                keyboard.append([InlineKeyboardButton(
                    f"{t.symbol} | {t.condition.value} {t.trigger_price}",
                    callback_data=f"deltrigger_{t.id[:12]}"
                )])
            keyboard.append([InlineKeyboardButton("取消", callback_data="cancel")])

            await update.message.reply_text(
                "<b>選擇要刪除的條件單：</b>",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        trigger_id = context.args[0]

        # 查找完整的 trigger_id
        triggers = self.trigger_manager.get_user_triggers(str(chat_id))
        full_id = None
        for t in triggers:
            if t.id.startswith(trigger_id):
                full_id = t.id
                break

        if not full_id:
            await update.message.reply_text(
                f"找不到 ID 為 <code>{trigger_id}</code> 的條件單\n\n"
                "使用 /triggers 查看條件單列表",
                parse_mode='HTML'
            )
            return

        # 需要 PIN 碼驗證
        self.state_manager.set_temp_data(chat_id, 'delete_trigger_id', full_id)
        self.state_manager.set_state(chat_id, TriggerSetupState.WAITING_PIN)

        await update.message.reply_text(
            "<b>刪除條件單需要 PIN 碼驗證</b>\n\n"
            "請輸入您的 PIN 碼：",
            parse_mode='HTML'
        )

    async def setpin_command(self, update: Update,
                             context: ContextTypes.DEFAULT_TYPE):
        """處理 /setpin 指令 - 設定 PIN 碼"""
        chat_id = update.effective_chat.id

        # 確保用戶已註冊
        if not self.user_manager.user_exists(chat_id):
            self.user_manager.create_user(
                chat_id,
                username=update.effective_user.username,
                first_name=update.effective_user.first_name
            )

        has_pin = self.user_manager.has_pin_code(chat_id)

        if has_pin:
            msg = (
                "<b>更新 PIN 碼</b>\n\n"
                "您已設定 PIN 碼\n"
                "請輸入新的 PIN 碼 (4-6 位數字)："
            )
        else:
            msg = (
                "<b>設定 PIN 碼</b>\n\n"
                "PIN 碼用於驗證敏感操作（如下單、刪除條件單）\n\n"
                "請輸入 PIN 碼 (4-6 位數字)："
            )

        self.state_manager.clear_state(chat_id)
        self.state_manager.set_state(chat_id, TriggerSetupState.WAITING_SET_PIN)

        await update.message.reply_text(msg, parse_mode='HTML')

    async def apikey_command(self, update: Update,
                             context: ContextTypes.DEFAULT_TYPE):
        """處理 /apikey 指令 - 查看/重新產生 API Key"""
        chat_id = update.effective_chat.id

        # 確保用戶已註冊
        if not self.user_manager.user_exists(chat_id):
            self.user_manager.create_user(
                chat_id,
                username=update.effective_user.username,
                first_name=update.effective_user.first_name
            )

        api_key = self.user_manager.get_api_key(chat_id)

        if api_key:
            # 顯示部分 API Key
            masked_key = api_key[:10] + "..." + api_key[-4:]
            keyboard = [
                [InlineKeyboardButton("重新產生", callback_data="regenerate_apikey")],
                [InlineKeyboardButton("↩️ 返回主選單", callback_data="menu_main")]
            ]

            await update.message.reply_text(
                f"<b>您的 API Key</b>\n\n"
                f"<code>{masked_key}</code>\n\n"
                f"API Key 用於 REST API 認證\n"
                f"請妥善保管，不要分享給他人\n\n"
                f"點擊「重新產生」會使舊的 API Key 失效",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            keyboard = [
                [InlineKeyboardButton("產生 API Key", callback_data="generate_apikey")],
                [InlineKeyboardButton("↩️ 返回主選單", callback_data="menu_main")]
            ]

            await update.message.reply_text(
                "<b>API Key</b>\n\n"
                "您尚未產生 API Key\n"
                "API Key 用於 REST API 認證，可讓外部程式操作條件單",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    # ========== 主選單回調方法 ==========

    async def start_trigger_setup(self, query, context: ContextTypes.DEFAULT_TYPE):
        """從主選單開始新增條件單流程"""
        chat_id = query.message.chat_id

        # 確保用戶已註冊
        if not self.user_manager.user_exists(chat_id):
            self.user_manager.create_user(
                chat_id,
                username=query.from_user.username,
                first_name=query.from_user.first_name
            )

        # 檢查是否有設定券商
        brokers = self.user_manager.get_broker_names(chat_id)
        if not brokers:
            await query.edit_message_text(
                "請先使用券商設定功能設定券商 API\n"
                "設定完成後才能建立條件單",
                reply_markup=self._get_back_to_menu_keyboard()
            )
            return

        # 檢查是否已設定 PIN 碼
        if not self.user_manager.has_pin_code(chat_id):
            await query.edit_message_text(
                "請先使用設定PIN碼功能設定 PIN 碼\n"
                "PIN 碼用於驗證敏感操作",
                reply_markup=self._get_back_to_menu_keyboard()
            )
            return

        self.state_manager.clear_state(chat_id)

        keyboard = [
            [InlineKeyboardButton("↩️ 返回主選單", callback_data="menu_main")]
        ]

        await query.edit_message_text(
            "<b>新增條件單</b>\n\n"
            "請輸入股票代號：\n"
            "例如: <code>2330</code> (台積電)",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        self.state_manager.set_state(chat_id, TriggerSetupState.WAITING_SYMBOL)

    async def show_triggers_list(self, query, context: ContextTypes.DEFAULT_TYPE):
        """從主選單顯示條件單列表"""
        chat_id = query.message.chat_id

        triggers = self.trigger_manager.get_user_triggers(str(chat_id))

        if not triggers:
            await query.edit_message_text(
                "尚未設定任何條件單\n\n"
                "點擊「新增條件單」開始建立",
                reply_markup=self._get_back_to_menu_keyboard()
            )
            return

        status_icons = {
            'active': '🟢',
            'triggered': '🟡',
            'executed': '✅',
            'failed': '❌',
            'cancelled': '⚫',
            'expired': '⏰'
        }

        trade_type_map = {
            'cash': '現股',
            'day_trade': '現沖',
            'margin_buy': '融資',
            'short_sell': '融券',
        }

        msg = "<b>條件單列表</b>\n\n"

        for t in triggers[:10]:  # 最多顯示 10 筆
            icon = status_icons.get(t.status.value, '⚪')
            action = "買" if t.order_action.value == "buy" else "賣"
            order_type = "市" if t.order_type.value == "market" else "限"
            trade_type = trade_type_map.get(t.trade_type.value, '現股')

            msg += (
                f"{icon} <code>{t.symbol}</code> | "
                f"價格 {t.condition.value} {t.trigger_price}\n"
                f"   → {trade_type} {order_type}價{action} {t.quantity}張 | "
                f"ID: <code>{t.id[:8]}</code>\n"
            )

        if len(triggers) > 10:
            msg += f"\n... 還有 {len(triggers) - 10} 筆\n"

        # 建立刪除按鈕
        keyboard = []
        active_triggers = [t for t in triggers if t.status.value == 'active'][:5]
        if active_triggers:
            for t in active_triggers:
                keyboard.append([InlineKeyboardButton(
                    f"刪除 {t.symbol} ({t.id[:8]})",
                    callback_data=f"deltrigger_{t.id[:12]}"
                )])

        keyboard.append([InlineKeyboardButton("↩️ 返回主選單", callback_data="menu_main")])

        await query.edit_message_text(
            msg.strip(),
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def start_setpin(self, query, context: ContextTypes.DEFAULT_TYPE):
        """從主選單開始設定 PIN 碼"""
        chat_id = query.message.chat_id

        # 確保用戶已註冊
        if not self.user_manager.user_exists(chat_id):
            self.user_manager.create_user(
                chat_id,
                username=query.from_user.username,
                first_name=query.from_user.first_name
            )

        has_pin = self.user_manager.has_pin_code(chat_id)

        if has_pin:
            msg = (
                "<b>更新 PIN 碼</b>\n\n"
                "您已設定 PIN 碼\n"
                "請輸入新的 PIN 碼 (4-6 位數字)："
            )
        else:
            msg = (
                "<b>設定 PIN 碼</b>\n\n"
                "PIN 碼用於驗證敏感操作（如下單、刪除條件單）\n\n"
                "請輸入 PIN 碼 (4-6 位數字)："
            )

        self.state_manager.clear_state(chat_id)
        self.state_manager.set_state(chat_id, TriggerSetupState.WAITING_SET_PIN)

        keyboard = [
            [InlineKeyboardButton("↩️ 返回主選單", callback_data="menu_main")]
        ]

        await query.edit_message_text(
            msg,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def show_apikey(self, query, context: ContextTypes.DEFAULT_TYPE):
        """從主選單顯示 API Key"""
        chat_id = query.message.chat_id

        # 確保用戶已註冊
        if not self.user_manager.user_exists(chat_id):
            self.user_manager.create_user(
                chat_id,
                username=query.from_user.username,
                first_name=query.from_user.first_name
            )

        api_key = self.user_manager.get_api_key(chat_id)

        if api_key:
            # 顯示部分 API Key
            masked_key = api_key[:10] + "..." + api_key[-4:]
            keyboard = [
                [InlineKeyboardButton("重新產生", callback_data="regenerate_apikey")],
                [InlineKeyboardButton("↩️ 返回主選單", callback_data="menu_main")]
            ]

            await query.edit_message_text(
                f"<b>您的 API Key</b>\n\n"
                f"<code>{masked_key}</code>\n\n"
                f"API Key 用於 REST API 認證\n"
                f"請妥善保管，不要分享給他人\n\n"
                f"點擊「重新產生」會使舊的 API Key 失效",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            keyboard = [
                [InlineKeyboardButton("產生 API Key", callback_data="generate_apikey")],
                [InlineKeyboardButton("↩️ 返回主選單", callback_data="menu_main")]
            ]

            await query.edit_message_text(
                "<b>API Key</b>\n\n"
                "您尚未產生 API Key\n"
                "API Key 用於 REST API 認證，可讓外部程式操作條件單",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    # ========== 訊息處理 ==========

    async def handle_message(self, update: Update,
                             context: ContextTypes.DEFAULT_TYPE) -> bool:
        """
        處理條件單相關的訊息

        Returns:
            bool: 是否已處理（True 表示已處理，不需要其他處理器處理）
        """
        chat_id = update.effective_chat.id
        text = update.message.text.strip()
        state = self.state_manager.get_state(chat_id)

        # 檢查是否是條件單相關的狀態
        # 注意: 有些狀態如 waiting_order_type, waiting_order_price 不以 waiting_trigger 開頭
        trigger_states = {
            TriggerSetupState.WAITING_SYMBOL,
            TriggerSetupState.WAITING_CONDITION,
            TriggerSetupState.WAITING_TRIGGER_PRICE,
            TriggerSetupState.WAITING_ACTION,
            TriggerSetupState.WAITING_TRADE_TYPE,
            TriggerSetupState.WAITING_ORDER_TYPE,
            TriggerSetupState.WAITING_ORDER_PRICE,
            TriggerSetupState.WAITING_QUANTITY,
            TriggerSetupState.WAITING_CONFIRM,
            TriggerSetupState.WAITING_PIN,
            TriggerSetupState.WAITING_SET_PIN,
            TriggerSetupState.WAITING_SET_PIN_CONFIRM,
        }
        if state not in trigger_states:
            return False

        if state == TriggerSetupState.WAITING_SYMBOL:
            await self._handle_symbol_input(update, text)
            return True

        elif state == TriggerSetupState.WAITING_TRIGGER_PRICE:
            await self._handle_trigger_price_input(update, text)
            return True

        elif state == TriggerSetupState.WAITING_ORDER_PRICE:
            await self._handle_order_price_input(update, text)
            return True

        elif state == TriggerSetupState.WAITING_QUANTITY:
            await self._handle_quantity_input(update, text)
            return True

        elif state == TriggerSetupState.WAITING_PIN:
            await self._handle_pin_verification(update, text)
            return True

        elif state == TriggerSetupState.WAITING_SET_PIN:
            await self._handle_set_pin(update, text)
            return True

        elif state == TriggerSetupState.WAITING_SET_PIN_CONFIRM:
            await self._handle_set_pin_confirm(update, text)
            return True

        return False

    def _format_price_header(self, temp: dict) -> str:
        """格式化股價標題行 (用於後續步驟持續顯示)"""
        symbol = temp.get('symbol', '')
        symbol_name = temp.get('symbol_name', '')
        current_price = temp.get('current_price')

        if current_price:
            return f"📊 <b>{symbol} {symbol_name}</b> 現價: <code>{current_price:.2f}</code>\n"
        else:
            return f"📊 <b>{symbol}</b>\n"

    async def _handle_symbol_input(self, update: Update, symbol: str):
        """處理股票代號輸入"""
        chat_id = update.effective_chat.id
        symbol = symbol.upper()
        self.state_manager.set_temp_data(chat_id, 'symbol', symbol)

        # 查詢股價並儲存到 temp_data
        try:
            from src.core.stock_info import get_stock_quote, format_price_info
            quote = await get_stock_quote(symbol)

            if quote:
                # 儲存股價資訊供後續步驟使用
                self.state_manager.set_temp_data(chat_id, 'symbol_name', quote.name)
                self.state_manager.set_temp_data(chat_id, 'current_price', quote.price)
                price_msg = format_price_info(quote) + "\n\n"
            else:
                price_msg = f"<b>{symbol}</b>\n(無法取得即時報價)\n\n"
        except Exception:
            price_msg = f"<b>{symbol}</b>\n\n"

        # 選擇觸發條件
        keyboard = [
            [
                InlineKeyboardButton("價格 >= (漲到)", callback_data="trigger_cond_>="),
                InlineKeyboardButton("價格 <= (跌到)", callback_data="trigger_cond_<=")
            ],
            [
                InlineKeyboardButton("價格 == (等於)", callback_data="trigger_cond_==")
            ],
            [InlineKeyboardButton("取消", callback_data="cancel")]
        ]

        await update.message.reply_text(
            f"{price_msg}"
            "<b>選擇觸發條件：</b>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        self.state_manager.set_state(chat_id, TriggerSetupState.WAITING_CONDITION)

    async def _handle_trigger_price_input(self, update: Update, text: str):
        """處理觸發價格輸入"""
        chat_id = update.effective_chat.id

        try:
            price = float(text)
            if price <= 0:
                await update.message.reply_text("價格必須大於 0，請重新輸入：")
                return

            self.state_manager.set_temp_data(chat_id, 'trigger_price', price)

            temp = self.state_manager.get_temp_data(chat_id)
            price_header = self._format_price_header(temp)

            # 選擇買/賣
            keyboard = [
                [
                    InlineKeyboardButton("買入", callback_data="trigger_action_buy"),
                    InlineKeyboardButton("賣出", callback_data="trigger_action_sell")
                ],
                [InlineKeyboardButton("取消", callback_data="cancel")]
            ]

            await update.message.reply_text(
                f"{price_header}"
                f"觸發價格: <code>{price}</code>\n\n"
                "<b>選擇交易方向：</b>",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            self.state_manager.set_state(chat_id, TriggerSetupState.WAITING_ACTION)
        except ValueError:
            await update.message.reply_text("請輸入有效的數字：")

    async def _handle_order_price_input(self, update: Update, text: str):
        """處理限價單價格輸入"""
        chat_id = update.effective_chat.id

        try:
            price = float(text)
            if price <= 0:
                await update.message.reply_text("價格必須大於 0，請重新輸入：")
                return

            self.state_manager.set_temp_data(chat_id, 'order_price', price)

            temp = self.state_manager.get_temp_data(chat_id)
            price_header = self._format_price_header(temp)

            await update.message.reply_text(
                f"{price_header}"
                f"限價單價格: <code>{price}</code>\n\n"
                "請輸入交易張數：",
                parse_mode='HTML'
            )
            self.state_manager.set_state(chat_id, TriggerSetupState.WAITING_QUANTITY)
        except ValueError:
            await update.message.reply_text("請輸入有效的數字：")

    async def _handle_quantity_input(self, update: Update, text: str):
        """處理張數輸入"""
        chat_id = update.effective_chat.id

        try:
            qty = int(text)
            if qty < 1:
                await update.message.reply_text("張數至少為 1，請重新輸入：")
                return
            if qty > 999:
                await update.message.reply_text("張數不得超過 999，請重新輸入：")
                return

            self.state_manager.set_temp_data(chat_id, 'quantity', qty)

            # 顯示確認訊息
            temp = self.state_manager.get_temp_data(chat_id)
            price_header = self._format_price_header(temp)
            action = "買入" if temp.get('action') == 'buy' else "賣出"
            order_type = "市價單" if temp.get('order_type') == 'market' else "限價單"
            symbol_name = temp.get('symbol_name', '')

            trade_type_map = {
                'cash': '現股',
                'day_trade': '現沖',
                'margin_buy': '融資',
                'short_sell': '融券',
            }
            trade_type = trade_type_map.get(temp.get('trade_type', 'cash'), '現股')

            msg = f"""{price_header}
<b>請確認條件單設定：</b>

股票: <code>{temp.get('symbol')}</code> {symbol_name}
觸發條件: 價格 {temp.get('condition')} {temp.get('trigger_price')}
交易類型: {trade_type}
動作: {action} {qty} 張
訂單類型: {order_type}
"""
            if temp.get('order_type') == 'limit':
                msg += f"委託價格: {temp.get('order_price')}\n"

            msg += "\n確定要建立此條件單嗎？"

            keyboard = [
                [
                    InlineKeyboardButton("確認", callback_data="trigger_confirm_yes"),
                    InlineKeyboardButton("取消", callback_data="trigger_confirm_no")
                ]
            ]

            await update.message.reply_text(
                msg.strip(),
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            self.state_manager.set_state(chat_id, TriggerSetupState.WAITING_CONFIRM)

        except ValueError:
            await update.message.reply_text("請輸入有效的整數：")

    async def _handle_pin_verification(self, update: Update, pin: str):
        """處理 PIN 碼驗證"""
        chat_id = update.effective_chat.id

        if not self.user_manager.verify_pin_code(chat_id, pin):
            await update.message.reply_text(
                "PIN 碼錯誤，請重新輸入：\n"
                "（或輸入 /cancel 取消操作）"
            )
            return

        temp = self.state_manager.get_temp_data(chat_id)

        if temp.get('delete_trigger_id'):
            # 刪除條件單
            trigger_id = temp.get('delete_trigger_id')
            success = self.trigger_manager.cancel_trigger_order(trigger_id, str(chat_id))

            if success:
                await update.message.reply_text(
                    "條件單已取消",
                    reply_markup=self._get_back_to_menu_keyboard()
                )
            else:
                await update.message.reply_text(
                    "取消失敗，請確認條件單狀態",
                    reply_markup=self._get_back_to_menu_keyboard()
                )

        elif temp.get('symbol'):
            # 建立條件單
            await self._create_trigger_order(update, temp)

        self.state_manager.clear_state(chat_id)

    async def _handle_set_pin(self, update: Update, pin: str):
        """處理設定 PIN 碼"""
        chat_id = update.effective_chat.id

        if not pin.isdigit() or len(pin) < 4 or len(pin) > 6:
            await update.message.reply_text(
                "PIN 碼必須是 4-6 位數字\n"
                "請重新輸入："
            )
            return

        self.state_manager.set_temp_data(chat_id, 'new_pin', pin)
        self.state_manager.set_state(chat_id, TriggerSetupState.WAITING_SET_PIN_CONFIRM)

        await update.message.reply_text(
            f"請再次輸入 PIN 碼以確認：\n"
            f"（輸入的 PIN 碼：{'*' * len(pin)}）"
        )

    async def _handle_set_pin_confirm(self, update: Update, pin: str):
        """處理確認 PIN 碼"""
        chat_id = update.effective_chat.id
        temp = self.state_manager.get_temp_data(chat_id)
        new_pin = temp.get('new_pin')

        if pin != new_pin:
            await update.message.reply_text(
                "兩次輸入的 PIN 碼不一致\n\n"
                "請重新設定，輸入新的 PIN 碼 (4-6 位數字)："
            )
            self.state_manager.set_state(chat_id, TriggerSetupState.WAITING_SET_PIN)
            return

        success = self.user_manager.set_pin_code(chat_id, pin)

        if success:
            await update.message.reply_text(
                "PIN 碼設定成功\n\n"
                "現在您可以使用條件單功能了",
                reply_markup=self._get_back_to_menu_keyboard()
            )
        else:
            await update.message.reply_text(
                "PIN 碼設定失敗，請稍後再試",
                reply_markup=self._get_back_to_menu_keyboard()
            )

        self.state_manager.clear_state(chat_id)

    async def _create_trigger_order(self, update: Update, temp: dict):
        """建立條件單"""
        chat_id = update.effective_chat.id

        # 取得券商 (必須先設定才能建立條件單)
        brokers = self.user_manager.get_broker_names(chat_id)
        if not brokers:
            await update.message.reply_text(
                "錯誤：尚未設定券商\n"
                "請先使用 /broker 設定券商 API"
            )
            return
        broker_name = brokers[0]

        trigger = self.trigger_manager.create_trigger_order(
            user_id=str(chat_id),
            symbol=temp.get('symbol'),
            condition=temp.get('condition'),
            trigger_price=temp.get('trigger_price'),
            order_action=temp.get('action'),
            order_type=temp.get('order_type'),
            trade_type=temp.get('trade_type', 'cash'),
            quantity=temp.get('quantity'),
            order_price=temp.get('order_price'),
            broker_name=broker_name
        )

        action = "買入" if temp.get('action') == 'buy' else "賣出"
        order_type = "市價" if temp.get('order_type') == 'market' else "限價"

        trade_type_map = {
            'cash': '現股',
            'day_trade': '現沖',
            'margin_buy': '融資',
            'short_sell': '融券',
        }
        trade_type = trade_type_map.get(temp.get('trade_type', 'cash'), '現股')

        await update.message.reply_text(
            f"<b>條件單已建立</b>\n\n"
            f"ID: <code>{trigger.id[:8]}</code>\n"
            f"股票: {trigger.symbol}\n"
            f"條件: 價格 {trigger.condition.value} {trigger.trigger_price}\n"
            f"交易類型: {trade_type}\n"
            f"動作: {order_type}{action} {trigger.quantity}張",
            parse_mode='HTML',
            reply_markup=self._get_back_to_menu_keyboard()
        )

    # ========== 回調處理 ==========

    async def handle_callback(self, update: Update,
                              context: ContextTypes.DEFAULT_TYPE) -> bool:
        """
        處理條件單相關的回調

        Returns:
            bool: 是否已處理
        """
        query = update.callback_query
        data = query.data

        # 檢查是否是條件單相關的回調
        if not data.startswith(('trigger_', 'deltrigger_', 'generate_apikey', 'regenerate_apikey')):
            return False

        await query.answer()
        chat_id = query.message.chat_id

        if data.startswith("trigger_cond_"):
            condition = data.replace("trigger_cond_", "")
            self.state_manager.set_temp_data(chat_id, 'condition', condition)

            temp = self.state_manager.get_temp_data(chat_id)
            price_header = self._format_price_header(temp)

            await query.edit_message_text(
                f"{price_header}"
                f"觸發條件: 價格 {condition}\n\n"
                "請輸入觸發價格：",
                parse_mode='HTML'
            )
            self.state_manager.set_state(chat_id, TriggerSetupState.WAITING_TRIGGER_PRICE)
            return True

        elif data.startswith("trigger_action_"):
            action = data.replace("trigger_action_", "")
            self.state_manager.set_temp_data(chat_id, 'action', action)

            temp = self.state_manager.get_temp_data(chat_id)
            price_header = self._format_price_header(temp)

            # 根據買/賣顯示不同的交易類型選項
            # 買入: 現股, 現沖, 融資
            # 賣出: 現股, 現沖, 融券
            if action == "buy":
                keyboard = [
                    [
                        InlineKeyboardButton("現股", callback_data="trigger_trade_cash"),
                        InlineKeyboardButton("現沖", callback_data="trigger_trade_day_trade"),
                    ],
                    [
                        InlineKeyboardButton("融資", callback_data="trigger_trade_margin_buy"),
                    ],
                    [InlineKeyboardButton("取消", callback_data="cancel")]
                ]
            else:
                keyboard = [
                    [
                        InlineKeyboardButton("現股", callback_data="trigger_trade_cash"),
                        InlineKeyboardButton("現沖", callback_data="trigger_trade_day_trade"),
                    ],
                    [
                        InlineKeyboardButton("融券", callback_data="trigger_trade_short_sell"),
                    ],
                    [InlineKeyboardButton("取消", callback_data="cancel")]
                ]

            action_text = "買入" if action == "buy" else "賣出"
            await query.edit_message_text(
                f"{price_header}"
                f"交易方向: {action_text}\n\n"
                "<b>選擇交易類型：</b>",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            self.state_manager.set_state(chat_id, TriggerSetupState.WAITING_TRADE_TYPE)
            return True

        elif data.startswith("trigger_trade_"):
            trade_type = data.replace("trigger_trade_", "")
            self.state_manager.set_temp_data(chat_id, 'trade_type', trade_type)

            temp = self.state_manager.get_temp_data(chat_id)
            price_header = self._format_price_header(temp)

            trade_type_map = {
                'cash': '現股',
                'day_trade': '現沖',
                'margin_buy': '融資',
                'short_sell': '融券',
            }
            trade_type_text = trade_type_map.get(trade_type, '現股')
            action_text = "買入" if temp.get('action') == "buy" else "賣出"

            keyboard = [
                [
                    InlineKeyboardButton("市價單", callback_data="trigger_type_market"),
                    InlineKeyboardButton("限價單", callback_data="trigger_type_limit")
                ],
                [InlineKeyboardButton("取消", callback_data="cancel")]
            ]

            await query.edit_message_text(
                f"{price_header}"
                f"交易方向: {action_text}\n"
                f"交易類型: {trade_type_text}\n\n"
                "<b>選擇訂單類型：</b>",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            self.state_manager.set_state(chat_id, TriggerSetupState.WAITING_ORDER_TYPE)
            return True

        elif data.startswith("trigger_type_"):
            order_type = data.replace("trigger_type_", "")
            self.state_manager.set_temp_data(chat_id, 'order_type', order_type)

            temp = self.state_manager.get_temp_data(chat_id)
            price_header = self._format_price_header(temp)

            if order_type == 'market':
                await query.edit_message_text(
                    f"{price_header}"
                    "訂單類型: 市價單\n\n"
                    "請輸入交易張數：",
                    parse_mode='HTML'
                )
                self.state_manager.set_state(chat_id, TriggerSetupState.WAITING_QUANTITY)
            else:
                await query.edit_message_text(
                    f"{price_header}"
                    "訂單類型: 限價單\n\n"
                    "請輸入委託價格：",
                    parse_mode='HTML'
                )
                self.state_manager.set_state(chat_id, TriggerSetupState.WAITING_ORDER_PRICE)
            return True

        elif data == "trigger_confirm_yes":
            await query.edit_message_text(
                "<b>建立條件單需要 PIN 碼驗證</b>\n\n"
                "請輸入您的 PIN 碼：",
                parse_mode='HTML'
            )
            self.state_manager.set_state(chat_id, TriggerSetupState.WAITING_PIN)
            return True

        elif data == "trigger_confirm_no":
            self.state_manager.clear_state(chat_id)
            await query.edit_message_text(
                "已取消",
                reply_markup=self._get_back_to_menu_keyboard()
            )
            return True

        elif data.startswith("deltrigger_"):
            trigger_id_prefix = data.replace("deltrigger_", "")

            # 查找完整的 trigger_id
            triggers = self.trigger_manager.get_user_triggers(str(chat_id))
            full_id = None
            for t in triggers:
                if t.id.startswith(trigger_id_prefix):
                    full_id = t.id
                    break

            if not full_id:
                await query.edit_message_text("找不到此條件單")
                return True

            self.state_manager.set_temp_data(chat_id, 'delete_trigger_id', full_id)
            self.state_manager.set_state(chat_id, TriggerSetupState.WAITING_PIN)

            await query.edit_message_text(
                "<b>刪除條件單需要 PIN 碼驗證</b>\n\n"
                "請輸入您的 PIN 碼：",
                parse_mode='HTML'
            )
            return True

        elif data == "generate_apikey" or data == "regenerate_apikey":
            try:
                api_key = self.user_manager.generate_api_key(chat_id)

                await query.edit_message_text(
                    f"<b>API Key 已產生</b>\n\n"
                    f"<code>{api_key}</code>\n\n"
                    f"請妥善保管此金鑰，它不會再次顯示完整內容\n\n"
                    f"使用方式：\n"
                    f"在 HTTP 請求中加入 Header:\n"
                    f"<code>X-API-Key: {api_key[:20]}...</code>",
                    parse_mode='HTML',
                    reply_markup=self._get_back_to_menu_keyboard()
                )
            except Exception as e:
                await query.edit_message_text(
                    f"產生 API Key 失敗: {e}",
                    reply_markup=self._get_back_to_menu_keyboard()
                )
            return True

        return False
