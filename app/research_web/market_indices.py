"""Versioned public index identities; vendor routing is not index authorship."""

from core.observability import get_logger

log = get_logger(__name__)
CORE = "core-v1"
TERMINAL = "terminal-v2"
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
        "https://quote.eastmoney.com/q/2.932000.html",
    ),
    ("000824.SH", "国企红利", "1.000824", "dividend", "CSI", CSI),
    (
        "399303.SZ",
        "国证2000",
        "0.399303",
        "scale",
        "CNI",
        "https://www.cnindex.com.cn/docs/gz_399303.pdf",
    ),
    ("000922.SH", "中证红利", "1.000922", "dividend", "CSI", CSI),
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
        ],
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
