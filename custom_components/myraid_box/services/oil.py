from datetime import datetime
from typing import Dict, Any, Optional
import re
import logging
from bs4 import BeautifulSoup
import aiohttp
from ..service_base import BaseService, AttributeConfig

_LOGGER = logging.getLogger(__name__)

DEFAULT_OIL_URL = "http://www.qiyoujiage.com/"

class OilService(BaseService):
    """增强版油价服务"""

    PROVINCE_MAP = {
        "北京": "beijing", "上海": "shanghai", "广东": "guangdong",
        "天津": "tianjin", "重庆": "chongqing", "河北": "hebei",
        "山西": "shanxi", "辽宁": "liaoning", "吉林": "jilin",
        "黑龙江": "heilongjiang", "江苏": "jiangsu", "浙江": "zhejiang",
        "安徽": "anhui", "福建": "fujian", "江西": "jiangxi",
        "山东": "shandong", "河南": "henan", "湖北": "hubei",
        "湖南": "hunan", "海南": "hainan", "四川": "sichuan",
        "贵州": "guizhou", "云南": "yunnan", "陕西": "shaanxi",
        "甘肃": "gansu", "青海": "qinghai", "台湾": "taiwan",
        "内蒙古": "neimenggu", "广西": "guangxi", "西藏": "xizang",
        "宁夏": "ningxia", "新疆": "xinjiang", "香港": "xianggang",
        "澳门": "aomen"
    }

    def __init__(self):
        super().__init__()

    @property
    def service_id(self) -> str:
        return "oil_price"

    @property
    def name(self) -> str:
        return "每日油价"

    @property
    def description(self) -> str:
        return "各省市最新油价（数据来源：汽油价格网）"

    @property
    def icon(self) -> str:
        return "mdi:gas-station"

    @property
    def config_fields(self) -> Dict[str, Dict[str, Any]]:
        return {
            "url": {
                "name": "API地址",
                "type": "str",
                "required": True,
                "default": DEFAULT_OIL_URL,
                "description": "模板变量: {province}将被替换为拼音"
            },
            "interval": {
                "name": "更新间隔",
                "type": "int",
                "default": 360,
                "min": 60,
                "max": 1440,
                "unit": "分钟"
            },
            "province": {
                "name": "省份",
                "type": "str",
                "required": True,
                "default": "北京",
                "options": list(self.PROVINCE_MAP.keys())
            }
        }

    async def fetch_data(self, coordinator, params: Dict[str, Any]) -> Dict[str, Any]:
        """获取油价数据"""
        province = params["province"]
        base_url = params["url"]
        
        pinyin = self.PROVINCE_MAP.get(province, "beijing")
        url = base_url.replace("{province}", pinyin)

        # 调用基类的网络请求方法
        response = await self._make_request(url)

        if response["status"] == "success":
            html = response["data"]
            return await self._parse_html(html, province, url)
        else:
            return {
                "error": response["error"],
                "province": province,
                "update_time": datetime.now().isoformat(),
                "status": "error"
            }

    async def _parse_html(self, html: str, province: str, source_url: str) -> Dict[str, Any]:
        """解析HTML页面"""
        soup = BeautifulSoup(html, "lxml")
        result = {
            "province": province,
            "source_url": source_url,
            "update_time": datetime.now().isoformat(),
            "status": "success",
            "prices": {}
        }
        
        # 解析油品价格
        for dl in soup.select("#youjia > dl"):
            if match := re.search(r"(\d+)#", dl.dt.text):
                oil_type = match.group(1)
                price = dl.dd.text.strip()
                result["prices"][oil_type] = price
                result[oil_type] = price  # 兼容旧版
        
        # 解析状态信息
        if state_div := soup.select_one("#youjiaCont > div:nth-child(2)"):
            result["status"] = state_div.get_text(" ", strip=True)
        
        return result

    def format_sensor_value(self, data: Any, sensor_config: Dict[str, Any]) -> str:
        """油价信息格式化"""
        if not data:
            return "⏳ 获取油价中..."
        
        if "error" in data:
            return f"⚠️ 错误: {data['error']}"

        lines = [f"📍 {data['province']}"]
        
        # 添加油价信息
        for oil_type in ["0", "92", "95", "98"]:
            if price := data.get(oil_type):
                lines.append(f"⛽ {oil_type}#: {price}元")
                
        # 添加状态信息
        if status := data.get("status"):
            lines.append(f"📢 {status}")
            
        return "\n".join(lines) if len(lines) > 1 else "无数据"

    def get_sensor_attributes(self, data: Any, sensor_config: Dict[str, Any]) -> Dict[str, Any]:
        """油价属性信息"""
        if not data:
            return {}
            
        attrs = {
            "update_time": data.get("update_time"),
            "data_source": data.get("source_url")
        }
        
        # 添加油品价格
        for oil_type, config in self.attributes.items():
            if oil_type in data:
                attrs[config["name"]] = data[oil_type]
                
        # 添加省份信息
        if province := data.get("province"):
            attrs["省份"] = province
            
        return attrs

    async def async_unload(self):
        """清理资源"""
        if self._session and not self._session.closed:
            await self._session.close()
            _LOGGER.debug("油价服务会话已关闭")