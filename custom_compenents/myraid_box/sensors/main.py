from .base import BaseSensor
from homeassistant.components.sensor import SensorEntity

class MainSensor(BaseSensor, SensorEntity):
    def __init__(self, coordinator, service_type: str, name: str, 
                 icon: str, unit: str, entry_id: str):
        super().__init__(coordinator)
        self._service_type = service_type
        self._attr_name = name
        self._attr_unique_id = f"myraid_box_{service_type}_main_{entry_id[:4]}"
        self._attr_icon = icon
        self._attr_native_unit_of_measurement = unit
        
        # 设备信息
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{service_type}_{entry_id}")},
            "name": name,
            "manufacturer": "万象盒子",
            "model": f"多服务数据集成器 - {service_type.upper()}"
        }

    @property
    def native_value(self):
        """主传感器值处理逻辑"""
        data = self.coordinator.data.get(self._service_type, {})
        if self._service_type == "hitokoto":
            return data.get("hitokoto", "暂无数据")
        elif self._service_type == "weather":
            return f"{data.get('temp', 'N/A')}°C"
        # 其他服务处理逻辑...
        return "未知服务类型"