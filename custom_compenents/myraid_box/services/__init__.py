from .hitokoto import HitokotoService
from .poetry import PoetryService
from .weather import WeatherService
from .oil import OilService
from ..const import register_service

# 注册所有服务
register_service(HitokotoService)
register_service(PoetryService)
register_service(WeatherService)
register_service(OilService)