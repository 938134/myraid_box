from abc import ABC, abstractmethod
from typing import Any, Dict
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from ..const import DOMAIN, DEVICE_MANUFACTURER, DEVICE_MODEL, ServiceRegistry

class BaseService(ABC):
    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
        self.hass = hass
        self.config_entry = config_entry
        self.session = async_get_clientsession(hass)
    
    @property
    def service_type(self) -> str:
        return self.__class__.__name__.replace("Service", "").lower()
    
    @abstractmethod
    async def async_update_data(self) -> Dict[str, Any]:
        pass
    
    def get_device_info(self) -> Dict[str, Any]:
        service_config = ServiceRegistry.get(self.service_type)
        return {
            "identifiers": {(DOMAIN, f"{self.service_type}_{self.config_entry.entry_id}")},
            "name": service_config["name"],
            "manufacturer": DEVICE_MANUFACTURER,
            "model": f"{DEVICE_MODEL} - {self.service_type.upper()}",
            "entry_type": "service",
        }
    
    @classmethod
    @abstractmethod
    def config_fields(cls) -> Dict[str, Dict[str, Any]]:
        return {}