"""
Telegram Bot 主程式
處理用戶互動、設定和指令
支援多券商、多標的網格交易
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

from src.core.user_manager import UserManager, UserStateManager, UserSetupState
from src.brokers import get_broker_list, SUPPORTED_BROKERS

logger = logging.getLogger('TelegramBot')


class TradingBot:
    """Telegram 交易機器人"""

    def __init__(self, token, user_manager, bot_manager=None):
        """
        初始化

        Args:
            token: Telegram Bot Token
            user_manager: UserManager 實例
            bot_manager: BotManager 實例 (管理交易機器人)
        """
        self.token = token
        self.user_manager = user_manager
        self.bot_manager = bot_manager
        self.state_manager = UserStateManager()
        self.app = None

    # ========== 基本指令 ==========

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """處理 /start 指令"""
        user = update.effective_user
        chat_id = update.effective_chat.id

        # 檢查用戶是否已註冊
        if not self.user_manager.user_exists(chat_id):
            self.user_manager.create_user(
                chat_id,
                username=user.username,
                first_name=user.first_name
            )

        welcome_msg = f"""
<b>歡迎使用網格交易機器人！</b>

嗨 {user.first_name}，我是你的股票網格交易助手。

<b>功能說明</b>
- 自動網格交易 - 在設定的價格區間內自動買賣
- 多券商支援 - 可同時設定多個券商帳號
- 多標的交易 - 可同時運行多個股票的網格策略
- 即時通知 - 下單、成交、停損停利即時推送

<b>快速開始</b>
1. /broker - 設定券商 API
2. /grid - 新增網格策略
3. /run - 啟動網格交易

<b>所有指令</b>
/help - 查看所有指令
        """
        await update.message.reply_text(welcome_msg.strip(), parse_mode='HTML')

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """處理 /help 指令"""
        help_msg = """
<b>指令說明</b>

<b>基本指令</b>
/start - 開始使用
/help - 顯示此說明

<b>券商管理</b>
/broker - 新增/管理券商設定
/brokers - 查看已設定的券商

<b>網格管理</b>
/grid - 新增網格策略
/grids - 查看所有網格策略
/edit [股票代號] - 編輯網格設定
/delete [股票代號] - 刪除網格設定

<b>交易控制</b>
/run [股票代號] - 啟動指定標的
/stop [股票代號] - 停止指定標的
/runall - 啟動所有網格
/stopall - 停止所有網格

