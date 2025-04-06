from datetime import timedelta, datetime
from typing import Dict, Any
from bs4 import BeautifulSoup
import re
import logging
from ..service_base import BaseService, AttributeConfig
from ..const import DOMAIN, DEVICE_MANUFACTURER, DEVICE_MODEL

_LOGGER = logging.getLogger(__name__)

class OilService(BaseService):
    """每日油价服务"""
    
    PROVINCE_MAP = {
        "beijing": "北京",
        "shanghai": "上海",
        "guangdong": "广东",
        # 其他省份...
    }
    
    @property
    def service_id(self) -> str:
        return "oil"
    
    @property
    def name(self) -> str:
        return "每日油价"
    
    @property
    def description(self) -> str:
        return "全国各省市实时油价查询（含0#柴油和98#汽油）"
    
    @property
    def url(self) -> str:
        return "http://www.qiyoujiage.com/{province}.shtml"
    
    @property
    def interval(self) -> timedelta:
        return timedelta(hours=1)
    
    @property
    def icon(self) -> str:
        return "mdi:gas-station"
    
    @property
    def config_fields(self) -> Dict[str, Dict[str, Any]]:
        return {
            "province": {
                "display_name": "省份名称",
                "description": "请输入省份拼音小写（如：beijing、guangdong）",
                "required": True,
                "default": "beijing"
            }
        }
    
    @property
    def attributes(self) -> Dict[str, AttributeConfig]:
        return {
            "0": {
                "name": "0号柴油",
                "icon": "mdi:gas-station",
                "unit": "元/L"
            },
            "92": {
                "name": "92号汽油",
                "icon": "mdi:gas-station",
                "unit": "元/L"
            },
            "95": {
                "name": "95号汽油",
                "icon": "mdi:gas-station",
                "unit": "元/L"
            },
            "98": {
                "name": "98号汽油",
                "icon": "mdi:gas-station",
                "unit": "元/L"
            },
            "update_time": {
                "name": "更新时间",
                "icon": "mdi:clock-outline"
            },
            "state": {
                "name": "油价状态",
                "icon": "mdi:information-outline"
            },
            "tips": {
                "name": "油价提示",
                "icon": "mdi:alert-circle-outline"
            }
        }
    
    async def fetch_data(self, coordinator, params):
        """获取油价数据"""
        province = params.get("province", "beijing")
        url = self.url.format(province=province)
        
        async with coordinator.session.get(url) as resp:
            html = await resp.text()
            return await self._parse_oil_data(html, province)
    
    async def _parse_oil_data(self, html: str, province: str) -> dict:
        """解析油价网页数据"""
        try:
            soup = BeautifulSoup(html, "lxml")
            result = {
                "province": self.PROVINCE_MAP.get(province, province),
                "update_time": datetime.now().strftime('%Y-%m-%d %H:%M'),
                "oil_types": {}
            }
            
            # 解析所有油品数据
            dls = soup.select("#youjia > dl")
            for dl in dls:
                dt_text = dl.select('dt')[0].text
                dd_text = dl.select('dd')[0].text
                
                # 匹配油品类型（92/95/98/0）
                if match := re.search(r"(\d+|0)#", dt_text):
                    oil_type = match.group(1)
                    result["oil_types"][oil_type] = {
                        "name": f"{oil_type}号" + ("柴油" if oil_type == "0" else "汽油"),
                        "price": dd_text
                    }
            
            # 添加直接访问的快捷字段
            for oil_type in ["0", "92", "95", "98"]:
                if oil_type in result["oil_types"]:
                    result[oil_type] = result["oil_types"][oil_type]["price"]
            
            # 解析状态信息
            state_div = soup.select("#youjiaCont > div")
            if len(state_div) > 1:
                result["state"] = state_div[1].contents[0].strip()
            
            tips_span = soup.select("#youjiaCont > div:nth-of-type(2) > span")
            if tips_span:
                result["tips"] = tips_span[0].text.strip()
                
            return result
            
        except Exception as e:
            _LOGGER.error(f"解析油价数据失败: {str(e)}")
            return {
                "error": str(e),
                "province": province
            }
    
    def format_main_value(self, data):
        """格式化油价主传感器显示"""
        if not data or "error" in data:
            return "暂无油价数据"
        
        prices = []
        for oil_type in ["0", "92", "95", "98"]:
            if oil_type in data:
                prices.append(f"{data[oil_type]}元")
        
        return f"{data.get('province', '')}油价: {', '.join(prices)}" if prices else "暂无油价数据"