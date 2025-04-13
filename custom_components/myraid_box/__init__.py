from __future__ import annotations
import importlib
import logging
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .const import DOMAIN, SERVICE_REGISTRY, register_service
from .service_base import BaseService

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """设置万象盒子组件并自动发现服务"""
    hass.data.setdefault(DOMAIN, {})
    
    # 自动注册所有服务
    services_dir = Path(__file__).parent / "services"
    _LOGGER.debug("正在扫描服务目录: %s", services_dir)
    
    registered = await _register_services(hass, services_dir)
    _LOGGER.info("已注册 %d 个服务: %s", len(registered), ", ".join(registered))
    
    return True

async def _register_services(hass: HomeAssistant, services_dir: Path) -> List[str]:
    """异步发现并注册所有服务类"""
    registered = []
    
    for service_file in services_dir.glob("*.py"):
        if service_file.name.startswith("_"):
            continue
            
        module_name = f"{__package__}.services.{service_file.stem}"
        try:
            # 使用异步导入避免阻塞事件循环
            module = await hass.async_add_import_executor_job(
                importlib.import_module,
                module_name
            )
            
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                
                if (isinstance(attr, type) and 
                    issubclass(attr, BaseService) and 
                    attr != BaseService):
                    
                    register_service(attr)
                    service_id = attr().service_id
                    registered.append(service_id)
                    _LOGGER.debug("已注册服务: %s 来自 %s", service_id, module_name)
                    
        except Exception as e:
            _LOGGER.error("加载服务 %s 失败: %s", service_file.name, str(e), exc_info=True)
    
    return registered

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """从配置项设置万象盒子"""
    _LOGGER.debug("正在初始化配置项: %s", entry.entry_id)
    
    coordinator = MyraidBoxCoordinator(hass, entry)
    
    try:
        await coordinator.async_ensure_data_loaded()
        coordinator._setup_individual_updaters()
    except Exception as ex:
        _LOGGER.error("协调器初始化失败: %s", str(ex), exc_info=True)
        return False
    
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # 使用新的异步平台设置方法
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    
    # 设置更新监听器
    entry.async_on_unload(
        entry.add_update_listener(async_update_options)
    )
    
    return True

class MyraidBoxCoordinator(DataUpdateCoordinator):
    """集成APScheduler的协调器"""
    
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        """初始化协调器"""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN
        )
        self.entry = entry
        self.session = async_get_clientsession(hass)
        self.scheduler = AsyncIOScheduler()
        self._jobs: Dict[str, Any] = {}
        self._data: Dict[str, Any] = {}
        self._enabled_services: List[str] = []
        
        # 启动调度器
        self.scheduler.start()
        _LOGGER.debug("APScheduler已启动")

    async def async_ensure_data_loaded(self) -> None:
        """加载已启用服务的初始数据"""
        self._enabled_services = [
            k.replace("enable_", "") 
            for k, v in self.entry.data.items() 
            if k.startswith("enable_") and v
        ]
        
        if not self._enabled_services:
            _LOGGER.warning("配置项中未找到已启用的服务")
            return
            
        _LOGGER.debug("正在为服务加载初始数据: %s", self._enabled_services)
        
        results = await asyncio.gather(
            *[self._fetch_service_data(sid) for sid in self._enabled_services],
            return_exceptions=True
        )
        
        for sid, result in zip(self._enabled_services, results):
            if isinstance(result, Exception):
                _LOGGER.error(
                    "服务 %s 初始数据加载失败: %s", 
                    sid, str(result),
                    exc_info=result
                )

    async def _fetch_service_data(self, service_id: str) -> None:
        """获取单个服务的数据"""
        if service_id not in SERVICE_REGISTRY:
            raise KeyError(f"服务 '{service_id}' 未注册")
            
        service = SERVICE_REGISTRY[service_id]()
        params = {
            k.split(f"{service_id}_")[1]: v 
            for k, v in self.entry.data.items() 
            if k.startswith(f"{service_id}_")
        }
        
        _LOGGER.debug("正在获取 %s 的数据，参数: %s", service_id, params)
        data = await service.fetch_data(self, params)
        
        self._data[service_id] = data
        self.async_set_updated_data(self._data)
        _LOGGER.debug("%s 数据已更新", service_id)

    def _setup_individual_updaters(self) -> None:
        """为每个服务设置APScheduler任务"""
        for service_id in self._enabled_services:
            self._update_service_interval(service_id)

    def _update_service_interval(self, service_id: str) -> None:
        """更新或创建服务的定时任务"""
        if service_id not in SERVICE_REGISTRY:
            _LOGGER.error("无法调度未注册的服务: %s", service_id)
            return
            
        service = SERVICE_REGISTRY[service_id]()
        interval = self._get_service_interval(service_id, service)
        
        # 移除现有任务
        if service_id in self._jobs:
            self._jobs[service_id].remove()
            del self._jobs[service_id]
            _LOGGER.debug("已移除 %s 的现有任务", service_id)
        
        # 创建新任务
        job = self.scheduler.add_job(
            self._create_service_updater(service_id),
            'interval',
            minutes=interval,
            id=f"{DOMAIN}_{service_id}",
            replace_existing=True,
            max_instances=1
        )
        
        self._jobs[service_id] = job
        _LOGGER.info(
            "已调度 %s，间隔: %d 分钟", 
            service_id, interval
        )

    def _get_service_interval(self, service_id: str, service: BaseService) -> int:
        """获取服务的更新间隔"""
        interval = self.entry.options.get(
            f"{service_id}_interval",
            self.entry.data.get(
                f"{service_id}_interval",
                service.config_fields.get("interval", {}).get("default", 10)
            )
        )
        return int(interval)

    def _create_service_updater(self, service_id: str):
        """创建APScheduler的更新闭包"""
        async def _service_updater():
            try:
                await self._fetch_service_data(service_id)
            except Exception as err:
                _LOGGER.error(
                    "更新 %s 失败: %s", 
                    service_id, str(err),
                    exc_info=True
                )
        return _service_updater

    async def async_unload(self) -> None:
        """清理资源"""
        self.scheduler.shutdown(wait=False)
        self._jobs.clear()
        _LOGGER.debug("协调器已卸载")

async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """处理配置项更新"""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """处理配置项卸载"""
    if DOMAIN not in hass.data or entry.entry_id not in hass.data[DOMAIN]:
        return True
        
    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_unload()
    
    # 卸载传感器平台
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.info("成功卸载配置项: %s", entry.entry_id)
    else:
        _LOGGER.warning("卸载配置项 %s 的平台失败", entry.entry_id)
    
    return unload_ok