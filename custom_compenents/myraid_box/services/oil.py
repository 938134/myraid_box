import logging
from datetime import timedelta
from bs4 import BeautifulSoup
from .base import BaseService
from ..const import register_service

_LOGGER = logging.getLogger(__name__)

@register_service(
    name="每日油价",
    description="全国各省市实时油价查询",
    url="http://www.qiyoujiage.com/{province}.shtml",
    interval=timedelta(hours=6),
    icon="mdi:gas-station",
    attributes={
        "0": {"name": "0号柴油", "icon": "mdi:gas-station", "unit": "元/L"},
        "92": {"name": "92号汽油", "icon": "mdi:gas-station", "unit": "元/L"},
        "update_time": {"name": "更新时间", "icon": "mdi:clock-outline"}
    },
    config_fields={
        "province": {
            "display_name": "省份拼音",
            "description": "如: beijing/shanghai",
            "default": "beijing"
        }
    }
)
class OilService(BaseService):
    async def async_update_data(self) -> dict:
        province = self.config_entry.data.get("oil_province", "beijing")
        url = ServiceRegistry.get("oil")["url"].format(province=province)
        
        try:
            async with self.session.get(url) as resp:
                html = await resp.text()
                return self._parse_oil_data(html, province)
        except Exception as e:
            _LOGGER.error(f"油价数据获取失败: {e}")
            return {"error": str(e), "province": province}
    
    def _parse_oil_data(self, html: str, province: str) -> dict:
        """解析油价页面"""
        soup = BeautifulSoup(html, 'html.parser')
        # 实际解析逻辑...
        return {
            "0": "7.50",
            "92": "8.00",
            "update_time": "2023-11-15 08:00",
            "province": province
        }