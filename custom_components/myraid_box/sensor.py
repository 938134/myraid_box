from __future__ import annotations
from typing import Any, Dict, List
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers import entity_registry
from .const import DOMAIN, DEVICE_MANUFACTURER, DEVICE_MODEL, SERVICE_REGISTRY

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """设置传感器"""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    @callback
    def async_update_sensors():
        """动态更新传感器"""
        # 获取当前所有实体
        ent_reg = entity_registry.async_get(hass)
        existing_entities = [
            entity_id 
            for entity_id, entry_ref in ent_reg.entities.items()
            if entry_ref.config_entry_id == entry.entry_id
        ]
        
        # 移除旧的传感器
        if existing_entities:
            for entity_id in existing_entities:
                ent_reg.async_remove(entity_id)
        
        # 添加新的传感器
        entities = []
        enabled_services = [
            k.replace("enable_", "") 
            for k, v in entry.data.items() 
            if k.startswith("enable_") and v
        ]
        
        for service_id in enabled_services:
            service_class = SERVICE_REGISTRY.get(service_id)
            if not service_class:
                continue
                
            service = service_class()
            service_data = coordinator.data.get(service_id)
            sensor_configs = service.get_sensor_configs(service_data)
            
            for config in sensor_configs:
                entities.append(MyraidBoxServiceSensor(
                    coordinator=coordinator,
                    service_type=service_id,
                    entry_id=entry.entry_id,
                    sensor_config=config
                ))
        
        async_add_entities(entities)
        hass.data[DOMAIN].setdefault("entities", {})
        hass.data[DOMAIN]["entities"][entry.entry_id] = entities
    
    # 监听配置项变化
    entry.async_on_unload(
        entry.add_update_listener(lambda hass, entry: async_update_sensors())
    )
    
    # 初始设置
    hass.data.setdefault(DOMAIN, {})
    async_update_sensors()

class MyraidBoxServiceSensor(CoordinatorEntity, SensorEntity):
    """万象盒子服务传感器"""
    
    _attr_entity_registry_enabled_default = True
    _attr_has_entity_name = False

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
        self._entry_id = entry_id
        
        self._attr_unique_id = self._generate_unique_id()
        self._attr_name = sensor_config.get("name", self._service.name)
        self._attr_icon = sensor_config.get("icon", self._service.icon)
        self._attr_native_unit_of_measurement = sensor_config.get("unit", self._service.unit)
        self._attr_device_class = sensor_config.get("device_class", self._service.device_class)
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{service_type}_{entry_id}")},
            name=self._service.name,
            manufacturer=DEVICE_MANUFACTURER,
            model=f"{DEVICE_MODEL} - {self._service.name}",
            entry_type="service",
        )

    def _generate_unique_id(self) -> str:
        """生成唯一ID"""
        prefix = self._entry_id[:4]
        service_name = self._service.name.lower().replace(" ", "_")
        sensor_key = self._sensor_config.get("key", "")
        
        if sensor_key and sensor_key != "main":
            return f"{prefix}_{DEVICE_MANUFACTURER.lower()}_{service_name}_{sensor_key}"
        return f"{prefix}_{DEVICE_MANUFACTURER.lower()}_{service_name}"

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