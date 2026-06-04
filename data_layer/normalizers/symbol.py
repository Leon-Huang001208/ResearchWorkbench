"""股票代码标准化"""


def normalize_a_share_symbol(raw_code: str) -> str:
    """将各种格式的 A 股代码标准化为 {code}.{exchange} 格式

    规则：
    - 60/68/90 开头 → .SH (上海)
    - 51/58 开头 → .SH (上交所ETF)
    - 00/30/20/159/16/399 开头 → .SZ (深圳)
    - 43/83/87/88 开头 → .BJ (北京/新三板)
    """
    code = str(raw_code).strip().upper()
    code = code.replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
    code = code.replace("SH.", "").replace("SZ.", "").replace("BJ.", "")

    if code.startswith(("60", "68", "90", "51", "58")):
        return f"{code}.SH"
    if code.startswith(("00", "30", "20", "159", "16", "399")):
        return f"{code}.SZ"
    if code.startswith(("43", "83", "87", "88")):
        return f"{code}.BJ"
    return code
