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
    coordinator = MyraidBoxCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
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
    # 取消所有定时任务
    if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
        coordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.async_unload()
    
    # 提示用户需要重启
    hass.components.persistent_notification.async_create(
        "万象盒子集成已卸载，建议重启Home Assistant以使更改完全生效。",
        title="万象盒子",
        notification_id=f"{DOMAIN}_unload"
    )
    
    # 卸载传感器平台
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
        self._data = {}  # 独立数据存储
        
        # 初始化时使用最小的更新间隔（仅用于兼容性）
        min_interval = min(
            entry.data.get(f"{service_id}_interval", 60)
            for service_id in SERVICE_REGISTRY
            if entry.data.get(f"enable_{service_id}", False)
        )
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=min_interval),
        )

    async def async_config_entry_first_refresh(self):
        """初始化时启动各服务的独立更新任务"""
        await super().async_config_entry_first_refresh()
        self._setup_individual_updaters()

    def _setup_individual_updaters(self):
        """为每个服务设置独立的更新任务"""
        # 从配置项中获取已启用的服务
        enabled_services = [
            k.replace("enable_", "") 
            for k, v in self.entry.data.items() 
            if k.startswith("enable_") and v
        ]
        
        for service_id in enabled_services:
            if service_id in SERVICE_REGISTRY:
                interval = timedelta(
                    minutes=self.entry.data.get(f"{service_id}_interval", 60)
                )
                self._create_service_updater(service_id, interval)

    def _create_service_updater(self, service_id: str, interval: timedelta):
        """创建单个服务的定时更新任务"""
        @callback
        async def _service_updater(now=None):
            """服务特定的更新函数"""
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
                self._data[service_id] = None

        # 取消现有任务（如果存在）
        if service_id in self._update_tasks:
            self._update_tasks[service_id]()
            self._update_tasks.pop(service_id)

        # 立即执行第一次更新
        self.hass.async_create_task(_service_updater())
        
        # 设置定时任务
        self._update_tasks[service_id] = async_track_time_interval(
            self.hass,
            _service_updater,
            interval
        )

    async def _async_update_data(self):
        """统一数据更新接口（保持兼容性）"""
        return self._data

    async def async_unload(self):
        """卸载时取消所有定时任务"""
        for cancel in self._update_tasks.values():
            cancel()
        self._update_tasks.clear()