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
    """Set up the Myraid Box component with auto-service discovery."""
    hass.data.setdefault(DOMAIN, {})
    
    # Auto-register all services
    services_dir = Path(__file__).parent / "services"
    _LOGGER.debug("Scanning for services in: %s", services_dir)
    
    registered = await _register_services(services_dir)
    _LOGGER.info("Registered %d services: %s", len(registered), ", ".join(registered))
    
    return True

async def _register_services(services_dir: Path) -> List[str]:
    """Discover and register all service classes."""
    registered = []
    
    for service_file in services_dir.glob("*.py"):
        if service_file.name.startswith("_"):
            continue
            
        module_name = f"{__package__}.services.{service_file.stem}"
        try:
            module = importlib.import_module(module_name)
            
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                
                if (isinstance(attr, type) and 
                    issubclass(attr, BaseService) and 
                    attr != BaseService):
                    
                    register_service(attr)
                    service_id = attr().service_id
                    registered.append(service_id)
                    _LOGGER.debug("Registered service: %s from %s", service_id, module_name)
                    
        except Exception as e:
            _LOGGER.error("Failed to load service %s: %s", service_file.name, str(e), exc_info=True)
    
    return registered

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Myraid Box from a config entry."""
    _LOGGER.debug("Initializing config entry: %s", entry.entry_id)
    
    coordinator = MyraidBoxCoordinator(hass, entry)
    
    try:
        await coordinator.async_ensure_data_loaded()
        coordinator._setup_individual_updaters()
    except Exception as ex:
        _LOGGER.error("Coordinator initialization failed: %s", str(ex), exc_info=True)
        return False
    
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # Forward sensor platform setup
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )
    
    # Setup update listener
    entry.async_on_unload(
        entry.add_update_listener(async_update_options)
    )
    
    return True

class MyraidBoxCoordinator(DataUpdateCoordinator):
    """Coordinator with APScheduler integration."""
    
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,  # We use APScheduler instead
        )
        self.entry = entry
        self.session = async_get_clientsession(hass)
        self.scheduler = AsyncIOScheduler()
        self._jobs: Dict[str, Any] = {}
        self._data: Dict[str, Any] = {}
        self._enabled_services: List[str] = []
        
        # Start scheduler
        self.scheduler.start()
        _LOGGER.debug("APScheduler started")

    async def async_ensure_data_loaded(self) -> None:
        """Load initial data for enabled services."""
        self._enabled_services = [
            k.replace("enable_", "") 
            for k, v in self.entry.data.items() 
            if k.startswith("enable_") and v
        ]
        
        if not self._enabled_services:
            _LOGGER.warning("No enabled services found in config entry")
            return
            
        _LOGGER.debug("Loading initial data for services: %s", self._enabled_services)
        
        results = await asyncio.gather(
            *[self._fetch_service_data(sid) for sid in self._enabled_services],
            return_exceptions=True
        )
        
        for sid, result in zip(self._enabled_services, results):
            if isinstance(result, Exception):
                _LOGGER.error(
                    "Initial data load failed for %s: %s", 
                    sid, str(result),
                    exc_info=result
                )

    async def _fetch_service_data(self, service_id: str) -> None:
        """Fetch data for a single service."""
        if service_id not in SERVICE_REGISTRY:
            raise KeyError(f"Service '{service_id}' not registered")
            
        service = SERVICE_REGISTRY[service_id]()
        params = {
            k.split(f"{service_id}_")[1]: v 
            for k, v in self.entry.data.items() 
            if k.startswith(f"{service_id}_")
        }
        
        _LOGGER.debug("Fetching data for %s with params: %s", service_id, params)
        data = await service.fetch_data(self, params)
        
        self._data[service_id] = data
        self.async_set_updated_data(self._data)
        _LOGGER.debug("Data updated for %s", service_id)

    def _setup_individual_updaters(self) -> None:
        """Setup APScheduler jobs for each service."""
        for service_id in self._enabled_services:
            self._update_service_interval(service_id)

    def _update_service_interval(self, service_id: str) -> None:
        """Update or create scheduled job for a service."""
        if service_id not in SERVICE_REGISTRY:
            _LOGGER.error("Cannot schedule unregistered service: %s", service_id)
            return
            
        service = SERVICE_REGISTRY[service_id]()
        interval = self._get_service_interval(service_id, service)
        
        # Remove existing job if present
        if service_id in self._jobs:
            self._jobs[service_id].remove()
            del self._jobs[service_id]
            _LOGGER.debug("Removed existing job for %s", service_id)
        
        # Create new job
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
            "Scheduled %s with interval: %d minutes", 
            service_id, interval
        )

    def _get_service_interval(self, service_id: str, service: BaseService) -> int:
        """Get update interval for a service."""
        # Priority: options > entry data > service default
        interval = self.entry.options.get(
            f"{service_id}_interval",
            self.entry.data.get(
                f"{service_id}_interval",
                service.config_fields.get("interval", {}).get("default", 10)
            )
        )
        return int(interval)

    def _create_service_updater(self, service_id: str):
        """Create update closure for APScheduler."""
        async def _service_updater():
            try:
                await self._fetch_service_data(service_id)
            except Exception as err:
                _LOGGER.error(
                    "Failed to update %s: %s", 
                    service_id, str(err),
                    exc_info=True
                )
        return _service_updater

    async def async_unload(self) -> None:
        """Clean up resources."""
        self.scheduler.shutdown(wait=False)
        self._jobs.clear()
        _LOGGER.debug("Coordinator unloaded")

async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle config entry updates."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle config entry unload."""
    if DOMAIN not in hass.data or entry.entry_id not in hass.data[DOMAIN]:
        return True
        
    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_unload()
    
    # Unload sensor platform
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.info("Successfully unloaded config entry: %s", entry.entry_id)
    else:
        _LOGGER.warning("Failed to unload platforms for entry: %s", entry.entry_id)
    
    return unload_ok