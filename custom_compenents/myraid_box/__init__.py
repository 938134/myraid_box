import logging
from datetime import timedelta
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import DOMAIN, SERVICE_REGISTRY
from .services import *  # 导入所有服务以完成注册

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict):
    """设置组件"""
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """通过配置项设置"""
    coordinator = MyraidBoxCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """卸载配置项"""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, ["sensor"]):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

async def async_update_options(hass: HomeAssistant, entry: ConfigEntry):
    """更新选项"""
    await hass.config_entries.async_reload(entry.entry_id)

class MyraidBoxCoordinator(DataUpdateCoordinator):
    """万象盒子数据协调器"""
    
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.entry = entry
        self.session = async_get_clientsession(hass)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=self._calculate_interval(),
        )

    def _calculate_interval(self):
        """计算更新间隔"""
        intervals = []
        for service_id, service_class in SERVICE_REGISTRY.items():
            if self.entry.data.get(f"enable_{service_id}", False):
                intervals.append(service_class().interval)
        return min(intervals) if intervals else timedelta(hours=1)

    async def _async_update_data(self):
        """从所有启用的服务获取数据"""
        data = {}
        for service_id, service_class in SERVICE_REGISTRY.items():
            if self.entry.data.get(f"enable_{service_id}", False):
                try:
                    service = service_class()
                    params = {
                        k.split(f"{service_id}_")[1]: v 
                        for k, v in self.entry.data.items() 
                        if k.startswith(f"{service_id}_")
                    }
                    data[service_id] = await service.fetch_data(self, params)
                except Exception as err:
                    _LOGGER.error("获取 %s 数据错误: %s", service_id, err)
                    data[service_id] = None
        return data