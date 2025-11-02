from __future__ import annotations
import logging
from typing import Any, Dict, Optional, List
from datetime import datetime

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers import entity_registry as er
from .const import DOMAIN, DEVICE_MANUFACTURER, DEVICE_MODEL, SERVICE_REGISTRY, VERSION

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """设置传感器实体"""
    coordinators = hass.data[DOMAIN][entry.entry_id]
    
    entities = []
    for service_id, coordinator in coordinators.items():
        if service_class := SERVICE_REGISTRY.get(service_id):
            service = service_class()
            service_data = coordinator.data
            
            # 安全获取传感器配置
            sensor_configs = (
                service.get_sensor_configs(service_data)
                if hasattr(service, 'get_sensor_configs')
                else getattr(service, 'sensor_configs', [{"key": "main"}])
            )
            
            # 只创建主传感器，属性通过 extra_state_attributes 显示
            for config in sensor_configs:
                # 跳过属性配置，它们会作为主传感器的属性显示
                if config.get("is_attribute", False):
                    continue
                    
                entity = MyriadBoxSensor(
                    coordinator=coordinator,
                    entry_id=entry.entry_id,
                    service_id=service_id,
                    sensor_config=config
                )
                entities.append(entity)
    
    if entities:
        async_add_entities(entities)
        _LOGGER.info("成功创建 %d 个传感器实体", len(entities))

class MyriadBoxSensor(CoordinatorEntity, SensorEntity):
    """万象盒子传感器实体 - 支持动态图标"""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator,
        entry_id: str,
        service_id: str,
        sensor_config: Dict[str, Any]
    ) -> None:
        """初始化传感器"""
        super().__init__(coordinator)
        self._service = SERVICE_REGISTRY[service_id]()
        self._entry_id = entry_id
        self._service_id = service_id
        self._sensor_config = sensor_config
        
        # 生成唯一ID
        self._attr_unique_id = self._generate_unique_id()
        self._attr_name = sensor_config.get("name")
        self._attr_icon = sensor_config.get("icon")
        self._attr_native_unit_of_measurement = sensor_config.get("unit")
        self._attr_device_class = sensor_config.get("device_class")
        
        # 正确处理 entity_category
        entity_category_str = sensor_config.get("entity_category")
        if entity_category_str == "diagnostic":
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        elif entity_category_str == "config":
            self._attr_entity_category = EntityCategory.CONFIG
        else:
            self._attr_entity_category = None
        
        # 设备信息 - 同一服务的所有传感器共享设备
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{service_id}_{entry_id}")},
            name=f"{self._service.device_name}",
            manufacturer=DEVICE_MANUFACTURER,
            model=f"{DEVICE_MODEL} - {self._service.name}",
            sw_version=VERSION
        )

        # 初始状态
        self._attr_native_value = "初始化中..."
        self._attr_available = False
        self._last_valid_value = None

    def _generate_unique_id(self) -> str:
        """生成唯一ID"""
        prefix = self._entry_id[:8]
        sensor_key = self._sensor_config.get("key", "unknown")
        return f"{prefix}_{self._service_id}_{sensor_key}"

    @property
    def native_value(self) -> Any:
        """返回传感器的主值"""
        if not self.coordinator.data:
            return "数据加载中..."
            
        sensor_key = self._sensor_config.get("key")
        return self._service.format_sensor_value(sensor_key, self.coordinator.data)

    @property
    def icon(self) -> str:
        """返回传感器的图标 - 支持动态图标"""
        if not self.coordinator.data:
            return self._attr_icon
            
        sensor_key = self._sensor_config.get("key")
        # 调用服务的动态图标方法
        dynamic_icon = self._service.get_sensor_icon(sensor_key, self.coordinator.data)
        return dynamic_icon if dynamic_icon else self._attr_icon

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """返回传感器的额外属性"""
        if not self.coordinator.data:
            return {}
            
        sensor_key = self._sensor_config.get("key")
        return self._service.get_sensor_attributes(sensor_key, self.coordinator.data)

    @callback
    def _handle_coordinator_update(self) -> None:
        """处理协调器更新"""
        try:
            sensor_key = self._sensor_config.get("key")
            new_value = self._service.format_sensor_value(sensor_key, self.coordinator.data)
            
            # 确保new_value是字符串且不为空
            if new_value is None:
                new_value = "数据无效"
            else:
                new_value = str(new_value)
            
            # 更新状态
            self._last_valid_value = new_value
            self._attr_native_value = new_value
            self._attr_available = True
                
            self.async_write_ha_state()
            _LOGGER.debug("[%s] 状态已更新: %s", self.entity_id, new_value)
                
        except Exception as e:
            _LOGGER.error("[%s] 更新失败: %s", self.entity_id, str(e))
            self._attr_available = False
            self._attr_native_value = self._last_valid_value or "服务暂不可用"
            self.async_write_ha_state()