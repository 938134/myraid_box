import logging
from datetime import timedelta
from typing import Any, Dict

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, ServiceRegistry

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: Dict[str, Any]) -> bool:
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = MyraidBoxCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, ["sensor"]):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)

class MyraidBoxCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.entry = entry
        self.services = self._init_services(hass, entry)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=self._calculate_interval(),
        )
    
    def _init_services(self, hass: HomeAssistant, entry: ConfigEntry) -> Dict[str, Any]:
        services = {}
        for service_type in ServiceRegistry.order():
            if entry.data.get(f"enable_{service_type}", False):
                try:
                    module = __import__(
                        f"myraid_box.services.{service_type}",
                        fromlist=[f"{service_type.capitalize()}Service"]
                    )
                    service_class = getattr(module, f"{service_type.capitalize()}Service")
                    services[service_type] = service_class(hass, entry)
                except Exception as e:
                    _LOGGER.error(f"初始化服务 {service_type} 失败: {e}")
        return services
    
    def _calculate_interval(self) -> timedelta:
        intervals = [
            ServiceRegistry.get(service_type)["interval"]
            for service_type in self.services
        ]
        return min(intervals) if intervals else timedelta(hours=1)
    
    async def _async_update_data(self) -> Dict[str, Any]:
        data = {}
        for service_type, service in self.services.items():
            try:
                data[service_type] = await service.async_update_data()
            except Exception as err:
                _LOGGER.error("更新 %s 数据错误: %s", service_type, err)
                data[service_type] = {"error": str(err)}
        return data