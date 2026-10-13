"""万象盒子配置流。

设计要点：
- ``BaseMyriadBoxFlow`` 作为纯 mixin，只承载 ConfigFlow / OptionsFlow 共用逻辑
- ``unique_id`` 生成规则保持不变（包含 token 哈希，虽不理想但改了会破坏
  现有配置；后续版本可提供迁移脚本单独处理）
- ``_ensure_services_loaded`` 保留但退化为同步调用 ``discover_services``
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, List

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import DEVICE_MANUFACTURER, DOMAIN, SERVICE_REGISTRY, discover_services

_LOGGER = logging.getLogger(__name__)


class BaseMyriadBoxFlow:
    """配置流与选项流共用逻辑。"""

    def __init__(self) -> None:
        # 同步注册服务（discover_services 现在幂等且不做 IO）
        discover_services()
        self._selected_services: list[str] = []
        self._current_service_index = 0

    # ------------------------------------------------------------
    # 服务元数据
    # ------------------------------------------------------------
    def _get_service_options(self) -> dict[str, str]:
        return {
            service_id: service_class().name
            for service_id, service_class in SERVICE_REGISTRY.items()
        }

    def _get_default_enabled_services(self) -> list[str]:
        return list(SERVICE_REGISTRY.keys())

    # ------------------------------------------------------------
    # Schema 构建
    # ------------------------------------------------------------
    def _build_service_schema(
        self, service_id: str, current_data: dict[str, Any] | None = None
    ) -> vol.Schema:
        service_class = SERVICE_REGISTRY[service_id]
        service = service_class()
        schema_dict: dict[Any, Any] = {}

        for field, config in service.config_fields.items():
            field_key = (
                f"{service_id}_{field}_password"
                if config["type"] == "password"
                else f"{service_id}_{field}"
            )

            if self._should_skip_field(field, config):
                continue

            field_description = config.get("name", field)
            if "description" in config:
                field_description += f" - {config['description']}"

            default_value = self._resolve_default(
                field_key, service_id, field, current_data, config
            )

            schema_dict[vol.Optional(field_key, default=default_value,
                                     description=field_description)] = self._schema_validator(config, default_value)

        return vol.Schema(schema_dict)

    @staticmethod
    def _resolve_default(
        field_key: str,
        service_id: str,
        field: str,
        current_data: dict[str, Any] | None,
        config: dict[str, Any],
    ) -> Any:
        """从当前配置或字段默认值中取初始值。"""
        if current_data is None:
            return config.get("default")

        original_field_key = f"{service_id}_{field}"
        if original_field_key in current_data:
            return current_data[original_field_key]
        if field_key in current_data:
            return current_data[field_key]
        return config.get("default")

    @staticmethod
    def _schema_validator(
        config: dict[str, Any], default_value: Any
    ) -> vol.Schema:
        field_type = config["type"]
        if field_type == "str":
            return cv.string
        if field_type == "int":
            return vol.Coerce(int)
        if field_type == "select":
            return vol.In(config.get("options", []))
        if field_type == "password":
            return cv.string
        return cv.string

    @staticmethod
    def _should_skip_field(field: str, config: Dict) -> bool:
        skip_fields = ["url"]
        skip_descriptions = ["API地址", "官网地址"]
        if field in skip_fields:
            return True
        description = config.get("description", "")
        return any(skip_desc in description for skip_desc in skip_descriptions)

    # ------------------------------------------------------------
    # 描述与校验
    # ------------------------------------------------------------
    def _get_service_description_placeholders(self, service_id: str) -> dict[str, str]:
        service_class = SERVICE_REGISTRY[service_id]
        service = service_class()
        progress = f"进度: {self._current_service_index + 1}/{len(self._selected_services)}"
        return {
            "service_name": service.name,
            "current_step": str(self._current_service_index + 1),
            "total_steps": str(len(self._selected_services)),
            "config_help": f"{progress}\n{service.config_help}",
        }

    @staticmethod
    async def _validate_service_config(
        service_id: str, user_input: dict[str, Any]
    ) -> dict[str, str]:
        errors: dict[str, str] = {}
        service_class = SERVICE_REGISTRY[service_id]

        try:
            service_config: dict[str, Any] = {}
            for field, config in service_class().config_fields.items():
                original_field_key = f"{service_id}_{field}"
                password_field_key = f"{service_id}_{field}_password"

                if config["type"] == "password" and password_field_key in user_input:
                    service_config[field] = user_input[password_field_key]
                elif original_field_key in user_input:
                    service_config[field] = user_input[original_field_key]

            service_class.validate_config(service_config)
        except ValueError as e:
            errors["base"] = str(e)
        return errors

    @staticmethod
    def _process_password_fields(user_input: dict[str, Any]) -> dict[str, Any]:
        """把 ``_password`` 后缀字段映射回原始字段名。"""
        processed: dict[str, Any] = {}
        for key, value in user_input.items():
            if key.endswith("_password"):
                processed[key[:-len("_password")]] = value
            else:
                processed[key] = value
        return processed


# ============================================================
# ConfigFlow
# ============================================================
@config_entries.HANDLERS.register(DOMAIN)
class MyriadBoxConfigFlow(config_entries.ConfigFlow, BaseMyriadBoxFlow):
    """分步配置流。"""

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self) -> None:
        BaseMyriadBoxFlow.__init__(self)
        self._config_data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """第一步：选择启用的服务。"""
        self._async_abort_entries_match()

        if user_input is not None:
            self._selected_services = list(user_input["selected_services"])
            if not self._selected_services:
                return self.async_show_form(
                    step_id="user",
                    data_schema=vol.Schema({
                        vol.Required("selected_services"): cv.multi_select(
                            self._get_service_options()
                        )
                    }),
                    errors={"base": "no_services_selected"},
                )
            self._current_service_index = 0
            return await self.async_step_service_config()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(
                    "selected_services",
                    default=self._get_default_enabled_services(),
                    description="选择要配置的服务",
                ): cv.multi_select(self._get_service_options())
            }),
            description_placeholders={
                "services_count": str(len(SERVICE_REGISTRY))
            },
        )

    async def async_step_service_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """第二步：逐个配置选中的服务。"""
        if self._current_service_index >= len(self._selected_services):
            return await self.async_step_final()

        service_id = self._selected_services[self._current_service_index]

        if user_input is not None:
            processed = self._process_password_fields(user_input)
            errors = await self._validate_service_config(service_id, processed)
            if errors:
                return self.async_show_form(
                    step_id="service_config",
                    data_schema=self._build_service_schema(service_id),
                    errors=errors,
                    description_placeholders=self._get_service_description_placeholders(
                        service_id
                    ),
                )
            self._config_data.update(processed)
            self._config_data[f"enable_{service_id}"] = True
            self._current_service_index += 1
            return await self.async_step_service_config()

        return self.async_show_form(
            step_id="service_config",
            data_schema=self._build_service_schema(service_id),
            description_placeholders=self._get_service_description_placeholders(
                service_id
            ),
        )

    async def async_step_final(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """第三步：确认配置。"""
        if user_input is not None:
            return await self._async_create_entry()

        service_names = [
            SERVICE_REGISTRY[sid]().name for sid in self._selected_services
        ]
        return self.async_show_form(
            step_id="final",
            data_schema=vol.Schema({}),
            description_placeholders={
                "services_list": "\n".join(f"• {n}" for n in service_names),
                "services_count": str(len(self._selected_services)),
            },
        )

    async def _async_create_entry(self) -> FlowResult:
        """落库。"""
        for service_id in SERVICE_REGISTRY:
            if service_id not in self._selected_services:
                self._config_data[f"enable_{service_id}"] = False

        # ⚠️ 兼容性说明：unique_id 依赖 md5(sorted(config_data.items()))，
        # 配置内容（含 token）参与哈希。改成仅基于服务集合会更干净，
        # 但会导致旧 ConfigEntry 的 unique_id 变化，触发 HA 要求用户
        # 重新走一次配置流程。保留原逻辑，避免升级即破坏。
        unique_id = hashlib.md5(
            str(sorted(self._config_data.items())).encode()
        ).hexdigest()

        await self.async_set_unique_id(f"myraid_box_{unique_id}")
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=DEVICE_MANUFACTURER,
            data=self._config_data,
            description=f"已启用 {len(self._selected_services)} 个服务",
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> MyriadBoxOptionsFlow:
        return MyriadBoxOptionsFlow(config_entry)


# ============================================================
# OptionsFlow
# ============================================================
class MyriadBoxOptionsFlow(config_entries.OptionsFlow, BaseMyriadBoxFlow):
    """选项流 —— 通过勾选状态直接管理服务。"""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        BaseMyriadBoxFlow.__init__(self)
        self._config_entry = config_entry
        self._updated_config = dict(config_entry.data)
        self._previous_config = dict(config_entry.data)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """第一步：选择启用/禁用的服务。"""
        if user_input is not None:
            selected: list[str] = []
            for service_id in SERVICE_REGISTRY:
                enable_key = f"enable_{service_id}"
                is_enabled = bool(user_input.get(enable_key, False))
                self._updated_config[enable_key] = is_enabled
                if is_enabled:
                    selected.append(service_id)

            if selected:
                self._selected_services = selected
                self._current_service_index = 0
                return await self.async_step_service_config()
            return await self._async_finish()

        schema_dict: dict[Any, Any] = {}
        for service_id, service_class in SERVICE_REGISTRY.items():
            service = service_class()
            is_enabled = self._updated_config.get(f"enable_{service_id}", False)
            schema_dict[vol.Optional(
                f"enable_{service_id}", default=is_enabled,
                description=f"{service.description}",
            )] = bool

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={
                "total_count": str(len(SERVICE_REGISTRY))
            },
        )

    async def async_step_service_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """第二步：更新选中服务的参数。"""
        if self._current_service_index >= len(self._selected_services):
            return await self._async_finish()

        service_id = self._selected_services[self._current_service_index]

        if user_input is not None:
            processed = self._process_password_fields(user_input)
            errors = await self._validate_service_config(service_id, processed)
            if errors:
                return self.async_show_form(
                    step_id="service_config",
                    data_schema=self._build_service_schema(
                        service_id, self._updated_config
                    ),
                    errors=errors,
                    description_placeholders=self._get_service_description_placeholders(
                        service_id
                    ),
                )
            self._updated_config.update(processed)
            self._current_service_index += 1
            return await self.async_step_service_config()

        return self.async_show_form(
            step_id="service_config",
            data_schema=self._build_service_schema(
                service_id, self._updated_config
            ),
            description_placeholders=self._get_service_description_placeholders(
                service_id
            ),
        )

    async def _async_finish(self) -> FlowResult:
        """完成选项流：更新配置 → 清理 → 重载。"""
        self.hass.config_entries.async_update_entry(
            self._config_entry, data=self._updated_config
        )

        # 清理被禁用的服务对应的实体/设备
        from . import async_cleanup_disabled_services

        async_cleanup_disabled_services(
            self.hass, self._config_entry, self._previous_config
        )

        await self.hass.config_entries.async_reload(self._config_entry.entry_id)

        return self.async_create_entry(title="选项已更新", data={})
