from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, TypedDict, List, NotRequired

class AttributeConfig(TypedDict):
    """Attribute configuration."""
    name: str
    icon: NotRequired[str]
    unit: NotRequired[str]
    device_class: NotRequired[str]
    value_map: NotRequired[Dict[str, str]]

class BaseService(ABC):
    """Base service class with improved type hints."""
    
    @property
    @abstractmethod
    def service_id(self) -> str:
        """Return service ID."""
        
    @property
    @abstractmethod
    def name(self) -> str:
        """Return service name."""
        
    @property
    @abstractmethod
    def description(self) -> str:
        """Return service description."""
        
    @property
    def icon(self) -> str:
        """Return default icon."""
        return "mdi:information"
    
    @property
    def unit(self) -> Optional[str]:
        """Return main sensor unit."""
        return None
    
    @property
    def device_class(self) -> Optional[str]:
        """Return device class."""
        return None
    
    @property
    def config_fields(self) -> Dict[str, Dict[str, Any]]:
        """Return configuration fields."""
        return {}
    
    @property
    def attributes(self) -> Dict[str, AttributeConfig]:
        """Return attribute configurations."""
        return {}
    
    @abstractmethod
    async def fetch_data(self, coordinator, params: Dict[str, Any]) -> Any:
        """Fetch data method."""
        
    def get_sensor_configs(self, service_data: Any) -> List[Dict[str, Any]]:
        """Get sensor configurations."""
        return [{
            "key": "main",
            "name": self.name,
            "icon": self.icon,
            "unit": self.unit,
            "device_class": self.device_class
        }]
    
    def format_sensor_value(self, data: Any, sensor_config: Dict[str, Any]) -> Any:
        """Format sensor value."""
        return str(data) if data is not None else "暂无数据"
    
    def is_sensor_available(self, data: Any, sensor_config: Dict[str, Any]) -> bool:
        """Check sensor availability."""
        return True
    
    def get_sensor_attributes(self, data: Any, sensor_config: Dict[str, Any]) -> Dict[str, Any]:
        """Get sensor attributes."""
        return {}