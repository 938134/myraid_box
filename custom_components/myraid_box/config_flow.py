from __future__ import annotations
import logging
from typing import Any, Dict, Optional, List, TypedDict
from homeassistant import config_entries
from homeassistant.core import callback, HomeAssistant
from homeassistant.data_entry_flow import FlowResult
import voluptuous as vol
from .const import DOMAIN, SERVICE_REGISTRY

_LOGGER = logging.getLogger(__name__)

class FlowData(TypedDict):
    """Type for flow data storage."""
    services_order: List[str]
    current_service_index: int
    config_data: Dict[str, Any]

class MyraidBoxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Optimized config flow for Myraid Box."""
    
    VERSION = 2
    _flow_data: FlowData = {
        "services_order": [],
        "current_service_index": 0,
        "config_data": {}
    }

    async def async_step_user(
        self, 
        user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step."""
        self._flow_data["services_order"] = sorted(
            SERVICE_REGISTRY.keys(),
            key=lambda x: SERVICE_REGISTRY[x]().name
        )
        self._flow_data["current_service_index"] = 0
        self._flow_data["config_data"] = {}
        
        if not self._flow_data["services_order"]:
            return self.async_abort(reason="no_services")
            
        return await self._async_handle_next_service()

    async def _async_handle_next_service(self) -> FlowResult:
        """Handle moving to next service or completion."""
        if self._flow_data["current_service_index"] >= len(self._flow_data["services_order"]):
            if not any(
                v for k, v in self._flow_data["config_data"].items() 
                if k.startswith("enable_")
            ):
                return self.async_abort(reason="no_services_selected")
            return self.async_create_entry(
                title="万象盒子",
                data=self._flow_data["config_data"]
            )
        
        service_id = self._flow_data["services_order"][self._flow_data["current_service_index"]]
        return await self._async_step_service_config(service_id)

    async def _async_step_service_config(
        self, 
        service_id: str
    ) -> FlowResult:
        """Generate config form for a service."""
        service_class = SERVICE_REGISTRY.get(service_id)
        if not service_class:
            return self.async_abort(reason="invalid_service")
        
        service = service_class()
        fields = service.config_fields
        
        schema_fields = {
            vol.Required(
                f"enable_{service_id}",
                default=self._flow_data["config_data"].get(f"enable_{service_id}", False)
            ): bool
        }
        
        if fields:
            for field, field_config in fields.items():
                field_key = f"{service_id}_{field}"
                field_type = field_config.get("type", "str").lower()
                
                # Handle province selection
                if field == "province" and hasattr(service, "PROVINCE_MAP"):
                    schema_fields[vol.Optional(
                        field_key,
                        default=self._flow_data["config_data"].get(
                            field_key, 
                            field_config.get("default", "")
                        )
                    )] = vol.In(list(service.PROVINCE_MAP.keys()))
                # Handle other field types
                elif field_type == "bool":
                    schema_fields[vol.Optional(
                        field_key,
                        default=self._flow_data["config_data"].get(
                            field_key,
                            field_config.get("default", False)
                        )
                    )] = bool
                elif field_type == "int":
                    schema_fields[vol.Optional(
                        field_key,
                        default=self._flow_data["config_data"].get(
                            field_key,
                            field_config.get("default", 0)
                        )
                    )] = vol.Coerce(int)
                elif field_type == "password":
                    schema_fields[vol.Optional(
                        field_key,
                        default=self._flow_data["config_data"].get(
                            field_key,
                            field_config.get("default", "")
                        )
                    )] = str
                else:  # Default to string
                    schema_fields[vol.Optional(
                        field_key,
                        default=self._flow_data["config_data"].get(
                            field_key,
                            field_config.get("default", "")
                        )
                    )] = str

        return self.async_show_form(
            step_id="service_config",
            data_schema=vol.Schema(schema_fields),
            description_placeholders={
                "service_name": service.name,
                "current_step": (
                    f"{self._flow_data['current_service_index'] + 1}/"
                    f"{len(self._flow_data['services_order'])}"
                )
            }
        )

    async def async_step_service_config(
        self, 
        user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle service config submission."""
        if user_input is None:
            return await self._async_handle_next_service()
        
        self._flow_data["config_data"].update(user_input)
        service_id = self._flow_data["services_order"][self._flow_data["current_service_index"]]
        
        if not user_input.get(f"enable_{service_id}", False):
            # Clean up disabled service configs
            for key in list(self._flow_data["config_data"].keys()):
                if key.startswith(f"{service_id}_"):
                    del self._flow_data["config_data"][key]
        
        self._flow_data["current_service_index"] += 1
        return await self._async_handle_next_service()

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry
    ) -> MyraidBoxOptionsFlow:
        """Get the options flow."""
        return MyraidBoxOptionsFlow(config_entry)

class MyraidBoxOptionsFlow(config_entries.OptionsFlow):
    """Optimized options flow."""
    
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self._config_data = dict(config_entry.data)
        self._services_order: List[str] = []
        self._current_service_index: int = 0

    async def async_step_init(
        self, 
        user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Initialize the options flow."""
        self._services_order = sorted(
            [k.replace("enable_", "") for k in self._config_data.keys() 
             if k.startswith("enable_")],
            key=lambda x: SERVICE_REGISTRY[x]().name
        )
        self._current_service_index = 0
        
        if not self._services_order:
            return self.async_abort(reason="no_services")
            
        return await self._async_handle_next_service()

    async def _async_handle_next_service(self) -> FlowResult:
        """Handle moving to next service or completion."""
        if self._current_service_index >= len(self._services_order):
            # Update entry with new data
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=self._config_data
            )
            return self.async_create_entry(title="", data=None)
        
        service_id = self._services_order[self._current_service_index]
        return await self._async_step_service_config(service_id)

    async def _async_step_service_config(
        self, 
        service_id: str
    ) -> FlowResult:
        """Generate options form for a service."""
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
                
                # Handle province selection
                if field == "province" and hasattr(service, "PROVINCE_MAP"):
                    schema_fields[vol.Optional(
                        field_key,
                        default=self._config_data.get(
                            field_key, 
                            field_config.get("default", "")
                        )
                    )] = vol.In(list(service.PROVINCE_MAP.keys()))
                # Handle other field types
                elif field_type == "bool":
                    schema_fields[vol.Optional(
                        field_key,
                        default=self._config_data.get(
                            field_key,
                            field_config.get("default", False)
                        )
                    )] = bool
                elif field_type == "int":
                    schema_fields[vol.Optional(
                        field_key,
                        default=self._config_data.get(
                            field_key,
                            field_config.get("default", 0)
                        )
                    )] = vol.Coerce(int)
                elif field_type == "password":
                    schema_fields[vol.Optional(
                        field_key,
                        default=self._config_data.get(
                            field_key,
                            field_config.get("default", "")
                        )
                    )] = str
                else:  # Default to string
                    schema_fields[vol.Optional(
                        field_key,
                        default=self._config_data.get(
                            field_key,
                            field_config.get("default", "")
                        )
                    )] = str

        return self.async_show_form(
            step_id="service_config",
            data_schema=vol.Schema(schema_fields),
            description_placeholders={
                "service_name": service.name,
                "current_step": (
                    f"{self._current_service_index + 1}/"
                    f"{len(self._services_order)}"
                )
            }
        )

    async def async_step_service_config(
        self, 
        user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle service options submission."""
        if user_input is None:
            return await self._async_handle_next_service()
        
        service_id = self._services_order[self._current_service_index]
        old_enabled = self._config_data.get(f"enable_{service_id}", False)
        
        self._config_data.update(user_input)
        new_enabled = user_input.get(f"enable_{service_id}", False)
        
        # Clean up disabled service configs
        if not new_enabled:
            for key in list(self._config_data.keys()):
                if key.startswith(f"{service_id}_"):
                    del self._config_data[key]
        
        self._current_service_index += 1
        return await self._async_handle_next_service()