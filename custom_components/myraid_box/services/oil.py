from __future__ import annotations
from datetime import datetime
from typing import Dict, Any, List
import re
import logging
from bs4 import BeautifulSoup
from ..service_base import BaseService, SensorConfig

_LOGGER = logging.getLogger(__name__)

class OilService(BaseService):
    """多传感器版每日油价服务"""

    DEFAULT_API_URL = "http://www.qiyoujiage.com/"
    DEFAULT_UPDATE_INTERVAL = 360

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
            "interval": {
                "name": "更新间隔",
                "type": "int",
                "default": self.DEFAULT_UPDATE_INTERVAL,
                "description": "更新间隔时间（分钟）"
            },
            "province": {
                "name": "省份",
                "type": "select",
                "default": "浙江",
                "description": "查询省份",
                "options": sorted(self.CATEGORY_MAP.keys(), key=lambda x: self.CATEGORY_MAP[x])
            }
        }

    def _get_sensor_configs(self) -> List[SensorConfig]:
        """返回每日油价的所有传感器配置（按显示顺序）"""
        return [
            self._create_sensor_config("92#", "92号", "mdi:gas-station", "元/升"),
            self._create_sensor_config("95#", "95号", "mdi:gas-station", "元/升"),
            self._create_sensor_config("98#", "98号", "mdi:gas-station", "元/升"),
            self._create_sensor_config("0#", "0号", "mdi:gas-station", "元/升"),
            self._create_sensor_config("province", "省份", "mdi:map-marker"),
            self._create_sensor_config("info", "窗口期", "mdi:calendar-clock"),
            self._create_sensor_config("tips", "走势", "mdi:chart-line")
        ]

    def build_request(self, params: Dict[str, Any]) -> tuple[str, Dict[str, Any], Dict[str, str]]:
        """构建请求参数"""
        base_url = self.default_api_url
        province_pinyin = self.CATEGORY_MAP.get(params["province"], "zhejiang")
        
        url = f"{base_url}/{province_pinyin}.shtml"
        headers = {
            "User-Agent": f"HomeAssistant/{self.service_id}",
            "Accept": "text/html"
        }
        return url, {}, headers

    def _build_request_headers(self) -> Dict[str, str]:
        """构建请求头"""
        return {
            "User-Agent": f"HomeAssistant/{self.service_id}",
            "Accept": "text/html"
        }
        
    def parse_response(self, response_data: Any) -> Dict[str, Any]:
        """解析响应数据为标准化字典"""
        if isinstance(response_data.get("data"), str):
            # 解析 HTML 内容
            soup = BeautifulSoup(response_data["data"], "html.parser")
            result = self._create_default_result(response_data.get("update_time", datetime.now().isoformat()))

            # 解析省份信息
            self._parse_province(soup, result)

            # 解析油品价格
            self._parse_oil_prices(soup, result)

            # 解析调价信息
            self._parse_adjustment_info(soup, result)

            return result
        else:
            # 如果响应数据不是 HTML 字符串，直接返回数据
            return response_data.get("data", {
                "update_time": response_data.get("update_time", datetime.now().isoformat())
            })

    def _create_default_result(self, update_time: str) -> Dict[str, Any]:
        """创建默认结果"""
        return {
            "status": "success",
            "province": "未知",
            "update_time": update_time, 
            "0#": "未知",
            "92#": "未知",
            "95#": "未知",
            "98#": "未知",
            "info": "未知",
            "tips": "未知"
        }

    def _parse_province(self, soup: BeautifulSoup, result: Dict[str, Any]) -> None:
        """解析省份信息"""
        title = soup.find("title")
        if title:
            title_text = title.text
            for province in self.CATEGORY_MAP.keys():
                if province in title_text:
                    result["province"] = province
                    break

    def _parse_oil_prices(self, soup: BeautifulSoup, result: Dict[str, Any]) -> None:
        """解析油品价格"""
        for dl in soup.select("#youjia > dl"):
            dt_text = dl.select('dt')[0].text.strip() if dl.select('dt') else ""
            dd_text = dl.select('dd')[0].text.strip() if dl.select('dd') else ""
            
            if match := re.search(r"(\d+)#", dt_text):
                oil_type = f"{match.group(1)}#"
                result[oil_type] = dd_text

    def _parse_adjustment_info(self, soup: BeautifulSoup, result: Dict[str, Any]) -> None:
        """解析调价信息"""
        # 解析调价信息
        info_divs = soup.select("#youjiaCont > div")
        if len(info_divs) > 1:
            result["info"] = info_divs[1].contents[0].strip() if info_divs[1].contents else "未知"
        
        # 解析涨跌信息
        tips_span = soup.select("#youjiaCont > div:nth-of-type(2) > span")
        if tips_span:
            result["tips"] = tips_span[0].text.strip()
            
        # 如果上面的选择器没有获取到完整信息，尝试其他选择器
        if result["tips"] == "未知" or len(result["tips"]) < 10:
            alternative_tips = soup.select("#youjiaCont > div")
            for div in alternative_tips:
                text = div.get_text().strip()
                if "预计下调" in text or "预计上调" in text:
                    result["tips"] = text
                    break

    def format_sensor_value(self, sensor_key: str, data: Any) -> Any:
        """格式化特定传感器的显示值"""
        value = self.get_sensor_value(sensor_key, data)
        
        if value is None:
            return "暂无数据"
            
        formatters = {
            "92#": self._format_oil_price,
            "95#": self._format_oil_price,
            "98#": self._format_oil_price,
            "0#": self._format_oil_price,
            "province": self._format_province,
            "info": self._format_info,
            "tips": self._format_tips
        }
        
        formatter = formatters.get(sensor_key, str)
        return formatter(value)

    def _format_oil_price(self, value: str) -> str:
        """格式化油价"""
        cleaned_value = value.replace("元/升", "").strip()
        return f"{cleaned_value}" if cleaned_value and cleaned_value != "未知" else "暂无数据"

    def _format_province(self, value: str) -> str:
        return value if value and value != "未知" else "未知省份"

    def _format_info(self, value: str) -> str:
        """格式化调价窗口期"""
        if value and value != "未知":
            if "下次油价" in value and "调整" in value:
                time_part = value.replace("下次油价", "").replace("调整", "").strip()
                return time_part
            return value
        return "暂无窗口期信息"

    def _format_tips(self, value: str) -> str:
        """格式化油价走势"""
        if value and value != "未知":
            if "预计下调" in value or "预计上调" in value:
                pattern = r'预计(?:上调|下调)油价.*?元/吨\(.*?\)'
                match = re.search(pattern, value)
                if match:
                    return match.group()
                else:
                    if "预计下调" in value:
                        start = value.find("预计下调")
                        return value[start:] if start != -1 else value
                    elif "预计上调" in value:
                        start = value.find("预计上调")
                        return value[start:] if start != -1 else value
            elif "搁浅" in value or "不作调整" in value:
                return "本轮搁浅"
            return value
        return "暂无走势信息"