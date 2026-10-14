"""测试全局 fixture。

本地无 Home Assistant 环境，需要在导入 custom_components 前打桩
homeassistant 与 jwt 相关模块，确保纯业务逻辑（parser / formatter /
error classifier）能被单测覆盖。

CI 里 aiohttp / pyjwt / beautifulsoup4 都是真实安装，无需桩。
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

# 确保仓库根目录在 sys.path 最前面，方便 `custom_components.*` 导入
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _install_homeassistant_stub() -> None:
    """桩 homeassistant 顶层 + 用到的子模块。

    目的：让 `custom_components.myraid_box.__init__` 和子模块（sensor.py,
    config_flow.py 等）能被成功 import，从而让 service 模块可以被测试代码
    访问。单测不真的调用 HA 的方法，只需 import 不炸即可。
    """
    if "homeassistant" in sys.modules:
        return

    def _mk(name: str) -> types.ModuleType:
        m = types.ModuleType(name)
        sys.modules[name] = m
        return m

    # ==========================================================
    # 顶层 homeassistant
    # ==========================================================
    ha = _mk("homeassistant")

    # ==========================================================
    # homeassistant.core
    # ==========================================================
    ha_core = _mk("homeassistant.core")

    class HomeAssistant:
        config = types.SimpleNamespace(time_zone="Asia/Shanghai")

    ha_core.HomeAssistant = HomeAssistant

    def callback(fn):
        return fn

    ha_core.callback = callback

    # ==========================================================
    # homeassistant.config_entries
    # ==========================================================
    ha_ce = _mk("homeassistant.config_entries")

    class ConfigEntry:
        entry_id = "test-entry-id"
        data = {}
        options = {}
        title = "test"
        unique_id = "test-unique"

        def __init__(self, data=None):
            self.data = data or {}
            self.options = {}

        @classmethod
        def __class_getitem__(cls, item):
            # 支持 `ConfigEntry[CoordinatorBundle]` 泛型下标语法
            return cls

    class ConfigFlow:
        domain = "test"
        VERSION = 1

        def async_create_entry(self, title="", data=None, description=None):
            return {"type": "create_entry", "title": title, "data": data or {}}

        def async_show_form(self, **kwargs):
            return {"type": "form", **kwargs}

    class OptionsFlow(ConfigFlow):
        pass

    class OptionsFlowWithReload(OptionsFlow):
        async def async_step_finish(self, user_input=None):
            return {"type": "reload", "path": None}

    class ConfigFlowResult(dict):
        pass

    class ConfigEntryNotReady(Exception):
        pass

    def async_entries(hass, domain):
        return []

    ha_ce.ConfigEntry = ConfigEntry
    ha_ce.ConfigFlow = ConfigFlow
    ha_ce.OptionsFlow = OptionsFlow
    ha_ce.OptionsFlowWithReload = OptionsFlowWithReload
    ha_ce.ConfigFlowResult = ConfigFlowResult
    ha_ce.ConfigEntryNotReady = ConfigEntryNotReady
    ha_ce.async_entries = async_entries
    ha_ce.CONN_CLASS_CLOUD_POLL = "cloud_poll"
    ha_ce.CONN_CLASS_CLOUD_PUSH = "cloud_push"
    ha_ce.CONN_CLASS_LOCAL_PUSH = "local_push"
    ha_ce.CONN_CLASS_ASSUMED = "assumed"

    # HANDLERS.register 装饰器（config_flow.py 用）
    class _Handlers:
        def register(self, domain):
            def _decorator(cls):
                return cls
            return _decorator

    ha_ce.HANDLERS = _Handlers()

    # ==========================================================
    # homeassistant.exceptions
    # ==========================================================
    ha_exc = _mk("homeassistant.exceptions")
    ha_exc.ConfigEntryNotReady = ConfigEntryNotReady

    # ==========================================================
    # homeassistant.helpers
    # ==========================================================
    ha_helpers = _mk("homeassistant.helpers")

    # --- aiohttp_client ---
    ha_aiohttp_client = _mk("homeassistant.helpers.aiohttp_client")

    def async_get_clientsession(hass):
        return None

    ha_aiohttp_client.async_get_clientsession = async_get_clientsession
    ha_helpers.aiohttp_client = ha_aiohttp_client

    # --- update_coordinator ---
    ha_coordinator = _mk("homeassistant.helpers.update_coordinator")

    class DataUpdateCoordinator:
        def __init__(self, hass, logger, *, name=None, update_interval=None,
                     update_method=None, **kwargs):
            self.hass = hass
            self._logger = logger
            self.name = name
            self.update_interval = update_interval
            self.update_method = update_method
            self.data = None

        async def async_config_entry_first_refresh(self):
            self.data = await self.update_method()

        async def async_refresh(self):
            self.data = await self.update_method()

    class CoordinatorEntity:
        def __init__(self, coordinator):
            self.coordinator = coordinator

    ha_coordinator.DataUpdateCoordinator = DataUpdateCoordinator
    ha_coordinator.CoordinatorEntity = CoordinatorEntity
    ha_helpers.update_coordinator = ha_coordinator

    # --- entity_registry / device_registry ---
    ha_er = _mk("homeassistant.helpers.entity_registry")

    class _FakeRegistry:
        def async_get(self, entity_id=None, suggested_object_id=None):
            return None

        def async_clear_entry(self, entry_id):
            pass

        def async_remove(self, entity_id):
            pass

        def async_entries_for_device(self, device_id, include_non_persistent=False):
            return []

    ha_er.async_get = lambda hass: _FakeRegistry()
    ha_er.async_entries_for_device = lambda ent_reg, device_id: []
    ha_helpers.entity_registry = ha_er

    ha_dr = _mk("homeassistant.helpers.device_registry")

    class _FakeDevice:
        id = "dev-id"
        identifiers = {("domain", "ident")}

    class _FakeDeviceRegistry:
        def async_remove_device(self, device_id):
            pass

        def async_entries_for_config_entry(self, entry_id):
            return []

    ha_dr.async_get = lambda hass: _FakeDeviceRegistry()
    ha_dr.async_entries_for_config_entry = lambda dev_reg, entry_id: []
    ha_helpers.device_registry = ha_dr

    # --- entity ---
    ha_entity = _mk("homeassistant.helpers.entity")

    class Entity:
        pass

    class DeviceInfo(dict):
        pass

    class EntityDescription:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class SensorEntityDescription(EntityDescription):
        pass

    class SensorDeviceClass:
        pass

    class EntityCategory:
        """HA EntityCategory 枚举桩（sensor.py 从这里导入）。"""
        DIAGNOSTIC = "diagnostic"
        CONFIG = "config"
        NONE = None

    ha_entity.Entity = Entity
    ha_entity.DeviceInfo = DeviceInfo
    ha_entity.EntityDescription = EntityDescription
    ha_entity.EntityCategory = EntityCategory
    ha_entity.SensorEntityDescription = SensorEntityDescription
    ha_entity.SensorDeviceClass = SensorDeviceClass
    ha_helpers.entity = ha_entity

    # --- entity_platform ---
    ha_ep = _mk("homeassistant.helpers.entity_platform")

    class AddEntitiesCallback:
        pass

    ha_ep.AddEntitiesCallback = AddEntitiesCallback
    ha_helpers.entity_platform = ha_ep

    # --- config_validation ---
    ha_cv = _mk("homeassistant.helpers.config_validation")
    ha_cv.string = str
    ha_cv.ensure_list = lambda x: x
    ha_cv.boolean = bool
    ha_cv.positive_int = int
    ha_cv.matches_regex = str
    ha_cv.require_schema = dict
    ha_helpers.config_validation = ha_cv

    # --- storage ---
    ha_storage = _mk("homeassistant.helpers.storage")

    class Store:
        def __init__(self, hass, version, key):
            self.hass = hass
            self.version = version
            self.key = key

    ha_storage.Store = Store
    ha_helpers.storage = ha_storage

    # ==========================================================
    # homeassistant.components
    # ==========================================================
    ha_components = _mk("homeassistant.components")

    # frontend
    ha_frontend = _mk("homeassistant.components.frontend")
    ha_frontend.add_extra_js_url = lambda hass, url, **kwargs: None
    ha_components.frontend = ha_frontend

    # http
    ha_http = _mk("homeassistant.components.http")

    class HomeAssistantView:
        url = ""
        name = ""
        requires_auth = False
        requires_admin = False

        def json(self, *args, **kwargs):
            return args[0] if args else None

    class StaticPathConfig:
        def __init__(self, url_path, path, cache_timeout):
            self.url_path = url_path
            self.path = path
            self.cache_timeout = cache_timeout

    ha_http.HomeAssistantView = HomeAssistantView
    ha_http.StaticPathConfig = StaticPathConfig
    ha_components.http = ha_http

    # sensor
    ha_sensor = _mk("homeassistant.components.sensor")
    ha_sensor.SensorEntity = type("SensorEntity", (Entity,), {})
    ha_sensor.SensorEntityDescription = SensorEntityDescription
    ha_sensor.SensorDeviceClass = SensorDeviceClass
    ha_sensor.StateClass = type("StateClass", (), {})
    ha_sensor.EntityCategory = type("EntityCategory", (), {"DIAGNOSTIC": "diagnostic"})
    ha_components.sensor = ha_sensor

    # ==========================================================
    # homeassistant.const
    # ==========================================================
    ha_const = _mk("homeassistant.const")
    ha_const.ATTR_ATTRIBUTION = "attribution"
    ha_const.CONF_PASSWORD = "password"
    ha_const.CONF_TOKEN = "token"
    ha_const.CONF_URL = "url"
    ha_const.CONF_TIMEOUT = "timeout"
    ha_const.CONF_USERNAME = "username"
    ha_const.ENTITY_CATEGORIES = ("diagnostic", "config")
    ha_const.TIME_SECONDS = "seconds"
    ha_const.ENTITY_CATEGORY_DIAGNOSTIC = "diagnostic"
    ha_const.PLATFORM = "platform"
    ha_const.DOMAIN = "homeassistant"
    ha_const.CONF_MODE = "mode"
    ha_const.CONF_ENABLED = "enabled"
    ha_const.PLATFORM_TYPE = "platform_type"

    # ==========================================================
    # homeassistant.data_entry_flow
    # ==========================================================
    ha_flow = _mk("homeassistant.data_entry_flow")
    ha_flow.FlowResult = ConfigFlowResult

    # ==========================================================
    # homeassistant.helpers.selector
    # ==========================================================
    ha_sel = _mk("homeassistant.helpers.selector")

    class SelectSelector:
        def __init__(self, config=None):
            pass

    class SelectSelectorConfig:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class SelectSelectorMode:
        DROPDOWN = "dropdown"
        LIST = "list"

    class TextSelector:
        pass

    class BooleanSelector:
        pass

    class NumberSelector:
        pass

    class UrlSelector:
        pass

    class DateSelector:
        pass

    class TimeSelector:
        pass

    class RecurrenceSelector:
        pass

    ha_sel.SelectSelector = SelectSelector
    ha_sel.SelectSelectorConfig = SelectSelectorConfig
    ha_sel.SelectSelectorMode = SelectSelectorMode
    ha_sel.TextSelector = TextSelector
    ha_sel.BooleanSelector = BooleanSelector
    ha_sel.NumberSelector = NumberSelector
    ha_sel.UrlSelector = UrlSelector
    ha_sel.DateSelector = DateSelector
    ha_sel.TimeSelector = TimeSelector
    ha_sel.RecurrenceSelector = RecurrenceSelector
    ha_helpers.selector = ha_sel

    # ==========================================================
    # 组装：把子模块挂到父模块上
    # ==========================================================
    ha.core = ha_core
    ha.config_entries = ha_ce
    ha.exceptions = ha_exc
    ha.helpers = ha_helpers
    ha.components = ha_components
    ha.const = ha_const
    ha.data_entry_flow = ha_flow
    ha.util = _mk("homeassistant.util")
    ha.util.dt = _mk("homeassistant.util.dt")
    ha.util.dt.utcnow = lambda: __import__("datetime").datetime.utcnow()
    ha.util.dt.parse_datetime = lambda x: x
    ha.util.dt.as_utc = lambda x: x
    ha.util.dt.dt = __import__("datetime")
    ha.util.yaml = _mk("homeassistant.util.yaml")

    # 顶层也要能看到子模块名
    ha.components = ha_components
    ha.helpers = ha_helpers
    ha.core = ha_core
    ha.const = ha_const
    ha.config_entries = ha_ce
    ha.exceptions = ha_exc
    ha.data_entry_flow = ha_flow


_install_homeassistant_stub()


_install_homeassistant_stub()


# ------------------------------------------------------------
# pytest fixtures
# ------------------------------------------------------------

import pytest  # noqa: E402  (必须在桩安装之后 import)

# 注：SERVICE_REGISTRY 自 3.0 起改为静态字典（在 const.py 定义时即完整），
# 无需再通过 fixture 调用 discover_services() 做初始化。