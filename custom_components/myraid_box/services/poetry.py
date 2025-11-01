from typing import Dict, Any, List
from datetime import datetime
import logging
import re
import aiohttp
import asyncio
from ..service_base import BaseService, SensorConfig

_LOGGER = logging.getLogger(__name__)

class PoetryService(BaseService):
    """多传感器版每日诗词服务 - v2 API版本"""

    DEFAULT_API_URL = "https://v2.jinrishici.com/one.json"
    DEFAULT_UPDATE_INTERVAL = 10

    def __init__(self):
        super().__init__()
        self._token = None
        self._token_initialized = False
        self._token_lock = asyncio.Lock()

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
            }
        }

    def _get_sensor_configs(self) -> List[SensorConfig]:
        """返回传感器配置"""
        return [
            self._create_sensor_config("content", "诗句", "mdi:format-quote-open"),
            self._create_sensor_config("author", "诗人", "mdi:account"),
            self._create_sensor_config("origin", "出处", "mdi:book"),
            self._create_sensor_config("dynasty", "朝代", "mdi:castle"),
            self._create_sensor_config("annotation", "注释", "mdi:comment-text")
        ]

    def build_request(self, params: Dict[str, Any]) -> tuple[str, Dict[str, Any], Dict[str, str]]:
        """构建请求参数"""
        return (
            self.DEFAULT_API_URL,
            {},
            {
                "Accept": "application/json",
                "User-Agent": f"HomeAssistant/{self.service_id}",
                **({"X-User-Token": self._token} if self._token else {})
            }
        )

    async def _ensure_token(self) -> str:
        """确保有有效的token"""
        async with self._token_lock:
            if self._token and self._token_initialized:
                return self._token

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get("https://v2.jinrishici.com/token", timeout=10) as response:
                        data = await response.json()
                        if data.get("status") == "success":
                            self._token = data.get("data")
                            self._token_initialized = True
                            _LOGGER.info("成功获取今日诗词API Token")
                            return self._token
            except Exception as e:
                _LOGGER.error(f"获取Token异常: {e}")

            self._token = "homeassistant-poetry-service"
            self._token_initialized = True
            return self._token

    async def fetch_data(self, session: aiohttp.ClientSession, params: Dict[str, Any]) -> Dict[str, Any]:
        """获取并解析数据"""
        await self._ensure_token()
        return self.parse_response(await super().fetch_data(session, params))

    def parse_response(self, response_data: Any, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """解析API响应数据"""
        try:
            # 直接获取诗词数据
            origin_data = response_data.get('data', {}).get('data', {}).get('origin', {})
            
            # 从origin数据中提取标准字段
            author = origin_data.get("author", "佚名")
            origin = origin_data.get("title", "未知")
            dynasty = origin_data.get("dynasty", "未知")
            full_content_list = origin_data.get("content", [])
            annotation_list = origin_data.get("translate", [])
            
            # 格式化内容
            content = self._format_poetry_content(full_content_list) if full_content_list else "无有效内容"
            annotation = self._format_annotation(annotation_list) if annotation_list else "无"

            return {
                "content": content,
                "author": author,
                "origin": origin,
                "dynasty": dynasty,
                "annotation": annotation,
                "update_time": datetime.now().isoformat()
            }
            
        except Exception as e:
            _LOGGER.error(f"解析数据时发生异常: {e}")
            return self._create_error_response()

    def _format_poetry_content(self, content_list: List[str]) -> str:
        """格式化诗句内容"""
        formatted_lines = [re.sub(r'([。！？])', r'\1\n', line.strip()) for line in content_list if line.strip()]
        return re.sub(r'\n+', '\n', '\n'.join(formatted_lines)).strip()

    def _format_annotation(self, annotation_list: List[str]) -> str:
        """格式化注释内容"""
        formatted = [f"{i}. {anno.strip()}" for i, anno in enumerate(annotation_list, 1) if anno.strip()]
        return '\n'.join(formatted) if formatted else "无注释"

    def get_sensor_value(self, sensor_key: str, data: Any) -> Any:
        """获取传感器值"""
        return data.get(sensor_key) if isinstance(data, dict) else None

    def format_sensor_value(self, sensor_key: str, data: Any) -> Any:
        """格式化传感器显示值"""
        value = self.get_sensor_value(sensor_key, data)
        return self._get_default_value(sensor_key) if not value else (
            re.sub(r'[「」『』"\'""]', '', value).strip() if sensor_key == "content" else value
        )

    def _get_default_value(self, sensor_key: str) -> str:
        """获取默认值"""
        return {
            "content": "无有效内容",
            "author": "佚名", 
            "origin": "未知",
            "dynasty": "未知",
            "annotation": "无"
        }.get(sensor_key, "暂无数据")

    def _create_error_response(self) -> Dict[str, Any]:
        """创建错误响应"""
        return {
            "content": "无有效内容",
            "author": "佚名",
            "origin": "未知", 
            "dynasty": "未知",
            "annotation": "无",
            "update_time": datetime.now().isoformat()
        }