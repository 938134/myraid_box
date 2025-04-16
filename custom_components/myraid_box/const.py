from typing import Dict, Type, List, Any
import importlib
from pathlib import Path
import logging
from .service_base import BaseService
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# 基础常量
DOMAIN = "myraid_box"
DEVICE_MANUFACTURER = "万象盒子"
DEVICE_MODEL = "多数据聚合"

# 服务注册表
SERVICE_REGISTRY: Dict[str, Type[BaseService]] = {}

# 在文件顶部添加
_services_discovered = False  # 标记是否已发现服务

async def discover_services(hass: HomeAssistant, services_dir: str) -> None:
    """自动发现并注册服务（确保只执行一次）"""
    global _services_discovered
    
    if _services_discovered:
        return  # 已发现过服务，直接返回
    
    services_path = Path(services_dir)
    for module_file in services_path.glob("*.py"):
        if module_file.name.startswith(("_", "base")) or not module_file.is_file():
            continue
        
        module_name = module_file.stem
        try:
            # 动态导入模块
            module = await hass.async_add_executor_job(
                importlib.import_module, 
                f"custom_components.myraid_box.services.{module_name}"
            )
            
            # 注册服务
            for attr_name in dir(module):
                obj = getattr(module, attr_name)
                if (isinstance(obj, type) and 
                    issubclass(obj, BaseService) and 
                    obj != BaseService and
                    hasattr(obj, 'service_id')):
                    register_service(obj)
                    
        except Exception as e:
            _LOGGER.error("加载服务模块 %s 失败: %s", module_name, e, exc_info=True)
    
    _services_discovered = True  # 标记为已发现

def register_service(service_class: Type[BaseService]) -> None:
    """注册服务到全局注册表（避免重复注册）"""
    try:
        instance = service_class()
        service_id = instance.service_id
        
        # 如果服务已存在且实现类相同，则跳过
        if service_id in SERVICE_REGISTRY and SERVICE_REGISTRY[service_id] == service_class:
            return
            
        if service_id in SERVICE_REGISTRY:
            _LOGGER.warning("服务ID %s 已存在，将被覆盖", service_id)
            
        SERVICE_REGISTRY[service_id] = service_class
        _LOGGER.debug("已注册服务: %s (%s)", instance.name, service_id)
        
    except Exception as e:
        _LOGGER.error("注册服务 %s 失败: %s", service_class.__name__, e)