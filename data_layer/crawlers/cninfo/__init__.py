"""巨潮资讯网（Cninfo）爬虫模块"""

from data_layer.crawlers.cninfo.cninfo import (
    CNINFO_CATEGORIES,
    CNINFO_PLATES,
    HAS_DEPENDENCIES,
    CninfoConfig,
    CninfoCrawler,
    cninfo_main,
)

__all__ = [
    "CninfoConfig",
    "CninfoCrawler",
    "cninfo_main",
    "CNINFO_PLATES",
    "CNINFO_CATEGORIES",
    "HAS_DEPENDENCIES",
]
