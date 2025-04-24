from __future__ import annotations
import logging
from typing import Any, Dict, Optional, List
from datetime import datetime

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers import entity_registry as er
from .const import DOMAIN, DEVICE_MANUFACTURER, DEVICE_MODEL, SERVICE_REGISTRY

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
                else [{"key": "main"}]
            )
            
            for config in sensor_configs:
                entities.append(MyriadBoxSensor(
                    coordinator=coordinator,
                    entry_id=entry.entry_id,
                    service_id=service_id,
                    sensor_config=config
                ))
    
    if entities:
        async_add_entities(entities)
        _LOGGER.info("成功创建 %d 个传感器实体", len(entities))

class MyriadBoxSensor(CoordinatorEntity, SensorEntity):
    """万象盒子传感器实体"""

    _attr_has_entity_name = False
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
        
        self._attr_unique_id = self._generate_unique_id()
        self._attr_name = sensor_config.get("name", self._service.name)
        self._attr_icon = sensor_config.get("icon", self._service.icon)
        self._attr_native_unit_of_measurement = sensor_config.get("unit")
        self._attr_device_class = sensor_config.get("device_class")
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{service_id}_{entry_id}")},
            name=f"{self._service.name}",
            manufacturer=DEVICE_MANUFACTURER,
            model=f"{DEVICE_MODEL} - {self._service.name}",
        )

        # 初始状态设置
        self._attr_native_value = "⏳ 连接服务中..."
        self._attr_available = False
        self._last_valid_value = None
        
        # 立即触发首次更新
        @callback
        def _first_update_listener():
            """首次更新后的清理"""
            coordinator.async_add_listener(_first_update_listener)
            self._attr_available = True  # 标记为可用
            
        coordinator.async_add_listener(_first_update_listener)
        coordinator.hass.async_create_task(coordinator.async_request_refresh())

    def _generate_unique_id(self) -> str:
        """生成唯一ID"""
        prefix = self._entry_id[:8]
        service_name = self._service.name.lower().replace(" ", "_")
        sensor_key = self._sensor_config.get("key", "main")
        return f"{prefix}_{service_name}_{sensor_key}"

    @property
    def native_value(self) -> Any:
        """返回传感器的主值"""
        if not self.coordinator.data:
            return "数据加载中..."
            
        return self._service.format_sensor_value(
            data=self.coordinator.data,
            sensor_config=self._sensor_config
        )
        
    @callback
    def _handle_coordinator_update(self) -> None:
        """处理协调器更新"""
        try:
            # 直接使用协调器的data属性
            new_value = self._service.format_sensor_value(
                self.coordinator.data,
                self._sensor_config
            )
            
            # 确保new_value是字符串且不为空
            new_value = str(new_value) if new_value is not None else "数据无效"
            
            # 强制更新状态
            self._last_valid_value = new_value
            self._attr_native_value = new_value
            self._attr_available = True
                
            # 更新属性
            self._attr_extra_state_attributes = self._service.get_sensor_attributes(
                self.coordinator.data,
                self._sensor_config
            )
                
            self.async_write_ha_state()
            _LOGGER.debug("[%s] 状态已更新", self.entity_id)
                
        except Exception as e:
            _LOGGER.error("[%s] 更新失败: %s", self.entity_id, str(e))
            self._attr_available = False
            self._attr_native_value = self._last_valid_value or "服务暂不可用"
            self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """返回额外属性"""
        if not self.coordinator.data:
            return {}
            
        return self._service.get_sensor_attributes(
            self.coordinator.data,
            self._sensor_config
        )