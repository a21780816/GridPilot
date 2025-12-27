"""
持久化儲存套件
"""

from .base import StorageBackend
from .json_storage import JsonStorage

__all__ = [
    'StorageBackend',
    'JsonStorage',
]
