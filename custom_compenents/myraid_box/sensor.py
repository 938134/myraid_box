from __future__ import annotations
from typing import Any, Dict, List
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
) -> None:
    """设置传感器"""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: List[SensorEntity] = []
    
    for service_id in coordinator.entry.data:
        if service_id.startswith("enable_") and coordinator.entry.data[service_id]:
            service_type = service_id.replace("enable_", "")
            entities.extend(create_sensors_for_service(coordinator, service_type, entry.entry_id))
    
    async_add_entities(entities)

def create_sensors_for_service(coordinator: Any, service_type: str, entry_id: str) -> List[SensorEntity]:
    """为服务创建传感器（确保主传感器在前，属性传感器在后）"""
    from .const import SERVICE_REGISTRY
    service_class = SERVICE_REGISTRY.get(service_type)
    if not service_class:
        return []
    
    service = service_class()
    entities: List[SensorEntity] = []
    
    # 主传感器（确保排序最前）
    main_sensor = MyraidBoxMainSensor(
        coordinator=coordinator,
        service=service,
        entry_id=entry_id
    )
    entities.append(main_sensor)
    
    # 属性传感器按名称排序（保持一致的显示顺序）
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
    """万象盒子主传感器（显示为'每日一言'）"""
    
    _attr_entity_registry_enabled_default = True
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: Any,
        service: BaseService,
        entry_id: str
    ) -> None:
        super().__init__(coordinator)
        self._service = service
        self._attr_name = service.name  # 直接使用服务名称（如"每日一言"）
        self._attr_unique_id = f"{DOMAIN}_{entry_id[:4]}_{service.service_id}_main"
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
    def native_value(self) -> Any:
        data = self.coordinator.data.get(self._service.service_id)
        return self._service.format_main_value(data)

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        data = self.coordinator.data.get(self._service.service_id, {})
        return {
            attr: self._service.get_attribute_value(data, attr)
            for attr in self._service.attributes
            if self._service.get_attribute_value(data, attr) is not None
        }

class MyraidBoxAttributeSensor(CoordinatorEntity, SensorEntity):
    """万象盒子属性传感器（显示为'每日一言-属性名'）"""
    
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: Any,
        service: BaseService,
        attribute: str,
        attr_config: Dict[str, Any],
        entry_id: str
    ) -> None:
        super().__init__(coordinator)
        self._service = service
        self._attribute = attribute
        self._attr_config = attr_config
        # 使用"服务名称-属性名称"格式
        self._attr_name = f"{service.name} - {attr_config.get('name', attribute)}"
        
        self._attr_unique_id = f"{DOMAIN}_{entry_id[:4]}_{service.service_id}_attr_{attribute}"
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
    def native_value(self) -> Any:
        data = self.coordinator.data.get(self._service.service_id)
        return self._service.get_attribute_value(data, self._attribute)