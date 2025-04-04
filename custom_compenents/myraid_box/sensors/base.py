from homeassistant.helpers.update_coordinator import CoordinatorEntity

class BaseSensor(CoordinatorEntity):
    """传感器基类"""
    
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_should_poll = False
    
    @property
    def available(self) -> bool:
        """实体可用性判断"""
        return (
            super().available and
            self._service_type in self.coordinator.data and
            self.coordinator.data[self._service_type] is not None
        )