"""
AkShare 宏观数据获取器
"""

from typing import List, Optional

import pandas as pd

from core.observability import get_logger

from .base import BaseAkShareFetcher, MacroData
from .config import AkShareConfig

logger = get_logger("akshare_macro")


class AkShareMacroFetcher(BaseAkShareFetcher):
    """AkShare 宏观数据获取器"""

    def __init__(self, config: Optional[AkShareConfig] = None):
        super().__init__(config)

    def get_gdp(self) -> List[MacroData]:
        """
        获取 GDP 数据

        Returns:
            宏观数据列表
        """
        self._initialize()
        logger.debug("Fetching GDP data...")

        try:
            # 获取中国 GDP 数据
            df = self.ak.macro_china_gdp_yearly()

            if df is None or df.empty:
                logger.warning("No GDP data returned")
                return []

            result: List[MacroData] = []

            for _, row in df.iterrows():
                try:
                    year = str(row.get("年份", "") or row.get("year", ""))
                    if not year:
                        continue

                    value = self._safe_float(row, "国内生产总值-绝对值") or self._safe_float(
                        row, "GDP"
                    )

                    if value is None:
                        continue

                    macro_data = MacroData(
                        indicator="GDP",
                        value=value,
                        period=year,
                        unit="亿元",
                        source="stats",
                        extra=row.to_dict(),
                    )
                    result.append(macro_data)
                except Exception as e:
                    logger.debug(f"Error processing GDP row: {e}")
                    continue

            logger.info(f"Fetched {len(result)} GDP records")
            return result

        except Exception as e:
            logger.error(f"Failed to fetch GDP data: {e}")
            return []

    def get_cpi(self) -> List[MacroData]:
        """
        获取 CPI 数据

        Returns:
            宏观数据列表
        """
        self._initialize()
        logger.debug("Fetching CPI data...")

        try:
            # 获取 CPI 数据
            df = self.ak.macro_china_cpi_monthly()

            if df is None or df.empty:
                logger.warning("No CPI data returned")
                return []

            result: List[MacroData] = []

            for _, row in df.iterrows():
                try:
                    month = str(row.get("月份", "") or row.get("month", ""))
                    if not month:
                        continue

                    value = self._safe_float(row, "全国") or self._safe_float(row, "CPI")

                    if value is None:
                        continue

                    macro_data = MacroData(
                        indicator="CPI",
                        value=value,
                        period=month,
                        unit="指数",
                        source="stats",
                        extra=row.to_dict(),
                    )
                    result.append(macro_data)
                except Exception as e:
                    logger.debug(f"Error processing CPI row: {e}")
                    continue

            logger.info(f"Fetched {len(result)} CPI records")
            return result

        except Exception as e:
            logger.error(f"Failed to fetch CPI data: {e}")
            return []

    def get_pmi(self) -> List[MacroData]:
        """
        获取 PMI 数据

        Returns:
            宏观数据列表
        """
        self._initialize()
        logger.debug("Fetching PMI data...")

        try:
            # 获取 PMI 数据
            df = self.ak.macro_china_pmi_monthly()

            if df is None or df.empty:
                logger.warning("No PMI data returned")
                return []

            result: List[MacroData] = []

            for _, row in df.iterrows():
                try:
                    month = str(row.get("月份", "") or row.get("month", ""))
                    if not month:
                        continue

                    value = self._safe_float(row, "制造业PMI") or self._safe_float(row, "PMI")

                    if value is None:
                        continue

                    macro_data = MacroData(
                        indicator="PMI",
                        value=value,
                        period=month,
                        unit="指数",
                        source="stats",
                        extra=row.to_dict(),
                    )
                    result.append(macro_data)
                except Exception as e:
                    logger.debug(f"Error processing PMI row: {e}")
                    continue

            logger.info(f"Fetched {len(result)} PMI records")
            return result

        except Exception as e:
            logger.error(f"Failed to fetch PMI data: {e}")
            return []

    def get_interest_rate(self) -> List[MacroData]:
        """
        获取利率数据

        Returns:
            宏观数据列表
        """
        self._initialize()
        logger.debug("Fetching interest rate data...")

        try:
            # 获取存款准备金率
            df = self.ak.macro_china_required_reserve_ratio()

            if df is None or df.empty:
                logger.warning("No interest rate data returned")
                return []

            result: List[MacroData] = []

            for _, row in df.iterrows():
                try:
                    date_str = str(row.get("日期", "") or row.get("date", ""))
                    if not date_str:
                        continue

                    value = self._safe_float(row, "大型存款类金融机构")

                    if value is None:
                        continue

                    macro_data = MacroData(
                        indicator="RequiredReserveRatio",
                        value=value,
                        period=date_str,
                        unit="%",
                        source="pbc",
                        extra=row.to_dict(),
                    )
                    result.append(macro_data)
                except Exception as e:
                    logger.debug(f"Error processing rate row: {e}")
                    continue

            logger.info(f"Fetched {len(result)} interest rate records")
            return result

        except Exception as e:
            logger.error(f"Failed to fetch interest rate data: {e}")
            return []

    def get_money_supply(self) -> List[MacroData]:
        """
        获取货币供应量数据

        Returns:
            宏观数据列表
        """
        self._initialize()
        logger.debug("Fetching money supply data...")

        try:
            # 获取货币供应量
            df = self.ak.macro_china_m2_yearly()

            if df is None or df.empty:
                logger.warning("No money supply data returned")
                return []

            result: List[MacroData] = []

            for _, row in df.iterrows():
                try:
                    year = str(row.get("年份", "") or row.get("year", ""))
                    if not year:
                        continue

                    # M2
                    m2_value = self._safe_float(row, "货币和准货币(M2)") or self._safe_float(
                        row, "M2"
                    )
                    if m2_value is not None:
                        macro_data = MacroData(
                            indicator="M2",
                            value=m2_value,
                            period=year,
                            unit="亿元",
                            source="pbc",
                            extra=row.to_dict(),
                        )
                        result.append(macro_data)

                    # M1
                    m1_value = self._safe_float(row, "货币(M1)") or self._safe_float(row, "M1")
                    if m1_value is not None:
                        macro_data = MacroData(
                            indicator="M1",
                            value=m1_value,
                            period=year,
                            unit="亿元",
                            source="pbc",
                            extra=row.to_dict(),
                        )
                        result.append(macro_data)

                except Exception as e:
                    logger.debug(f"Error processing money supply row: {e}")
                    continue

            logger.info(f"Fetched {len(result)} money supply records")
            return result

        except Exception as e:
            logger.error(f"Failed to fetch money supply data: {e}")
            return []

    def get_all_macro(self, indicators: Optional[List[str]] = None) -> List[MacroData]:
        """
        获取所有宏观数据

        Args:
            indicators: 指定获取的指标列表，None 则获取全部

        Returns:
            宏观数据列表
        """
        all_data: List[MacroData] = []

        indicator_map = {
            "GDP": self.get_gdp,
            "CPI": self.get_cpi,
            "PMI": self.get_pmi,
            "InterestRate": self.get_interest_rate,
            "MoneySupply": self.get_money_supply,
        }

        if indicators is None:
            indicators = list(indicator_map.keys())

        for indicator in indicators:
            if indicator in indicator_map:
                try:
                    data = indicator_map[indicator]()
                    all_data.extend(data)
                except Exception as e:
                    logger.error(f"Failed to fetch {indicator}: {e}")

        logger.info(f"Fetched total {len(all_data)} macro records")
        return all_data

    def _safe_float(self, row: pd.Series, key: str) -> Optional[float]:
        """安全地获取浮点值"""
        if key not in row:
            return None
        val = row[key]
        if pd.isna(val):
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None
