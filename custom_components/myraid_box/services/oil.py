from typing import Dict, Any, List
import logging
import re
from bs4 import BeautifulSoup
from ..service_base import BaseService, SensorConfig, RequestConfig

_LOGGER = logging.getLogger(__name__)


class OilService(BaseService):
    """每日油价服务"""

    DEFAULT_API_URL = "http://www.qiyoujiage.com"
    DEFAULT_UPDATE_INTERVAL = 360

    # 省份映射
    PROVINCE_MAP = {
        "北京": "beijing", "上海": "shanghai", "广东": "guangdong",
        "天津": "tianjin", "重庆": "chongqing", "浙江": "zhejiang",
        "江苏": "jiangsu", "山东": "shandong", "四川": "sichuan"
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
        return "获取各省市最新油价"

    @property
    def config_fields(self) -> Dict[str, Dict[str, Any]]:
        return {
            "interval": {
                "name": "更新间隔",
                "type": "int",
                "default": self.DEFAULT_UPDATE_INTERVAL,
                "description": "更新间隔（分钟）"
            },
            "province": {
                "name": "省份",
                "type": "select", 
                "default": "浙江",
                "options": sorted(self.PROVINCE_MAP.keys())
            }
        }

    def _get_sensor_configs(self) -> List[SensorConfig]:
        """传感器配置"""
        return [
            self._create_sensor_config("province", "省份", "mdi:map-marker"),
            self._create_sensor_config("92#", "92号", "mdi:gas-station", "元/升"),
            self._create_sensor_config("95#", "95号", "mdi:gas-station", "元/升"), 
            self._create_sensor_config("98#", "98号", "mdi:gas-station", "元/升"),
            self._create_sensor_config("0#", "0号", "mdi:gas-station", "元/升"),
            self._create_sensor_config("tips", "提示", "mdi:information")
        ]

    def _build_base_request(self, params: Dict[str, Any]) -> RequestConfig:
        """构建请求"""
        province = params.get("province", "浙江")
        province_pinyin = self.PROVINCE_MAP.get(province, "zhejiang")
        
        return RequestConfig(
            url=f"{self.default_api_url}/{province_pinyin}.shtml",
            method="GET",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )

    def _parse_raw_response(self, response_data: Any) -> Dict[str, Any]:
        """解析响应数据"""
        if not isinstance(response_data, str):
            return {"status": "error", "error": "无效响应"}

        try:
            soup = BeautifulSoup(response_data, "html.parser")
            
            result = {
                "province": self._get_province_from_params(),
                "92#": None,
                "95#": None, 
                "98#": None,
                "0#": None,
                "tips": "暂无信息"
            }

            # 解析油价
            self._parse_oil_prices(soup, result)
            # 解析提示信息
            self._parse_tips(soup, result)

            return result
            
        except Exception as e:
            return {"status": "error", "error": f"解析失败: {str(e)}"}

    def _get_province_from_params(self) -> str:
        """从配置参数获取省份"""
        # 这里需要访问配置参数，简化处理返回默认值
        return "浙江"

    def _parse_oil_prices(self, soup: BeautifulSoup, result: Dict[str, Any]) -> None:
        """解析油价"""
        oil_dls = soup.select("#youjia dl")
        
        for dl in oil_dls:
            dt = dl.find('dt')
            dd = dl.find('dd')
            
            if not dt or not dd:
                continue
                
            oil_text = dt.get_text().strip()
            price_text = dd.get_text().strip()
            
            price_match = re.search(r'(\d+\.\d+)', price_text)
            if price_match:
                price = float(price_match.group(1))
                
                if "92" in oil_text:
                    result["92#"] = price
                elif "95" in oil_text:
                    result["95#"] = price
                elif "98" in oil_text:
                    result["98#"] = price
                elif "0" in oil_text:
                    result["0#"] = price

    def _parse_tips(self, soup: BeautifulSoup, result: Dict[str, Any]) -> None:
        """解析提示信息"""
        info_container = soup.select_one("#youjiaCont")
        if not info_container:
            return
            
        text = info_container.get_text(strip=True)
        
        # 提取调整时间
        time_match = re.search(r'下次油价\s*(\d+月\d+日\d*时)\s*调整', text)
        time_info = time_match.group(1) if time_match else ""
        
        # 提取走势信息
        trend_element = info_container.select_one('span[style*="color:#F00"]')
        trend_text = trend_element.get_text().strip() if trend_element else ""
        trend_text = re.sub(r'，大家相互转告.*', '', trend_text)
        
        # 合并信息
        if time_info and trend_text:
            result["tips"] = f"{time_info}调整，{trend_text}"
        elif time_info:
            result["tips"] = f"{time_info}调整"
        elif trend_text:
            result["tips"] = trend_text

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> None:
        """验证配置"""
        province = config.get("province")
        if province and province not in cls.PROVINCE_MAP:
            raise ValueError(f"无效省份: {province}")