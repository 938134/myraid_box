from typing import Dict, Any, List
from datetime import datetime
import logging
import re
from ..service_base import BaseService, SensorConfig

_LOGGER = logging.getLogger(__name__)

class PoetryService(BaseService):
    """多传感器版每日诗词服务"""

    DEFAULT_API_URL = "https://v1.jinrishici.com"
    DEFAULT_UPDATE_INTERVAL = 10

    CATEGORY_MAP = {
        "随机": "all",
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
        return "从古诗词API获取经典诗词"

    @property
    def icon(self) -> str:
        return "mdi:book-open-variant"

    @property
    def config_fields(self) -> Dict[str, Dict[str, Any]]:
        return {
            "interval": {
                "name": "更新间隔",
                "type": "int",
                "default": self.DEFAULT_UPDATE_INTERVAL,
                "description": "更新间隔时间（分钟）"
            },
            "category": {
                "name": "分类",
                "type": "select",
                "default": "随机",
                "description": "诗词分类",
                "options": sorted(self.CATEGORY_MAP.keys(), key=lambda x: x)
            }
        }

    def _get_sensor_configs(self) -> List[SensorConfig]:
        """返回每日诗词的所有传感器配置（按显示顺序）"""
        return [
            self._create_sensor_config("content", "诗句", "mdi:book-open-variant", sort_order=1),
            self._create_sensor_config("author", "诗人", "mdi:account", sort_order=2),
            self._create_sensor_config("origin", "出处", "mdi:book", sort_order=3),
            self._create_sensor_config("dynasty", "朝代", "mdi:castle", sort_order=4)
        ]

    def build_request(self, params: Dict[str, Any]) -> tuple[str, Dict[str, Any], Dict[str, str]]:
        """构建请求参数"""
        base_url = self.default_api_url
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
        if isinstance(response_data, dict) and "data" in response_data:
            data = response_data["data"]
        else:
            data = response_data
            
        update_time = response_data.get("update_time", datetime.now().isoformat())
        
        if not isinstance(data, dict):
            _LOGGER.error(f"无效的API响应格式: {type(data)}")
            return self._create_error_response(update_time)

        return {
            "content": data.get("content", "无有效内容"),
            "author": data.get("author", "未知"),
            "origin": data.get("origin", "未知"),
            "dynasty": data.get("dynasty", "未知"),
            "update_time": update_time
        }

    def _create_error_response(self, update_time: str) -> Dict[str, Any]:
        """创建错误响应"""
        return {
            "content": "数据解析错误",
            "author": "未知",
            "origin": "未知",
            "dynasty": "未知",
            "update_time": update_time
        }

    def format_sensor_value(self, sensor_key: str, data: Any) -> Any:
        """格式化特定传感器的显示值"""
        value = self.get_sensor_value(sensor_key, data)
        
        if value is None:
            return "暂无数据"
            
        formatters = {
            "content": self._format_content,
            "author": self._format_author,
            "origin": self._format_origin,
            "dynasty": self._format_dynasty
        }
        
        formatter = formatters.get(sensor_key, str)
        return formatter(value)

    def _format_content(self, value: str) -> str:
        if value and value != "无有效内容":
            cleaned_value = re.sub(r'[「」『』"\'""]', '', value)
            return cleaned_value.strip()
        return value

    def _format_author(self, value: str) -> str:
        return value if value and value != "未知" else "佚名"

    def _format_origin(self, value: str) -> str:
        return value if value and value != "未知" else "未知出处"

    def _format_dynasty(self, value: str) -> str:
        return value if value and value != "未知" else "未知朝代"