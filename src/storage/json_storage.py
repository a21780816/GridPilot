"""
JSON 檔案儲存實作
儲存於 users/{chat_id}/triggers/*.json

使用 filelock 確保檔案操作的原子性，避免競態條件
"""

import json
import logging
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from filelock import FileLock, Timeout

from .base import StorageBackend
from src.models.trigger_order import TriggerOrder
from src.models.enums import TriggerStatus
from src.models.order_log import OrderLog

logger = logging.getLogger('JsonStorage')

# 檔案鎖超時時間 (秒)
LOCK_TIMEOUT = 10


class JsonStorage(StorageBackend):
    """JSON 檔案儲存實作"""

    def __init__(self, base_dir: str = './users'):
        """
        初始化 JSON 儲存

        Args:
            base_dir: 用戶資料根目錄
        """
        self.base_dir = Path(base_dir)
        self._api_key_cache: dict = {}  # api_key -> user_id 快取
        self._cache_loaded = False
        # 確保鎖定檔案目錄存在
        self._locks_dir = self.base_dir / '.locks'
        self._locks_dir.mkdir(parents=True, exist_ok=True)
        # 條件單索引快取 (trigger_id -> user_id)
        self._trigger_index: dict = {}
        self._trigger_index_loaded = False

    def _get_lock(self, file_path: Path) -> FileLock:
        """取得檔案對應的鎖定物件"""
        # 使用相對路徑作為鎖定檔案名稱，避免路徑過長
        lock_name = str(file_path.relative_to(self.base_dir)).replace('/', '_').replace('\\', '_')
        lock_path = self._locks_dir / f'{lock_name}.lock'
        return FileLock(lock_path, timeout=LOCK_TIMEOUT)

    def _get_triggers_dir(self, user_id: str) -> Path:
        """取得用戶條件單目錄"""
        triggers_dir = self.base_dir / str(user_id) / 'triggers'
        triggers_dir.mkdir(parents=True, exist_ok=True)
        return triggers_dir

    def _get_logs_dir(self, user_id: str) -> Path:
        """取得用戶執行紀錄目錄"""
        logs_dir = self.base_dir / str(user_id) / 'trigger_logs'
        logs_dir.mkdir(parents=True, exist_ok=True)
        return logs_dir

    def _get_trigger_path(self, user_id: str, trigger_id: str) -> Path:
        """取得條件單檔案路徑"""
        return self._get_triggers_dir(user_id) / f'{trigger_id}.json'

    def _get_user_config_path(self, user_id: str) -> Path:
        """取得用戶設定檔路徑"""
        return self.base_dir / str(user_id) / 'config.json'

    # ========== TriggerOrder 操作 ==========

    def _load_trigger_index(self) -> None:
        """載入條件單索引 (trigger_id -> user_id)"""
        if self._trigger_index_loaded:
            return

        if not self.base_dir.exists():
            self._trigger_index_loaded = True
            return

        for user_dir in self.base_dir.iterdir():
            if not user_dir.is_dir() or user_dir.name.startswith('.'):
                continue

            triggers_dir = user_dir / 'triggers'
            if triggers_dir.exists():
                for trigger_file in triggers_dir.glob('*.json'):
                    trigger_id = trigger_file.stem
                    self._trigger_index[trigger_id] = user_dir.name

        self._trigger_index_loaded = True
        logger.debug(f"已載入 {len(self._trigger_index)} 個條件單索引")

    def save_trigger_order(self, trigger: TriggerOrder) -> None:
        """儲存條件單 (使用檔案鎖定確保原子性)"""
        file_path = self._get_trigger_path(trigger.user_id, trigger.id)
        lock = self._get_lock(file_path)

        try:
            with lock:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(trigger.to_dict(), f, ensure_ascii=False, indent=2)
            # 更新索引快取
            self._trigger_index[trigger.id] = trigger.user_id
            logger.debug(f"條件單已儲存: {trigger.id}")
        except Timeout:
            logger.error(f"儲存條件單超時 {trigger.id}: 無法取得檔案鎖定")
            raise
        except Exception as e:
            logger.error(f"儲存條件單失敗 {trigger.id}: {e}")
            raise

    def get_trigger_order(self, trigger_id: str) -> Optional[TriggerOrder]:
        """取得條件單 (使用索引快取加速查找)"""
        # 先嘗試從索引查找
        self._load_trigger_index()

        if trigger_id in self._trigger_index:
            user_id = self._trigger_index[trigger_id]
            trigger_path = self._get_trigger_path(user_id, trigger_id)
            if trigger_path.exists():
                try:
                    with open(trigger_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        return TriggerOrder.from_dict(data)
                except Exception as e:
                    logger.error(f"讀取條件單失敗 {trigger_path}: {e}")
                    # 索引可能已過期，移除
                    del self._trigger_index[trigger_id]

        # 索引找不到，回退到遍歷方式
        for user_dir in self.base_dir.iterdir():
            if not user_dir.is_dir() or user_dir.name.startswith('.'):
                continue

            trigger_path = user_dir / 'triggers' / f'{trigger_id}.json'
            if trigger_path.exists():
                try:
                    with open(trigger_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        # 更新索引
                        self._trigger_index[trigger_id] = user_dir.name
                        return TriggerOrder.from_dict(data)
                except Exception as e:
                    logger.error(f"讀取條件單失敗 {trigger_path}: {e}")

        return None

    def get_user_triggers(self,
                          user_id: str,
                          status: Optional[TriggerStatus] = None) -> List[TriggerOrder]:
        """取得用戶的條件單列表"""
        triggers_dir = self._get_triggers_dir(user_id)
        triggers = []

        for file_path in triggers_dir.glob('*.json'):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    trigger = TriggerOrder.from_dict(data)

                    if status is None or trigger.status == status:
                        triggers.append(trigger)
            except Exception as e:
                logger.warning(f"讀取條件單失敗 {file_path}: {e}")

        # 按建立時間排序 (新的在前)
        triggers.sort(key=lambda t: t.created_at, reverse=True)
        return triggers

    def get_triggers_by_status(self, status: TriggerStatus) -> List[TriggerOrder]:
        """取得所有指定狀態的條件單"""
        all_triggers = []

        if not self.base_dir.exists():
            return all_triggers

        for user_dir in self.base_dir.iterdir():
            if not user_dir.is_dir() or user_dir.name.startswith('.'):
                continue

            triggers = self.get_user_triggers(user_dir.name, status)
            all_triggers.extend(triggers)

        return all_triggers

    def delete_trigger_order(self, trigger_id: str) -> bool:
        """刪除條件單 (使用索引加速查找)"""
        # 先嘗試從索引查找
        self._load_trigger_index()

        if trigger_id in self._trigger_index:
            user_id = self._trigger_index[trigger_id]
            trigger_path = self._get_trigger_path(user_id, trigger_id)
            if trigger_path.exists():
                try:
                    trigger_path.unlink()
                    del self._trigger_index[trigger_id]
                    logger.info(f"條件單已刪除: {trigger_id}")
                    return True
                except Exception as e:
                    logger.error(f"刪除條件單失敗 {trigger_id}: {e}")
                    return False

        # 索引找不到，回退到遍歷方式
        for user_dir in self.base_dir.iterdir():
            if not user_dir.is_dir() or user_dir.name.startswith('.'):
                continue

            trigger_path = user_dir / 'triggers' / f'{trigger_id}.json'
            if trigger_path.exists():
                try:
                    trigger_path.unlink()
                    # 從索引移除 (如果存在)
                    self._trigger_index.pop(trigger_id, None)
                    logger.info(f"條件單已刪除: {trigger_id}")
                    return True
                except Exception as e:
                    logger.error(f"刪除條件單失敗 {trigger_id}: {e}")
                    return False

        return False

    # ========== OrderLog 操作 ==========

    def save_order_log(self, log: OrderLog) -> None:
        """儲存執行紀錄 (使用 JSONL 格式，檔案鎖定確保原子性)"""
        logs_dir = self._get_logs_dir(log.user_id)
        file_path = logs_dir / f'{log.trigger_order_id}.jsonl'
        lock = self._get_lock(file_path)

        try:
            with lock:
                with open(file_path, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(log.to_dict(), ensure_ascii=False) + '\n')
            logger.debug(f"執行紀錄已儲存: {log.id}")
        except Timeout:
            logger.error(f"儲存執行紀錄超時: 無法取得檔案鎖定")
        except Exception as e:
            logger.error(f"儲存執行紀錄失敗: {e}")

    def get_trigger_logs(self, trigger_id: str) -> List[OrderLog]:
        """取得條件單的執行紀錄"""
        logs = []

        for user_dir in self.base_dir.iterdir():
            if not user_dir.is_dir() or user_dir.name.startswith('.'):
                continue

            log_path = user_dir / 'trigger_logs' / f'{trigger_id}.jsonl'
            if log_path.exists():
                try:
                    with open(log_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            if line.strip():
                                data = json.loads(line)
                                logs.append(OrderLog.from_dict(data))
                except Exception as e:
                    logger.warning(f"讀取執行紀錄失敗 {log_path}: {e}")

        # 按時間排序 (新的在前)
        logs.sort(key=lambda l: l.created_at, reverse=True)
        return logs

    def get_user_logs(self,
                      user_id: str,
                      limit: int = 100) -> List[OrderLog]:
        """取得用戶的所有執行紀錄"""
        logs = []
        logs_dir = self._get_logs_dir(user_id)

        for log_path in logs_dir.glob('*.jsonl'):
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            logs.append(OrderLog.from_dict(data))
            except Exception as e:
                logger.warning(f"讀取執行紀錄失敗 {log_path}: {e}")

        # 按時間排序並限制筆數
        logs.sort(key=lambda l: l.created_at, reverse=True)
        return logs[:limit]

    # ========== 用戶 API Key 操作 ==========

    def _load_api_key_cache(self) -> None:
        """載入所有用戶的 API Key 到快取"""
        if self._cache_loaded:
            return

        if not self.base_dir.exists():
            self._cache_loaded = True
            return

        for user_dir in self.base_dir.iterdir():
            if not user_dir.is_dir() or user_dir.name.startswith('.'):
                continue

            config_path = user_dir / 'config.json'
            if config_path.exists():
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                        api_key = config.get('api_key')
                        if api_key:
                            self._api_key_cache[api_key] = user_dir.name
                except Exception as e:
                    logger.warning(f"讀取用戶設定失敗 {config_path}: {e}")

        self._cache_loaded = True
        logger.debug(f"已載入 {len(self._api_key_cache)} 個 API Key")

    def get_user_by_api_key(self, api_key: str) -> Optional[str]:
        """透過 API Key 取得用戶 ID"""
        self._load_api_key_cache()
        return self._api_key_cache.get(api_key)

    def save_user_api_key(self, user_id: str, api_key: str) -> None:
        """儲存用戶的 API Key (使用檔案鎖定確保原子性)"""
        config_path = self._get_user_config_path(user_id)
        lock = self._get_lock(config_path)

        try:
            with lock:
                # 讀取現有設定
                config = {}
                if config_path.exists():
                    try:
                        with open(config_path, 'r', encoding='utf-8') as f:
                            config = json.load(f)
                    except Exception:
                        pass

                # 更新 API Key
                old_api_key = config.get('api_key')
                config['api_key'] = api_key
                config['api_key_updated_at'] = datetime.now().isoformat()

                # 儲存
                config_path.parent.mkdir(parents=True, exist_ok=True)
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, ensure_ascii=False, indent=2)

            # 更新快取 (在鎖定外更新，避免持有鎖定過久)
            if old_api_key and old_api_key in self._api_key_cache:
                del self._api_key_cache[old_api_key]
            self._api_key_cache[api_key] = user_id

            logger.info(f"用戶 {user_id} 的 API Key 已更新")
        except Timeout:
            logger.error(f"儲存 API Key 超時: 無法取得檔案鎖定")
            raise

    # ========== 輔助方法 ==========

    def get_user_config(self, user_id: str) -> dict:
        """取得用戶設定"""
        config_path = self._get_user_config_path(user_id)

        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"讀取用戶設定失敗 {config_path}: {e}")

        return {}

    def save_user_config(self, user_id: str, config: dict) -> None:
        """儲存用戶設定 (使用檔案鎖定確保原子性)"""
        config_path = self._get_user_config_path(user_id)
        lock = self._get_lock(config_path)

        try:
            with lock:
                config_path.parent.mkdir(parents=True, exist_ok=True)
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, ensure_ascii=False, indent=2)
        except Timeout:
            logger.error(f"儲存用戶設定超時: 無法取得檔案鎖定")
            raise

    def get_stats(self) -> dict:
        """取得儲存統計資訊"""
        stats = {
            'total_users': 0,
            'total_triggers': 0,
            'active_triggers': 0,
            'total_logs': 0
        }

        if not self.base_dir.exists():
            return stats

        for user_dir in self.base_dir.iterdir():
            if not user_dir.is_dir() or user_dir.name.startswith('.'):
                continue

            stats['total_users'] += 1

            triggers_dir = user_dir / 'triggers'
            if triggers_dir.exists():
                for trigger_file in triggers_dir.glob('*.json'):
                    stats['total_triggers'] += 1
                    try:
                        with open(trigger_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            if data.get('status') == 'active':
                                stats['active_triggers'] += 1
                    except Exception:
                        pass

            logs_dir = user_dir / 'trigger_logs'
            if logs_dir.exists():
                for log_file in logs_dir.glob('*.jsonl'):
                    try:
                        with open(log_file, 'r', encoding='utf-8') as f:
                            stats['total_logs'] += sum(1 for _ in f)
                    except Exception:
                        pass

        return stats
