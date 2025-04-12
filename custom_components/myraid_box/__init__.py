import logging
from datetime import datetime, timedelta
import asyncio
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from .const import DOMAIN, SERVICE_REGISTRY
from .services import *  

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict):
    """设置组件"""
    return True
    
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """通过配置项设置"""
    _LOGGER.debug("初始化配置项，配置内容: %s", entry.data)
    coordinator = MyraidBoxCoordinator(hass, entry)
    
    # 首次加载数据并初始化定时任务
    await coordinator.async_ensure_data_loaded()
    coordinator._setup_individual_updaters()
    
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    
    return True

async def async_update_options(hass: HomeAssistant, entry: ConfigEntry):
    """配置项更新时重新加载"""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """卸载配置项时提示重启"""
    if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
        coordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.async_unload()
    
    hass.components.persistent_notification.async_create(
        "万象盒子集成已卸载，建议重启Home Assistant以使更改完全生效。",
        title="万象盒子",
        notification_id=f"{DOMAIN}_unload"
    )
    
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok

class MyraidBoxCoordinator(DataUpdateCoordinator):
    """万象盒子数据协调器（优化版）"""
    
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.entry = entry
        self.session = async_get_clientsession(hass)
        self._update_tasks = {}
        self._data = {}
        self._enabled_services = []
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,
        )
    
    async def async_ensure_data_loaded(self):
        """确保所有服务数据已加载"""
        self._enabled_services = [
            k.replace("enable_", "") 
            for k, v in self.entry.data.items() 
            if k.startswith("enable_") and v
        ]
        
        await asyncio.gather(*[
            self._fetch_service_data(service_id)
            for service_id in self._enabled_services
        ])
    
    async def _fetch_service_data(self, service_id: str):
        """获取单个服务数据"""
        try:
            service = SERVICE_REGISTRY[service_id]()
            params = {
                k.split(f"{service_id}_")[1]: v 
                for k, v in self.entry.data.items() 
                if k.startswith(f"{service_id}_")
            }
            self._data[service_id] = await service.fetch_data(self, params)
            self.async_set_updated_data(self._data)
        except Exception as err:
            _LOGGER.error("获取 %s 数据错误: %s", service_id, err)

    def _setup_individual_updaters(self):
        """为每个服务设置独立的更新任务"""
        for service_id in self._enabled_services:
            if service_id in SERVICE_REGISTRY:
                self._update_service_interval(service_id)
    
    def _update_service_interval(self, service_id: str):
        """更新或创建服务的定时任务"""
        service = SERVICE_REGISTRY[service_id]()
        
        interval_minutes = self.entry.options.get(
            f"{service_id}_interval",
            self.entry.data.get(
                f"{service_id}_interval",
                service.config_fields.get("interval", {}).get("default", 10)
            )
        )
        
        interval = timedelta(minutes=interval_minutes)
        _LOGGER.info(
            "服务 %s 的更新间隔设置为 %s 分钟",
            service_id, interval.total_seconds() / 60
        )
        
        if service_id in self._update_tasks:
            self._update_tasks[service_id]()
        
        self._create_service_updater(service_id, interval)
    
    def _create_service_updater(self, service_id: str, interval: timedelta):
        """创建单个服务的定时更新任务"""
        @callback
        async def _service_updater(now=None):
            try:
                service = SERVICE_REGISTRY[service_id]()
                params = {
                    k.split(f"{service_id}_")[1]: v 
                    for k, v in self.entry.data.items() 
                    if k.startswith(f"{service_id}_")
                }
                self._data[service_id] = await service.fetch_data(self, params)
                self.async_set_updated_data(self._data)
            except Exception as err:
                _LOGGER.error("获取 %s 数据错误: %s", service_id, err)

        self._update_tasks[service_id] = async_track_time_interval(
            self.hass,
            _service_updater,
            interval
        )
        self.hass.async_create_task(_service_updater())
    
    def update_service_status(self, service_id: str, enabled: bool):
        """更新服务状态"""
        if enabled and service_id not in self._enabled_services:
            self._enabled_services.append(service_id)
            self._update_service_interval(service_id)
            self.hass.async_create_task(self._fetch_service_data(service_id))
        elif not enabled and service_id in self._enabled_services:
            self._enabled_services.remove(service_id)
            if service_id in self._update_tasks:
                self._update_tasks[service_id]()
                del self._update_tasks[service_id]
            if service_id in self._data:
                del self._data[service_id]
                self.async_set_updated_data(self._data)

    async def async_unload(self):
        """卸载时取消所有定时任务"""
        for cancel in self._update_tasks.values():
            cancel()
        self._update_tasks.clear()