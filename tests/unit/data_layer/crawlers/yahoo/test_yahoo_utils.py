"""
Yahoo Finance 工具函数测试
"""

from data_layer.crawlers.yahoo.utils import (
    convert_symbol,
    detect_market,
    get_supported_intervals,
    get_supported_periods,
    is_valid_yahoo_symbol,
)


class TestSymbolConversion:
    """Symbol 转换测试"""

    def test_convert_akshare_sh(self):
        """测试转换 AkShare 上交所 symbol"""
        result = convert_symbol("sh600519", source="akshare")
        assert result == "600519.SS"

    def test_convert_akshare_sz(self):
        """测试转换 AkShare 深交所 symbol"""
        result = convert_symbol("sz000001", source="akshare")
        assert result == "000001.SZ"

    def test_convert_akshare_hk(self):
        """测试转换 AkShare 港股 symbol"""
        result = convert_symbol("hk00700", source="akshare")
        assert result == "00700.HK"

    def test_convert_baostock_sh(self):
        """测试转换 BaoStock 上交所 symbol"""
        result = convert_symbol("sh.600519", source="baostock")
        assert result == "600519.SS"

    def test_convert_baostock_sz(self):
        """测试转换 BaoStock 深交所 symbol"""
        result = convert_symbol("sz.000001", source="baostock")
        assert result == "000001.SZ"

    def test_convert_already_yahoo_format(self):
        """测试已经是 Yahoo 格式的不转换"""
        assert convert_symbol("AAPL", source="akshare") == "AAPL"
        assert convert_symbol("00700.HK", source="akshare") == "00700.HK"
        assert convert_symbol("^GSPC", source="akshare") == "^GSPC"


class TestMarketDetection:
    """市场检测测试"""

    def test_detect_us_market(self):
        """测试检测美股市场"""
        assert detect_market("AAPL") == "us"
        assert detect_market("MSFT") == "us"

    def test_detect_hk_market(self):
        """测试检测港股市场"""
        assert detect_market("00700.HK") == "hk"
        assert detect_market("00005.HK") == "hk"

    def test_detect_cn_market(self):
        """测试检测A股市场"""
        assert detect_market("600519.SS") == "cn"
        assert detect_market("000001.SZ") == "cn"

    def test_detect_index(self):
        """测试检测指数"""
        assert detect_market("^GSPC") == "index"
        assert detect_market("^DJI") == "index"
        assert detect_market("^IXIC") == "index"

    def test_detect_unknown(self):
        """测试检测未知市场"""
        # 未知格式返回 None
        assert detect_market("unknown.format") is None


class TestSupportedValues:
    """支持的取值测试"""

    def test_supported_intervals(self):
        """测试支持的 K线间隔"""
        intervals = get_supported_intervals()
        assert isinstance(intervals, list)
        assert len(intervals) > 0
        assert "1d" in intervals
        assert "1wk" in intervals
        assert "1mo" in intervals
        assert "1m" in intervals

    def test_supported_periods(self):
        """测试支持的时间段"""
        periods = get_supported_periods()
        assert isinstance(periods, list)
        assert len(periods) > 0
        assert "1d" in periods
        assert "1y" in periods
        assert "max" in periods


class TestSymbolValidation:
    """Symbol 验证测试"""

    def test_valid_us_symbols(self):
        """测试有效的美股 symbol"""
        assert is_valid_yahoo_symbol("AAPL") is True
        assert is_valid_yahoo_symbol("MSFT") is True
        assert is_valid_yahoo_symbol("GOOGL") is True

    def test_valid_hk_symbols(self):
        """测试有效的港股 symbol"""
        assert is_valid_yahoo_symbol("00700.HK") is True
        assert is_valid_yahoo_symbol("00005.HK") is True

    def test_valid_cn_symbols(self):
        """测试有效的A股 symbol"""
        assert is_valid_yahoo_symbol("600519.SS") is True
        assert is_valid_yahoo_symbol("000001.SZ") is True

    def test_valid_index_symbols(self):
        """测试有效的指数 symbol"""
        assert is_valid_yahoo_symbol("^GSPC") is True
        assert is_valid_yahoo_symbol("^DJI") is True
        assert is_valid_yahoo_symbol("^IXIC") is True

    def test_invalid_symbols(self):
        """测试无效的 symbol"""
        assert is_valid_yahoo_symbol("") is False
        assert is_valid_yahoo_symbol(None) is False
        assert is_valid_yahoo_symbol(123) is False
