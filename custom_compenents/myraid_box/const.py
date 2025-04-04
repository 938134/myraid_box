from datetime import timedelta
from typing import TypedDict, NotRequired, Dict, Any, List

DOMAIN = "myraid_box"
DEVICE_MANUFACTURER = "万象盒子"
DEVICE_MODEL = "多服务数据集成器"

class AttributeConfig(TypedDict):
    name: str
    icon: str
    unit: NotRequired[str]
    enabled: NotRequired[bool]

class ServiceConfig(TypedDict):
    name: str
    description: str
    url: str
    interval: timedelta
    icon: NotRequired[str]
    unit: NotRequired[str]
    config_fields: NotRequired[Dict[str, Dict[str, Any]]]
    attributes: NotRequired[Dict[str, AttributeConfig]]

class ServiceRegistry:
    _services: Dict[str, ServiceConfig] = {}
    
    @classmethod
    def register(cls, service_type: str, config: ServiceConfig):
        cls._services[service_type] = config
    
    @classmethod
    def get(cls, service_type: str) -> ServiceConfig:
        return cls._services.get(service_type)
    
    @classmethod
    def all(cls) -> Dict[str, ServiceConfig]:
        return cls._services
    
    @classmethod
    def order(cls) -> List[str]:
        return list(cls._services.keys())
    
    @classmethod
    def get_attributes_config(cls, service_type: str) -> Dict[str, AttributeConfig]:
        return cls._services.get(service_type, {}).get("attributes", {})
    
    @classmethod
    def get_enabled_attributes(cls, service_type: str) -> List[str]:
        attributes = cls.get_attributes_config(service_type)
        return [attr for attr, config in attributes.items() 
               if config.get("enabled", True)]

def register_service(service_type: str, **kwargs):
    def decorator(cls):
        ServiceRegistry.register(service_type, ServiceConfig(**kwargs))
        return cls
    return decorator

HITOKOTO_TYPE_MAP = {
    "a": "动画", "b": "漫画", "c": "游戏", "d": "文学",
    "e": "原创", "f": "来自网络", "g": "其他", "h": "影视",
    "i": "诗词", "j": "网易云", "k": "哲学", "l": "抖机灵"
}