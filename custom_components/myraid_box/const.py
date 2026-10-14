"""常量与 unique_id 生成工具。

约定：本文件只放**纯数据**——常量、与 unique_id 迁移相关的工具函数。

不在此文件里放：
- 类定义（ServiceCoordinator 在 coordinator.py、MyraidBoxAPIView 在 api_view.py）
- 运行时行为（服务注册表在 registry.py，扫描 services/ 目录动态发现）

如需 `SERVICE_REGISTRY` 或 `discover_services`，请从 ``.registry`` 导入。
"""

from __future__ import annotations

import hashlib

# ============================================================
# 集成基本信息
# ============================================================

DOMAIN = "myraid_box"
DEVICE_MANUFACTURER = "万象盒子"
DEVICE_MODEL = "多数据聚合"
VERSION = "3.3.0"

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
