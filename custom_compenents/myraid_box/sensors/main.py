from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MainSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, service_type: str, name: str, 
                 icon: str, unit: str, entry_id: str):
        super().__init__(coordinator)
        self._service_type = service_type
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{service_type}_main_{entry_id[:4]}"
        self._attr_icon = icon
        self._attr_native_unit_of_measurement = unit
        self._entry_id = entry_id