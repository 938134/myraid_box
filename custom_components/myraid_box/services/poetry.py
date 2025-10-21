from typing import Dict, Any, List
from datetime import datetime
import aiohttp
import logging
import re
from ..service_base import BaseService, SensorConfig

_LOGGER = logging.getLogger(__name__)

DEFAULT_POETRY_API = "https://v1.jinrishici.com"

class PoetryService(BaseService):
    """多传感器版每日诗词服务"""

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
                "name": "更新间隔（分钟）",
                "type": "int",
                "default": 10,
                "description": "更新间隔时间"
            },
            "category": {
                "name": "分类",
                "type": "select",
                "default": "全部",
                "description": "诗词分类",
                "options": sorted(self.CATEGORY_MAP.keys(), key=lambda x: x)
            }
        }

    @property
    def sensor_configs(self) -> List[SensorConfig]:
        """返回每日诗词的所有传感器配置"""
        return [
            {
                "key": "content",
                "name": "诗句",
                "icon": "mdi:book-open-variant",
                "device_class": None
            },
            {
                "key": "author",
                "name": "诗人",
                "icon": "mdi:account",
                "device_class": None
            },
            {
                "key": "origin",
                "name": "出处",
                "icon": "mdi:book",
                "device_class": None
            },
            {
                "key": "dynasty",
                "name": "朝代",
                "icon": "mdi:castle",
                "device_class": None
            }
        ]

    def build_request(self, params: Dict[str, Any]) -> tuple[str, Dict[str, Any], Dict[str, str]]:
        """构建请求参数"""
        base_url = params["url"].strip('/')
        category = params.get("category", "全部")
        
        category_code = self.CATEGORY_MAP.get(category, "all")
        url = f"{base_url}/{category_code}"

        headers = {
            "Accept": "application/json",
            "User-Agent": f"HomeAssistant/{self.service_id}"
        }
        return url, {}, headers

    def parse_response(self, response_data: Any) -> Dict[str, Any]:
        """解析响应数据为标准化字典"""
        # 提取原始数据
        if isinstance(response_data, dict) and "data" in response_data:
            data = response_data["data"]
        else:
            data = response_data
            
        update_time = response_data.get("update_time", datetime.now().isoformat())
        
        if not isinstance(data, dict):
            _LOGGER.error(f"无效的API响应格式: {type(data)}")
            return {
                "content": "数据解析错误",
                "author": "未知",
                "origin": "未知",
                "dynasty": "未知",
                "update_time": update_time
            }

        # 返回标准化数据字典
        return {
            "content": data.get("content", "无有效内容"),
            "author": data.get("author", "未知"),
            "origin": data.get("origin", "未知"),
            "dynasty": data.get("dynasty", "未知"),
            "update_time": update_time
        }

    def format_sensor_value(self, sensor_key: str, data: Any) -> Any:
        """格式化特定传感器的显示值"""
        value = self.get_sensor_value(sensor_key, data)
        
        if value is None:
            return "暂无数据"
            
        # 为不同传感器提供特定的格式化
        if sensor_key == "content":
            # 去掉诗句中的引号和其他标点符号
            if value and value != "无有效内容":
                # 使用正则表达式移除所有中文和英文引号
                cleaned_value = re.sub(r'[「」『』"\'""]', '', value)
                return cleaned_value.strip()
            return value
        elif sensor_key == "author":
            return value if value and value != "未知" else "佚名"
        elif sensor_key == "origin":
            return value if value and value != "未知" else "未知出处"
        elif sensor_key == "dynasty":
            return value if value and value != "未知" else "未知朝代"
        else:
            return str(value)