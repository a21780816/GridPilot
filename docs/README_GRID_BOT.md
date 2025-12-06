# 股票網格交易機器人

使用富果交易 API 和市場數據 API 實現的自動化網格交易系統。

## 功能特色

- 自動化網格交易策略
- 即時價格監控
- 自動買入/賣出執行
- 持倉狀態追蹤
- 交易記錄保存

## 安裝需求

```bash
pip install esun-trade
pip install fugle-marketdata
```

## 快速開始

### 1. 申請 API 金鑰

**富果交易 API:**
- 前往富果證券申請 API 權限
- 下載配置檔並放置於 `config/config.simulation.ini`（模擬環境）

**Fugle 市場數據 API:**
- 前往 https://developer.fugle.tw/ 申請 API 金鑰

### 2. 計算所需本金

使用本金計算器來估算所需資金：

```bash
python3 calculate_capital.py
```

輸入您的網格參數，系統會自動計算：
- 最壞情況所需本金
- 平均情況所需本金
- 建議準備本金（含 20% 緩衝）

### 3. 配置參數

編輯 `config/grid_config_example.py`：

```python
# 交易參數
STOCK_SYMBOL = "2330"    # 股票代號
LOWER_PRICE = 1500.0     # 網格下限
UPPER_PRICE = 1520.0     # 網格上限
GRID_NUM = 10            # 網格數量
QUANTITY_PER_GRID = 1    # 每格交易量（張）
CHECK_INTERVAL = 60      # 檢查間隔（秒）

# 風險控制
MAX_CAPITAL = 18000000   # 最大本金（使用計算器得到的建議值）
```

### 4. 啟動機器人

**方法一：使用啟動腳本（推薦）**

```bash
python3 run_grid_bot.py
```

**方法二：自己撰寫程式碼**

```python
from grid_trading_bot import GridTradingBot

# 初始化
bot = GridTradingBot(
    config_file='./config/config.simulation.ini',
    api_key='YOUR_FUGLE_API_KEY'
)

# 設置網格
bot.setup_grid(
    symbol="2330",
    lower_price=500.0,
    upper_price=600.0,
    grid_num=10,
    quantity_per_grid=1
)

# 啟動
bot.run(check_interval=60)
```

## 網格交易原理

### 什麼是網格交易？

網格交易是一種量化交易策略，在價格區間內設置多個買賣點位：

1. **設定價格區間**: 例如 500-600 元
2. **劃分網格**: 將區間分成 10 格，每格 10 元
3. **自動交易**:
   - 價格下跌到網格點 → 買入
   - 價格上漲到網格點 → 賣出
4. **重複循環**: 持續執行，賺取價差

### 範例說明

假設設定：
- 股票: 2330 台積電
- 價格區間: 500-600 元
- 網格數量: 10 格
- 每格數量: 1 張

網格點位：
```
600 元 ← 上限
590 元 [賣出點]
580 元 [賣出點]
570 元 [賣出點]
...
520 元 [買入點]
510 元 [買入點]
500 元 ← 下限
```

當價格從 550 → 540，機器人會在 540 買入 1 張
當價格從 540 → 550，機器人會在 550 賣出 1 張

## 主要功能

### GridTradingBot 類別

#### 初始化
```python
bot = GridTradingBot(config_file, api_key)
```

#### 設置網格
```python
bot.setup_grid(
    symbol="2330",        # 股票代號
    lower_price=500.0,    # 下限價格
    upper_price=600.0,    # 上限價格
    grid_num=10,          # 網格數量
    quantity_per_grid=1   # 每格數量（張）
)
```

#### 啟動機器人
```python
bot.run(check_interval=60)  # 每 60 秒檢查一次
```

#### 停止機器人
```python
bot.stop()  # 或按 Ctrl+C
```

#### 查詢持倉
```python
position = bot.get_position()
print(position)
```

#### 獲取當前價格
```python
price = bot.get_current_price()
print(f"當前價格: {price}")
```

## 風險提醒

### 使用前必讀

1. **先使用模擬環境測試**
   - 使用 `config/config.simulation.ini` 進行測試
   - 確認策略運作正常後再考慮正式環境

2. **網格交易適用場景**
   - ✅ 震盪盤整行情
   - ✅ 價格波動規律
   - ❌ 單邊上漲趨勢（會過早賣出）
   - ❌ 單邊下跌趨勢（會持續買入虧損）

3. **風險控制**
   - 設定合理的價格區間
   - 控制每格交易數量
   - 設定最大持倉限制
   - 定期檢查交易狀況

4. **資金管理**
   - 預留足夠資金進行網格交易
   - 不要使用全部資金
   - 建議單一股票不超過總資金 20%

## 策略範例

### 保守型策略
適合穩健投資者，使用大型股：

```python
STOCK_SYMBOL = "0050"   # 元大台灣50
LOWER_PRICE = 130.0
UPPER_PRICE = 150.0
GRID_NUM = 10
QUANTITY_PER_GRID = 1
CHECK_INTERVAL = 120
```

### 積極型策略
適合能承受較高風險的投資者：

```python
STOCK_SYMBOL = "2454"   # 聯發科
LOWER_PRICE = 800.0
UPPER_PRICE = 1000.0
GRID_NUM = 20
QUANTITY_PER_GRID = 1
CHECK_INTERVAL = 60
```

### 測試型策略
小額測試，熟悉系統：

```python
STOCK_SYMBOL = "2603"   # 長榮
LOWER_PRICE = 100.0
UPPER_PRICE = 150.0
GRID_NUM = 5
QUANTITY_PER_GRID = 1
CHECK_INTERVAL = 180
```

## 監控與日誌

機器人運行時會顯示：

```
==================================================
時間: 2025-10-31 14:30:00
股票: 2330
當前價格: 555.0
持倉數量: 3 張
成本價格: 545.0
未實現損益: +3000
已執行買單: 3 / 已執行賣單: 1
==================================================
```

## 常見問題

### Q1: 機器人會 24 小時運行嗎？
A: 是的，但建議只在交易時段運行（09:00-13:30）。您可以在非交易時段停止機器人。

### Q2: 如何調整網格參數？
A: 停止機器人後，重新調用 `setup_grid()` 並重啟。

### Q3: 會不會重複下單？
A: 機器人會記錄每個網格點的執行狀態，避免重複下單。

### Q4: 如何處理未成交的訂單？
A: 目前版本會持續下單。建議定期檢查訂單狀態，手動取消未成交的訂單。

### Q5: 可以同時運行多個股票嗎？
A: 可以，但需要為每個股票創建獨立的 GridTradingBot 實例。

## 進階功能（待開發）

- [ ] 停損/停利功能
- [ ] 訂單狀態自動檢查
- [ ] 交易日誌導出
- [ ] 回測功能
- [ ] 多股票同時運行
- [ ] 動態調整網格
- [ ] 電報/LINE 通知

## 技術支援

- 富果交易 API 文檔: https://www.esunsec.com.tw/trading-platforms/api-trading/docs/
- Fugle 市場數據 API: https://developer.fugle.tw/docs/data/intro/

## 免責聲明

本程式僅供學習和研究使用。使用本程式進行實際交易的所有風險由使用者自行承擔。

- 網格交易存在風險，可能導致資金損失
- 請先在模擬環境充分測試
- 建議諮詢專業投資顧問
- 作者不對任何交易損失負責

## 授權

MIT License
