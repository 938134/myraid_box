"""万象盒子传感器平台。

关键改动（相对上一版）：
- ``MyriadBoxSensor`` 不再自己实例化 ``BaseService``，而是通过
  coordinator 复用同一个 service 对象。原来 60 个 sensor 会创建
  60 个 service 实例（连带 60 个 aiohttp session 对象），
  现在每个 service 全 HA 生命周期只有 1 个实例。
- 移除 ``_handle_coordinator_update`` 里对 ``_attr_native_value`` 的手写同步，
  HA 的 ``native_value`` property 每次状态变更都会被读取，无需冗余缓存。
- 添加 ``_attr_unique_id`` 更清晰的注释，说明生成策略的稳定性要求。
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DEVICE_MANUFACTURER,
    DEVICE_MODEL,
    DOMAIN,
    VERSION,
)
from .registry import SERVICE_REGISTRY
from .service_base import BaseService, SensorConfig

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """为每个启用的服务创建对应传感器。"""
    runtime = getattr(entry, "runtime_data", None)
    if not runtime:
        _LOGGER.error("runtime_data 未就绪，跳过传感器创建")
        return

    coordinators = runtime["coordinators"]

    entities: list[MyriadBoxSensor] = []
    for service_id, coordinator in coordinators.items():
        service: BaseService = coordinator.service  # ← 复用单例
        sensor_configs = service.sensor_configs

        for config in sensor_configs:
            if config.get("is_attribute", False):
                continue
            entities.append(
                MyriadBoxSensor(
                    coordinator=coordinator,
                    entry_id=entry.entry_id,
                    service_id=service_id,
                    service=service,
                    sensor_config=config,
                )
            )

    if entities:
        async_add_entities(entities)
        _LOGGER.info("成功创建 %d 个传感器实体", len(entities))


class MyriadBoxSensor(CoordinatorEntity, SensorEntity):
    """万象盒子传感器 —— 遵循 HA 2024.6+ 实体规范。"""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator,
        entry_id: str,
        service_id: str,
        service: BaseService,
        sensor_config: SensorConfig,
    ) -> None:
        super().__init__(coordinator)

        self._service = service  # 复用 coordinator 里的 service 实例
        self._entry_id = entry_id
        self._service_id = service_id
        self._sensor_config = sensor_config

        # unique_id：稳定、可预测、跨 HA 实例一致
        # 格式：<entry_id 前 8 位>_<service_id>_<sensor_key>
        # entry_id 前 8 位足以区分不同 ConfigEntry 实例
        self._attr_unique_id = self._generate_unique_id()

        # translation_key：HA 从 translations/&lt;locale&gt;.json 里加载
        #   entity.sensor.&lt;domain&gt;.&lt;translation_key&gt;.name
        # 优先级：sensor_config 显式指定 > 自动生成 (service_id_key)
        # 自动生成的 key 会去掉非法字符（如 "#"），并把末尾下划线去掉
        self._attr_translation_key = self._generate_translation_key()

        # 属性：device_class 影响 UI 显示（温度/湿度/百分比等专用格式）
        self._attr_device_class = sensor_config.get("device_class")
        self._attr_native_unit_of_measurement = sensor_config.get("unit")
        self._attr_icon = sensor_config.get("icon")

        # EntityCategory 走 Enum，不写字符串
        entity_category_str = sensor_config.get("entity_category")
        if entity_category_str == "diagnostic":
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        elif entity_category_str == "config":
            self._attr_entity_category = EntityCategory.CONFIG
        else:
            self._attr_entity_category = None

        # DeviceInfo：同一服务的所有 sensor 共享一个设备
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{service_id}_{entry_id}")},
            name=service.device_name,
            manufacturer=DEVICE_MANUFACTURER,
            model=f"{DEVICE_MODEL} - {service.name}",
            sw_version=VERSION,
            configuration_url=(
                "https://www.home-assistant.io/integrations/" + DOMAIN
            ),
        )

    def _generate_unique_id(self) -> str:
        """生成稳定的 unique_id。

        稳定性要求：
        - 不能依赖运行时时序、哈希随机种子
        - 变更此函数逻辑会导致 HA 重建所有实体，用户需重新配置仪表盘
        """
        prefix = self._entry_id[:8]
        sensor_key = self._sensor_config.get("key", "unknown")
        return f"{prefix}_{self._service_id}_{sensor_key}"

    def _generate_translation_key(self) -> str:
        """生成 translation_key。

        优先使用 sensor_config 里显式指定的 ``translation_key``；否则
        自动生成 ``f"{service_id}_{key}"``。

        HA 对 translation_key 有格式要求：只允许 ``[a-z0-9_]``。
        因此自动生成时会把大写转小写、其它字符（如 "#"、"-"）替换为
        下划线，并把末尾下划线去掉。例如：
        - key="92#"     → "oilprice_92"
        - key="day3_weather" → "weather_day3_weather"

        这个规则要与 translations/*.json 里的 key 严格一致，
        否则 HA 会回退显示 key 字符串本身（例如 ``weather_92``），
        用户看到的实体名会很丑。
        """
        explicit = self._sensor_config.get("translation_key")
        if explicit:
            return explicit

        sensor_key = self._sensor_config.get("key", "unknown")
        # 1) 转小写
        slug = sensor_key.lower()
        # 2) 非 [a-z0-9_] 全部替换成下划线
        slug = re.sub(r"[^a-z0-9_]", "_", slug)
        # 3) 连续下划线折叠成一个
        slug = re.sub(r"_+", "_", slug)
        # 4) 去首尾下划线
        slug = slug.strip("_")
        return f"{self._service_id}_{slug}"

    # ------------------------------------------------------------
    # 属性读取 —— HA 每次状态更新会重新调用
    # ------------------------------------------------------------
    @property
    def native_value(self) -> Any:
        """传感器主值。coordinator 数据异常时返回 None，HA 显示为 unknown。"""
        if not self.coordinator.data:
            return None
        return self._service.format_sensor_value(
            self._sensor_config.get("key", ""),
            self.coordinator.data,
        )

    @property
    def icon(self) -> str:
        """动态图标（服务可以根据数据切换图标，如天气变化）。"""
        if not self.coordinator.data:
            return self._attr_icon
        dynamic_icon = self._service.get_sensor_icon(
            self._sensor_config.get("key", ""),
            self.coordinator.data,
        )
        return dynamic_icon or self._attr_icon

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """附加属性。空字典返回 None 避免 HA 白跑一次 state 更新。"""
        if not self.coordinator.data:
            return None
        attrs = self._service.get_sensor_attributes(
            self._sensor_config.get("key", ""),
            self.coordinator.data,
        )
        return attrs or None
