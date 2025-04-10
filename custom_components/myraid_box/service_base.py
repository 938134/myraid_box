from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, TypedDict, List

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
    
    def get_sensor_configs(self, service_data: Any) -> List[Dict[str, Any]]:
        """
        根据服务数据返回传感器配置列表
        默认返回一个主传感器的配置
        """
        return [{
            "key": "main",
            "name": self.name,
            "icon": self.icon,
            "unit": self.unit,
            "device_class": self.device_class
        }]
    
    def format_sensor_value(self, data: Any, sensor_config: Dict[str, Any]) -> Any:
        """
        格式化传感器值
        :param data: 服务数据
        :param sensor_config: 传感器配置
        """
        return str(data) if data is not None else "暂无数据"
    
    def is_sensor_available(self, data: Any, sensor_config: Dict[str, Any]) -> bool:
        """
        检查传感器是否可用
        :param data: 服务数据
        :param sensor_config: 传感器配置
        """
        return True
    
    def get_sensor_attributes(self, data: Any, sensor_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取传感器额外属性
        :param data: 服务数据
        :param sensor_config: 传感器配置
        """
        return {}