from __future__ import annotations

import logging
from typing import Dict, Type

from .service_base import BaseService
from .services.hitokoto import HitokotoService
from .services.poetry import PoetryService
from .services.weather import WeatherService
from .services.oil import OilService
from .services.history import HistoryService
from .services.istoreos import IStoreOSService

_LOGGER = logging.getLogger(__name__)

DOMAIN = "myraid_box"
DEVICE_MANUFACTURER = "万象盒子"
DEVICE_MODEL = "多数据聚合"
VERSION = "2.1.0"

CARD_NAME = "myraid_box_card"
CARD_VERSION = "1.0.0"

# API 端点
API_ENDPOINT = "/api/myraid_box/data"

# 显式声明所有服务 —— 新增服务时在此处添加即可
SERVICE_CLASSES: list[Type[BaseService]] = [
    HitokotoService,
    PoetryService,
    WeatherService,
    OilService,
    HistoryService,
    IStoreOSService,
]

SERVICE_REGISTRY: Dict[str, Type[BaseService]] = {}


def register_service(service_class: Type[BaseService]) -> None:
    """注册服务到全局注册表（幂等）"""
    try:
        instance = service_class()
        service_id = instance.service_id
    except Exception as e:  # pragma: no cover - 防御性
        _LOGGER.error("注册服务 %s 失败: %s", service_class.__name__, e)
        return

    if SERVICE_REGISTRY.get(service_id) is service_class:
        return

    if service_id in SERVICE_REGISTRY:
        _LOGGER.warning("服务 ID %s 已存在，将被 %s 覆盖", service_id, service_class.__name__)

    SERVICE_REGISTRY[service_id] = service_class
    _LOGGER.debug("已注册服务: %s (%s)", instance.name, service_id)


def init_services() -> None:
    """初始化服务注册表。同步、幂等。

    HA 2024.6+ 推荐在集成 import 阶段完成注册，
    避免使用运行时 importlib 扫描带来的不确定性与开销。
    """
    for cls in SERVICE_CLASSES:
        register_service(cls)


def discover_services(_hass=None, _services_dir: str = "") -> None:
    """保留原接口以兼容旧调用点；现在退化为 init_services()。

    历史版本通过 importlib 扫描 services/ 目录动态注册，
    现改为显式列表（SERVICE_CLASSES）。
    """
    init_services()
