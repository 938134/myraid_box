from typing import Dict, Type, List, Any
from .service_base import BaseService

DOMAIN = "myraid_box"
DEVICE_MANUFACTURER = "万象盒子"
DEVICE_MODEL = "多数据聚合"

SERVICE_REGISTRY: Dict[str, Type[BaseService]] = {}

def register_service(service_class: Type[BaseService]):
    """注册服务"""
    if not service_class or not issubclass(service_class, BaseService):
        raise ValueError("Invalid service class")
    SERVICE_REGISTRY[service_class().service_id] = service_class

def get_service_config(service_id: str) -> Dict[str, Any]:
    """获取服务配置"""
    if service_id not in SERVICE_REGISTRY:
        return {}
    return SERVICE_REGISTRY[service_id]().get_config()

def get_service_order() -> List[str]:
    """获取服务顺序"""
    return sorted(SERVICE_REGISTRY.keys())