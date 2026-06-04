"""数据适配器"""
from data_layer.adapters.akshare_adapter import AKShareAdapter
from data_layer.adapters.baostock_adapter import BaoStockAdapter
from data_layer.adapters.base import BaseDataAdapter
from data_layer.adapters.china_stock_adapter import ChinaStockAdapter
from data_layer.adapters.cls_adapter import CLSAdapter
from data_layer.adapters.cninfo_adapter import CninfoAdapter
from data_layer.adapters.cnstock_adapter import CNStockAdapter
from data_layer.adapters.ifind_adapter import IFinDAdapter
from data_layer.adapters.local_data_adapter import LocalDataAdapter
from data_layer.adapters.pdf_adapter import PDFAdapter
from data_layer.adapters.wind.wind_adapter import WindAdapter
from data_layer.adapters.yahoo_adapter import YahooAdapter
from data_layer.adapters.zq_adapter import ZQAdapter

__all__ = [
    "BaseDataAdapter",
    "PDFAdapter",
    "IFinDAdapter",
    "ChinaStockAdapter",
    "AKShareAdapter",
    "BaoStockAdapter",
    "YahooAdapter",
    "LocalDataAdapter",
    "CLSAdapter",
    "CninfoAdapter",
    "CNStockAdapter",
    "ZQAdapter",
    "WindAdapter",
]
