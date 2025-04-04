from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class AttributeSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, service_type: str, attribute: str,
                 name: str, icon: str, unit: str, entry_id: str, device_id: str):
        super().__init__(coordinator)
        self._service_type = service_type
        self._attribute = attribute
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{service_type}_{attribute}_{entry_id[:4]}"
        self._attr_icon = icon
        self._attr_native_unit_of_measurement = unit