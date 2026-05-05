"""数据适配器"""
from data_layer.adapters.base import BaseDataAdapter
from data_layer.adapters.ifind_adapter import IFinDAdapter
from data_layer.adapters.local_data_adapter import LocalDataAdapter
from data_layer.adapters.pdf_adapter import PDFAdapter

__all__ = [
    "BaseDataAdapter",
    "PDFAdapter",
    "IFinDAdapter",
    "LocalDataAdapter",
]
