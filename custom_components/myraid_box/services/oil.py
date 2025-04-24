from __future__ import annotations
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
import re
import logging
from bs4 import BeautifulSoup
from ..service_base import BaseService, AttributeConfig

_LOGGER = logging.getLogger(__name__)

DEFAULT_OIL_URL = "http://www.qiyoujiage.com/"

class OilService(BaseService):
    """完整实现的油价查询服务"""

    CATEGORY_MAP = {
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
        return "oilprice"

    @property
    def name(self) -> str:
        return "每日油价"

    @property
    def description(self) -> str:
        return "从汽油价格网获取各省市最新油价"

    @property
    def icon(self) -> str:
        return "mdi:gas-station"

    @property
    def config_fields(self) -> Dict[str, Dict[str, Any]]:
        return {
            "url": {
                "name": "API地址",
                "type": "str",
                "default": DEFAULT_OIL_URL,
                "description": "汽油价格网地址"
            },
            "interval": {
                "name": "更新间隔（分钟）",
                "type": "int",
                "default": 360,
                "description": "更新间隔时间"
            },
            "province": {
                "name": "省份",
                "type": "select",
                "default": "浙江",
                "description": "查询省份",
                "options": sorted(self.CATEGORY_MAP.keys(), key=lambda x: self.CATEGORY_MAP[x])
            }
        }

    @property
    def attributes(self) -> Dict[str, AttributeConfig]:
        return {
            "0#": {"name": "0号柴油", "icon": "mdi:gas-station"},
            "92#": {"name": "92号汽油", "icon": "mdi:gas-station"},
            "95#": {"name": "95号汽油", "icon": "mdi:gas-station"},
            "98#": {"name": "98号汽油", "icon": "mdi:gas-station"},
            "info": {"name": "调价窗口", "icon": "mdi:calendar"},
            "tips": {"name": "价格趋势", "icon": "mdi:trending-up"},
            "update_time": {"name": "更新时间", "icon": "mdi:clock"}
        }

    def build_request(self, params: Dict[str, Any]) -> tuple[str, Dict[str, Any], Dict[str, str]]:
        """构建请求参数"""
        base_url = params["url"].strip('/')
        province_pinyin = self.CATEGORY_MAP.get(params["province"], "zhejiang")
        
        url = f"{base_url}/{province_pinyin}.shtml"
        headers = {
            "User-Agent": f"HomeAssistant/{self.service_id}",
            "Accept": "text/html"
        }
        return url, {}, headers
        
    def parse_response(self, response_data: Any) -> Dict[str, Any]:
        """统一解析响应数据"""
        if isinstance(response_data.get("data"), str):
            # 直接解析 HTML 内容
            soup = BeautifulSoup(response_data["data"], "html.parser")
            result = {
                "status": "success",
                "province": "未知",  # 默认值，稍后从网页内容中解析
                "update_time": response_data.get("update_time", datetime.now().isoformat()), 
                "0#": "未知",
                "92#": "未知",
                "95#": "未知",
                "98#": "未知",
                "info": "未知",
                "tips": "未知"
            }

            # 解析省份信息
            title = soup.find("title").text
            for province in self.CATEGORY_MAP.keys():
                if province in title:
                    result["province"] = province
                    break

            # 解析油品价格
            for dl in soup.select("#youjia > dl"):
                dt_text = dl.select('dt')[0].text.strip()
                dd_text = dl.select('dd')[0].text.strip()
                
                if match := re.search(r"(\d+)#", dt_text):
                    oil_type = f"{match.group(1)}#"
                    result[oil_type] = dd_text

            # 解析调价信息
            info_divs = soup.select("#youjiaCont > div")
            if len(info_divs) > 1:
                result["info"] = info_divs[1].contents[0].strip()
            
            # 解析涨跌信息
            tips_span = soup.select("#youjiaCont > div:nth-of-type(2) > span")
            if tips_span:
                result["tips"] = tips_span[0].text.strip()

            return result
        else:
            # 如果响应数据不是 HTML 字符串，直接返回数据
            return response_data.get("data", {
                "update_time": response_data.get("update_time", datetime.now().isoformat())
            })

    def format_sensor_value(self, data: Any, sensor_config: Dict[str, Any]) -> str:
        """生成主传感器显示值"""
        if not data or data.get("status") != "success":
            return "⏳ 数据获取中..." if data is None else f"⚠️ {data.get('error', '获取失败')}"

        parsed_data = self.parse_response(data)
        lines = [f"📍 {parsed_data['province']}"] 
        
        for oil_type in ["0#", "92#", "95#", "98#"]:
            if oil_type in parsed_data:
                lines.append(f"⛽ {self.attributes[oil_type]['name']}: {parsed_data[oil_type]}元")
        
        if parsed_data.get("info") != "未知":
            lines.append(f"📅 {parsed_data['info']}")
        
        if parsed_data.get("tips") != "未知":
            lines.append(f"📈 {parsed_data['tips']}")
        
        return "\n".join(lines)

    def get_sensor_attributes(self, data: Any, sensor_config: Dict[str, Any]) -> Dict[str, Any]:
        """生成传感器属性字典"""
        if not data or data.get("status") != "success":
            return {}

        parsed_data = self.parse_response(data)
        attributes = {
            attr: parsed_data.get(attr, "未知")
            for attr in self.attributes.keys()
        }
        attributes["update_time"] = parsed_data.get("update_time", datetime.now().isoformat())
        
        # 调用父类方法处理值映射等通用逻辑
        return super().get_sensor_attributes(attributes, sensor_config)

    def get_sensor_configs(self, service_data: Any) -> List[Dict[str, Any]]:
        """返回传感器配置列表"""
        return [{
            "key": "main",
            "name": self.name,
            "icon": self.icon,
            "unit": None,
            "device_class": None
        }]