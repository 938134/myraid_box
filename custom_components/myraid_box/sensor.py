from __future__ import annotations
from typing import Any, Dict, List
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN, DEVICE_MANUFACTURER, DEVICE_MODEL, SERVICE_REGISTRY

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """设置传感器"""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    
    # 从配置项中获取已启用的服务
    enabled_services = [
        k.replace("enable_", "") 
        for k, v in entry.data.items() 
        if k.startswith("enable_") and v
    ]
    
    for service_id in enabled_services:
        # 获取服务实例
        service_class = SERVICE_REGISTRY.get(service_id)
        if not service_class:
            continue
            
        service = service_class()
        service_data = coordinator.data.get(service_id)
        
        # 让服务决定创建哪些传感器
        sensor_configs = service.get_sensor_configs(service_data)
        
        for config in sensor_configs:
            entities.append(MyraidBoxServiceSensor(
                coordinator=coordinator,
                service_type=service_id,
                entry_id=entry.entry_id,
                sensor_config=config
            ))
    
    async_add_entities(entities)

class MyraidBoxServiceSensor(CoordinatorEntity, SensorEntity):
    """万象盒子服务传感器"""
    
    _attr_entity_registry_enabled_default = True
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        service_type: str,
        entry_id: str,
        sensor_config: Dict[str, Any]
    ):
        super().__init__(coordinator)
        self._service = SERVICE_REGISTRY.get(service_type)()
        self._service_type = service_type
        self._sensor_config = sensor_config
        
        # 设置唯一ID，确保每个传感器都有不同的ID
        self._attr_unique_id = self._generate_unique_id(entry_id)
        
        # 设置基本属性
        self._attr_name = sensor_config.get("name", self._service.name)
        self._attr_icon = sensor_config.get("icon", self._service.icon)
        self._attr_native_unit_of_measurement = sensor_config.get("unit", self._service.unit)
        self._attr_device_class = sensor_config.get("device_class", self._service.device_class)
        
        # 设备信息
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{service_type}_{entry_id}")},
            name=self._service.name,
            manufacturer=DEVICE_MANUFACTURER,
            model=f"{DEVICE_MODEL} - {self._service.name}",
            entry_type="service",
        )
        
        self.async_on_remove(
            coordinator.async_add_listener(self._handle_data_update)
        )
    
    def _handle_data_update(self):
        """当数据更新时重新生成传感器配置"""
        data = self.coordinator.data.get(self._service_type)
        if data and hasattr(self._service, 'get_sensor_configs'):
            new_configs = self._service.get_sensor_configs(data)
            # 更新传感器配置（需要根据实际需求实现）
            self._update_sensor_config(new_configs)

    def _generate_unique_id(self, entry_id: str) -> str:
        """生成唯一ID，确保每个传感器都有不同的ID"""
        # 使用entry_id前4字符作为前缀
        prefix = entry_id[:4]
        
        # 获取服务名称拼音小写下划线格式
        service_name = self._service.name.lower().replace(" ", "_")
        
        # 获取传感器key（对于天气服务是day_0, day_1等）
        sensor_key = self._sensor_config.get("key", "")
        
        # 组合成唯一ID
        if sensor_key and sensor_key != "main":
            return f"{prefix}_{self._service_type}_{service_name}_{sensor_key}"
        
        return f"{prefix}_{self._service_type}_{service_name}"

    @property
    def native_value(self):
        """返回传感器值"""
        data = self.coordinator.data.get(self._service_type)
        return self._service.format_sensor_value(
            data=data,
            sensor_config=self._sensor_config
        )

    @property
    def available(self) -> bool:
        """确定传感器是否可用"""
        data = self.coordinator.data.get(self._service_type)
        return (
            super().available and
            data is not None and
            self._service.is_sensor_available(
                data=data,
                sensor_config=self._sensor_config
            )
        )

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """返回额外属性"""
        data = self.coordinator.data.get(self._service_type)
        return self._service.get_sensor_attributes(
            data=data,
            sensor_config=self._sensor_config
        )