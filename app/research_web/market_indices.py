"""Versioned public index identities; vendor routing is not index authorship."""

from core.observability import get_logger

log = get_logger(__name__)
CORE = "core-v1"
TERMINAL = "terminal-v2"
GLOBAL = "global-v1"
CATALOG_VERSION = "mainland-indices-20261023-v2"
CSI = "https://www.csindex.com.cn/"
CNI = "https://www.cnindex.com.cn/zh_indices/cni/style/index.html?act_menu=2&index_type=202"
CORE_INDEXES = (
    ("000001.SH", "上证指数", "1.000001"),
    ("399001.SZ", "深证成指", "0.399001"),
    ("000016.SH", "上证50", "1.000016"),
    ("000680.SH", "科创综指", "1.000680"),
    ("399006.SZ", "创业板指", "0.399006"),
    ("399673.SZ", "创业板50", "0.399673"),
    ("000688.SH", "科创50", "1.000688"),
    ("899050.BJ", "北证50", "0.899050"),
    ("000300.SH", "沪深300", "1.000300"),
    ("000905.SH", "中证500", "1.000905"),
    ("000510.SH", "中证A500", "1.000510"),
    ("000852.SH", "中证1000", "1.000852"),
)
EXTRA_INDEXES = (
    # CSI932000 is vendor market2, independently of its logical SH price code.
    (
        "932000.SH",
        "中证2000",
        "2.932000",
        "scale",
        "CSI",
        "https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/932000factsheet.pdf",
    ),
    (
        "000824.SH",
        "国企红利",
        "1.000824",
        "dividend",
        "CSI",
        "https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/000824factsheet.pdf",
    ),
    (
        "399303.SZ",
        "国证2000",
        "0.399303",
        "scale",
        "CNI",
        "https://www.cnindex.com.cn/docs/gz_399303.pdf",
    ),
    (
        "000922.SH",
        "中证红利",
        "1.000922",
        "dividend",
        "CSI",
        "https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/000922factsheet.pdf",
    ),
    ("399370.SZ", "国证成长", "0.399370", "style", "CNI", CNI),
    ("399371.SZ", "国证价值", "0.399371", "style", "CNI", CNI),
    ("399372.SZ", "大盘成长", "0.399372", "style", "CNI", CNI),
    ("399373.SZ", "大盘价值", "0.399373", "style", "CNI", CNI),
    ("399374.SZ", "中盘成长", "0.399374", "style", "CNI", CNI),
    ("399375.SZ", "中盘价值", "0.399375", "style", "CNI", CNI),
    ("399376.SZ", "小盘成长", "0.399376", "style", "CNI", CNI),
    ("399377.SZ", "小盘价值", "0.399377", "style", "CNI", CNI),
)
DEFAULT_PINS = (
    "000001.SH",
    "399001.SZ",
    "000300.SH",
    "000905.SH",
    "000852.SH",
    "932000.SH",
    "000824.SH",
)


def selected_indexes(index_set=CORE):
    if index_set == CORE:
        return CORE_INDEXES
    if index_set == TERMINAL:
        return CORE_INDEXES + tuple(item[:3] for item in EXTRA_INDEXES)
    log.warning("market_index_set_rejected")
    raise ValueError("market_invalid_index_set")


def public_catalog():
    items = []
    for asset, name, secid in CORE_INDEXES:
        publisher = (
            "CNI"
            if asset.endswith(".SZ")
            else (
                "BSE"
                if asset.endswith(".BJ")
                else "SSE" if asset.startswith(("000001", "000016", "000680", "000688")) else "CSI"
            )
        )
        group = (
            "broad"
            if asset in {"000001.SH", "399001.SZ", "000510.SH", "399006.SZ", "000680.SH"}
            else "scale"
        )
        items.append(
            {
                "asset": asset,
                "code": asset.split(".")[0],
                "name": name,
                "group": group,
                "publisher": publisher,
                "definition_url": (
                    CNI
                    if publisher == "CNI"
                    else (
                        "https://www.bse.cn/"
                        if publisher == "BSE"
                        else "https://www.sse.com.cn/" if publisher == "SSE" else CSI
                    )
                ),
                "return_basis": "price_index",
            }
        )
    for asset, name, secid, group, publisher, url in EXTRA_INDEXES:
        items.append(
            {
                "asset": asset,
                "code": asset.split(".")[0],
                "name": name,
                "group": group,
                "publisher": publisher,
                "definition_url": url,
                "return_basis": "price_index",
            }
        )
    return {
        "catalog_version": CATALOG_VERSION,
        "default_set": TERMINAL,
        "index_sets": [
            {"id": key, "assets": [item[0] for item in selected_indexes(key)]}
            for key in (CORE, TERMINAL)
        ]
        + [{"id": GLOBAL, "assets": list(GLOBAL_INDEXES)}],
        "global_catalog": global_catalog(),
        "groups": [
            {"id": key, "label": label}
            for key, label in (
                ("broad", "宽基"),
                ("scale", "规模"),
                ("style", "成长价值"),
                ("dividend", "红利"),
            )
        ],
        "items": items,
        "default_pins": list(DEFAULT_PINS),
    }


# Source symbols are routing identities, never fund substitutes or index authors.
GLOBAL_INDEXES = {
    "SSE": ("000001.SH", "000001.SS", "SSE", "https://www.sse.com.cn/"),
    "CSI300": ("000300.SH", "000300.SS", "CSI", CSI),
    "CHINEXT": ("399006.SZ", "399006.SZ", "CNI", CNI),
    "SP500": (
        "SP500",
        "^GSPC",
        "S&P Dow Jones Indices",
        "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
    ),
    "NASDAQ": ("NASDAQ", "^IXIC", "Nasdaq", "https://indexes.nasdaq.com/Index/Overview/COMP"),
    "DJI": (
        "DJI",
        "^DJI",
        "S&P Dow Jones Indices",
        "https://www.spglobal.com/spdji/en/indices/equity/dow-jones-industrial-average/",
    ),
    "HSI": (
        "HSI",
        "^HSI",
        "Hang Seng Indexes",
        "https://www.hsi.com.hk/eng/indexes/all-indexes/hsi",
    ),
    "HSCEI": (
        "HSCEI",
        "^HSCE",
        "Hang Seng Indexes",
        "https://www.hsi.com.hk/eng/indexes/all-indexes/hscei",
    ),
    "HSTECH": (
        "HSTECH",
        "^HSTECH",
        "Hang Seng Indexes",
        "https://www.hsi.com.hk/eng/indexes/all-indexes/hstech",
    ),
}


def global_catalog():
    from .market_scoring.profiles import profile_for

    items = []
    for index_id, (code, symbol, publisher, url) in GLOBAL_INDEXES.items():
        profile = profile_for(index_id)
        items.append(
            {
                **{
                    key: profile[key]
                    for key in ("index_id", "name", "market", "currency", "timezone")
                },
                "asset": index_id,
                "code": code,
                "source_symbol": symbol,
                "publisher": publisher,
                "definition_url": url,
                "return_basis": "price_index",
            }
        )
    return {"version": GLOBAL, "items": items, "default_pins": ["SSE", "SP500", "HSI"]}
