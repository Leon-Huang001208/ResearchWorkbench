"""缓存工具模块"""
from functools import wraps
from typing import Callable

def cached_property(func: Callable) -> property:
    """缓存属性装饰器
    
    该装饰器会将属性的计算结果缓存到实例变量中，避免重复计算
    """
    cache_name = f"_{func.__name__}"
    
    @wraps(func)
    def wrapper(self):
        if not hasattr(self, cache_name):
            setattr(self, cache_name, func(self))
        return getattr(self, cache_name)
    
    return property(wrapper)
