"""所有 service 必须能用两种签名实例化：

1. ``ServiceClass()`` — config_flow 阶段（不注入 hass）
2. ``ServiceClass(hass=stub_hass)`` — coordinator 阶段（注入 hass）

这是之前 5 个 service ``__init__() got an unexpected keyword argument 'hass'``
崩溃的回归防线。

3.2.0 版本起 SERVICE_REGISTRY 恢复动态发现（扫描 services/ 目录自动注册），
3.3.0 版本起注册表迁到独立的 registry.py 模块（const.py 回归纯数据）。
新增服务只需在 services/ 下丢一个文件，无需修改 const.py。
"""
from __future__ import annotations

from custom_components.myraid_box.registry import (
    SERVICE_REGISTRY,
    discover_services,
)


class _StubHass:
    """最小 hass 桩，只需被 __init__ 保存即可。"""

    config = type("C", (), {"time_zone": "Asia/Shanghai"})()


def test_registry_non_empty():
    assert len(SERVICE_REGISTRY) >= 5


def test_all_services_have_required_props():
    for service_id, cls in SERVICE_REGISTRY.items():
        svc = cls(hass=_StubHass())
        assert svc.service_id, f"{service_id} 缺 service_id"
        assert svc.name, f"{service_id} 缺 name"
        assert svc.config_fields, f"{service_id} 缺 config_fields"
        assert svc._get_sensor_configs() is not None, f"{service_id} sensor 配置异常"


def test_all_services_accept_no_arg():
    """config_flow 阶段只读静态配置，无 hass 也必须能实例化。"""
    for service_id, cls in SERVICE_REGISTRY.items():
        # 不传 hass，允许默认 None
        assert cls() is not None, f"{service_id} 无参实例化失败"


def test_all_services_accept_hass_kwarg():
    """关键：所有子类必须支持 hass= 关键字参数（coordinator 注入）。"""
    for service_id, cls in SERVICE_REGISTRY.items():
        try:
            svc = cls(hass=_StubHass())
        except TypeError as e:
            raise AssertionError(
                f"{service_id} 不支持 hass= 关键字：{e}"
            ) from e
        assert svc._hass is not None


def test_registry_keys_match_service_id_property():
    """SERVICE_REGISTRY 的 key 必须与 service 类 service_id property 返回值一致。

    registry.py 的 discover_services 通过 ``cls().service_id`` 拿到 key，
    如果哪个 service 的 service_id 被改了（比如 oil 从 oilprice 改成 oil），
    或 discover 逻辑出现 bug，此测试会立刻报警，避免 config_flow /
    coordinator 找不到服务。
    """
    for registry_key, cls in SERVICE_REGISTRY.items():
        svc = cls()
        assert svc.service_id == registry_key, (
            f"SERVICE_REGISTRY key `{registry_key}` 与 {cls.__name__}.service_id "
            f"(`{svc.service_id}`) 不一致"
        )


def test_discover_services_idempotent():
    """discover_services 默认调用是 no-op，不重复扫描，也不丢条目。"""
    from custom_components.myraid_box import registry as registry_mod

    before = dict(registry_mod.SERVICE_REGISTRY)
    assert discover_services() is registry_mod.SERVICE_REGISTRY
    after = dict(registry_mod.SERVICE_REGISTRY)
    assert before == after, "discover_services 默认调用不应改变 registry 内容"


def test_discover_forces_repopulate():
    """discover_services(force=True) 会在 registry 被清空后重新填好。"""
    from custom_components.myraid_box import registry as registry_mod

    original = dict(registry_mod.SERVICE_REGISTRY)
    try:
        registry_mod.SERVICE_REGISTRY.clear()
        assert registry_mod.SERVICE_REGISTRY == {}
        registry_mod.discover_services(force=True)
        assert len(registry_mod.SERVICE_REGISTRY) >= 5, "force 后 registry 未重新填充"
        for sid, cls in registry_mod.SERVICE_REGISTRY.items():
            assert cls().service_id == sid
    finally:
        registry_mod.SERVICE_REGISTRY.clear()
        registry_mod.SERVICE_REGISTRY.update(original)


def test_new_service_requires_no_const_change():
    """v3.2 语义回归防线：discover 通过扫描 services/ 目录自动注册。

    不直接新建磁盘文件（避免污染源码树），而是用 monkeypatch 让
    discover 看到的 services 目录多出一个假文件，验证 discover 逻辑
    真的会把它识别成 BaseService 子类注册进来。
    """
    from pathlib import Path as _Path

    from custom_components.myraid_box import registry as registry_mod
    from custom_components.myraid_box.service_base import BaseService

    real_services_dir = _Path(registry_mod.__file__).parent / "services"

    class ZetaService(BaseService):
        @property
        def service_id(self) -> str:
            return "zeta_dummy"

        @property
        def name(self) -> str:
            return "Zeta Dummy"

        @property
        def description(self) -> str:
            return "test-only dummy service"

        @property
        def config_fields(self):
            return {}

        def _parse_raw_response(self, response_data):
            return {}

        def fetch_data(self, config):
            return {}

        def get_sensor_configs(self, data):
            return []

    # 用一个小 module 承载新类，让 importlib.import_module 通过 sys.modules 命中
    import sys as _sys
    import types as _types

    fake_module = _types.ModuleType("custom_components.myraid_box.services.zeta_dummy")
    fake_module.ZetaService = ZetaService
    _sys.modules["custom_components.myraid_box.services.zeta_dummy"] = fake_module

    real_glob = _Path.glob
    fake_path = real_services_dir / "zeta_dummy.py"

    def fake_glob(self, pattern):
        result = list(real_glob(self, pattern))
        if pattern == "*.py" and str(self) == str(real_services_dir):
            result.append(fake_path)
        return result

    monkeypatched = _Path.glob
    _Path.glob = fake_glob
    try:
        registry_mod.SERVICE_REGISTRY.clear()
        registry_mod.discover_services(force=True)
        assert "zeta_dummy" in registry_mod.SERVICE_REGISTRY
        assert registry_mod.SERVICE_REGISTRY["zeta_dummy"] is ZetaService
    finally:
        _Path.glob = monkeypatched
        del _sys.modules["custom_components.myraid_box.services.zeta_dummy"]
        # 恢复 registry 到测试前的状态
        registry_mod.SERVICE_REGISTRY.clear()
        registry_mod.discover_services(force=True)
