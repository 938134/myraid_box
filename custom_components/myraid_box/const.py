from typing import Dict, Type, List, Any
import importlib
from pathlib import Path
import logging
from .service_base import BaseService

_LOGGER = logging.getLogger(__name__)

# 基础常量
DOMAIN = "myraid_box"
DEVICE_MANUFACTURER = "万象盒子"
DEVICE_MODEL = "多数据聚合"

# 服务注册表
SERVICE_REGISTRY: Dict[str, Type[BaseService]] = {}

def discover_services(services_dir: str) -> None:
    """自动发现并注册服务"""
    services_path = Path(services_dir)
    for module_file in services_path.glob("*.py"):
        if module_file.name.startswith(("_", "base")) or not module_file.is_file():
            continue
        
        module_name = module_file.stem
        try:
            module = importlib.import_module(f".{module_name}", package="custom_components.myraid_box.services")
            for attr_name in dir(module):
                obj = getattr(module, attr_name)
                if (isinstance(obj, type) and 
                    issubclass(obj, BaseService) and 
                    obj != BaseService and
                    hasattr(obj, 'service_id')):
                    register_service(obj)
        except Exception as e:
            _LOGGER.error("加载服务模块 %s 失败: %s", module_name, e, exc_info=True)

def register_service(service_class: Type[BaseService]) -> None:
    """注册服务到全局注册表"""
    try:
        instance = service_class()
        if instance.service_id in SERVICE_REGISTRY:
            _LOGGER.warning("服务ID %s 已存在，将被覆盖", instance.service_id)
        SERVICE_REGISTRY[instance.service_id] = service_class
        _LOGGER.debug("已注册服务: %s (%s)", instance.name, instance.service_id)
    except Exception as e:
        _LOGGER.error("注册服务 %s 失败: %s", service_class.__name__, e)