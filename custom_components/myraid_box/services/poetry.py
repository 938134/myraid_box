from typing import Dict, Any, List
from datetime import datetime, timedelta
import aiohttp
import logging
from ..service_base import BaseService, AttributeConfig

_LOGGER = logging.getLogger(__name__)

DEFAULT_POETRY_API = "https://v1.jinrishici.com"

class PoetryService(BaseService):
    """增强版诗词服务"""

    CATEGORY_MAP = {
        "全部": "all",
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

    @property
    def service_id(self) -> str:
        return "poetry"

    @property
    def name(self) -> str:
        return "每日诗词"

    @property
    def description(self) -> str:
        return "从古诗词API获取每日一句经典诗词"

    @property
    def icon(self) -> str:
        return "mdi:book-open-variant"

    @property
    def config_fields(self) -> Dict[str, Dict[str, Any]]:
        return {
            "url": {
                "name": "API地址",
                "type": "str",
                "default": DEFAULT_POETRY_API,
                "description": "古诗词API地址"
            },
            "interval": {
                "name": "更新间隔",
                "type": "int",
                "default": 10,
                "description": "更新间隔时间（分钟）"
            },
            "category": {
                "name": "分类",
                "type": "select",
                "default": "全部",
                "description": "选择诗词的分类",
                "options": sorted(self.CATEGORY_MAP.keys(), key=lambda x: x)
            }
        }

    @property
    def attributes(self) -> Dict[str, AttributeConfig]:
        return {
            "author": {
                "name": "作者",
                "icon": "mdi:account"
            },
            "origin": {
                "name": "出处",
                "icon": "mdi:book"
            },
            "update_time": {
                "name": "更新时间",
                "icon": "mdi:clock"
            }
        }

    def _build_request(self, params: Dict[str, Any]) -> tuple[str, Dict[str, Any], Dict[str, str]]:
        base_url = params["url"].strip('/')
        category = params.get("category", "全部")
        
        category_code = self.CATEGORY_MAP.get(category, "all")
        url = f"{base_url}/{category_code}"

        headers = {
            "Accept": "application/json",
            "User-Agent": f"HomeAssistant/{self.service_id}"
        }
        return url, {}, headers

    def _parse_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """增强版响应解析"""
        data = response_data.get("data", response_data)
        
        if not isinstance(data, dict):
            _LOGGER.error(f"无效的API响应格式: {type(data)}")
            return {
                "content": "数据解析错误",
                "author": "未知",
                "origin": "未知",
                "update_time": datetime.now().isoformat()
            }

        # 转换分类代码为可读名称
        category_code = data.get("category", "")
        category_name = self.CATEGORY_MAP.get(category_code, f"未知({category_code})")

        return {
            "content": data.get("content", "无有效内容"),
            "author": data.get("author", "未知"),
            "origin": data.get("origin", "未知"),
            "update_time": datetime.now().isoformat()
        }

    def format_sensor_value(self, data: Any, sensor_config: Dict[str, Any]) -> str:
        """带错误处理的显示格式化"""
        if not data or data.get("status") != "success":
            return "⏳ 加载中..." if data is None else f"⚠️ {data.get('error', '获取失败')}"
    
        try:
            parsed = self._parse_response(data)
            lines = [f"「{parsed['content']}」"]
    
            attribution = []
            if parsed["author"] and parsed["author"] != "未知":
                attribution.append(parsed["author"])
            if parsed["origin"]:
                attribution.append(parsed["origin"])
    
            if attribution:
                lines.append(f"—— {' '.join(attribution)}")
    
            return "\n".join(lines)
        except Exception as e:
            _LOGGER.error(f"格式化显示值时出错: {str(e)}")
            return "⚠️ 显示错误"

    def get_sensor_attributes(self, data: Any, sensor_config: Dict[str, Any]) -> Dict[str, Any]:
        """完整的属性获取方法"""
        if not data or data.get("status") != "success":
            return {}
        
        try:
            parsed = self._parse_response(data)
            return super().get_sensor_attributes({
                "author": parsed["author"],
                "origin": parsed["origin"],
                "update_time": parsed["update_time"]
            }, sensor_config)
        except Exception as e:
            _LOGGER.error(f"获取属性时出错: {str(e)}")
            return {}

    def get_sensor_configs(self, service_data: Any) -> List[Dict[str, Any]]:
        return [{
            "key": "main",
            "name": self.name,
            "icon": self.icon,
            "unit": None,
            "device_class": None
        }]