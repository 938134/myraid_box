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
        
        # 设置基本属性
        self._attr_unique_id = f"{entry_id[:4]}_{service_type}"
        #self._attr_name = sensor_config.get("name", self._service.name)
        self._attr_name = None
        self._attr_icon = sensor_config.get("icon", self._service.icon)
        self._attr_native_unit_of_measurement = sensor_config.get("unit", self._service.unit)
        self._attr_device_class = sensor_config.get("device_class", self._service.device_class)
        
        # 设备信息
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{service_type}_{entry_id}")},
            #identifiers={(DOMAIN, f"{service_type}_{entry_id}_{sensor_config.get('key', 'main')}")},
            name=self._service.name,
            manufacturer=DEVICE_MANUFACTURER,
            model=f"{DEVICE_MODEL} - {self._service.name}",
            entry_type="service",
        )

    def _generate_unique_id(self, entry_id: str) -> str:
        """生成唯一ID，格式为sensor.manufacturer_service_name"""
        # 将设备制造商转换为拼音小写下划线格式
        manufacturer_pinyin = "mo_xiang_he_zi" 
        
        # 将服务名称转换为拼音小写下划线格式
        service_name_pinyin = self._service.name.lower().replace(" ", "_")
        
        # 如果有传感器键值且不是main，则附加到ID中
        key = self._sensor_config.get("key", "")
        if key and key != "main":
            return f"sensor.{manufacturer_pinyin}_{service_name_pinyin}_{key}"
        
        return f"sensor.{manufacturer_pinyin}_{service_name_pinyin}"

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