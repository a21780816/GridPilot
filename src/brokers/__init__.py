"""
券商介面模組
支援多家券商的抽象介面
"""

from .base import BaseBroker
from .esun import EsunBroker

# 支援的券商清單
SUPPORTED_BROKERS = {
    'esun': {
        'name': '玉山富果',
        'class': EsunBroker,
        'description': '玉山證券富果交易 API'
    },
    # 未來可擴充其他券商
    # 'fugle': {
    #     'name': '富果',
    #     'class': FugleBroker,
    #     'description': '富果交易 API'
    # },
    # 'sinopac': {
    #     'name': '永豐',
    #     'class': SinopacBroker,
    #     'description': '永豐證券 Shioaji API'
    # },
}


def get_broker(broker_type, config):
    """
    取得券商實例

    Args:
        broker_type: 券商類型 (esun, fugle, sinopac...)
        config: 券商設定

    Returns:
        BaseBroker: 券商實例
    """
    if broker_type not in SUPPORTED_BROKERS:
        raise ValueError(f"不支援的券商: {broker_type}")

    broker_class = SUPPORTED_BROKERS[broker_type]['class']
    return broker_class(config)


def get_broker_list():
    """取得支援的券商清單"""
    return {k: v['name'] for k, v in SUPPORTED_BROKERS.items()}
