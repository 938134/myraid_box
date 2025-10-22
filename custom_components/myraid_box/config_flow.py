from __future__ import annotations
from typing import Any, Dict
import hashlib
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv
from pathlib import Path

from .const import DOMAIN, DEVICE_MANUFACTURER, SERVICE_REGISTRY, discover_services

@config_entries.HANDLERS.register(DOMAIN)
class MyriadBoxConfigFlow(config_entries.ConfigFlow):
    """极简配置流 - 单页完成所有服务配置"""

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self) -> None:
        """初始化配置流"""
        self._config_data = {}
        self._services_loaded = False

    async def async_step_user(self, user_input: Dict[str, Any] = None) -> FlowResult:
        """处理用户配置步骤 - 单页完成所有配置"""
        self._async_abort_entries_match()
        
        # 确保服务已加载
        if not self._services_loaded:
            services_dir = str(Path(__file__).parent / "services")
            await discover_services(self.hass, services_dir)
            self._services_loaded = True

        errors = {}
        if user_input is not None:
            # 验证配置
            errors = await self._validate_config(user_input)
            if not errors:
                return await self._async_create_entry(user_input)

        # 构建动态表单
        schema = await self._build_dynamic_schema()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(schema),
            errors=errors,
            description_placeholders={
                "services_count": str(len(SERVICE_REGISTRY))
            }
        )

    async def _build_dynamic_schema(self) -> Dict:
        """构建动态配置表单"""
        schema = {}
        
        for service_id, service_class in SERVICE_REGISTRY.items():
            service = service_class()
            
            # 添加启用开关
            schema[vol.Optional(
                f"enable_{service_id}",
                default=True,
                description=f"启用 {service.name}"
            )] = bool

            # 动态添加服务的配置字段
            for field, config in service.config_fields.items():
                field_key = f"{service_id}_{field}"
                
                # 跳过不需要显示的字段
                if self._should_skip_field(field, config):
                    continue
                    
                # 组合字段描述
                field_description = f"{config.get('name', field)}"
                if 'description' in config:
                    field_description += f" - {config['description']}"
                
                # 根据字段类型构建表单元素
                if config["type"] == "str":
                    schema[vol.Optional(
                        field_key,
                        default=config.get("default", ""),
                        description=field_description
                    )] = cv.string
                elif config["type"] == "int":
                    schema[vol.Optional(
                        field_key,
                        default=config.get("default", 10),
                        description=field_description
                    )] = vol.Coerce(int)
                elif config["type"] == "select":
                    schema[vol.Optional(
                        field_key,
                        default=config.get("default", ""),
                        description=field_description
                    )] = vol.In(config.get("options", []))
                elif config["type"] == "password":
                    schema[vol.Optional(
                        field_key,
                        default=config.get("default", ""),
                        description=field_description
                    )] = cv.string

        return schema

    def _should_skip_field(self, field: str, config: Dict) -> bool:
        """判断是否跳过该字段"""
        skip_fields = ["url"]
        skip_descriptions = ["API地址", "官网地址"]
        
        if field in skip_fields:
            return True
            
        description = config.get('description', '')
        if any(skip_desc in description for skip_desc in skip_descriptions):
            return True
            
        return False

    async def _validate_config(self, user_input: Dict[str, Any]) -> Dict[str, str]:
        """验证用户输入"""
        errors = {}
        
        # 检查是否至少启用了一个服务
        enabled_services = [
            service_id for service_id in SERVICE_REGISTRY.keys()
            if user_input.get(f"enable_{service_id}", False)
        ]
        
        if not enabled_services:
            errors["base"] = "no_services_selected"
            return errors

        # 验证各个服务的配置
        for service_id in enabled_services:
            service_class = SERVICE_REGISTRY[service_id]
            # 使用类方法验证配置
            try:
                service_config = {
                    k.replace(f"{service_id}_", ""): v 
                    for k, v in user_input.items() 
                    if k.startswith(f"{service_id}_")
                }
                service_class.validate_config(service_config)
            except ValueError as e:
                errors[f"enable_{service_id}"] = str(e)

        return errors

    async def _async_create_entry(self, user_input: Dict[str, Any]) -> FlowResult:
        """创建配置条目"""
        # 生成唯一ID
        unique_id = hashlib.md5(
            str(sorted(user_input.items())).encode()
        ).hexdigest()
        
        await self.async_set_unique_id(f"myraid_box_{unique_id}")
        self._abort_if_unique_id_configured()
        
        return self.async_create_entry(
            title=f"{DEVICE_MANUFACTURER}",
            data=user_input,
            description=f"已启用 {len([k for k in user_input if k.startswith('enable_') and user_input[k]])} 个服务"
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """创建选项流"""
        return MyriadBoxOptionsFlow(config_entry)


class MyriadBoxOptionsFlow(config_entries.OptionsFlow):
    """极简选项流 - 复用主配置逻辑"""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """初始化选项流"""
        self.config_entry = config_entry
        self._services_loaded = False

    async def async_step_init(self, user_input: Dict[str, Any] = None) -> FlowResult:
        """初始化选项配置"""
        # 确保服务已加载
        if not self._services_loaded:
            services_dir = str(Path(__file__).parent / "services")
            await discover_services(self.hass, services_dir)
            self._services_loaded = True

        errors = {}
        if user_input is not None:
            errors = await self._validate_config(user_input)
            if not errors:
                return await self._async_update_entry(user_input)

        # 构建动态表单（使用当前配置作为默认值）
        schema = await self._build_dynamic_schema()
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema),
            errors=errors
        )

    async def _build_dynamic_schema(self) -> Dict:
        """构建动态配置表单（使用当前配置值）"""
        schema = {}
        current_data = self.config_entry.data
        
        for service_id, service_class in SERVICE_REGISTRY.items():
            service = service_class()
            
            # 添加启用开关（使用当前值）
            schema[vol.Optional(
                f"enable_{service_id}",
                default=current_data.get(f"enable_{service_id}", True),
                description=f"启用 {service.name}"
            )] = bool

            # 动态添加服务的配置字段
            for field, config in service.config_fields.items():
                field_key = f"{service_id}_{field}"
                
                # 跳过不需要显示的字段
                if self._should_skip_field(field, config):
                    continue
                    
                # 组合字段描述
                field_description = f"{config.get('name', field)}"
                if 'description' in config:
                    field_description += f" - {config['description']}"
                
                # 使用当前配置值作为默认值
                default_value = current_data.get(field_key, config.get("default"))
                
                # 根据字段类型构建表单元素
                if config["type"] == "str":
                    schema[vol.Optional(
                        field_key,
                        default=default_value or "",
                        description=field_description
                    )] = cv.string
                elif config["type"] == "int":
                    schema[vol.Optional(
                        field_key,
                        default=int(default_value) if default_value else config.get("default", 10),
                        description=field_description
                    )] = vol.Coerce(int)
                elif config["type"] == "select":
                    schema[vol.Optional(
                        field_key,
                        default=default_value or config.get("default", ""),
                        description=field_description
                    )] = vol.In(config.get("options", []))
                elif config["type"] == "password":
                    schema[vol.Optional(
                        field_key,
                        default=default_value or "",
                        description=field_description
                    )] = cv.string

        return schema

    def _should_skip_field(self, field: str, config: Dict) -> bool:
        """判断是否跳过该字段"""
        skip_fields = ["url"]
        skip_descriptions = ["API地址", "官网地址"]
        
        if field in skip_fields:
            return True
            
        description = config.get('description', '')
        if any(skip_desc in description for skip_desc in skip_descriptions):
            return True
            
        return False

    async def _validate_config(self, user_input: Dict[str, Any]) -> Dict[str, str]:
        """验证用户输入"""
        errors = {}
        
        # 检查是否至少启用了一个服务
        enabled_services = [
            service_id for service_id in SERVICE_REGISTRY.keys()
            if user_input.get(f"enable_{service_id}", False)
        ]
        
        if not enabled_services:
            errors["base"] = "no_services_selected"
            return errors

        # 验证各个服务的配置
        for service_id in enabled_services:
            service_class = SERVICE_REGISTRY[service_id]
            # 使用类方法验证配置
            try:
                service_config = {
                    k.replace(f"{service_id}_", ""): v 
                    for k, v in user_input.items() 
                    if k.startswith(f"{service_id}_")
                }
                service_class.validate_config(service_config)
            except ValueError as e:
                errors[f"enable_{service_id}"] = str(e)

        return errors

    async def _async_update_entry(self, user_input: Dict[str, Any]) -> FlowResult:
        """更新配置条目"""
        # 更新配置条目数据
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data=user_input
        )
        
        # 触发重新加载以创建/移除实体
        await self.hass.config_entries.async_reload(self.config_entry.entry_id)
        
        return self.async_create_entry(title="", data=None)