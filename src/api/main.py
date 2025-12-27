"""
FastAPI 應用入口
"""

import logging
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .middleware.auth import APIKeyMiddleware
from .routes import health_router, trigger_orders_router, users_router

if TYPE_CHECKING:
    from src.core.user_manager import UserManager
    from src.core.trigger_order_manager import TriggerOrderManager

logger = logging.getLogger('API')


def create_app(
    user_manager: 'UserManager',
    trigger_manager: 'TriggerOrderManager',
    title: str = "條件單交易 API",
    debug: bool = False
) -> FastAPI:
    """
    建立 FastAPI 應用

    Args:
        user_manager: 用戶管理器
        trigger_manager: 條件單管理器
        title: API 標題
        debug: 除錯模式

    Returns:
        FastAPI: FastAPI 應用實例
    """
    app = FastAPI(
        title=title,
        description="""
## 條件單交易 REST API

提供價格觸發條件單的管理功能，供 AI 自動化操作使用。

### 認證方式

使用 API Key 認證，在 HTTP Header 中加入：

```
X-API-Key: your_api_key_here
```

API Key 可透過 Telegram Bot 的 `/apikey` 指令取得。

### 主要功能

- 建立/查詢/更新/刪除條件單
- 查詢股票即時報價
- 用戶資訊管理
        """,
        version="1.0.0",
        docs_url="/docs" if debug else "/docs",
        redoc_url="/redoc" if debug else "/redoc",
        openapi_url="/openapi.json"
    )

    # 儲存管理器到 app.state
    app.state.user_manager = user_manager
    app.state.trigger_manager = trigger_manager

    # 加入 CORS 中介軟體
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生產環境應限制
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 加入 API Key 認證中介軟體
    app.add_middleware(
        APIKeyMiddleware,
        user_manager=user_manager,
        exclude_paths=[
            "/",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/v1/health",
            "/api/v1/health/ready"
        ]
    )

    # 註冊路由
    app.include_router(health_router)
    app.include_router(trigger_orders_router)
    app.include_router(users_router)

    @app.get("/", tags=["Root"])
    async def root():
        """API 根路徑"""
        return {
            "service": "trigger-order-api",
            "version": "1.0.0",
            "docs": "/docs",
            "health": "/api/v1/health"
        }

    @app.on_event("startup")
    async def startup_event():
        logger.info("API 服務啟動")

    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("API 服務關閉")

    return app
