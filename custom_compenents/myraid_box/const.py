from datetime import timedelta
from typing import Dict, Type, List, Any
from .service_base import BaseService

# 基础常量
DOMAIN = "myraid_box"
DEVICE_MANUFACTURER = "万象盒子"
DEVICE_MODEL = "多功能数据聚合器"

# 服务注册表
SERVICE_REGISTRY: Dict[str, Type[BaseService]] = {}

def register_service(service_class: Type[BaseService]):
    """注册服务"""
    instance = service_class()
    SERVICE_REGISTRY[instance.service_id] = service_class

def get_service_config(service_id: str) -> Dict[str, Any]:
    """获取服务配置"""
    service_class = SERVICE_REGISTRY.get(service_id)
    if not service_class:
        return {}
    return service_class().get_config()

def get_service_order() -> List[str]:
    """获取服务顺序"""
    return list(SERVICE_REGISTRY.keys())