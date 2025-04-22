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
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers import event
from homeassistant.components.logbook import LOGBOOK_ENTRY_MESSAGE, LOGBOOK_ENTRY_NAME, LOGBOOK_ENTRY_ENTITY_ID
from .const import DOMAIN, DEVICE_MANUFACTURER, DEVICE_MODEL, SERVICE_REGISTRY

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """设置传感器实体"""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    @callback
    def async_update_sensor_entities(now=None) -> None:
        """动态更新传感器实体"""
        ent_reg = er.async_get(hass)
        existing_entities = [
            ent.entity_id 
            for ent in er.async_entries_for_config_entry(ent_reg, entry.entry_id)
            if ent.domain == "sensor"
        ]
        
        if existing_entities:
            for entity_id in existing_entities:
                ent_reg.async_remove(entity_id)
            _LOGGER.debug("已移除 %d 个旧实体", len(existing_entities))
        
        entities = []
        enabled_services = [
            k.replace("enable_", "") 
            for k, v in entry.data.items() 
            if k.startswith("enable_") and v
        ]
        
        for service_id in enabled_services:
            if service_class := SERVICE_REGISTRY.get(service_id):
                service = service_class()
                service_data = coordinator.data.get(service_id, {})
                
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
        else:
            _LOGGER.warning("没有可用的传感器实体")
    
    # 立即创建实体，不再延迟
    async_update_sensor_entities()
    entry.async_on_unload(
        coordinator.async_add_listener(async_update_sensor_entities)
    )

class MyriadBoxSensor(CoordinatorEntity, SensorEntity):
    """万象盒子传感器实体"""

    _attr_has_entity_name = False
    _attr_should_poll = False  # 禁用轮询，完全依赖coordinator更新

    def __init__(self, coordinator, entry_id: str, service_id: str, sensor_config: Dict[str, Any]):
        super().__init__(coordinator)
        self._service = SERVICE_REGISTRY[service_id]()
        self._entry_id = entry_id
        self._service_id = service_id
        self._sensor_config = sensor_config
        
        self._attr_unique_id = f"{entry_id[:8]}_{service_id}_{sensor_config.get('key', 'main')}"
        self._attr_name = sensor_config.get("name", self._service.name)
        self._attr_icon = sensor_config.get("icon", self._service.icon)
        
        # 状态跟踪
        self._current_value = None
        self._last_logged_value = None
        
        # 基础属性
        self._attr_unique_id = self._generate_unique_id()
        self._attr_name = sensor_config.get("name", self._service.name)
        self._attr_icon = sensor_config.get("icon", self._service.icon)
        self._attr_native_unit_of_measurement = sensor_config.get("unit")
        self._attr_device_class = sensor_config.get("device_class")
        
        # 设备信息
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{service_id}_{entry_id}")},
            name=f"{self._service.name}",
            manufacturer=DEVICE_MANUFACTURER,
            model=f"{DEVICE_MODEL} - {self._service.name}",
        )

    def _generate_unique_id(self) -> str:
        """生成唯一ID"""
        prefix = self._entry_id[:8]
        service_name = self._service.name.lower().replace(" ", "_")
        sensor_key = self._sensor_config.get("key", "main")
        return f"{prefix}_{service_name}_{sensor_key}"

    @property
    def available(self) -> bool:
        """实体是否可用"""
        data = self.coordinator.data.get(self._service_id, {})
        return data.get("status") == "success" if data else False

    @property
    def native_value(self) -> Any:
        """返回当前值"""
        return self._current_value

    @callback
    def _handle_coordinator_update(self) -> None:
        """处理coordinator更新"""
        data = self.coordinator.data.get(self._service_id, {})
        new_value = self._service.format_sensor_value(data, self._sensor_config)
        
        # 值未变化则直接返回
        if new_value == self._current_value:
            return
            
        # 更新当前值
        old_value = self._current_value
        self._current_value = new_value
        
        # 记录日志（仅在值实际变化时）
        if new_value != self._last_logged_value:
            self._log_value_change(old_value, new_value)
            self._last_logged_value = new_value
            
        # 通知HA状态变化
        self.async_write_ha_state()

    def _log_value_change(self, old_value: Any, new_value: Any) -> None:
        """记录值变化日志"""
        log_msg = f"状态更新: {new_value}"
        _LOGGER.info("[%s] %s", self.entity_id, log_msg)
        
        self.hass.bus.async_fire(
            "logbook_entry",
            {
                "name": self._attr_name,
                "message": log_msg,
                "entity_id": self.entity_id,
            }
        )

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """返回额外属性"""
        data = self.coordinator.data.get(self._service_id, {})
        attrs = self._service.get_sensor_attributes(
            data=data,
            sensor_config=self._sensor_config
        )
        
        # 添加服务状态信息
        if hasattr(self.coordinator, 'get_service_status'):
            if status := self.coordinator.get_service_status(self._service_id):
                attrs.update({
                    "last_update": status.get("last_update"),
                    "service_status": status.get("status"),
                    **({"error": status["error"]} if "error" in status else {})
                })
        
        return attrs

    @property
    def suggested_display_precision(self) -> int | None:
        """根据单位建议显示精度"""
        if self.native_unit_of_measurement in ("°C", "°F"):
            return 1
        return None