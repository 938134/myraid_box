"""万象盒子集成 —— HA 2024.8+ 重构版。

关键变化（3.0.0）：
- **unique_id 去 token 化**：老 unique_id 基于 ``md5(config_data)``（含 token），
  改一次 token 就会变成新配置。3.0.0 起基于 ``md5(sorted(selected_services))``，
  不含任何敏感字段。老用户在首次升级时自动迁移，无需重新走配置流程。
- ``minimum_ha_version`` 升 2024.8+，依赖 ``async_migrate_unique_id`` API。

关键变化（2.x）：
- ``requires_auth = True``（原为 False，会向任意 HTTP 客户端泄露 token/私钥）
- 使用 ``ConfigEntry.runtime_data`` 泛型替代 ``hass.data[DOMAIN]``
- ``ServiceCoordinator`` 持有唯一 ``service`` 实例并注入 ``hass``，
  传感器从 coordinator 复用，不再每个 sensor 都新建 service
- 使用 HA 全局 aiohttp session，去掉自建 session 与 ``async_unload``
- 删除 ``_last_successful_data`` 死代码
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from collections.abc import Sequence
from typing import Any, TypedDict

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig

from .api_view import MyraidBoxAPIView
from .config_flow import MyriadBoxConfigFlow
from .const import (
    DOMAIN,
    generate_config_unique_id,
    is_legacy_unique_id,
)
from .coordinator import ServiceCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: Sequence[str] = ("sensor",)


# ============================================================
# 运行时数据容器
# ============================================================
class CoordinatorBundle(TypedDict):
    """单个 ConfigEntry 的运行时数据。

    HA 2024.6+ 使用 ConfigEntry.runtime_data 泛型承载集成运行时状态，
    避免使用 ``hass.data[DOMAIN][entry.entry_id]`` 全局字典。
    """

    coordinators: dict[str, "ServiceCoordinator"]


class MyraidBoxConfigEntry(ConfigEntry[CoordinatorBundle]):
    """带运行时数据泛型的 ConfigEntry 类型别名。"""


# ============================================================
# Frontend Card 注册
# ============================================================
def _compute_file_hash(file_path: str) -> str | None:
    try:
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()[:8]
    except Exception:  # pragma: no cover - 防御性
        pass
    return None


async def setup_myraid_card(hass: HomeAssistant) -> bool:
    """注册卡片前端资源。幂等。"""
    card_js_rel = f"custom_components/{DOMAIN}/frontend/myraid_box_card.js"
    card_path = "/myriad_card_local"
    frontend_dir = hass.config.path(f"custom_components/{DOMAIN}/frontend")

    try:
        # ⚠️  不要用 async_add_executor_job(os.makedirs, dir, exist_ok=True)
        # HA 的 async_add_executor_job 会把 kwarg 转成位置参数，导致
        # os.makedirs 收到 (dir, True) → TypeError。改用包装函数。
        await hass.async_add_executor_job(_ensure_dir, frontend_dir)

        card_js_path = hass.config.path(card_js_rel)
        js_hash = await harness_safe_compute_hash(hass, card_js_path)
        version = js_hash or str(int(time.time()))

        await harness_safe_register_static_path(hass, card_path, frontend_dir)
        add_extra_js_url(hass, f"{card_path}/myraid_box_card.js?ver={version}")
        _LOGGER.info("万象盒子卡片已注册，版本: %s", version)
        return True
    except Exception as e:  # pragma: no cover - 前端注册失败不阻断集成
        _LOGGER.error("注册万象盒子卡片失败: %s", e)
        return False


def _ensure_dir(dir_path: str) -> None:
    """确保目录存在。包装 os.makedirs 让 async_add_executor_job 能干净调用。"""
    os.makedirs(dir_path, exist_ok=True)


async def harness_safe_compute_hash(
    hass: HomeAssistant, file_path: str
) -> str | None:
    """异步计算文件哈希。异常时返回 None。"""
    try:
        return await hass.async_add_executor_job(_compute_file_hash, file_path)
    except Exception:
        return None


async def harness_safe_register_static_path(
    hass: HomeAssistant, card_path: str, frontend_dir: str
) -> None:
    """注册静态资源路径。

    HA 2024.6+ 会警告重复注册；用 try/except 吞掉 duplicate 错误。
    """
    try:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(card_path, frontend_dir, False)]
        )
    except ValueError as e:
        if "already" in str(e).lower():
            _LOGGER.debug("静态资源路径已存在，跳过重复注册")
        else:
            raise


# ============================================================
# Setup / Unload
# ============================================================
async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """配置顶层挂载（仅注册 flow、API、前端资源）。"""
    hass.http.register_view(MyraidBoxAPIView)
    await setup_myraid_card(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: MyraidBoxConfigEntry) -> bool:
    """通过配置条目设置。"""
    # ================================================================
    # 3.0.0+ unique_id 迁移：v1 → v2（去 token 化）
    # ================================================================
    # 老 unique_id = ``myraid_box_<md5(config_data)>``
    #   ⚠️  含 token / private_key，用户改一次 token 就变新配置
    # 新 unique_id = ``myraid_box_v2_<md5(sorted(selected_services))>``
    #   ✓  只基于启用服务集合，改 token 不影响
    #
    # 迁移只在首次升级 3.0 时发生一次，之后 HA 会持久化新 unique_id。
    #
    # ⚠️  async_migrate_unique_id 是 HA 2024.8 引入的 API。老版本 HA
    # 没有此方法，直接调用会 AttributeError 导致集成加载失败。
    # 这里做防御性 hasattr 检查：老版本 HA 用户跳过迁移，保持旧
    # unique_id 继续运行（功能正常，只是 future-proof 稍弱）。
    if is_legacy_unique_id(entry.unique_id):
        selected = [
            k.removeprefix("enable_")
            for k, v in entry.data.items()
            if k.startswith("enable_") and v
        ]
        new_unique_id = generate_config_unique_id(selected)
        if hasattr(entry, "async_migrate_unique_id"):
            _LOGGER.info(
                "迁移 ConfigEntry unique_id (v1 → v2): %s → %s",
                entry.unique_id, new_unique_id,
            )
            await entry.async_migrate_unique_id(hass, new_unique_id)
        else:
            _LOGGER.warning(
                "当前 HA 版本不支持 async_migrate_unique_id（需 2024.8+），"
                "跳过 unique_id 迁移，继续使用旧 unique_id：%s。"
                "建议升级 Home Assistant 到 2024.8+ 以获得完整功能。",
                entry.unique_id,
            )

    coordinators: dict[str, ServiceCoordinator] = {}
    enabled_services = [
        k.removeprefix("enable_")
        for k, v in entry.data.items()
        if k.startswith("enable_") and v
    ]

    if not enabled_services:
        _LOGGER.warning("未启用任何服务")
        return True

    failed: list[str] = []
    for service_id in enabled_services:
        try:
            coordinator = ServiceCoordinator(hass, entry, service_id)
            await coordinator.async_config_entry_first_refresh()
            coordinators[service_id] = coordinator
            _LOGGER.info("服务初始化成功: %s", service_id)
        except ConfigEntryNotReady:
            raise  # 交给 HA 处理重试
        except Exception as e:
            _LOGGER.error("服务 %s 初始化失败: %s", service_id, e)
            failed.append(service_id)

    if not coordinators:
        raise ConfigEntryNotReady("所有服务初始化失败")

    if failed:
        _LOGGER.warning("以下服务初始化失败，将在下次刷新时重试: %s", failed)

    # HA 2024.6+ 泛型运行时数据
    entry.runtime_data = {"coordinators": coordinators}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MyraidBoxConfigEntry) -> bool:
    """卸载集成。"""
    unload_ok = await harness_safe_unload(hass, entry)
    if unload_ok:
        _LOGGER.debug("成功卸载万象盒子集成")
    return unload_ok


async def harness_safe_unload(hass: HomeAssistant, entry: MyraidBoxConfigEntry) -> bool:
    """内部卸载逻辑。"""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: MyraidBoxConfigEntry) -> None:
    """重载配置条目。"""
    _LOGGER.debug("重新加载万象盒子配置条目")
    if not await async_unload_entry(hass, entry):
        _LOGGER.error("卸载失败，取消重载")
        return
    await async_setup_entry(hass, entry)


async def async_remove_entry(hass: HomeAssistant, entry: MyraidBoxConfigEntry) -> None:
    """移除配置条目时的清理。"""
    _LOGGER.debug("移除万象盒子配置条目")

    ent_reg = er.async_get(hass)
    ent_reg.async_clear_entry(entry.entry_id)

    dev_reg = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(dev_reg, entry.entry_id)
    for device in devices:
        # 只清理不再被任何实体引用的孤儿设备
        remaining = er.async_entries_for_device(ent_reg, device.id)
        if not remaining:
            dev_reg.async_remove_device(device.id)


@callback
def async_update_sensors(hass: HomeAssistant, entry: MyraidBoxConfigEntry) -> None:
    """动态更新传感器（保留旧接口）。"""
    hass.async_create_task(async_reload_entry(hass, entry))


@callback
def async_cleanup_disabled_services(
    hass: HomeAssistant,
    entry: MyraidBoxConfigEntry,
    previous_config: dict[str, Any],
) -> None:
    """清理被禁用的服务的实体和设备。"""
    current_enabled = {
        k.removeprefix("enable_")
        for k, v in entry.data.items()
        if k.startswith("enable_") and v
    }
    previous_enabled = {
        k.removeprefix("enable_")
        for k, v in previous_config.items()
        if k.startswith("enable_") and v
    }
    disabled = previous_enabled - current_enabled
    if not disabled:
        return

    _LOGGER.debug("清理被禁用服务的实体: %s", disabled)
    _cleanup_service_entities(hass, entry, disabled)


@callback
def _cleanup_service_entities(
    hass: HomeAssistant,
    entry: MyraidBoxConfigEntry,
    service_ids: set[str],
) -> None:
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    devices = dr.async_entries_for_config_entry(dev_reg, entry.entry_id)
    for device in devices:
        for ident in device.identifiers:
            if ident[0] != DOMAIN:
                continue
            dev_service_id = ident[1].split("_", 1)[0]
            if dev_service_id in service_ids:
                entities = er.async_entries_for_device(ent_reg, device.id)
                for entity in entities:
                    ent_reg.async_remove(entity.entity_id)
                dev_reg.async_remove_device(device.id)
                _LOGGER.debug("已移除被禁用服务 %s 的设备", dev_service_id)
                break
