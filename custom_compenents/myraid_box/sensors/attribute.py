from .base import BaseSensor
from homeassistant.components.sensor import SensorEntity
from ..const import DOMAIN

class AttributeSensor(BaseSensor, SensorEntity):
    def __init__(self, coordinator, service_type: str, attribute: str,
                 name: str, icon: str, unit: str, entry_id: str, device_id: str):
        super().__init__(coordinator)
        self._service_type = service_type
        self._attribute = attribute
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{service_type}_{attribute}_{entry_id[:4]}"
        self._attr_icon = icon
        self._attr_native_unit_of_measurement = unit
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_id)},
        }

    @property
    def native_value(self):
        """属性值处理"""
        data = self.coordinator.data.get(self._service_type, {})
        return data.get(self._attribute, "未知")