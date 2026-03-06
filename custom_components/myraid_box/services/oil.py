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

    # 省份映射（保持不变）
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
            # 原有油价传感器
            self._create_sensor_config("92#", "92号汽油", "mdi:gas-station", "元/升"),
            self._create_sensor_config("95#", "95号汽油", "mdi:gas-station", "元/升"),
            self._create_sensor_config("98#", "98号汽油", "mdi:gas-station", "元/升"),
            self._create_sensor_config("0#", "0号柴油", "mdi:gas-station", "元/升"),
            self._create_sensor_config("province", "省份", "mdi:map-marker"),
            self._create_sensor_config("tip", "油价贴士", "mdi:information-outline"),
            
            # 新增：倒计时传感器（不单独做日期传感器）
            self._create_sensor_config("countdown", "调价倒计时", "mdi:calendar-clock", "天"),
        ]

    def _build_base_request(self, params: Dict[str, Any]) -> RequestConfig:
        """构建油价网站请求（保持不变）"""
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
        """解析油价网站响应数据 - 添加倒计时计算"""
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
                "tip": "暂无调价信息",
                "countdown": None,  # 新增：倒计时天数
            }

            # 解析油品价格（保持不变）
            oil_items = soup.select("#youjia dl")
            for item in oil_items:
                oil_type = item.find('dt').get_text().strip()
                price_text = item.find('dd').get_text().strip()
                
                price_match = re.search(r'(\d+\.\d+)', price_text)
                if price_match:
                    price = float(price_match.group(1))
                    
                    if "92#" in oil_type:
                        result["92#"] = price
                    elif "95#" in oil_type:
                        result["95#"] = price
                    elif "98#" in oil_type:
                        result["98#"] = price
                    elif "0#" in oil_type:
                        result["0#"] = price

            # 解析调价信息
            info_container = soup.select_one("#youjiaCont")
            if info_container:
                text = info_container.get_text()
                
                # 提取调整时间和趋势
                window = re.search(r'下次油价(\d+月\d+日\d*时)调整', text)
                trend = info_container.select_one('span[style*="color:#F00"]')
                
                # 构建贴士信息
                if window and trend:
                    trend_text = re.sub(r'，大家相互转告.*', '', trend.get_text().strip())
                    result["tip"] = f"{trend_text}，下次调整：{window.group(1)}"
                elif window:
                    result["tip"] = f"下次调整：{window.group(1)}"
                elif trend:
                    trend_text = re.sub(r'，大家相互转告.*', '', trend.get_text().strip())
                    result["tip"] = trend_text

                # 从贴士中提取日期并计算倒计时
                result["countdown"] = self._calculate_countdown(text)

            return result
            
        except Exception as e:
            return {
                "status": "error", 
                "error": f"解析油价数据失败: {str(e)}"
            }

    def _calculate_countdown(self, text: str) -> int | None:
        """从文本中提取调价日期并计算倒计时天数"""
        try:
            # 匹配多种日期格式
            patterns = [
                r'下次调整[：:]\s*(\d{1,2})月(\d{1,2})日',  # 标准格式
                r'下次油价(\d{1,2})月(\d{1,2})日',          # 网站格式
                r'调整时间[：:]\s*(\d{1,2})月(\d{1,2})日',  # 其他格式
                r'(\d{1,2})月(\d{1,2})日.*?调整',            # 灵活匹配
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    month = int(match.group(1))
                    day = int(match.group(2))
                    
                    now = datetime.now()
                    current_year = now.year
                    
                    # 构建日期对象（设置为当天23:59:59，这样倒计时更准确）
                    try:
                        adjust_date = datetime(current_year, month, day, 23, 59, 59)
                    except ValueError:
                        # 如果日期无效（如2月30日），跳过
                        continue
                    
                    # 如果调价日期已经过去（且不是今天），则设置为明年
                    if adjust_date.date() < now.date():
                        adjust_date = datetime(current_year + 1, month, day, 23, 59, 59)
                    
                    # 计算剩余天数
                    days_left = (adjust_date - now).days
                    
                    # 如果剩余天数为负数，返回0（表示今天调价）
                    return max(0, days_left)
            
            return None
            
        except Exception as e:
            _LOGGER.debug("[油价服务] 计算倒计时失败: %s", str(e))
            return None

    def format_sensor_value(self, sensor_key: str, data: Any) -> Any:
        """格式化传感器显示值"""
        value = self.get_sensor_value(sensor_key, data)
        
        if value is None:
            return self._get_sensor_default(sensor_key)
            
        # 对油价进行特殊格式化
        if sensor_key in ["92#", "95#", "98#", "0#"]:
            return value
        
        # 倒计时传感器返回整数
        if sensor_key == "countdown":
            if value is None or value < 0:
                return None
            return int(value)
        
        # 对贴士信息进行长度限制
        if sensor_key == "tip" and value and len(value) > 100:
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
            
            # 从贴士中提取调价日期（用于属性显示）
            tip = parsed_data.get("tip", "")
            adjust_date = self._extract_date_from_tip(tip)
            
            attributes.update({
                "92号汽油": f"{oil_92}元/升" if oil_92 is not None else "未知",
                "95号汽油": f"{oil_95}元/升" if oil_95 is not None else "未知",
                "98号汽油": f"{oil_98}元/升" if oil_98 is not None else "未知",
                "0号柴油": f"{oil_0}元/升" if oil_0 is not None else "未知",
                "油价贴士": tip,
                "调价日期": adjust_date if adjust_date else "未知",
                "数据来源": "qiyoujiage.com",
                "更新时间": data.get("update_time", "未知")
            })
        
        # 为倒计时传感器添加详情
        elif sensor_key == "countdown":
            tip = parsed_data.get("tip", "")
            adjust_date = self._extract_date_from_tip(tip)
            days_left = parsed_data.get("countdown")
            
            if adjust_date:
                attributes["调价日期"] = adjust_date
                attributes["调价时间"] = "当日24时"
            
            # 添加今日状态描述
            if days_left is not None:
                if days_left == 0:
                    attributes["今日状态"] = "今日调价"
                elif days_left == 1:
                    attributes["今日状态"] = "明天调价"
                elif days_left <= 3:
                    attributes["今日状态"] = f"还有{days_left}天，临近调价"
                else:
                    attributes["今日状态"] = f"还有{days_left}天"
        
        return attributes

    def _extract_date_from_tip(self, tip: str) -> str | None:
        """从贴士文本中提取调价日期"""
        try:
            # 匹配日期格式：3月9日
            match = re.search(r'(\d{1,2})月(\d{1,2})日', tip)
            if match:
                month = int(match.group(1))
                day = int(match.group(2))
                
                now = datetime.now()
                year = now.year
                
                # 如果日期已过，可能是明年
                if month < now.month or (month == now.month and day < now.day):
                    year += 1
                
                return f"{year}年{month}月{day}日"
            
            return None
        except Exception:
            return None

    def get_sensor_icon(self, sensor_key: str, data: Any) -> str:
        """获取传感器的动态图标"""
        # 为倒计时传感器添加动态图标
        if sensor_key == "countdown":
            value = self.get_sensor_value(sensor_key, data)
            if value is not None:
                if value == 0:
                    return "mdi:alert-circle"      # 今日调价
                elif value == 1:
                    return "mdi:clock-alert-outline"  # 明天调价
                elif value <= 3:
                    return "mdi:clock-alert"       # 临近调价（2-3天）
                else:
                    return "mdi:calendar-arrow-right"  # 还有一段时间
            return "mdi:calendar-arrow-right"
        
        return super().get_sensor_icon(sensor_key, data)

    def _get_default_value(self, key: str) -> Any:
        """根据字段名返回默认值"""
        if key in ["92#", "95#", "98#", "0#"]:
            return None
            
        if key == "countdown":
            return None
            
        defaults = {
            "province": "未知省份",
            "tip": "暂无调价信息",
        }
        return defaults.get(key, super()._get_default_value(key))

    def _get_sensor_default(self, sensor_key: str) -> Any:
        """获取传感器默认值"""
        if sensor_key in ["92#", "95#", "98#", "0#"]:
            return None
            
        if sensor_key == "countdown":
            return None
            
        defaults = {
            "province": "加载中...", 
            "tip": "加载中...",
        }
        return defaults.get(sensor_key, super()._get_sensor_default(sensor_key))

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> None:
        """验证服务配置"""
        province = config.get("province")
        if province and province not in cls.PROVINCE_MAP:
            raise ValueError(f"无效的省份: {province}")