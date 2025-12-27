"""
API 路由
"""

from .health import router as health_router
from .trigger_orders import router as trigger_orders_router
from .users import router as users_router

__all__ = [
    'health_router',
    'trigger_orders_router',
    'users_router',
]