<b>狀態查詢</b>
/status - 查看所有運行中的網格狀態
/status [股票代號] - 查看指定標的狀態
        """
        await update.message.reply_text(help_msg.strip(), parse_mode='HTML')

    # ========== 券商管理 ==========

    async def broker_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """處理 /broker 指令 - 管理券商設定"""
        chat_id = update.effective_chat.id

        # 清除之前的狀態
        self.state_manager.clear_state(chat_id)

        # 檢查是否已有設定過券商
        existing_brokers = self.user_manager.get_all_broker_configs(chat_id)

        if existing_brokers:
            # 已有券商設定，顯示管理選單
            msg = "<b>券商管理</b>\n\n<b>已設定的券商：</b>\n"
            for b in existing_brokers:
                broker_name = SUPPORTED_BROKERS.get(b['broker_name'], {}).get('name', b['broker_name'])
                env = b.get('env', 'N/A')
                env_display = '模擬' if env == 'simulation' else '正式' if env == 'production' else env
                msg += f"• {broker_name} ({env_display})\n"

            keyboard = [
                [InlineKeyboardButton("新增券商", callback_data="broker_add_new")],
                [InlineKeyboardButton("重新設定", callback_data="broker_reconfigure")],
                [InlineKeyboardButton("取消", callback_data="cancel")]
            ]

            await update.message.reply_text(
                msg,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            # 沒有券商設定，直接進入新增流程
            await self._show_broker_selection(update.message, chat_id)

    async def _show_broker_selection(self, message, chat_id):
        """顯示券商選擇清單"""
        brokers = get_broker_list()
        keyboard = []
        for broker_id, broker_name in brokers.items():
            keyboard.append([InlineKeyboardButton(broker_name, callback_data=f"broker_select_{broker_id}")])

        keyboard.append([InlineKeyboardButton("取消", callback_data="cancel")])

        await message.reply_text(
            "<b>新增券商設定</b>\n\n請選擇您的券商：",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        self.state_manager.set_state(chat_id, UserSetupState.WAITING_BROKER_SELECT)

    async def brokers_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """處理 /brokers 指令 - 查看已設定的券商"""
        chat_id = update.effective_chat.id
        brokers = self.user_manager.get_all_broker_configs(chat_id)

        if not brokers:
            await update.message.reply_text(
                "尚未設定任何券商\n\n使用 /broker 新增券商設定"
            )
            return

        msg = "<b>已設定的券商</b>\n\n"
        for i, b in enumerate(brokers, 1):
            broker_name = SUPPORTED_BROKERS.get(b['broker_name'], {}).get('name', b['broker_name'])
            msg += f"{i}. {broker_name}\n"
            msg += f"   更新時間: {b.get('updated_at', 'N/A')[:10]}\n\n"

        msg += "使用 /broker 新增更多券商"
        await update.message.reply_text(msg.strip(), parse_mode='HTML')

    # ========== 網格管理 ==========

    async def grid_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """處理 /grid 指令 - 新增網格策略"""
        chat_id = update.effective_chat.id

        # 檢查是否有設定券商
        brokers = self.user_manager.get_broker_names(chat_id)
        if not brokers:
            await update.message.reply_text(
                "請先使用 /broker 設定券商 API"
            )
            return

        # 清除之前的狀態
        self.state_manager.clear_state(chat_id)

        await update.message.reply_text(
            "<b>新增網格策略</b>\n\n"
            "請輸入股票代號：\n"
            "例如: <code>2330</code> (台積電)",
            parse_mode='HTML'
        )
        self.state_manager.set_state(chat_id, UserSetupState.WAITING_GRID_SYMBOL)

    async def grids_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """處理 /grids 指令 - 查看所有網格策略"""
        chat_id = update.effective_chat.id
        grids = self.user_manager.get_all_grid_configs(chat_id)

        if not grids:
            await update.message.reply_text(
                "尚未設定任何網格策略\n\n使用 /grid 新增網格策略"
            )
            return

        msg = "<b>已設定的網格策略</b>\n\n"
        for g in grids:
            status = "🟢 運行中" if g.get('is_running') else "⚪ 已停止"
            broker_name = SUPPORTED_BROKERS.get(g.get('broker'), {}).get('name', g.get('broker', 'N/A'))
            msg += f"<b>{g['symbol']}</b> {status}\n"
            msg += f"  券商: {broker_name}\n"
            msg += f"  區間: {g['lower_price']} ~ {g['upper_price']}\n"
            msg += f"  網格: {g['grid_num']} 格, 每格 {g['quantity_per_grid']} 張\n\n"

        msg += "使用 /run [代號] 啟動 | /stop [代號] 停止"
        await update.message.reply_text(msg.strip(), parse_mode='HTML')

    async def delete_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """處理 /delete 指令 - 刪除網格設定"""
        chat_id = update.effective_chat.id

        if not context.args:
            await update.message.reply_text(
                "請指定要刪除的股票代號\n"
                "例如: /delete 2330"
            )
            return

        symbol = context.args[0].upper()

        # 檢查是否正在運行
        if self.bot_manager:
            status = self.bot_manager.get_grid_status(chat_id, symbol)
            if status and status.get('is_running'):
                await update.message.reply_text(
                    f"{symbol} 正在運行中，請先使用 /stop {symbol} 停止"
                )
                return

        if self.user_manager.delete_grid_config(chat_id, symbol):
            await update.message.reply_text(f"已刪除 {symbol} 的網格設定")
        else:
            await update.message.reply_text(f"找不到 {symbol} 的網格設定")

    # ========== 交易控制 ==========

    async def run_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """處理 /run 指令 - 啟動網格"""
        chat_id = update.effective_chat.id

        if not context.args:
            # 顯示可啟動的網格
            grids = self.user_manager.get_all_grid_configs(chat_id)
            stopped = [g for g in grids if not g.get('is_running')]

            if not stopped:
                await update.message.reply_text(
                    "沒有可啟動的網格\n\n"
                    "使用 /grid 新增網格策略\n"
                    "使用 /grids 查看所有網格"
                )
                return

            keyboard = []
            for g in stopped:
                keyboard.append([
                    InlineKeyboardButton(
                        f"{g['symbol']} ({g['lower_price']}~{g['upper_price']})",
                        callback_data=f"run_grid_{g['symbol']}"
                    )
                ])
            keyboard.append([InlineKeyboardButton("取消", callback_data="cancel")])

            await update.message.reply_text(
                "<b>選擇要啟動的網格：</b>",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        symbol = context.args[0].upper()
        await self._start_grid(chat_id, symbol, update.message)

    async def stop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """處理 /stop 指令 - 停止網格"""
        chat_id = update.effective_chat.id

        if not context.args:
            # 顯示可停止的網格
            if not self.bot_manager:
                await update.message.reply_text("交易管理器未初始化")
                return

            running = self.bot_manager.get_user_running_grids(chat_id)

            if not running:
                await update.message.reply_text("目前沒有運行中的網格")
                return

            keyboard = []
            for g in running:
                keyboard.append([
                    InlineKeyboardButton(
                        f"{g['symbol']} (${g.get('current_price', 'N/A')})",
                        callback_data=f"stop_grid_{g['symbol']}"
                    )
                ])
            keyboard.append([InlineKeyboardButton("取消", callback_data="cancel")])

            await update.message.reply_text(
                "<b>選擇要停止的網格：</b>",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        symbol = context.args[0].upper()
        await self._stop_grid(chat_id, symbol, update.message)

    async def runall_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """處理 /runall 指令 - 啟動所有網格"""
        chat_id = update.effective_chat.id
        grids = self.user_manager.get_all_grid_configs(chat_id)
        stopped = [g for g in grids if not g.get('is_running')]

        if not stopped:
            await update.message.reply_text("沒有可啟動的網格")
            return

        started = 0
        failed = []

        for g in stopped:
            success, msg = self.bot_manager.start_grid(chat_id, g['symbol'])
            if success:
                started += 1
            else:
                failed.append(f"{g['symbol']}: {msg}")

        result = f"已啟動 {started} 個網格"
        if failed:
            result += f"\n\n失敗:\n" + "\n".join(failed)

        await update.message.reply_text(result)

    async def stopall_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """處理 /stopall 指令 - 停止所有網格"""
        chat_id = update.effective_chat.id

        if not self.bot_manager:
            await update.message.reply_text("交易管理器未初始化")
            return

        stopped = self.bot_manager.stop_user_all_grids(chat_id)
        await update.message.reply_text(f"已停止 {stopped} 個網格")

    async def _start_grid(self, chat_id, symbol: str, message):
        """啟動單一網格"""
        if not self.bot_manager:
            await message.reply_text("交易管理器未初始化")
            return

        grid = self.user_manager.get_grid_config(chat_id, symbol)
        if not grid:
            await message.reply_text(f"找不到 {symbol} 的網格設定")
            return

        success, msg = self.bot_manager.start_grid(chat_id, symbol)

        if success:
            await message.reply_text(
                f"🟢 <b>{symbol} 網格已啟動</b>\n\n"
                f"區間: {grid['lower_price']} ~ {grid['upper_price']}\n"
                f"網格: {grid['grid_num']} 格\n\n"
                f"使用 /status {symbol} 查看狀態",
                parse_mode='HTML'
            )
        else:
            await message.reply_text(f"啟動失敗: {msg}")

    async def _stop_grid(self, chat_id, symbol: str, message):
        """停止單一網格"""
        if not self.bot_manager:
            await message.reply_text("交易管理器未初始化")
            return

        success, msg = self.bot_manager.stop_grid(chat_id, symbol)

        if success:
            await message.reply_text(f"🔴 {symbol} 網格已停止")
        else:
            await message.reply_text(f"停止失敗: {msg}")

    # ========== 狀態查詢 ==========

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """處理 /status 指令 - 查詢狀態"""
        chat_id = update.effective_chat.id

        if not self.bot_manager:
            await update.message.reply_text("交易管理器未初始化")
            return

        if context.args:
            # 查詢特定標的
            symbol = context.args[0].upper()
            status = self.bot_manager.get_grid_status(chat_id, symbol)

            if not status:
                await update.message.reply_text(f"{symbol} 目前沒有在運行")
                return

            msg = f"""
