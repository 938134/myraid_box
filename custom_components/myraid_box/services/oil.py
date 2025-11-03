from typing import Dict, Any, List
from datetime import datetime
import logging
import re
from bs4 import BeautifulSoup
from ..service_base import BaseService, SensorConfig, RequestConfig

_LOGGER = logging.getLogger(__name__)


class OilService(BaseService):
    """每日油价服务 - 使用新版基类"""

    DEFAULT_API_URL = "http://www.qiyoujiage.com"
    DEFAULT_UPDATE_INTERVAL = 360  # 油价变化较慢，6小时更新一次
    DEFAULT_TIMEOUT = 30

    # 省份映射
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
        self._current_province = "浙江"  # 默认省份

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
    def config_help(self) -> str:
        return "⛽ 油价服务配置说明：\n1. 选择要查询的省份\n2. 油价数据每天更新，建议设置较长更新间隔"

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
                "options": sorted(self.PROVINCE_MAP.keys())
            }
        }

    def _get_sensor_configs(self) -> List[SensorConfig]:
        """返回每日油价的所有传感器配置"""
        return [
            self._create_sensor_config("92#", "92号汽油", "mdi:gas-station", "元/升"),
            self._create_sensor_config("95#", "95号汽油", "mdi:gas-station", "元/升"),
            self._create_sensor_config("98#", "98号汽油", "mdi:gas-station", "元/升"),
            self._create_sensor_config("0#", "0号柴油", "mdi:gas-station", "元/升"),
            self._create_sensor_config("province", "省份", "mdi:map-marker"),
            self._create_sensor_config("info", "窗口期", "mdi:calendar-clock"),
            self._create_sensor_config("trend", "走势", "mdi:chart-line")
        ]

    def _build_base_request(self, params: Dict[str, Any]) -> RequestConfig:
        """构建油价网站请求"""
        province = params.get("province", "浙江")
        self._current_province = province
        province_pinyin = self.PROVINCE_MAP.get(province, "zhejiang")
        
        url = f"{self.default_api_url}/{province_pinyin}.shtml"
        
        return RequestConfig(
            url=url,
            method="GET",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
            }
        )

    def _parse_raw_response(self, response_data: Any) -> Dict[str, Any]:
        """解析油价网站响应数据"""
        if not isinstance(response_data, str):
            return {
                "status": "error",
                "error": "无效的响应格式"
            }

        try:
            soup = BeautifulSoup(response_data, "html.parser")
            
            # 初始化结果
            result = {
                "92#": None,
                "95#": None, 
                "98#": None,
                "0#": None,
                "province": self._current_province,
                "info": "未知",
                "trend": "未知"
            }

            # 解析油品价格
            self._parse_oil_prices(soup, result)
            
            # 解析调价信息
            self._parse_adjustment_info(soup, result)

            return result
            
        except Exception as e:
            return {
                "status": "error", 
                "error": f"解析油价数据失败: {str(e)}"
            }

    def _parse_oil_prices(self, soup: BeautifulSoup, result: Dict[str, Any]) -> None:
        """解析油品价格"""
        # 查找所有油价dl元素
        oil_dls = soup.select("#youjia dl")
        
        for dl in oil_dls:
            dt = dl.find('dt')
            dd = dl.find('dd')
            
            if not dt or not dd:
                continue
                
            oil_text = dt.get_text().strip()
            price_text = dd.get_text().strip()
            
            # 提取纯数字价格
            price_match = re.search(r'(\d+\.\d+)', price_text)
            if price_match:
                price = float(price_match.group(1))
                
                # 根据油品类型分配
                if "92" in oil_text:
                    result["92#"] = price
                elif "95" in oil_text:
                    result["95#"] = price
                elif "98" in oil_text:
                    result["98#"] = price
                elif "0" in oil_text:
                    result["0#"] = price

    def _parse_adjustment_info(self, soup: BeautifulSoup, result: Dict[str, Any]) -> None:
        """解析调价信息"""
        # 查找调价信息容器
        info_container = soup.select_one("#youjiaCont")
        if not info_container:
            return
            
        # 获取所有文本内容
        all_text = info_container.get_text()
        
        # 解析窗口期信息
        window_match = re.search(r'下次油价\s*(\d+月\d+日\d*时)\s*调整', all_text)
        if window_match:
            result["info"] = window_match.group(1)
        else:
            # 备用匹配模式
            window_match_alt = re.search(r'(\d+月\d+日\d*时)', all_text)
            if window_match_alt:
                result["info"] = window_match_alt.group(1)
        
        # 解析走势信息 - 查找红色文本
        trend_element = info_container.select_one('span[style*="color:#F00"]')
        if trend_element:
            trend_text = trend_element.get_text().strip()
            # 清理多余的空白字符
            trend_text = re.sub(r'\s+', ' ', trend_text)
            # 去掉"大家相互转告"等多余文字
            trend_text = re.sub(r'，大家相互转告.*', '', trend_text)
            result["trend"] = trend_text
        else:
            # 备用：从文本中提取走势信息
            trend_match = re.search(r'预计(?:上调|下调)[^。]*?元/吨[^。]*', all_text)
            if trend_match:
                trend_text = trend_match.group(0).strip()
                trend_text = re.sub(r'，大家相互转告.*', '', trend_text)
                result["trend"] = trend_text
            elif "搁浅" in all_text or "不作调整" in all_text:
                result["trend"] = "本轮搁浅"
            else:
                # 最后尝试提取包含"预计"的整句话
                forecast_match = re.search(r'预计[^，。！？]*[，。！？]', all_text)
                if forecast_match:
                    result["trend"] = forecast_match.group(0).strip()

    def format_sensor_value(self, sensor_key: str, data: Any) -> Any:
        """格式化传感器显示值"""
        value = self.get_sensor_value(sensor_key, data)
        
        if value is None:
            return self._get_sensor_default(sensor_key)
            
        # 对油价进行特殊格式化
        if sensor_key in ["92#", "95#", "98#", "0#"]:
            # 返回数值，HA会自动添加单位
            return value
        
        # 对走势信息进行长度限制
        if sensor_key == "trend" and value and len(value) > 100:
            return value[:97] + "..."
            
        return super().format_sensor_value(sensor_key, data)

    def get_sensor_attributes(self, sensor_key: str, data: Any) -> Dict[str, Any]:
        """获取传感器的额外属性"""
        attributes = super().get_sensor_attributes(sensor_key, data)
        
        if not data or data.get("status") != "success":
            return attributes
            
        parsed_data = data.get("data", {})
        
        # 为省份传感器添加完整油价信息
        if sensor_key == "province":
            # 格式化油价显示
            oil_92 = parsed_data.get("92#")
            oil_95 = parsed_data.get("95#")
            oil_98 = parsed_data.get("98#")
            oil_0 = parsed_data.get("0#")
            
            attributes.update({
                "92号汽油": f"{oil_92}元/升" if oil_92 is not None else "未知",
                "95号汽油": f"{oil_95}元/升" if oil_95 is not None else "未知",
                "98号汽油": f"{oil_98}元/升" if oil_98 is not None else "未知",
                "0号柴油": f"{oil_0}元/升" if oil_0 is not None else "未知",
                "调价窗口": parsed_data.get("info", "未知"),
                "价格走势": parsed_data.get("trend", "未知"),
                "数据来源": "qiyoujiage.com",
                "更新时间": data.get("update_time", "未知")
            })
        
        return attributes

    def _get_default_value(self, key: str) -> Any:
        """根据字段名返回默认值"""
        # 油价字段返回None，让HA显示为"未知"
        if key in ["92#", "95#", "98#", "0#"]:
            return None
            
        defaults = {
            "province": "未知省份",
            "info": "未知窗口期",
            "trend": "未知走势"
        }
        return defaults.get(key, super()._get_default_value(key))

    def _get_sensor_default(self, sensor_key: str) -> Any:
        """获取传感器默认值"""
        # 油价传感器返回None，其他返回文本
        if sensor_key in ["92#", "95#", "98#", "0#"]:
            return None
            
        defaults = {
            "province": "加载中...", 
            "info": "加载中...",
            "trend": "加载中..."
        }
        return defaults.get(sensor_key, super()._get_sensor_default(sensor_key))

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> None:
        """验证服务配置"""
        province = config.get("province")
        if province and province not in cls.PROVINCE_MAP:
            raise ValueError(f"无效的省份: {province}")