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
    
    VERSION = 2
    _services_order: List[str] = []
    _current_service_index: int = 0
    _config_data: Dict[str, Any] = {}

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """第一步：初始化流程"""
        self._services_order = sorted(
            SERVICE_REGISTRY.keys(),
            key=lambda x: SERVICE_REGISTRY[x]().name
        )
        self._current_service_index = 0
        self._config_data = {}
        
        if not self._services_order:
            return self.async_abort(reason="no_services")
            
        return await self._async_handle_next_service()

    async def _async_handle_next_service(self) -> FlowResult:
        if self._current_service_index >= len(self._services_order):
            if not any(v for k, v in self._config_data.items() if k.startswith("enable_")):
                return self.async_abort(reason="no_services_selected")
            return self.async_create_entry(title="万象盒子", data=self._config_data)
        
        service_id = self._services_order[self._current_service_index]
        return await self._async_step_service_config(service_id)

    async def _async_step_service_config(self, service_id: str) -> FlowResult:
        service_class = SERVICE_REGISTRY.get(service_id)
        if not service_class:
            return self.async_abort(reason="invalid_service")
        
        service = service_class()
        fields = service.config_fields
        
        # 构建表单字段（标签和描述通过翻译文件提供）
        schema_fields = {
            vol.Required(
                f"enable_{service_id}",
                default=self._config_data.get(f"enable_{service_id}", False)
            ): bool
        }
        
        if fields:
            for field, field_config in fields.items():
                field_key = f"{service_id}_{field}"
                
                # 根据字段类型创建验证器
                field_type = field_config.get("type", "str").lower()
                if field_type == "bool":
                    schema_fields[vol.Optional(
                        field_key,
                        default=self._config_data.get(field_key, field_config.get("default", False))
                    )] = bool
                elif field_type == "int":
                    schema_fields[vol.Optional(
                        field_key,
                        default=self._config_data.get(field_key, field_config.get("default", 0))
                    )] = int
                elif field_type == "password":
                    schema_fields[vol.Optional(
                        field_key,
                        default=self._config_data.get(field_key, field_config.get("default", ""))
                    )] = str
                else:  # 默认为字符串类型
                    schema_fields[vol.Optional(
                        field_key,
                        default=self._config_data.get(field_key, field_config.get("default", ""))
                    )] = str

        return self.async_show_form(
            step_id="service_config",
            data_schema=vol.Schema(schema_fields),
            description_placeholders={
                "service_name": service.name,
                "current_step": f"{self._current_service_index + 1}/{len(self._services_order)}"
            }
        )

    async def async_step_service_config(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        if user_input is None:
            return await self._async_handle_next_service()
        
        # 处理用户输入
        self._config_data.update(user_input)
        service_id = self._services_order[self._current_service_index]
        
        # 如果禁用服务，清除相关配置
        if not user_input.get(f"enable_{service_id}", False):
            keys_to_remove = [k for k in self._config_data.keys() if k.startswith(f"{service_id}_")]
            for key in keys_to_remove:
                self._config_data.pop(key, None)
        
        self._current_service_index += 1
        return await self._async_handle_next_service()

    def _get_field_type(self, field_type: str):
        """辅助方法：将字段类型字符串转换为Python类型"""
        type_map = {
            "str": str,
            "int": int,
            "bool": bool,
            "password": str
        }
        return type_map.get(field_type.lower(), str)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> MyraidBoxOptionsFlow:
        """创建选项配置流"""
        return MyraidBoxOptionsFlow(config_entry)

class MyraidBoxOptionsFlow(config_entries.OptionsFlow):
    """万象盒子选项配置流"""
    
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry
        self._config_data = dict(config_entry.data)
        self._services_order: List[str] = []
        self._current_service_index: int = 0

    async def async_step_init(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """初始化选项流程"""
        self._services_order = sorted(
            [k.replace("enable_", "") for k in self._config_data.keys() if k.startswith("enable_")],
            key=lambda x: SERVICE_REGISTRY[x]().name
        )
        self._current_service_index = 0
        
        if not self._services_order:
            return self.async_abort(reason="no_services")
            
        return await self._async_handle_next_service()

    async def _async_handle_next_service(self) -> FlowResult:
        """处理下一个服务配置"""
        if self._current_service_index >= len(self._services_order):
            # 更新配置项
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=self._config_data
            )
            return self.async_create_entry(title="", data=None)
        
        service_id = self._services_order[self._current_service_index]
        return await self._async_step_service_config(service_id)

    async def _async_step_service_config(self, service_id: str) -> FlowResult:
        """单个服务的配置步骤"""
        service_class = SERVICE_REGISTRY.get(service_id)
        if not service_class:
            return self.async_abort(reason="invalid_service")
        
        service = service_class()
        fields = service.config_fields
        
        schema_fields = {
            vol.Required(
                f"enable_{service_id}",
                default=self._config_data.get(f"enable_{service_id}", False)
            ): bool
        }
        
        if fields:
            for field, field_config in fields.items():
                field_key = f"{service_id}_{field}"
                field_type = field_config.get("type", "str").lower()
                
                if field_type == "bool":
                    schema_fields[vol.Optional(
                        field_key,
                        default=self._config_data.get(field_key, field_config.get("default", False))
                    )] = bool
                elif field_type == "int":
                    schema_fields[vol.Optional(
                        field_key,
                        default=self._config_data.get(field_key, field_config.get("default", 0))
                    )] = int
                elif field_type == "password":
                    schema_fields[vol.Optional(
                        field_key,
                        default=self._config_data.get(field_key, field_config.get("default", ""))
                    )] = str
                else:
                    schema_fields[vol.Optional(
                        field_key,
                        default=self._config_data.get(field_key, field_config.get("default", ""))
                    )] = str

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
        service_id = self._services_order[self._current_service_index]
        
        if not user_input.get(f"enable_{service_id}", False):
            keys_to_remove = [k for k in self._config_data.keys() if k.startswith(f"{service_id}_")]
            for key in keys_to_remove:
                self._config_data.pop(key, None)
        
        self._current_service_index += 1
        return await self._async_handle_next_service()