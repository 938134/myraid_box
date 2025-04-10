from __future__ import annotations
import logging
from typing import Any, Dict, Optional, List
from homeassistant import config_entries
from homeassistant.core import callback, HomeAssistant
from homeassistant.data_entry_flow import FlowResult
import voluptuous as vol
from .const import DOMAIN, SERVICE_REGISTRY

_LOGGER = logging.getLogger(__name__)

class MyraidBoxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """万象盒子配置流程"""
    
    VERSION = 1
    _services_order: List[str] = []
    _current_service_index: int = 0
    _config_data: Dict[str, Any] = {}

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """第一步：服务选择"""
        if user_input is not None:
            if not any(v for k, v in user_input.items() if k.startswith("enable_")):
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._get_services_schema(),
                    errors={"base": "at_least_one_service"}
                )
            
            # 存储用户输入并准备下一步
            self._config_data.update(user_input)
            self._services_order = [
                k.replace("enable_", "") 
                for k, v in user_input.items() 
                if k.startswith("enable_") and v
            ]
            self._current_service_index = 0
            
            # 如果没有需要配置的服务，直接创建条目
            if not self._services_order:
                return self.async_create_entry(title="万象盒子", data=self._config_data)
                
            return await self._async_handle_next_service()
    
        return self.async_show_form(
            step_id="user",
            data_schema=self._get_services_schema(),
            description_placeholders={
                "title": "服务选择",
                "description": "请选择需要启用的服务"
            }
        )

    def _get_services_schema(self) -> vol.Schema:
        """获取服务选择表单"""
        schema = {}
        for service_id in SERVICE_REGISTRY:
            service_class = SERVICE_REGISTRY.get(service_id)
            if service_class:
                service = service_class()
                schema[vol.Optional(
                    f"enable_{service_id}",
                    default=False,
                    description=f"启用 {service.name}"
                )] = bool
        return vol.Schema(schema)

    async def _async_handle_next_service(self) -> FlowResult:
        """处理下一个服务配置"""
        if self._current_service_index >= len(self._services_order):
            return self.async_create_entry(title="万象盒子", data=self._config_data)
        
        service_id = self._services_order[self._current_service_index]
        return await self._async_step_service_config(service_id)

    async def _async_step_service_config(self, service_id: str) -> FlowResult:
        """服务配置步骤"""
        service_class = SERVICE_REGISTRY.get(service_id)
        if not service_class:
            return self.async_abort(reason="invalid_service")
        
        service = service_class()
        fields = service.config_fields
        
        if not fields:
            self._current_service_index += 1
            return await self._async_handle_next_service()

        schema_fields = {}
        for field, field_config in fields.items():
            field_key = f"{service_id}_{field}"
            schema_fields[vol.Required(
                field_key,
                default=self._config_data.get(field_key, field_config.get("default")),
                description=field_config.get("description", field)
            )] = self._get_field_type(field_config.get("type", "str"))

        return self.async_show_form(
            step_id="service_config",
            data_schema=vol.Schema(schema_fields),
            description_placeholders={
                "service_name": service.name,
                "current_step": f"{self._current_service_index + 1}/{len(self._services_order)}"
            }
        )

    async def async_step_service_config(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """处理服务配置提交"""
        if user_input is None:
            return await self._async_handle_next_service()
        
        self._config_data.update(user_input)
        self._current_service_index += 1
        return await self._async_handle_next_service()

    def _get_field_type(self, field_type: str):
        """字段类型映射"""
        return {
            "str": str,
            "int": int,
            "bool": bool,
            "password": str
        }.get(field_type.lower(), str)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> MyraidBoxOptionsFlow:
        return MyraidBoxOptionsFlow(config_entry)

class MyraidBoxOptionsFlow(config_entries.OptionsFlow):
    """万象盒子选项配置"""
    
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry
        self._config_data = dict(config_entry.data)
        self._services_order: List[str] = []
        self._current_service_index: int = 0

    async def async_step_init(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """初始化选项流程"""
        self._services_order = [
            k.replace("enable_", "") 
            for k, v in self._config_data.items() 
            if k.startswith("enable_") and v
        ]
        self._current_service_index = 0
        return await self._async_handle_next_service()

    async def _async_handle_next_service(self) -> FlowResult:
        """处理下一个服务配置"""
        if self._current_service_index >= len(self._services_order):
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=self._config_data
            )
            return self.async_create_entry(title="", data=None)
        
        service_id = self._services_order[self._current_service_index]
        return await self._async_step_service_config(service_id)

    async def _async_step_service_config(self, service_id: str) -> FlowResult:
        """服务配置步骤"""
        service_class = SERVICE_REGISTRY.get(service_id)
        if not service_class:
            return self.async_abort(reason="invalid_service")
        
        service = service_class()
        fields = service.config_fields
        
        if not fields:
            self._current_service_index += 1
            return await self._async_handle_next_service()

        schema_fields = {}
        for field, field_config in fields.items():
            field_key = f"{service_id}_{field}"
            schema_fields[vol.Required(
                field_key,
                default=self._config_data.get(field_key, field_config.get("default")),
                description=field_config.get("description", field)
            )] = self._get_field_type(field_config.get("type", "str"))

        return self.async_show_form(
            step_id="service_config",
            data_schema=vol.Schema(schema_fields),
            description_placeholders={
                "service_name": service.name,
                "current_step": f"{self._current_service_index + 1}/{len(self._services_order)}"
            }
        )

    async def async_step_service_config(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """处理服务配置提交"""
        if user_input is None:
            return await self._async_handle_next_service()
        
        self._config_data.update(user_input)
        self._current_service_index += 1
        return await self._async_handle_next_service()

    def _get_field_type(self, field_type: str):
        """字段类型映射"""
        return {
            "str": str,
            "int": int,
            "bool": bool,
            "password": str
        }.get(field_type.lower(), str)