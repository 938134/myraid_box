from datetime import datetime
from typing import Dict, Any, Optional
from urllib.parse import urlparse, urljoin
import logging
from custom_components.myraid_box.service_base import BaseService, AttributeConfig

_LOGGER = logging.getLogger(__name__)

DEFAULT_POETRY_API = "https://v1.jinrishici.com"  # 去掉默认的分类路径

# 分类映射表
CATEGORY_MAP = {
    "全部": "all",  # 修改为 "全部" 对应 "all"
    "抒情": "shuqing",
    "四季": "siji",
    "山水": "shanshui",
    "天气": "tianqi",
    "人物": "renwu",
    "人生": "rensheng",
    "生活": "shenghuo",
    "节日": "jieri",
    "动物": "dongwu",
    "植物": "zhiwu",
    "食物": "shiwu"
}

class PoetryService(BaseService):
    """增强版诗词服务"""

    def __init__(self):
        super().__init__()

    @property
    def service_id(self) -> str:
        return "poetry"

    @property
    def name(self) -> str:
        return "每日诗词"

    @property
    def description(self) -> str:
        return "获取经典诗词（支持自定义API）"

    @property
    def icon(self) -> str:
        return "mdi:book-open-variant"

    @property
    def config_fields(self) -> Dict[str, Dict[str, Any]]:
        return {
            "url": {
                "name": "API地址",
                "type": "str",
                "required": True,
                "default": DEFAULT_POETRY_API,
                "description": "支持以下端点：\n- 默认: https://v1.jinrishici.com\n- 备用: https://api.jinrishici.com/v1/sentence",
                "regex": r"^https?://(v1\.|api\.)?jinrishici\.com",
                "placeholder": DEFAULT_POETRY_API
            },
            "interval": {
                "name": "更新间隔（分钟）",
                "type": "int",
                "default": 10
            },
            "category": {
                "name": "分类",
                "type": "str",
                "required": False,
                "default": "全部",
                "options": list(CATEGORY_MAP.keys()),
                "description": "选择诗词的分类"
            }
        }

    async def fetch_data(self, coordinator, params: Dict[str, Any]) -> Dict[str, Any]:
        """获取诗词数据"""
        base_url = params["url"].strip()
        category = params.get("category", "全部")  # 默认分类为“全部”

        # 根据分类动态调整URL
        category_code = CATEGORY_MAP.get(category, "all")  # 默认为 "all"
        url = urljoin(base_url + "/", category_code)

        # 调用基类的网络请求方法
        response = await self._make_request(url, headers={
            "User-Agent": "HomeAssistant/MyriadBox"
        })

        if response["status"] == "success":
            data = response["data"]
            return {
                **data,
                "api_source": urlparse(url).netloc,
                "update_time": datetime.now().isoformat(),
                "status": "success"
            }
        else:
            return {
                "error": response["error"],
                "api_source": urlparse(url).netloc,
                "update_time": datetime.now().isoformat(),
                "status": "error"
            }

    def format_sensor_value(self, data: Any, sensor_config: Dict[str, Any]) -> str:
        """增强诗词显示格式"""
        if not data or not data.get("content"):
            return "⏳ 诗词加载中..."

        lines = [data["content"]]

        # 构建作者信息
        author_info = []
        if dynasty := data.get("dynasty"):
            author_info.append(dynasty)
        if author := data.get("author"):
            author_info.append(author)
        if author_info:
            lines.append(f"—— {'·'.join(author_info)}")

        # 添加出处
        if origin := data.get("origin"):
            lines.append(f"《{origin}》")

        return "\n".join(lines)

    def get_sensor_attributes(self, data: Any, sensor_config: Dict[str, Any]) -> Dict[str, Any]:
        """增强属性信息"""
        if not data:
            return {}

        attrs = {
            "api_source": data.get("api_source"),
            "update_time": data.get("update_time")
        }

        for attr in ["dynasty", "author", "origin", "content"]:
            if value := data.get(attr):
                attrs[attr] = value

        return attrs