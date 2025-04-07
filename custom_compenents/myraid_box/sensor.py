from __future__ import annotations
from typing import Any, Dict
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN, DEVICE_MANUFACTURER, DEVICE_MODEL
from .service_base import BaseService

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """设置传感器"""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    
    for service_id in coordinator.entry.data:
        if service_id.startswith("enable_") and coordinator.entry.data[service_id]:
            service_type = service_id.replace("enable_", "")
            entities.extend(create_sensors_for_service(coordinator, service_type, entry.entry_id))
    
    async_add_entities(entities)

def create_sensors_for_service(coordinator, service_type: str, entry_id: str) -> list:
    """为服务创建传感器（主传感器置顶，属性传感器按名称排序）"""
    from .const import SERVICE_REGISTRY
    service_class = SERVICE_REGISTRY.get(service_type)
    if not service_class:
        return []
    
    service = service_class()
    entities = []
    
    # 主传感器（确保unique_id字典序最小，排序最前）
    main_sensor = MyraidBoxMainSensor(
        coordinator=coordinator,
        service=service,
        entry_id=entry_id
    )
    entities.append(main_sensor)
    
    # 属性传感器按名称排序（确保顺序一致）
    sorted_attributes = sorted(service.attributes.items(), key=lambda x: x[0])
    for attr, attr_config in sorted_attributes:
        entities.append(MyraidBoxAttributeSensor(
            coordinator=coordinator,
            service=service,
            attribute=attr,
            attr_config=attr_config,
            entry_id=entry_id
        ))
    
    return entities

class MyraidBoxMainSensor(CoordinatorEntity, SensorEntity):
    """万象盒子主传感器（强制置顶）"""
    
    _attr_entity_registry_enabled_default = True  # 确保默认启用
    _attr_has_entity_name = True  # 使用更规范的命名方式

    def __init__(
        self,
        coordinator,
        service: BaseService,
        entry_id: str
    ):
        super().__init__(coordinator)
        self._service = service
        self._attr_name = None  # 设置为None，使用设备名称
        self._attr_unique_id = f"{DOMAIN}_{entry_id[:4]}_{service.service_id}"  # 简化unique_id
        self._attr_icon = service.icon
        self._attr_native_unit_of_measurement = service.unit
        self._attr_device_class = service.device_class
        self._entry_id = entry_id
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{service.service_id}_{entry_id}")},
            name=service.name,
            manufacturer=DEVICE_MANUFACTURER,
            model=f"{DEVICE_MODEL} - {service.service_id.upper()}",
            entry_type="service",
        )

    @property
    def available(self) -> bool:
        return (
            super().available and
            self._service.service_id in self.coordinator.data and
            self.coordinator.data[self._service.service_id] is not None
        )

    @property
    def native_value(self):
        data = self.coordinator.data.get(self._service.service_id)
        return self._service.format_main_value(data)

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """返回额外属性"""
        data = self.coordinator.data.get(self._service.service_id, {})
        return {
            attr: self._service.get_attribute_value(data, attr)
            for attr in self._service.attributes
            if self._service.get_attribute_value(data, attr) is not None
        }

class MyraidBoxAttributeSensor(CoordinatorEntity, SensorEntity):
    """万象盒子属性传感器（按名称排序）"""
    
    _attr_has_entity_name = True  # 使用更规范的命名方式

    def __init__(
        self,
        coordinator,
        service: BaseService,
        attribute: str,
        attr_config: Dict[str, Any],
        entry_id: str
    ):
        super().__init__(coordinator)
        self._service = service
        self._attribute = attribute
        self._attr_config = attr_config
        self._attr_name = f"-{attr_config.get('name', attribute)}" # 设置属性名称
        self._attr_unique_id = f"{DOMAIN}_{entry_id[:4]}_{service.service_id}_{attribute}"  # 简化unique_id
        self._attr_icon = attr_config.get("icon", "mdi:information")
        self._attr_native_unit_of_measurement = attr_config.get("unit")
        self._attr_device_class = attr_config.get("device_class")
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{service.service_id}_{entry_id}")},
        )

    @property
    def available(self) -> bool:
        return (
            super().available and
            self._service.service_id in self.coordinator.data and
            self.coordinator.data[self._service.service_id] is not None
        )

    @property
    def native_value(self):
        data = self.coordinator.data.get(self._service.service_id)
        return self._service.get_attribute_value(data, self._attribute)