"""常量与 unique_id 生成工具。

约定：本文件只放**纯数据**——常量、与 unique_id 迁移相关的工具函数。

不在此文件里放：
- 类定义（ServiceCoordinator 在 coordinator.py、MyraidBoxAPIView 在 api_view.py）
- 运行时行为（服务注册表在 registry.py，扫描 services/ 目录动态发现）

如需 `SERVICE_REGISTRY` 或 `discover_services`，请从 ``.registry`` 导入。

版本信息唯一真源：``manifest.json``
─────────────────────────────────────
``DOMAIN`` / ``INTEGRATION_NAME`` / ``VERSION`` 都在模块加载时从同目录的
``manifest.json`` 动态读取。**升版只需改 manifest.json 一处**，其他所有
引用（sensor 的 DeviceInfo.sw_version、UI 标题、changelog 等）自动同步。
CI 里另有 job 校验 README badge 与 hacs.json 是否跟 manifest 对齐。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

# ============================================================
# 从 manifest.json 读取集成身份（唯一真源）
# ============================================================

_MANIFEST_PATH = Path(__file__).parent / "manifest.json"
_MANIFEST = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))

DOMAIN: str = _MANIFEST["domain"]
INTEGRATION_NAME: str = _MANIFEST["name"]
VERSION: str = _MANIFEST["version"]

# ============================================================
# UI 展示用的辅助常量（不来自 manifest）
# ============================================================

# 设备页"制造商"字段——复用集成名，避免和 manifest.name 出现分歧。
DEVICE_MANUFACTURER: str = INTEGRATION_NAME

# 设备页"型号"字段——用户视角的分类描述，manifest 里没有对应字段，
# 保留为独立常量。sensor.py 拼接成 "{DEVICE_MODEL} - {service.name}"。
DEVICE_MODEL = "多数据聚合"

# 卡片
CARD_NAME = "myraid_box_card"
CARD_VERSION = "1.0.0"

# HTTP 端点
API_ENDPOINT = "/api/myraid_box/data"


# ============================================================
# ConfigEntry.unique_id 生成规则（v2，3.0.0+）
# ============================================================
#
# 旧规则（v1，<=2.2.0）：
#   myraid_box_<md5(sorted(config_data.items()))>
#   ⚠️  config_data 包含 token / private_key / api_host，
#       用户改一次 token 就会得到新 unique_id，HA 视为新配置。
#
# 新规则（v2，>=3.0.0）：
#   myraid_box_v2_<md5(sorted(selected_services))>
#   ✓  只包含用户选择启用的服务集合，语义清晰。
#   ✓  改 token / 改 API 密钥不影响 unique_id。
#   ✓  v2 前缀便于识别 + 迁移检测。
#
# 用户升级 3.0 时 __init__.py 会自动把旧 unique_id 迁移到新格式，
# 不需要重新走配置流程。

NEW_UNIQUE_ID_PREFIX = "myraid_box_v2_"
LEGACY_UNIQUE_ID_PREFIX = "myraid_box_"


def generate_config_unique_id(selected_services: list[str]) -> str:
    """基于启用服务集合生成 v2 unique_id。

    规则：``myraid_box_v2_<md5(",".join(sorted(selected_services)))>``

    :param selected_services: 服务 id 列表（如 ``["weather", "oilprice"]``）
    :returns: 完整的 unique_id 字符串
    """
    key = ",".join(sorted(selected_services))
    hash_val = hashlib.md5(key.encode()).hexdigest()
    return f"{NEW_UNIQUE_ID_PREFIX}{hash_val}"


def is_legacy_unique_id(unique_id: str | None) -> bool:
    """判断 unique_id 是否为旧格式（v1，含 token 哈希）。

    识别规则：以 ``myraid_box_`` 开头但**不以** ``myraid_box_v2_`` 开头。
    """
    if not unique_id:
        return False
    return unique_id.startswith(LEGACY_UNIQUE_ID_PREFIX) and not unique_id.startswith(
        NEW_UNIQUE_ID_PREFIX
    )