<b>{symbol} 運行狀態</b>

<b>價格資訊</b>
- 當前價格: {status.get('current_price', 'N/A')}
- 網格區間: {status['lower_price']} ~ {status['upper_price']}

<b>持倉資訊</b>
- 持倉數量: {status.get('position_qty', 0)} 張
- 成本均價: {status.get('avg_price', 'N/A')}
- 未實現損益: {status.get('unrealized_pnl', 0):+,.0f}

<b>訂單統計</b>
- 買單: {status.get('pending_buys', 0)} 委託中 / {status.get('filled_buys', 0)} 已成交
- 賣單: {status.get('pending_sells', 0)} 委託中 / {status.get('filled_sells', 0)} 已成交

<b>運行資訊</b>
- 啟動時間: {status.get('started_at', 'N/A')[:19] if status.get('started_at') else 'N/A'}
- 檢查次數: {status.get('iteration', 0)}
            """
            await update.message.reply_text(msg.strip(), parse_mode='HTML')
        else:
            # 查詢所有運行中的網格
            running = self.bot_manager.get_user_running_grids(chat_id)

            if not running:
                await update.message.reply_text(
                    "目前沒有運行中的網格\n\n"
                    "使用 /run 啟動網格\n"
                    "使用 /grids 查看所有網格"
                )
                return

            msg = f"<b>運行中的網格 ({len(running)})</b>\n\n"
            for s in running:
                pnl = s.get('unrealized_pnl', 0)
                pnl_str = f"+{pnl:,.0f}" if pnl >= 0 else f"{pnl:,.0f}"
                msg += f"<b>{s['symbol']}</b> ${s.get('current_price', 'N/A')}\n"
                msg += f"  持倉: {s.get('position_qty', 0)}張 | 損益: {pnl_str}\n\n"

            msg += "使用 /status [代號] 查看詳細狀態"
            await update.message.reply_text(msg.strip(), parse_mode='HTML')

    # ========== 回調處理 ==========

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """處理按鈕回調"""
        query = update.callback_query
        await query.answer()

        chat_id = query.message.chat_id
        data = query.data

        if data == "cancel":
            self.state_manager.clear_state(chat_id)
            await query.edit_message_text("已取消")
            return

        # 新增券商
        if data == "broker_add_new":
            brokers = get_broker_list()
            keyboard = []
            for broker_id, broker_name in brokers.items():
                keyboard.append([InlineKeyboardButton(broker_name, callback_data=f"broker_select_{broker_id}")])
            keyboard.append([InlineKeyboardButton("取消", callback_data="cancel")])

            await query.edit_message_text(
                "<b>新增券商設定</b>\n\n請選擇您的券商：",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            self.state_manager.set_state(chat_id, UserSetupState.WAITING_BROKER_SELECT)

        # 重新設定券商（選擇要重設的券商）
        elif data == "broker_reconfigure":
            existing_brokers = self.user_manager.get_all_broker_configs(chat_id)
            keyboard = []
            for b in existing_brokers:
                broker_id = b['broker_name']
                broker_name = SUPPORTED_BROKERS.get(broker_id, {}).get('name', broker_id)
                keyboard.append([InlineKeyboardButton(broker_name, callback_data=f"broker_reconfig_{broker_id}")])
            keyboard.append([InlineKeyboardButton("取消", callback_data="cancel")])

            await query.edit_message_text(
                "<b>重新設定券商</b>\n\n請選擇要重新設定的券商：",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        # 重新設定特定券商
        elif data.startswith("broker_reconfig_"):
            broker_type = data.replace("broker_reconfig_", "")
            self.state_manager.set_temp_data(chat_id, 'broker_type', broker_type)

            broker_info = SUPPORTED_BROKERS.get(broker_type)
            if broker_info:
                await query.edit_message_text(
                    f"重新設定: <b>{broker_info['name']}</b>\n\n"
                    f"📄 請上傳設定檔 (.ini)\n\n"
                    f"設定檔格式範例：\n"
                    f"<code>[Esun]\n"
                    f"PersonId = A123456789\n"
                    f"Account = 1234567\n"
                    f"CertPath = xxx.p12\n"
                    f"CertPassword = 123456\n"
                    f"Env = simulation</code>",
                    parse_mode='HTML'
                )
                self.state_manager.set_state(chat_id, UserSetupState.WAITING_CONFIG_FILE)

        # 券商選擇
        elif data.startswith("broker_select_"):
            broker_type = data.replace("broker_select_", "")
            self.state_manager.set_temp_data(chat_id, 'broker_type', broker_type)

            broker_info = SUPPORTED_BROKERS.get(broker_type)
            if broker_info:
                await query.edit_message_text(
                    f"已選擇: <b>{broker_info['name']}</b>\n\n"
                    f"📄 請上傳設定檔 (.ini)\n\n"
                    f"設定檔格式範例：\n"
                    f"<code>[Esun]\n"
                    f"PersonId = A123456789\n"
                    f"Account = 1234567\n"
                    f"CertPath = xxx.p12\n"
                    f"CertPassword = 123456\n"
                    f"Env = simulation</code>",
                    parse_mode='HTML'
                )
                self.state_manager.set_state(chat_id, UserSetupState.WAITING_CONFIG_FILE)

        # 選擇網格使用的券商
        elif data.startswith("grid_broker_"):
            broker_name = data.replace("grid_broker_", "")
            self.state_manager.set_temp_data(chat_id, 'broker', broker_name)

            await query.edit_message_text(
                "請輸入網格價格下限：",
                parse_mode='HTML'
            )
            self.state_manager.set_state(chat_id, UserSetupState.WAITING_LOWER_PRICE)

        # 確認儲存網格
        elif data == "grid_confirm_yes":
            await self._save_grid_config(chat_id, query)

        elif data == "grid_confirm_no":
            self.state_manager.clear_state(chat_id)
            await query.edit_message_text("已取消設定。使用 /grid 重新開始。")

        # 啟動網格
        elif data.startswith("run_grid_"):
            symbol = data.replace("run_grid_", "")
            await query.edit_message_text(f"正在啟動 {symbol}...")
            await self._start_grid(chat_id, symbol, query.message)

        # 停止網格
        elif data.startswith("stop_grid_"):
            symbol = data.replace("stop_grid_", "")
            await self._stop_grid(chat_id, symbol, query.message)

    # ========== 訊息處理 ==========

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """處理一般訊息 (用於互動式設定)"""
        chat_id = update.effective_chat.id
        text = update.message.text.strip()
        state = self.state_manager.get_state(chat_id)

        if state == UserSetupState.IDLE:
            await update.message.reply_text(
                "請使用指令與我互動\n"
                "輸入 /help 查看所有指令"
            )
            return

        # ===== 券商設定流程 =====
        if state == UserSetupState.WAITING_CONFIG_FILE:
            # 提示使用者上傳檔案而不是輸入文字
            await update.message.reply_text(
                "請上傳 .ini 設定檔，而不是輸入文字\n\n"
                "📎 點擊輸入框旁的迴紋針圖示來上傳檔案"
            )
            return

        elif state == UserSetupState.WAITING_CERT_FILE:
            # 提示使用者上傳檔案而不是輸入文字
            await update.message.reply_text(
                "請上傳 .p12 憑證檔，而不是輸入文字\n\n"
                "📎 點擊輸入框旁的迴紋針圖示來上傳檔案"
            )
            return

        # ===== 網格設定流程 =====
        elif state == UserSetupState.WAITING_GRID_SYMBOL:
            symbol = text.upper()
            # 檢查是否已存在
            existing = self.user_manager.get_grid_config(chat_id, symbol)
            if existing:
                await update.message.reply_text(
                    f"{symbol} 已有設定\n"
                    f"使用 /edit {symbol} 修改\n"
                    f"或 /delete {symbol} 刪除"
                )
                self.state_manager.clear_state(chat_id)
                return

            self.state_manager.set_temp_data(chat_id, 'symbol', symbol)

            # 查詢股價資訊
            from src.core.stock_info import get_stock_quote, format_price_info
            quote = await get_stock_quote(symbol)

            if quote:
                price_info = format_price_info(quote)
                price_msg = f"{price_info}\n\n"
            else:
                price_msg = f"<b>{symbol}</b>\n(無法取得即時報價)\n\n"

            # 選擇券商
            brokers = self.user_manager.get_broker_names(chat_id)
            if len(brokers) == 1:
                # 只有一個券商，直接使用
                self.state_manager.set_temp_data(chat_id, 'broker', brokers[0])
                await update.message.reply_text(
                    f"{price_msg}"
                    "請輸入網格價格下限：",
                    parse_mode='HTML'
                )
                self.state_manager.set_state(chat_id, UserSetupState.WAITING_LOWER_PRICE)
            else:
                # 多個券商，讓用戶選擇
                keyboard = []
                for b in brokers:
                    name = SUPPORTED_BROKERS.get(b, {}).get('name', b)
                    keyboard.append([InlineKeyboardButton(name, callback_data=f"grid_broker_{b}")])

                await update.message.reply_text(
                    f"{price_msg}"
                    "請選擇要使用的券商：",
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                self.state_manager.set_state(chat_id, UserSetupState.WAITING_GRID_BROKER)

        elif state == UserSetupState.WAITING_LOWER_PRICE:
            try:
                price = float(text)
                self.state_manager.set_temp_data(chat_id, 'lower_price', price)
                await update.message.reply_text(
                    f"價格下限: <code>{price}</code>\n\n"
                    "請輸入網格價格上限：",
                    parse_mode='HTML'
                )
                self.state_manager.set_state(chat_id, UserSetupState.WAITING_UPPER_PRICE)
            except ValueError:
                await update.message.reply_text("請輸入有效的數字")

        elif state == UserSetupState.WAITING_UPPER_PRICE:
            try:
                price = float(text)
                temp = self.state_manager.get_temp_data(chat_id)
                if price <= temp.get('lower_price', 0):
                    await update.message.reply_text("上限必須大於下限，請重新輸入：")
                    return
                self.state_manager.set_temp_data(chat_id, 'upper_price', price)
                await update.message.reply_text(
                    f"價格上限: <code>{price}</code>\n\n"
                    "請輸入網格數量（建議 5-20）：",
                    parse_mode='HTML'
                )
                self.state_manager.set_state(chat_id, UserSetupState.WAITING_GRID_NUM)
            except ValueError:
                await update.message.reply_text("請輸入有效的數字")

        elif state == UserSetupState.WAITING_GRID_NUM:
            try:
                num = int(text)
                if num < 2 or num > 50:
                    await update.message.reply_text("網格數量請設定在 2-50 之間")
                    return
                self.state_manager.set_temp_data(chat_id, 'grid_num', num)
                await update.message.reply_text(
                    f"網格數量: <code>{num}</code>\n\n"
                    "請輸入每格交易張數：",
                    parse_mode='HTML'
                )
                self.state_manager.set_state(chat_id, UserSetupState.WAITING_QUANTITY)
            except ValueError:
                await update.message.reply_text("請輸入有效的整數")

        elif state == UserSetupState.WAITING_QUANTITY:
            try:
                qty = int(text)
                if qty < 1:
                    await update.message.reply_text("張數至少為 1")
                    return
                self.state_manager.set_temp_data(chat_id, 'quantity_per_grid', qty)

                # 顯示確認
                temp = self.state_manager.get_temp_data(chat_id)
                broker_name = SUPPORTED_BROKERS.get(temp.get('broker'), {}).get('name', temp.get('broker'))

                msg = f"""
