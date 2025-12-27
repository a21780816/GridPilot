"""
儲存後端抽象基類
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from src.models.trigger_order import TriggerOrder
from src.models.enums import TriggerStatus
from src.models.order_log import OrderLog


class StorageBackend(ABC):
    """儲存後端抽象基類"""

    # ========== TriggerOrder 操作 ==========

    @abstractmethod
    def save_trigger_order(self, trigger: TriggerOrder) -> None:
        """
        儲存條件單

        Args:
            trigger: 條件單物件
        """
        pass

    @abstractmethod
    def get_trigger_order(self, trigger_id: str) -> Optional[TriggerOrder]:
        """
        取得條件單

        Args:
            trigger_id: 條件單 ID

        Returns:
            TriggerOrder 或 None
        """
        pass

    @abstractmethod
    def get_user_triggers(self,
                          user_id: str,
                          status: Optional[TriggerStatus] = None) -> List[TriggerOrder]:
        """
        取得用戶的條件單列表

        Args:
            user_id: 用戶 ID (chat_id)
            status: 篩選狀態 (可選)

        Returns:
            條件單列表
        """
        pass

    @abstractmethod
    def get_triggers_by_status(self, status: TriggerStatus) -> List[TriggerOrder]:
        """
        取得指定狀態的所有條件單

        Args:
            status: 條件單狀態

        Returns:
            條件單列表
        """
        pass

    @abstractmethod
    def delete_trigger_order(self, trigger_id: str) -> bool:
        """
        刪除條件單

        Args:
            trigger_id: 條件單 ID

        Returns:
            是否刪除成功
        """
        pass

    def get_all_active_triggers(self) -> List[TriggerOrder]:
        """
        取得所有活躍的條件單

        Returns:
            活躍狀態的條件單列表
        """
        return self.get_triggers_by_status(TriggerStatus.ACTIVE)

    # ========== OrderLog 操作 ==========

    @abstractmethod
    def save_order_log(self, log: OrderLog) -> None:
        """
        儲存執行紀錄

        Args:
            log: 執行紀錄物件
        """
        pass

    @abstractmethod
    def get_trigger_logs(self, trigger_id: str) -> List[OrderLog]:
        """
        取得條件單的執行紀錄

        Args:
            trigger_id: 條件單 ID

        Returns:
            執行紀錄列表
        """
        pass

    @abstractmethod
    def get_user_logs(self,
                      user_id: str,
                      limit: int = 100) -> List[OrderLog]:
        """
        取得用戶的執行紀錄

        Args:
            user_id: 用戶 ID
            limit: 最大筆數

        Returns:
            執行紀錄列表
        """
        pass

    # ========== 用戶 API Key 操作 ==========

    @abstractmethod
    def get_user_by_api_key(self, api_key: str) -> Optional[str]:
        """
        透過 API Key 取得用戶 ID

        Args:
            api_key: API Key

        Returns:
            用戶 ID (chat_id) 或 None
        """
        pass

    @abstractmethod
    def save_user_api_key(self, user_id: str, api_key: str) -> None:
        """
        儲存用戶的 API Key

        Args:
            user_id: 用戶 ID
            api_key: API Key
        """
        pass
