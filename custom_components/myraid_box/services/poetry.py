# poetry.py 完整修复
from datetime import datetime
from typing import Dict, Any, Optional
from urllib.parse import urlparse
import logging
import aiohttp
from custom_components.myraid_box.service_base import BaseService, AttributeConfig

_LOGGER = logging.getLogger(__name__)

DEFAULT_POETRY_API = "https://v1.jinrishici.com/all"

class PoetryService(BaseService):
    """增强版诗词服务"""

    def __init__(self):
        super().__init__()
        self._session = None

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
                "description": "支持以下端点：\n- 默认: https://v1.jinrishici.com/all\n- 备用: https://api.jinrishici.com/v1/sentence",
                "regex": r"^https?://(v1\.|api\.)?jinrishici\.com/",
                "placeholder": DEFAULT_POETRY_API
            },
            "interval": {
                "name": "更新间隔",
                "type": "int",
                "default": 10,
                "min": 10,
                "max": 1440,
                "unit": "分钟"
            }
        }

    async def ensure_session(self):
        """确保会话存在"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10))
            _LOGGER.debug("创建诗词API会话")

    async def fetch_data(self, coordinator, params: Dict[str, Any]) -> Dict[str, Any]:
        """获取诗词数据"""
        await self.ensure_session()
        url = params["url"].strip()
        
        try:
            _LOGGER.debug("正在从 %s 获取诗词...", url)
            async with self._session.get(url, headers={
                "User-Agent": "HomeAssistant/MyraidBox"
            }) as resp:
                resp.raise_for_status()
                data = await resp.json()
                
                return {
                    **data,
                    "api_source": urlparse(url).netloc,
                    "update_time": datetime.now().isoformat(),
                    "status": "success"
                }
                
        except Exception as e:
            _LOGGER.error("诗词获取失败: %s", str(e), exc_info=True)
            return {
                "error": str(e),
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

    async def async_unload(self):
        """清理资源"""
        if self._session and not self._session.closed:
            await self._session.close()
            _LOGGER.debug("诗词服务会话已关闭")