<b>請確認網格策略設定：</b>

- 股票代號: {temp.get('symbol')}
- 使用券商: {broker_name}
- 價格下限: {temp.get('lower_price')}
- 價格上限: {temp.get('upper_price')}
- 網格數量: {temp.get('grid_num')}
- 每格張數: {qty}

確定要儲存這個設定嗎？
                """
                await update.message.reply_text(
                    msg.strip(),
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("確認", callback_data="grid_confirm_yes"),
                            InlineKeyboardButton("取消", callback_data="grid_confirm_no")
                        ]
                    ])
                )
                self.state_manager.set_state(chat_id, UserSetupState.WAITING_GRID_CONFIRM)

            except ValueError:
                await update.message.reply_text("請輸入有效的整數")

    # ========== 檔案上傳處理 ==========

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """處理檔案上傳"""
        chat_id = update.effective_chat.id
        state = self.state_manager.get_state(chat_id)
        document = update.message.document

        if state == UserSetupState.IDLE:
            await update.message.reply_text(
                "請先使用 /broker 指令開始設定流程"
            )
            return

        # 取得檔案資訊
        file_name = document.file_name
        file_size = document.file_size

        # 檔案大小限制 (1MB)
        if file_size > 1024 * 1024:
            await update.message.reply_text("檔案太大，請上傳小於 1MB 的檔案")
            return

        # ===== 處理設定檔 (.ini) =====
        if state == UserSetupState.WAITING_CONFIG_FILE:
            if not file_name.endswith('.ini'):
                await update.message.reply_text(
                    "請上傳 .ini 格式的設定檔\n"
                    "例如: config.simulation.ini"
                )
                return

            try:
                # 下載檔案
                file = await context.bot.get_file(document.file_id)
                file_bytes = await file.download_as_bytearray()
                config_content = file_bytes.decode('utf-8')

                # 暫存設定內容
                self.state_manager.set_temp_data(chat_id, 'config_content', config_content)
                self.state_manager.set_temp_data(chat_id, 'config_filename', file_name)

                # 驗證設定檔格式
                temp = self.state_manager.get_temp_data(chat_id)
                broker_type = temp.get('broker_type')
                self.user_manager.parse_broker_config_file(config_content, broker_type)

                await update.message.reply_text(
                    f"✅ 設定檔已接收: <code>{file_name}</code>\n\n"
                    f"🔐 請上傳憑證檔 (.p12)",
                    parse_mode='HTML'
                )
                self.state_manager.set_state(chat_id, UserSetupState.WAITING_CERT_FILE)

            except UnicodeDecodeError:
                await update.message.reply_text(
                    "設定檔編碼錯誤，請確認是 UTF-8 編碼的文字檔"
                )
            except ValueError as e:
                await update.message.reply_text(
                    f"設定檔格式錯誤: {e}\n\n"
                    f"請檢查設定檔內容後重新上傳"
                )
            except Exception as e:
                logger.error(f"處理設定檔錯誤: {e}")
                await update.message.reply_text(
                    f"處理設定檔時發生錯誤，請稍後再試"
                )

        # ===== 處理憑證檔 (.p12) =====
        elif state == UserSetupState.WAITING_CERT_FILE:
            if not file_name.endswith('.p12'):
                await update.message.reply_text(
                    "請上傳 .p12 格式的憑證檔"
                )
                return

            try:
                # 下載憑證檔
                file = await context.bot.get_file(document.file_id)
                cert_bytes = bytes(await file.download_as_bytearray())

                # 取得暫存資料
                temp = self.state_manager.get_temp_data(chat_id)
                broker_type = temp.get('broker_type')
                config_content = temp.get('config_content')

                # 儲存券商設定和憑證
                saved_config = self.user_manager.save_broker_from_config_file(
                    chat_id=chat_id,
                    broker_name=broker_type,
                    config_content=config_content,
                    cert_content=cert_bytes,
                    cert_filename=file_name
                )

                # 清除狀態
                self.state_manager.clear_state(chat_id)

                broker_name = SUPPORTED_BROKERS.get(broker_type, {}).get('name', broker_type)
                env = saved_config.get('env', 'N/A')
                env_display = '模擬環境' if env == 'simulation' else '正式環境' if env == 'production' else env

                await update.message.reply_text(
                    f"✅ <b>券商設定完成</b>\n\n"
                    f"券商: {broker_name}\n"
                    f"帳號: {saved_config.get('account', 'N/A')}\n"
                    f"環境: {env_display}\n\n"
                    f"使用 /grid 設定網格策略",
                    parse_mode='HTML'
                )

            except Exception as e:
                logger.error(f"處理憑證檔錯誤: {e}")
                await update.message.reply_text(
                    f"處理憑證檔時發生錯誤: {e}\n\n"
                    f"請重新上傳或使用 /broker 重新開始"
                )

    async def _save_grid_config(self, chat_id, query):
        """儲存網格設定"""
        temp = self.state_manager.get_temp_data(chat_id)
        symbol = temp.get('symbol')

        grid_config = {
            'broker': temp.get('broker'),
            'lower_price': temp.get('lower_price'),
            'upper_price': temp.get('upper_price'),
            'grid_num': temp.get('grid_num'),
            'quantity_per_grid': temp.get('quantity_per_grid'),
            'check_interval': 60  # 預設 60 秒
        }

        self.user_manager.save_grid_config(chat_id, symbol, grid_config)
        self.state_manager.clear_state(chat_id)

        await query.edit_message_text(
            f"<b>{symbol} 網格策略設定完成</b>\n\n"
            f"使用 /grids 查看所有網格\n"
            f"使用 /run {symbol} 啟動交易",
            parse_mode='HTML'
        )

    # ========== 啟動 ==========

    def run(self):
        """啟動 Bot"""
        self.app = Application.builder().token(self.token).build()

        # 註冊指令處理器
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("help", self.help_command))

        # 券商管理
        self.app.add_handler(CommandHandler("broker", self.broker_command))
        self.app.add_handler(CommandHandler("brokers", self.brokers_command))

        # 網格管理
        self.app.add_handler(CommandHandler("grid", self.grid_command))
        self.app.add_handler(CommandHandler("grids", self.grids_command))
        self.app.add_handler(CommandHandler("delete", self.delete_command))

        # 交易控制
        self.app.add_handler(CommandHandler("run", self.run_command))
        self.app.add_handler(CommandHandler("stop", self.stop_command))
        self.app.add_handler(CommandHandler("runall", self.runall_command))
        self.app.add_handler(CommandHandler("stopall", self.stopall_command))

        # 狀態查詢
        self.app.add_handler(CommandHandler("status", self.status_command))

        # 回調處理器
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))

        # 訊息處理器
        self.app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.handle_message
        ))

        # 檔案上傳處理器
        self.app.add_handler(MessageHandler(
            filters.Document.ALL,
            self.handle_document
        ))

        logger.info("Telegram Bot 啟動中...")
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    import sys
    from pathlib import Path

    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )

    # 從設定檔讀取 Token
    try:
        from config.grid_config_example import TELEGRAM_BOT_TOKEN
    except ImportError:
        print("請在 config/grid_config_example.py 設定 TELEGRAM_BOT_TOKEN")
        sys.exit(1)

    if not TELEGRAM_BOT_TOKEN:
        print("TELEGRAM_BOT_TOKEN 未設定")
        sys.exit(1)

    user_manager = UserManager()
    bot = TradingBot(TELEGRAM_BOT_TOKEN, user_manager)
    bot.run()
