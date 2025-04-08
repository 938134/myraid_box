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
    
    # 映射表：中文省份名称映射到拼音
    PROVINCE_MAP = {
        "北京": "beijing",
        "上海": "shanghai",
        "广东": "guangdong",
        "天津": "tianjin",
        "重庆": "chongqing",
        "河北": "hebei",
        "山西": "shanxi",
        "辽宁": "liaoning",
        "吉林": "jilin",
        "黑龙江": "heilongjiang",
        "江苏": "jiangsu",
        "浙江": "zhejiang",
        "安徽": "anhui",
        "福建": "fujian",
        "江西": "jiangxi",
        "山东": "shandong",
        "河南": "henan",
        "湖北": "hubei",
        "湖南": "hunan",
        "广东": "guangdong",
        "海南": "hainan",
        "四川": "sichuan",
        "贵州": "guizhou",
        "云南": "yunnan",
        "陕西": "shaanxi",
        "甘肃": "gansu",
        "青海": "qinghai",
        "台湾": "taiwan",
        "内蒙古": "neimenggu",
        "广西": "guangxi",
        "西藏": "xizang",
        "宁夏": "ningxia",
        "新疆": "xinjiang",
        "香港": "xianggang",
        "澳门": "aomen"
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
        # 用户直接输入中文省份名称
        return {
            "province": {
                "display_name": "省份名称",
                "description": "请输入省份中文名称（如：北京、广东）",
                "required": True,
                "default": "北京"
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
        province_zh = params.get("province", "北京")  # 用户输入的中文省份名称
        province_pinyin = self.PROVINCE_MAP.get(province_zh, "beijing")  # 转换为拼音
        url = self.url.format(province=province_pinyin)
        
        try:
            async with coordinator.session.get(url) as resp:
                html = await resp.text()
                return await self._parse_oil_data(html, province_zh)
        except Exception as e:
            _LOGGER.error(f"获取油价数据失败: {str(e)}")
            return {
                "error": f"获取油价数据失败: {str(e)}",
                "province": province_zh
            }
    
    async def _parse_oil_data(self, html: str, province_zh: str) -> dict:
        """解析油价网页数据"""
        try:
            soup = BeautifulSoup(html, "lxml")
            result = {
                "province": province_zh,  # 使用中文省份名称
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
                "error": f"解析油价数据失败: {str(e)}",
                "province": province_zh
            }
            
    def format_main_value(self, data):
        """格式化油价主传感器显示"""
        if not data or "error" in data:
            return "暂无油价数据"
        
        # 油品价格信息
        price_lines = [
            f"⛽0#柴油: {data['0']}元" if '0' in data else None,
            f"⛽92#汽油: {data['92']}元" if '92' in data else None,
            f"⛽95#汽油: {data['95']}元" if '95' in data else None,
            f"⛽98#汽油: {data['98']}元" if '98' in data else None
        ]
        price_lines = [line for line in price_lines if line is not None]  # 移除空行
        
        # 构建结果
        result = []
        if price_lines:
            result.extend(price_lines)
        
        # 添加状态信息（如果有）
        if "state" in data:
            result.append(f"📢{data['state']}")
            
        # 添加提示信息（如果有）
        if "tips" in data:
            result.append(f"💡{data['tips']}")
        
        return "\n".join(result) if result else "暂无油价数据"