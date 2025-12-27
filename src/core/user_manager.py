"""
用戶資料管理模組
管理多用戶的設定、券商帳號和多標的網格設定
"""

import os
import json
import logging
from configparser import ConfigParser
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger('UserManager')


class UserManager:
    """用戶資料管理器"""

    def __init__(self, base_dir='./users'):
        """
        初始化用戶管理器

        Args:
            base_dir: 用戶資料存放目錄
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_user_dir(self, chat_id) -> Path:
        """取得用戶目錄路徑"""
        return self.base_dir / str(chat_id)

    def _get_config_path(self, chat_id) -> Path:
        """取得用戶設定檔路徑"""
        return self._get_user_dir(chat_id) / 'config.json'

    def _get_brokers_dir(self, chat_id) -> Path:
        """取得用戶券商設定目錄"""
        return self._get_user_dir(chat_id) / 'brokers'

    def _get_grids_dir(self, chat_id) -> Path:
        """取得用戶網格設定目錄"""
        return self._get_user_dir(chat_id) / 'grids'

    def _get_credentials_dir(self, chat_id) -> Path:
        """取得用戶憑證目錄"""
        return self._get_user_dir(chat_id) / 'credentials'

    def _get_logs_dir(self, chat_id) -> Path:
        """取得用戶日誌目錄"""
        return self._get_user_dir(chat_id) / 'logs'

    # ========== 用戶基本操作 ==========

    def user_exists(self, chat_id) -> bool:
        """檢查用戶是否已註冊"""
        return self._get_config_path(chat_id).exists()

    def create_user(self, chat_id, username=None, first_name=None) -> Dict:
        """
        建立新用戶

        Args:
            chat_id: Telegram Chat ID
            username: Telegram 用戶名
            first_name: 用戶名字
        """
        user_dir = self._get_user_dir(chat_id)
        user_dir.mkdir(parents=True, exist_ok=True)

        # 建立子目錄
        self._get_brokers_dir(chat_id).mkdir(exist_ok=True)
        self._get_grids_dir(chat_id).mkdir(exist_ok=True)
        self._get_credentials_dir(chat_id).mkdir(exist_ok=True)
        self._get_logs_dir(chat_id).mkdir(exist_ok=True)

        # 初始用戶設定
        config = {
            'chat_id': str(chat_id),
            'username': username,
            'first_name': first_name,
            'created_at': datetime.now().isoformat(),
            'last_active': datetime.now().isoformat()
        }

        self._save_json(self._get_config_path(chat_id), config)
        logger.info(f"新用戶已建立: {chat_id}")
        return config

    def get_user_config(self, chat_id) -> Optional[Dict]:
        """取得用戶基本設定"""
        return self._load_json(self._get_config_path(chat_id))

    def update_user_config(self, chat_id, updates: Dict):
        """更新用戶基本設定"""
        config = self.get_user_config(chat_id)
        if config is None:
            raise ValueError(f"用戶不存在: {chat_id}")

        config.update(updates)
        config['last_active'] = datetime.now().isoformat()
        self._save_json(self._get_config_path(chat_id), config)

    def delete_user(self, chat_id) -> bool:
        """刪除用戶資料"""
        import shutil
        user_dir = self._get_user_dir(chat_id)
        if user_dir.exists():
            shutil.rmtree(user_dir)
            logger.info(f"用戶已刪除: {chat_id}")
            return True
        return False

    def get_all_users(self) -> List[Dict]:
        """取得所有用戶列表"""
        users = []
        for user_dir in self.base_dir.iterdir():
            if user_dir.is_dir() and not user_dir.name.startswith('.'):
                config = self.get_user_config(user_dir.name)
                if config:
                    users.append(config)
        return users

    # ========== PIN 碼與 API Key 操作 ==========

    def set_pin_code(self, chat_id, pin_code: str) -> bool:
        """
        設定用戶 PIN 碼

        Args:
            chat_id: Telegram Chat ID
            pin_code: PIN 碼 (4-6 位數字)

        Returns:
            bool: 是否設定成功
        """
        if not pin_code or not pin_code.isdigit() or len(pin_code) < 4 or len(pin_code) > 6:
            return False

        config = self.get_user_config(chat_id)
        if config is None:
            return False

        config['pin_code'] = pin_code
        config['pin_code_set_at'] = datetime.now().isoformat()
        self._save_json(self._get_config_path(chat_id), config)
        logger.info(f"用戶 {chat_id} 已設定 PIN 碼")
        return True

    def verify_pin_code(self, chat_id, pin_code: str) -> bool:
        """
        驗證用戶 PIN 碼

        Args:
            chat_id: Telegram Chat ID
            pin_code: 要驗證的 PIN 碼

        Returns:
            bool: 是否正確
        """
        config = self.get_user_config(chat_id)
        if config is None:
            return False

        stored_pin = config.get('pin_code')
        if not stored_pin:
            return False

        return stored_pin == pin_code

    def has_pin_code(self, chat_id) -> bool:
        """檢查用戶是否已設定 PIN 碼"""
        config = self.get_user_config(chat_id)
        return config is not None and bool(config.get('pin_code'))

    def generate_api_key(self, chat_id) -> str:
        """
        為用戶生成新的 API Key

        Args:
            chat_id: Telegram Chat ID

        Returns:
            str: 新的 API Key
        """
        import secrets

        config = self.get_user_config(chat_id)
        if config is None:
            raise ValueError(f"用戶不存在: {chat_id}")

        api_key = f"sk-{secrets.token_urlsafe(32)}"
        config['api_key'] = api_key
        config['api_key_created_at'] = datetime.now().isoformat()
        self._save_json(self._get_config_path(chat_id), config)

        logger.info(f"用戶 {chat_id} 已生成新的 API Key")
        return api_key

    def get_api_key(self, chat_id) -> Optional[str]:
        """取得用戶的 API Key"""
        config = self.get_user_config(chat_id)
        if config is None:
            return None
        return config.get('api_key')

    def get_user_by_api_key(self, api_key: str) -> Optional[str]:
        """
        透過 API Key 取得用戶 ID

        Args:
            api_key: API Key

        Returns:
            用戶的 chat_id 或 None
        """
        for user_dir in self.base_dir.iterdir():
            if not user_dir.is_dir() or user_dir.name.startswith('.'):
                continue

            config = self.get_user_config(user_dir.name)
            if config and config.get('api_key') == api_key:
                return user_dir.name

        return None

    def get_allowed_chat_ids(self, chat_id) -> List[str]:
        """
        取得用戶的授權 Chat ID 列表

        Args:
            chat_id: 主用戶的 Chat ID

        Returns:
            授權的 Chat ID 列表
        """
        config = self.get_user_config(chat_id)
        if config is None:
            return []
        return config.get('allowed_chat_ids', [])

    def set_allowed_chat_ids(self, chat_id, allowed_ids: List[str]) -> bool:
        """
        設定用戶的授權 Chat ID 列表

        Args:
            chat_id: 主用戶的 Chat ID
            allowed_ids: 授權的 Chat ID 列表

        Returns:
            bool: 是否設定成功
        """
        config = self.get_user_config(chat_id)
        if config is None:
            return False

        config['allowed_chat_ids'] = allowed_ids
        config['allowed_chat_ids_updated_at'] = datetime.now().isoformat()
        self._save_json(self._get_config_path(chat_id), config)
        logger.info(f"用戶 {chat_id} 已更新授權 Chat ID 列表")
        return True

    def is_chat_id_allowed(self, owner_chat_id, check_chat_id) -> bool:
        """
        檢查 Chat ID 是否被授權

        Args:
            owner_chat_id: 主用戶的 Chat ID
            check_chat_id: 要檢查的 Chat ID

        Returns:
            bool: 是否被授權
        """
        # 主用戶永遠被授權
        if str(owner_chat_id) == str(check_chat_id):
            return True

        allowed_ids = self.get_allowed_chat_ids(owner_chat_id)
        return str(check_chat_id) in allowed_ids

    # ========== 券商設定操作 ==========

    def get_broker_config(self, chat_id, broker_name: str) -> Optional[Dict]:
        """
        取得特定券商設定

        Args:
            chat_id: Telegram Chat ID
            broker_name: 券商名稱 (esun, yuanta, fugle...)
        """
        broker_path = self._get_brokers_dir(chat_id) / f'{broker_name}.json'
        return self._load_json(broker_path)

    def save_broker_config(self, chat_id, broker_name: str, config: Dict):
        """
        儲存券商設定

        Args:
            chat_id: Telegram Chat ID
            broker_name: 券商名稱
            config: 券商設定 (api_key, api_secret, cert_path 等)
        """
        broker_path = self._get_brokers_dir(chat_id) / f'{broker_name}.json'
        config['broker_name'] = broker_name
        config['updated_at'] = datetime.now().isoformat()
        self._save_json(broker_path, config)
        logger.info(f"券商設定已儲存: {chat_id}/{broker_name}")

    def delete_broker_config(self, chat_id, broker_name: str) -> bool:
        """刪除券商設定"""
        broker_path = self._get_brokers_dir(chat_id) / f'{broker_name}.json'
        if broker_path.exists():
            broker_path.unlink()
            logger.info(f"券商設定已刪除: {chat_id}/{broker_name}")
            return True
        return False

    def get_all_broker_configs(self, chat_id) -> List[Dict]:
        """取得用戶所有券商設定"""
        brokers = []
        brokers_dir = self._get_brokers_dir(chat_id)
        if brokers_dir.exists():
            # 讀取 .ini 檔案
            for broker_file in brokers_dir.glob('*.ini'):
                config = self._load_ini_config(broker_file)
                if config:
                    config['broker_name'] = broker_file.stem  # esun.ini -> esun
                    brokers.append(config)
        return brokers

    def get_broker_names(self, chat_id) -> List[str]:
        """取得用戶已設定的券商名稱列表"""
        brokers_dir = self._get_brokers_dir(chat_id)
        if not brokers_dir.exists():
            return []
        return [f.stem for f in brokers_dir.glob('*.ini')]

    # ========== 網格設定操作 ==========

    def get_grid_config(self, chat_id, symbol: str) -> Optional[Dict]:
        """
        取得特定標的的網格設定

        Args:
            chat_id: Telegram Chat ID
            symbol: 股票代號
        """
        grid_path = self._get_grids_dir(chat_id) / f'{symbol}.json'
        return self._load_json(grid_path)

    def save_grid_config(self, chat_id, symbol: str, config: Dict):
        """
        儲存標的網格設定

        Args:
            chat_id: Telegram Chat ID
            symbol: 股票代號
            config: 網格設定
                - broker: 使用的券商
                - lower_price: 價格下限
                - upper_price: 價格上限
                - grid_num: 網格數量
                - quantity_per_grid: 每格張數
                - stop_loss_price: 停損價 (可選)
                - take_profit_price: 停利價 (可選)
                - max_capital: 最大本金 (可選)
        """
        grid_path = self._get_grids_dir(chat_id) / f'{symbol}.json'

        # 確保基本欄位
        config['symbol'] = symbol
        config['updated_at'] = datetime.now().isoformat()
        if 'created_at' not in config:
            config['created_at'] = datetime.now().isoformat()
        if 'is_running' not in config:
            config['is_running'] = False

        self._save_json(grid_path, config)
        logger.info(f"網格設定已儲存: {chat_id}/{symbol}")

    def delete_grid_config(self, chat_id, symbol: str) -> bool:
        """刪除標的網格設定"""
        grid_path = self._get_grids_dir(chat_id) / f'{symbol}.json'
        if grid_path.exists():
            grid_path.unlink()
            logger.info(f"網格設定已刪除: {chat_id}/{symbol}")
            return True
        return False

    def get_all_grid_configs(self, chat_id) -> List[Dict]:
        """取得用戶所有標的的網格設定"""
        grids = []
        grids_dir = self._get_grids_dir(chat_id)
        if grids_dir.exists():
            for grid_file in grids_dir.glob('*.json'):
                config = self._load_json(grid_file)
                if config:
                    grids.append(config)
        return grids

    def get_grid_symbols(self, chat_id) -> List[str]:
        """取得用戶已設定的標的代號列表"""
        grids_dir = self._get_grids_dir(chat_id)
        if not grids_dir.exists():
            return []
        return [f.stem for f in grids_dir.glob('*.json')]

    def set_grid_running_status(self, chat_id, symbol: str, is_running: bool):
        """設定標的的運行狀態"""
        config = self.get_grid_config(chat_id, symbol)
        if config:
            config['is_running'] = is_running
            config['last_status_change'] = datetime.now().isoformat()
            self.save_grid_config(chat_id, symbol, config)

    def get_running_grids(self, chat_id) -> List[Dict]:
        """取得用戶所有運行中的網格"""
        return [g for g in self.get_all_grid_configs(chat_id) if g.get('is_running')]

    def get_all_running_grids(self) -> List[Dict]:
        """取得所有用戶所有運行中的網格 (含 chat_id)"""
        running = []
        for user in self.get_all_users():
            chat_id = user['chat_id']
            for grid in self.get_running_grids(chat_id):
                grid['chat_id'] = chat_id
                running.append(grid)
        return running

    # ========== 憑證檔案操作 ==========

    def save_credential_file(self, chat_id, broker_name: str, filename: str, content: bytes) -> str:
        """
        儲存憑證檔案

        Args:
            chat_id: Telegram Chat ID
            broker_name: 券商名稱
            filename: 檔案名稱
            content: 檔案內容 (bytes)

        Returns:
            str: 檔案路徑
        """
        # 在憑證目錄下建立券商子目錄
        cred_dir = self._get_credentials_dir(chat_id) / broker_name
        cred_dir.mkdir(parents=True, exist_ok=True)

        file_path = cred_dir / filename
        with open(file_path, 'wb') as f:
            f.write(content)

        logger.info(f"憑證檔案已儲存: {chat_id}/{broker_name}/{filename}")
        return str(file_path)

    def get_credential_path(self, chat_id, broker_name: str, filename: str) -> Optional[str]:
        """取得憑證檔案路徑"""
        file_path = self._get_credentials_dir(chat_id) / broker_name / filename
        if file_path.exists():
            return str(file_path)
        return None

    def get_logs_dir(self, chat_id) -> Path:
        """取得用戶日誌目錄"""
        return self._get_logs_dir(chat_id)

    # ========== 設定檔解析 ==========

    def parse_broker_config_file(self, content: str, broker_name: str) -> Dict:
        """
        解析券商設定檔內容 (.ini 格式)

        Args:
            content: .ini 檔案內容 (字串)
            broker_name: 券商名稱

        Returns:
            Dict: 解析後的設定
        """
        config = ConfigParser()
        config.read_string(content)

        result = {}

        # 解析玉山證券設定
        if broker_name == 'esun':
            if config.has_section('Esun'):
                section = 'Esun'
            elif config.has_section('esun'):
                section = 'esun'
            else:
                raise ValueError("設定檔缺少 [Esun] 區段")

            # 必要欄位
            required_fields = ['PersonId', 'Account', 'CertPath', 'CertPassword', 'Env']
            for field in required_fields:
                if not config.has_option(section, field):
                    raise ValueError(f"設定檔缺少 {field} 欄位")

            result = {
                'person_id': config.get(section, 'PersonId'),
                'account': config.get(section, 'Account'),
                'cert_path': config.get(section, 'CertPath'),
                'cert_password': config.get(section, 'CertPassword'),
                'env': config.get(section, 'Env'),
            }

            # 可選欄位
            if config.has_option(section, 'BrokerId'):
                result['broker_id'] = config.get(section, 'BrokerId')
            else:
                result['broker_id'] = '6460'  # 玉山預設

        else:
            # 其他券商 - 一般性解析
            for section in config.sections():
                for key, value in config.items(section):
                    result[key] = value

        return result

    def save_broker_from_config_file(
        self,
        chat_id,
        broker_name: str,
        config_content: str,
        cert_content: bytes = None,
        cert_filename: str = None
    ) -> Dict:
        """
        從設定檔內容儲存券商設定

        Args:
            chat_id: Telegram Chat ID
            broker_name: 券商名稱
            config_content: .ini 設定檔內容
            cert_content: 憑證檔案內容 (bytes)
            cert_filename: 憑證檔案名稱

        Returns:
            Dict: 儲存的設定
        """
        # 解析設定檔以驗證格式
        config = self.parse_broker_config_file(config_content, broker_name)

        # 如果有憑證檔案，儲存憑證
        if cert_content and cert_filename:
            cert_path = self.save_credential_file(
                chat_id, broker_name, cert_filename, cert_content
            )
            # 更新 config_content 中的 CertPath
            config['cert_path'] = cert_path

        # 儲存 .ini 檔案
        self._save_broker_ini(chat_id, broker_name, config_content, config.get('cert_path'))

        return config

    def _save_broker_ini(self, chat_id, broker_name: str, config_content: str, cert_path: str = None):
        """儲存券商 .ini 設定檔"""
        brokers_dir = self._get_brokers_dir(chat_id)
        brokers_dir.mkdir(parents=True, exist_ok=True)

        ini_path = brokers_dir / f'{broker_name}.ini'

        # 如果有新的憑證路徑，更新 config_content
        if cert_path:
            config = ConfigParser()
            config.read_string(config_content)

            # 找到正確的 section
            section = None
            for s in config.sections():
                if s.lower() == broker_name.lower() or s.lower() == 'esun':
                    section = s
                    break

            if section and config.has_option(section, 'CertPath'):
                config.set(section, 'CertPath', cert_path)

            # 寫入檔案
            with open(ini_path, 'w', encoding='utf-8') as f:
                config.write(f)
        else:
            # 直接儲存原始內容
            with open(ini_path, 'w', encoding='utf-8') as f:
                f.write(config_content)

        logger.info(f"券商設定已儲存: {chat_id}/{broker_name}.ini")

    # ========== 工具方法 ==========

    def _load_ini_config(self, path: Path) -> Optional[Dict]:
        """讀取 .ini 設定檔"""
        if not path.exists():
            return None
        try:
            config = ConfigParser()
            config.read(path, encoding='utf-8')

            result = {}
            broker_name = path.stem  # esun.ini -> esun

            if broker_name == 'esun':
                # 玉山證券 - 支援兩種格式
                if config.has_section('Esun') or config.has_section('esun'):
                    # 新格式: [Esun] section
                    section = 'Esun' if config.has_section('Esun') else 'esun'
                    result = {
                        'person_id': config.get(section, 'PersonId', fallback=''),
                        'account': config.get(section, 'Account', fallback=''),
                        'cert_path': config.get(section, 'CertPath', fallback=''),
                        'cert_password': config.get(section, 'CertPassword', fallback=''),
                        'env': config.get(section, 'Env', fallback=''),
                        'broker_id': config.get(section, 'BrokerId', fallback='6460'),
                    }
                elif config.has_section('Core'):
                    # 舊格式: [Core], [Cert], [Api], [User] sections
                    env_map = {'SIMULATION': 'simulation', 'PRODUCTION': 'production'}
                    raw_env = config.get('Core', 'Environment', fallback='')
                    result = {
                        'entry': config.get('Core', 'Entry', fallback=''),
                        'env': env_map.get(raw_env, raw_env.lower()),
                        'cert_path': config.get('Cert', 'Path', fallback=''),
                        'api_key': config.get('Api', 'Key', fallback=''),
                        'api_secret': config.get('Api', 'Secret', fallback=''),
                        'account': config.get('User', 'Account', fallback=''),
                    }
            else:
                # 其他券商 - 一般性解析
                for section in config.sections():
                    for key, value in config.items(section):
                        result[key] = value

            return result
        except Exception as e:
            logger.error(f"讀取 INI 失敗 {path}: {e}")
            return None

    def _load_json(self, path: Path) -> Optional[Dict]:
        """讀取 JSON 檔案"""
        if not path.exists():
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"讀取 JSON 失敗 {path}: {e}")
            return None

    def _save_json(self, path: Path, data: Dict):
        """儲存 JSON 檔案"""
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"儲存 JSON 失敗 {path}: {e}")
            raise


# ========== 用戶設定狀態 (用於互動式設定流程) ==========

class UserSetupState:
    """用戶設定狀態追蹤"""

    IDLE = 'idle'

    # 券商設定流程
    WAITING_BROKER_SELECT = 'waiting_broker_select'
    WAITING_CONFIG_FILE = 'waiting_config_file'  # 等待上傳設定檔 (.ini)
    WAITING_CERT_FILE = 'waiting_cert_file'      # 等待上傳憑證檔 (.p12)
    WAITING_API_KEY = 'waiting_api_key'
    WAITING_API_SECRET = 'waiting_api_secret'
    WAITING_CERT_PASSWORD = 'waiting_cert_password'
    WAITING_ACCOUNT_ID = 'waiting_account_id'

    # 網格設定流程
    WAITING_GRID_SYMBOL = 'waiting_grid_symbol'
    WAITING_GRID_BROKER = 'waiting_grid_broker'  # 選擇要用哪個券商
    WAITING_LOWER_PRICE = 'waiting_lower_price'
    WAITING_UPPER_PRICE = 'waiting_upper_price'
    WAITING_GRID_NUM = 'waiting_grid_num'
    WAITING_QUANTITY = 'waiting_quantity'
    WAITING_STOP_LOSS = 'waiting_stop_loss'
    WAITING_TAKE_PROFIT = 'waiting_take_profit'
    WAITING_GRID_CONFIRM = 'waiting_grid_confirm'

    # 操作確認
    WAITING_DELETE_CONFIRM = 'waiting_delete_confirm'

    # 股價查詢
    WAITING_QUOTE_SYMBOL = 'waiting_quote_symbol'


class UserStateManager:
    """用戶互動狀態管理"""

    def __init__(self):
        self._states = {}  # chat_id -> state
        self._temp_data = {}  # chat_id -> temp data during setup

    def get_state(self, chat_id) -> str:
        """取得用戶當前狀態"""
        return self._states.get(str(chat_id), UserSetupState.IDLE)

    def set_state(self, chat_id, state: str):
        """設定用戶狀態"""
        self._states[str(chat_id)] = state

    def clear_state(self, chat_id):
        """清除用戶狀態"""
        chat_id = str(chat_id)
        self._states.pop(chat_id, None)
        self._temp_data.pop(chat_id, None)

    def get_temp_data(self, chat_id) -> Dict:
        """取得暫存資料"""
        return self._temp_data.get(str(chat_id), {})

    def set_temp_data(self, chat_id, key: str, value):
        """設定暫存資料"""
        chat_id = str(chat_id)
        if chat_id not in self._temp_data:
            self._temp_data[chat_id] = {}
        self._temp_data[chat_id][key] = value

    def update_temp_data(self, chat_id, data: Dict):
        """批次更新暫存資料"""
        chat_id = str(chat_id)
        if chat_id not in self._temp_data:
            self._temp_data[chat_id] = {}
        self._temp_data[chat_id].update(data)

    def clear_temp_data(self, chat_id):
        """清除暫存資料"""
        self._temp_data.pop(str(chat_id), None)
