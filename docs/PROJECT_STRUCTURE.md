# 專案結構說明

```
stock/
├── config/                           # 配置文件資料夾
│   ├── config.simulation.ini         # 富果交易 API 模擬環境配置
│   ├── grid_config_example.py        # 網格機器人配置範例
│   ├── F131228150_20261031.p12      # API 憑證文件
│   └── *.whl                         # 安裝包
│
├── test/                             # 測試程式
│   ├── index.py
│   ├── login.py
│   ├── stock_price.py
│   └── treade.py
│
├── grid_trading_bot.py               # 網格交易機器人主程式
├── run_grid_bot.py                   # 啟動腳本（推薦使用）
├── README_GRID_BOT.md                # 使用說明文檔
└── PROJECT_STRUCTURE.md              # 本文件
```

## 快速開始

### 1. 設定配置
編輯 `config/grid_config_example.py`，填入您的 API 金鑰和交易參數。

### 2. 啟動機器人
```bash
python3 run_grid_bot.py
```

## 主要文件說明

### config/config.simulation.ini
富果交易 API 的配置文件，包含：
- API Entry Point
- 憑證路徑
- API Key 和 Secret
- 帳號資訊

### config/grid_config_example.py
網格交易機器人的配置參數，包含：
- Fugle API 金鑰
- 股票代號
- 網格價格區間
- 網格數量
- 交易數量
- 檢查間隔

### grid_trading_bot.py
網格交易機器人的核心程式，包含：
- GridTradingBot 類別
- 價格監控功能
- 自動下單功能
- 持倉查詢功能

### run_grid_bot.py
啟動腳本，自動讀取配置並啟動機器人。

## 注意事項

1. **不要提交敏感資訊到版本控制**
   - config.simulation.ini（包含 API Key）
   - *.p12 憑證文件
   - 包含真實 API 金鑰的配置文件

2. **先使用模擬環境測試**
   - 確保使用 config.simulation.ini
   - 充分測試後再考慮正式環境

3. **定期備份配置**
   - 保存好您的配置文件
   - 記錄交易參數和策略
