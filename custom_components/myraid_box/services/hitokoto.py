from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from urllib.parse import urlparse, parse_qs, urlencode
import logging
import aiohttp
from ..service_base import BaseService, AttributeConfig

_LOGGER = logging.getLogger(__name__)

DEFAULT_HITOKOTO_API = "https://v1.hitokoto.cn/"

class HitokotoService(BaseService):
    """增强版一言服务"""

    # 修改后的分类映射，类似油价的省份映射
    CATEGORY_MAP = {
        "动画": "a", "漫画": "b", "游戏": "c", "文学": "d",
        "原创": "e", "来自网络": "f", "其他": "g", "影视": "h",
        "诗词": "i", "网易云": "j", "哲学": "k", "抖机灵": "l"
    }

    def __init__(self):
        super().__init__()
        self._session = None
        self._last_fetch_time = None

    @property
    def service_id(self) -> str:
        return "hitokoto"

    @property
    def name(self) -> str:
        return "每日一言"

    @property
    def description(self) -> str:
        return "获取励志名言（支持自定义API源）"

    @property
    def icon(self) -> str:
        return "mdi:format-quote-close"

    @property
    def config_fields(self) -> Dict[str, Dict[str, Any]]:
        return {
            "url": {
                "name": "API地址",
                "type": "str",
                "required": True,
                "default": DEFAULT_HITOKOTO_API,
                "description": "支持参数：\n- c=d 文学\n- c=i 诗词\n- c=k 哲学",
                "regex": r"^https?://v1\.hitokoto\.cn/.*",
                "placeholder": DEFAULT_HITOKOTO_API
            },
            "interval": {
                "name": "更新间隔",
                "type": "int",
                "default": 30,
                "min": 10,
                "max": 1440,
                "unit": "分钟",
                "description": "建议30分钟更新一次"
            },
            "category": {
                "name": "分类",
                "type": "str",
                "required": False,
                "default": "哲学",
                "options": list(self.CATEGORY_MAP.keys()),
                "description": "选择一言的分类"
            }
        }

    @property
    def attributes(self) -> Dict[str, AttributeConfig]:
        return {
            "from": {"name": "来源", "icon": "mdi:source-branch"},
            "from_who": {"name": "作者", "icon": "mdi:account"},
            "type": {"name": "分类", "icon": "mdi:tag", "value_map": {v: k for k, v in self.CATEGORY_MAP.items()}}
        }

    async def ensure_session(self):
        """确保会话存在"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))
            _LOGGER.debug("创建新的HTTP会话")

    async def fetch_data(self, coordinator, params: Dict[str, Any]) -> Dict[str, Any]:
        """获取一言数据（带重试机制）"""
        await self.ensure_session()
        base_url = params["url"].strip()
        category = params.get("category", "哲学")  # 默认分类为哲学
        
        # 根据分类动态调整URL
        category_code = self.CATEGORY_MAP.get(category, "k")  # 默认为哲学
        query_params = parse_qs(urlparse(base_url).query)
        query_params["c"] = [category_code]
        url = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}{urlparse(base_url).path}?{urlencode(query_params, doseq=True)}"
        
        try:
            _LOGGER.debug("正在从 %s 获取数据...", url)
            async with self._session.get(url, headers={
                "Accept": "application/json",
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
            _LOGGER.error("获取数据失败: %s", str(e), exc_info=True)
            return {
                "error": str(e),
                "api_source": urlparse(url).netloc,
                "update_time": datetime.now().isoformat(),
                "status": "error"
            }

    def format_sensor_value(self, data: Any, sensor_config: Dict[str, Any]) -> str:
        """格式化显示内容"""
        if not data or data.get("status") != "success":
            return "⚠️ 数据获取失败" if data and "error" in data else "⏳ 加载中..."
            
        parts = [data.get("hitokoto", "暂无内容")]
        
        # 添加作者信息
        if author := data.get("from_who"):
            parts.append(f"—— {author}")
            
        # 添加来源信息
        if source := data.get("from"):
            parts.append(f"「{source}」")
            
        # 添加分类信息
        if type_ := data.get("type"):
            parts.append(f"分类: {self.attributes['type']['value_map'].get(type_, '未知')}")
            
        return "\n".join(parts)

    def get_sensor_attributes(self, data: Any, sensor_config: Dict[str, Any]) -> Dict[str, Any]:
        """构建属性字典"""
        if not data:
            return {}
            
        attrs = {
            "update_time": data.get("update_time"),
            "api_source": data.get("api_source"),
            "status": data.get("status", "unknown")
        }
        
        # 添加标准属性
        for attr, config in self.attributes.items():
            if value := data.get(attr):
                if "value_map" in config:
                    value = config["value_map"].get(str(value), value)
                attrs[config["name"]] = value
                
        # 添加错误信息（如果存在）
        if "error" in data:
            attrs["error"] = data["error"]
            
        return attrs

    async def async_unload(self):
        """清理资源"""
        if self._session and not self._session.closed:
            await self._session.close()
            _LOGGER.debug("HTTP会话已关闭")