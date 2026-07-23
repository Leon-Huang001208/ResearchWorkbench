"""symbol normalizer 单元测试"""

from data_layer.normalizers.symbol import normalize_a_share_symbol


def test_normalize_sh_symbol():
    """上交所股票：60/68/90 开头 → .SH"""
    assert normalize_a_share_symbol("600519") == "600519.SH"
    assert normalize_a_share_symbol("688001") == "688001.SH"
    assert normalize_a_share_symbol("900901") == "900901.SH"


def test_normalize_sz_symbol():
    """深交所股票：00/30/20 开头 → .SZ"""
    assert normalize_a_share_symbol("000001") == "000001.SZ"
    assert normalize_a_share_symbol("300750") == "300750.SZ"
    assert normalize_a_share_symbol("002594") == "002594.SZ"


def test_normalize_bj_symbol():
    """北交所/新三板：43/83/87/88 开头 → .BJ"""
    assert normalize_a_share_symbol("830799") == "830799.BJ"
    assert normalize_a_share_symbol("430001") == "430001.BJ"
    assert normalize_a_share_symbol("870001") == "870001.BJ"
    assert normalize_a_share_symbol("880001") == "880001.BJ"


def test_normalize_already_with_suffix():
    """已有后缀的代码去掉后缀重新判断"""
    assert normalize_a_share_symbol("600519.SH") == "600519.SH"
    assert normalize_a_share_symbol("000001.SZ") == "000001.SZ"
    assert normalize_a_share_symbol("830799.BJ") == "830799.BJ"


def test_normalize_unknown_code():
    """未知格式代码保持原样"""
    assert normalize_a_share_symbol("ABC123") == "ABC123"


def test_normalize_lowercase():
    """小写交易所后缀"""
    assert normalize_a_share_symbol("600519.sh") == "600519.SH"
    assert normalize_a_share_symbol("000001.sz") == "000001.SZ"


def test_normalize_with_spaces():
    """带前后空格"""
    assert normalize_a_share_symbol(" 600519 ") == "600519.SH"
