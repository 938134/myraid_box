from __future__ import annotations
from typing import Any, Dict
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN, DEVICE_MANUFACTURER, DEVICE_MODEL

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
        entities.append(MyraidBoxServiceSensor(
            coordinator=coordinator,
            service_type=service_id,
            entry_id=entry.entry_id
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
        entry_id: str
    ):
        super().__init__(coordinator)
        from .const import SERVICE_REGISTRY
        self._service = SERVICE_REGISTRY.get(service_type)()
        self._service_type = service_type
        self._attr_unique_id = f"{entry_id[:4]}_{service_type}"
        self._attr_icon = self._service.icon
        self._attr_native_unit_of_measurement = self._service.unit
        self._attr_device_class = self._service.device_class
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{service_type}_{entry_id}")},
            name=self._service.name,
            manufacturer=DEVICE_MANUFACTURER,
            model=f"{DEVICE_MODEL} - {self._service.name}",
            entry_type="service",
        )

    def _get_service_icon(self) -> str:
        """获取服务图标，确保返回有效值"""
        icon = getattr(self._service, 'icon', None)
        return icon if icon else "mdi:information"

    @property
    def name(self) -> str:
        """返回传感器名称，直接使用服务名称"""
        return self._service.name

    @property
    def native_value(self):
        data = self.coordinator.data.get(self._service_type)
        value = self._service.format_main_value(data)
        
        # 处理特殊状态值
        if value in ["unavailable", "error", "None"]:
            return None  # 返回None让HA处理为不可用状态
        return str(value).replace('None', '') if value else None

    @property
    def available(self) -> bool:
        return (
            super().available and
            self._service_type in self.coordinator.data and
            self.coordinator.data[self._service_type] is not None and
            self.coordinator.data[self._service_type].get("state") != "unavailable"
        )

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """返回额外属性，仅包含服务中attributes定义的属性"""
        data = self.coordinator.data.get(self._service_type, {})
        attributes = {}
        
        for attr, attr_config in self._service.attributes.items():
            value = self._service.get_attribute_value(data, attr)
            if value is not None:
                # 使用映射表中的中文名称作为属性键
                attr_name = attr_config.get("name", attr)
                attributes[attr_name] = value
        
        return attributes