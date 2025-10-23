from __future__ import annotations
from typing import Any, Dict, List
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
    """优雅的分步配置流"""

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self) -> None:
        """初始化配置流"""
        self._config_data = {}
        self._services_loaded = False
        self._selected_services: List[str] = []
        self._current_service_index = 0

    async def async_step_user(self, user_input: Dict[str, Any] = None) -> FlowResult:
        """第一步：选择要配置的服务"""
        self._async_abort_entries_match()
        
        # 确保服务已加载
        if not self._services_loaded:
            services_dir = str(Path(__file__).parent / "services")
            await discover_services(self.hass, services_dir)
            self._services_loaded = True

        if user_input is not None:
            self._selected_services = user_input["selected_services"]
            if not self._selected_services:
                return self.async_show_form(
                    step_id="user",
                    data_schema=vol.Schema({
                        vol.Required("selected_services"): cv.multi_select(
                            self._get_service_options()
                        )
                    }),
                    errors={"base": "no_services_selected"}
                )
            self._current_service_index = 0
            return await self.async_step_service_config()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(
                    "selected_services",
                    default=self._get_default_enabled_services(),
                    description="选择要配置的服务"
                ): cv.multi_select(self._get_service_options())
            }),
            description_placeholders={
                "services_count": str(len(SERVICE_REGISTRY))
            }
        )

    async def async_step_service_config(self, user_input: Dict[str, Any] = None) -> FlowResult:
        """第二步：逐个配置选中的服务"""
        if self._current_service_index >= len(self._selected_services):
            return await self.async_step_final()

        service_id = self._selected_services[self._current_service_index]
        service_class = SERVICE_REGISTRY[service_id]
        service = service_class()

        if user_input is not None:
            # 验证并保存配置
            errors = await self._validate_service_config(service_id, user_input)
            if errors:
                return self.async_show_form(
                    step_id="service_config",
                    data_schema=self._build_service_schema(service_id),
                    errors=errors,
                    description_placeholders=self._get_service_description_placeholders(service_id)
                )
            
            # 保存配置并前进到下一个服务
            self._config_data.update(user_input)
            self._config_data[f"enable_{service_id}"] = True
            self._current_service_index += 1
            return await self.async_step_service_config()

        return self.async_show_form(
            step_id="service_config",
            data_schema=self._build_service_schema(service_id),
            description_placeholders=self._get_service_description_placeholders(service_id)
        )

    def _get_service_description_placeholders(self, service_id: str) -> Dict[str, str]:
        """获取服务的描述占位符"""
        service_class = SERVICE_REGISTRY[service_id]
        service = service_class()
        
        # 进度信息单独一行，配置说明在下面
        progress_info = f"进度: {self._current_service_index + 1}/{len(self._selected_services)}"
        combined_help = f"{progress_info}\n{service.config_help}"
        
        return {
            "service_name": service.name,
            "current_step": f"{self._current_service_index + 1}",
            "total_steps": f"{len(self._selected_services)}",
            "config_help": combined_help
        }

    async def async_step_final(self, user_input: Dict[str, Any] = None) -> FlowResult:
        """最后一步：确认配置"""
        if user_input is not None:
            return await self._async_create_entry()

        # 显示配置摘要
        service_names = []
        for service_id in self._selected_services:
            service_class = SERVICE_REGISTRY[service_id]
            service_names.append(service_class().name)

        return self.async_show_form(
            step_id="final",
            data_schema=vol.Schema({}),
            description_placeholders={
                "services_list": "\n".join([f"• {name}" for name in service_names]),
                "services_count": str(len(self._selected_services))
            }
        )

    def _build_service_schema(self, service_id: str) -> vol.Schema:
        """构建单个服务的配置表单"""
        service_class = SERVICE_REGISTRY[service_id]
        service = service_class()
        schema_dict = {}

        for field, config in service.config_fields.items():
            field_key = f"{service_id}_{field}"
            
            if self._should_skip_field(field, config):
                continue
                
            field_description = config.get('name', field)
            
            # 为天气服务的字段添加紧凑的描述
            if service_id == "weather":
                if field == "private_key":
                    field_description = "EdDSA私钥 (PEM格式)"
                elif field == "project_id":
                    field_description = "项目ID"
                elif field == "key_id":
                    field_description = "密钥ID"
                elif field == "api_host":
                    field_description = "API主机"
                elif field == "location":
                    field_description = "城市名称"
                elif field == "interval":
                    field_description = "更新间隔"
            elif 'description' in config:
                field_description += f" - {config['description']}"
            
            default_value = config.get("default")
            
            if config["type"] == "str":
                schema_dict[vol.Optional(
                    field_key,
                    default=default_value or "",
                    description=field_description
                )] = cv.string
            elif config["type"] == "int":
                schema_dict[vol.Optional(
                    field_key,
                    default=default_value or 10,
                    description=field_description
                )] = vol.Coerce(int)
            elif config["type"] == "select":
                schema_dict[vol.Optional(
                    field_key,
                    default=default_value or "",
                    description=field_description
                )] = vol.In(config.get("options", []))
            elif config["type"] == "password":
                # 使用密码字段类型，隐藏输入内容
                schema_dict[vol.Optional(
                    field_key,
                    default=default_value or "",
                    description=field_description
                )] = cv.string

        return vol.Schema(schema_dict)

    async def _validate_service_config(self, service_id: str, user_input: Dict[str, Any]) -> Dict[str, str]:
        """验证单个服务的配置"""
        errors = {}
        service_class = SERVICE_REGISTRY[service_id]
        
        try:
            service_config = {
                k.replace(f"{service_id}_", ""): v 
                for k, v in user_input.items() 
                if k.startswith(f"{service_id}_")
            }
            service_class.validate_config(service_config)
        except ValueError as e:
            errors["base"] = str(e)
            
        return errors

    def _get_service_options(self) -> Dict[str, str]:
        """获取服务选项"""
        options = {}
        for service_id, service_class in SERVICE_REGISTRY.items():
            service = service_class()
            options[service_id] = service.name
        return options

    def _get_default_enabled_services(self) -> List[str]:
        """获取默认启用的服务"""
        return list(SERVICE_REGISTRY.keys())

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

    async def _async_create_entry(self) -> FlowResult:
        """创建配置条目"""
        # 确保未选择的服务被禁用
        for service_id in SERVICE_REGISTRY.keys():
            if service_id not in self._selected_services:
                self._config_data[f"enable_{service_id}"] = False
        
        # 生成唯一ID
        unique_id = hashlib.md5(
            str(sorted(self._config_data.items())).encode()
        ).hexdigest()
        
        await self.async_set_unique_id(f"myraid_box_{unique_id}")
        self._abort_if_unique_id_configured()
        
        return self.async_create_entry(
            title=f"{DEVICE_MANUFACTURER}",
            data=self._config_data,
            description=f"已启用 {len(self._selected_services)} 个服务"
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """创建选项流"""
        return MyriadBoxOptionsFlow(config_entry)


class MyriadBoxOptionsFlow(config_entries.OptionsFlow):
    """优雅的选项配置流"""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """初始化选项流"""
        self.config_entry = config_entry
        self._services_loaded = False
        self._current_service_index = 0
        self._enabled_services: List[str] = []
        self._selected_services: List[str] = []

    async def async_step_init(self, user_input: Dict[str, Any] = None) -> FlowResult:
        """第一步：选择要修改的服务"""
        if not self._services_loaded:
            services_dir = str(Path(__file__).parent / "services")
            await discover_services(self.hass, services_dir)
            self._services_loaded = True

        # 获取当前启用的服务
        self._enabled_services = [
            service_id for service_id in SERVICE_REGISTRY.keys()
            if self.config_entry.data.get(f"enable_{service_id}", False)
        ]

        if user_input is not None:
            selected_services = user_input["selected_services"]
            if not selected_services:
                return self.async_show_form(
                    step_id="init",
                    data_schema=vol.Schema({
                        vol.Required("selected_services"): cv.multi_select(
                            self._get_service_options()
                        )
                    }),
                    errors={"base": "no_services_selected"}
                )
            
            self._selected_services = selected_services
            self._current_service_index = 0
            return await self.async_step_service_config()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(
                    "selected_services",
                    default=self._enabled_services,
                    description="选择要修改配置的服务"
                ): cv.multi_select(self._get_service_options())
            })
        )

    async def async_step_service_config(self, user_input: Dict[str, Any] = None) -> FlowResult:
        """第二步：逐个配置选中的服务"""
        if self._current_service_index >= len(self._selected_services):
            return await self.async_step_final()

        service_id = self._selected_services[self._current_service_index]
        service_class = SERVICE_REGISTRY[service_id]
        service = service_class()

        if user_input is not None:
            # 验证配置
            errors = await self._validate_service_config(service_id, user_input)
            if errors:
                return self.async_show_form(
                    step_id="service_config",
                    data_schema=self._build_service_schema(service_id),
                    errors=errors,
                    description_placeholders=self._get_service_description_placeholders(service_id)
                )
            
            # 更新配置并前进
            updated_data = dict(self.config_entry.data)
            updated_data.update(user_input)
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=updated_data
            )
            
            self._current_service_index += 1
            return await self.async_step_service_config()

        return self.async_show_form(
            step_id="service_config",
            data_schema=self._build_service_schema(service_id),
            description_placeholders=self._get_service_description_placeholders(service_id)
        )

    def _get_service_description_placeholders(self, service_id: str) -> Dict[str, str]:
        """获取服务的描述占位符"""
        service_class = SERVICE_REGISTRY[service_id]
        service = service_class()
        
        base_placeholders = {
            "service_name": service.name,
            "current_step": f"{self._current_service_index + 1}",
            "total_steps": f"{len(self._selected_services)}"
        }
        
        # 为天气服务添加紧凑的配置说明
        if service_id == "weather":
            base_placeholders.update({
                "config_help": (
                    "🌤️ 天气服务配置说明：\n"
                    "1. 注册和风天气开发者账号：https://dev.qweather.com/\n"
                    "2. 创建项目获取项目ID、密钥ID和EdDSA私钥\n"
                    "3. 城市名称支持中文、拼音或LocationID"
                )
            })
        else:
            base_placeholders["config_help"] = f"配置 {service.name} 的相关参数"
            
        return base_placeholders

    async def async_step_final(self, user_input: Dict[str, Any] = None) -> FlowResult:
        """最后一步：完成配置"""
        # 触发重新加载
        await self.hass.config_entries.async_reload(self.config_entry.entry_id)
        return self.async_create_entry(title="", data=None)

    def _build_service_schema(self, service_id: str) -> vol.Schema:
        """构建单个服务的配置表单"""
        service_class = SERVICE_REGISTRY[service_id]
        service = service_class()
        schema_dict = {}
        current_data = self.config_entry.data

        for field, config in service.config_fields.items():
            field_key = f"{service_id}_{field}"
            
            if self._should_skip_field(field, config):
                continue
                
            field_description = config.get('name', field)
            
            # 为天气服务的字段添加紧凑的描述
            if service_id == "weather":
                if field == "private_key":
                    field_description = "EdDSA私钥 (PEM格式)"
                elif field == "project_id":
                    field_description = "项目ID"
                elif field == "key_id":
                    field_description = "密钥ID"
                elif field == "api_host":
                    field_description = "API主机"
                elif field == "location":
                    field_description = "城市名称"
                elif field == "interval":
                    field_description = "更新间隔"
            elif 'description' in config:
                field_description += f" - {config['description']}"
            
            default_value = current_data.get(field_key, config.get("default"))
            
            if config["type"] == "str":
                schema_dict[vol.Optional(
                    field_key,
                    default=default_value or "",
                    description=field_description
                )] = cv.string
            elif config["type"] == "int":
                schema_dict[vol.Optional(
                    field_key,
                    default=int(default_value) if default_value else config.get("default", 10),
                    description=field_description
                )] = vol.Coerce(int)
            elif config["type"] == "select":
                schema_dict[vol.Optional(
                    field_key,
                    default=default_value or config.get("default", ""),
                    description=field_description
                )] = vol.In(config.get("options", []))
            elif config["type"] == "password":
                # 使用密码字段类型，隐藏输入内容
                schema_dict[vol.Optional(
                    field_key,
                    default=default_value or "",
                    description=field_description
                )] = cv.string

        return vol.Schema(schema_dict)

    async def _validate_service_config(self, service_id: str, user_input: Dict[str, Any]) -> Dict[str, str]:
        """验证单个服务的配置"""
        errors = {}
        service_class = SERVICE_REGISTRY[service_id]
        
        try:
            service_config = {
                k.replace(f"{service_id}_", ""): v 
                for k, v in user_input.items() 
                if k.startswith(f"{service_id}_")
            }
            service_class.validate_config(service_config)
        except ValueError as e:
            errors["base"] = str(e)
            
        return errors

    def _get_service_options(self) -> Dict[str, str]:
        """获取服务选项"""
        options = {}
        for service_id, service_class in SERVICE_REGISTRY.items():
            service = service_class()
            options[service_id] = service.name
        return options

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