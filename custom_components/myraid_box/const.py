from typing import Dict, Type, List, Any
import importlib
from pathlib import Path
import logging
from .service_base import BaseService
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

DOMAIN = "myraid_box"
DEVICE_MANUFACTURER = "万象盒子"
DEVICE_MODEL = "多数据聚合"
VERSION = "1.0.0"

CARD_NAME = "myraid_box_card"
CARD_VERSION = "1.0.0"

# API端点
API_ENDPOINT = "/api/myraid_box/data"

SERVICE_REGISTRY: Dict[str, Type[BaseService]] = {}
_services_discovered = False


async def discover_services(hass: HomeAssistant, services_dir: str) -> None:
    """自动发现并注册服务"""
    global _services_discovered
    
    if _services_discovered:
        return
    
    services_path = Path(services_dir)
    
    def get_module_names():
        return [f.stem for f in services_path.glob("*.py") 
                if not f.name.startswith(("_", "base")) and f.is_file()]
    
    module_names = await hass.async_add_executor_job(get_module_names)
    
    for module_name in module_names:
        try:
            module = await hass.async_add_executor_job(
                importlib.import_module, 
                f"custom_components.myraid_box.services.{module_name}"
            )
            
            for attr_name in dir(module):
                obj = getattr(module, attr_name)
                if (isinstance(obj, type) and 
                    issubclass(obj, BaseService) and 
                    obj != BaseService and
                    hasattr(obj, 'service_id')):
                    register_service(obj)
                    
        except Exception as e:
            _LOGGER.error("加载服务模块 %s 失败: %s", module_name, e, exc_info=True)
    
    _services_discovered = True


def register_service(service_class: Type[BaseService]) -> None:
    """注册服务到全局注册表"""
    try:
        instance = service_class()
        service_id = instance.service_id
        
        if service_id in SERVICE_REGISTRY and SERVICE_REGISTRY[service_id] == service_class:
            return
            
        if service_id in SERVICE_REGISTRY:
            _LOGGER.warning("服务ID %s 已存在，将被覆盖", service_id)
            
        SERVICE_REGISTRY[service_id] = service_class
        _LOGGER.debug("已注册服务: %s (%s)", instance.name, service_id)
        
    except Exception as e:
        _LOGGER.error("注册服务 %s 失败: %s", service_class.__name__, e)