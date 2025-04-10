from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, TypedDict

class AttributeConfig(TypedDict, total=False):
    """属性配置类型"""
    name: str
    icon: Optional[str]
    unit: Optional[str]
    device_class: Optional[str]
    value_map: Optional[Dict[str, str]]

class BaseService(ABC):
    """服务基类"""
    
    @property
    @abstractmethod
    def service_id(self) -> str:
        """服务ID(英文标识)"""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """服务名称"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """服务描述"""
        pass
    
    @property
    def icon(self) -> str:
        """默认图标"""
        return "mdi:information"
    
    @property
    def unit(self) -> Optional[str]:
        """主传感器单位"""
        return None
    
    @property
    def device_class(self) -> Optional[str]:
        """主传感器设备类"""
        return None
    
    @property
    def config_fields(self) -> Dict[str, Dict[str, Any]]:
        """配置字段（由子类实现）"""
        return {}
    
    @property
    def attributes(self) -> Dict[str, AttributeConfig]:
        """属性配置"""
        return {}
    
    @abstractmethod
    async def fetch_data(self, coordinator, params: Dict[str, Any]) -> Any:
        """获取数据方法"""
        pass
    
    def format_main_value(self, data: Any) -> Any:
        """格式化主传感器值"""
        return str(data) if data is not None else "暂无数据"
    
    def get_attribute_value(self, data: Any, attribute: str) -> Any:
        """获取属性值"""
        if not data or not isinstance(data, dict):
            return None
            
        attr_config = self.attributes.get(attribute, {})
        raw_value = data.get(attribute)
        
        if raw_value is None:
            return None
            
        if "value_map" in attr_config:
            return attr_config["value_map"].get(str(raw_value), raw_value)
        
        return raw_value