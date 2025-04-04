"""Services package initialization."""
from .base import BaseService
from .hitokoto import HitokotoService
from .poetry import PoetryService
from .weather import WeatherService
from .oil import OilService

__all__ = [
    'BaseService',
    'HitokotoService',
    'PoetryService',
    'WeatherService',
    'OilService'
]