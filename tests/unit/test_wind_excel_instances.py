"""Excel inventory failures must not create extra Wind login instances."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from data_layer.adapters.wind.excel_instances import (
    _ProcessOutputCompat,
    prepare_macos_excel_compat,
    running_excel_apps,
)
from data_layer.adapters.wind.exceptions import WindNotConnectedError


@pytest.mark.parametrize(
    "record", ['"pid"=93626\n', "[ NULL ]\n bundle path=[ NULL ]\n pid = 93626 !cgsConnection\n"]
)
def test_pid_record_formats(record):
    delegate = MagicMock()
    delegate.check_output.return_value = record.encode()
    assert (
        _ProcessOutputCompat(delegate).check_output(
            ["lsappinfo", "info", "-only", "pid", "ASN:0x0-0x548247d"]
        )
        == b'"pid"=93626\n'
    )


@pytest.mark.parametrize(
    "record",
    [
        "invalid",
        "pid = 123\npid = 456",
        "pid = 0",
        "pid = 123.5",
        "pid = 123\npid = invalid",
        "pid = 123\npid = [ NULL ]",
        "pid = 123 !cgsConnection pid = 456",
        "pid = 123trailing",
    ],
)
def test_unknown_identity_is_not_an_empty_inventory(record):
    delegate = MagicMock()
    delegate.check_output.return_value = record.encode()
    with pytest.raises(ValueError):
        _ProcessOutputCompat(delegate).check_output(
            ["lsappinfo", "info", "-only", "pid", "ASN:0x0-0x548247d"]
        )


def test_native_recovery_attaches_existing_pid_without_launch():
    xw = MagicMock()
    running = MagicMock()
    xw.apps.__iter__.side_effect = [
        ValueError("invalid literal for int(): '[ NULL ]'"),
        iter([running]),
    ]
    native = SimpleNamespace(subprocess=MagicMock())
    with (
        patch("data_layer.adapters.wind.excel_instances.sys.platform", "darwin"),
        patch(
            "data_layer.adapters.wind.excel_instances.importlib.import_module", return_value=native
        ),
    ):
        assert running_excel_apps(xw) == [running]
    assert isinstance(native.subprocess, _ProcessOutputCompat)
    xw.App.assert_not_called()


@pytest.mark.parametrize("error", [ValueError("unexpected"), RuntimeError("unavailable")])
def test_unknown_enumeration_failure_never_launches_excel(error):
    xw = MagicMock()
    xw.apps.__iter__.side_effect = error
    with pytest.raises(WindNotConnectedError):
        running_excel_apps(xw)
    xw.App.assert_not_called()


def test_normal_empty_inventory_remains_empty():
    xw = MagicMock()
    xw.apps = []
    assert running_excel_apps(xw) == []
    xw.App.assert_not_called()


def test_isolated_compat_preparation_never_reads_application_inventory():
    native = SimpleNamespace(subprocess=MagicMock())
    with (
        patch("data_layer.adapters.wind.excel_instances.sys.platform", "darwin"),
        patch.dict("sys.modules", {"xlwings._xlmac": native}),
    ):
        prepare_macos_excel_compat()
        wrapper = native.subprocess
        prepare_macos_excel_compat()
    assert isinstance(wrapper, _ProcessOutputCompat)
    assert native.subprocess is wrapper
    wrapper._delegate.check_output.assert_not_called()


def test_spill_trims_mac_empty_strings_but_preserves_zero():
    from data_layer.adapters.wind.client import _trim_wsd_matrix

    assert _trim_wsd_matrix([["2026-10-16", 0, ""], ["", "", ""]]) == [["2026-10-16", 0]]


def test_worksheet_options_are_independent_arguments_not_a_sdk_option_string():
    from data_layer.adapters.wind.client import build_wsd_formula

    assert build_wsd_formula(
        "SENSEX.BO",
        "close",
        "2026-10-01",
        "2026-10-09",
        "Period=D;PriceAdj=U;Days=Alldays;Fill=Blank;TradingCalendar=IDC",
    ) == (
        '=wsd("SENSEX.BO","close","2026-10-01","2026-10-09",'
        '"Period=D","PriceAdj=U","Days=Alldays","Fill=Blank","TradingCalendar=IDC")'
    )


def test_worksheet_formula_preserves_blank_options_and_escapes_argument_quotes():
    from data_layer.adapters.wind.client import build_wsd_formula

    assert build_wsd_formula('A"B', "close", "2026-10-01", "2026-10-09", "") == (
        '=wsd("A""B","close","2026-10-01","2026-10-09","")'
    )


def test_subprocess_compat_leaves_unrelated_output_and_module_untouched():
    delegate = MagicMock()
    delegate.check_output.return_value = b"untouched"
    wrapper = _ProcessOutputCompat(delegate)
    assert wrapper.check_output(["another", "command"]) == b"untouched"
    delegate.check_output.assert_called_once_with(["another", "command"])


def test_stale_null_pid_is_preserved_for_native_xlwings_filter():
    delegate = MagicMock()
    delegate.check_output.return_value = b'"pid"=[ NULL ]\n'
    wrapper = _ProcessOutputCompat(delegate)
    assert wrapper.check_output(["lsappinfo", "info", "-only", "pid", "ASN:0x0-0x1"]) == (
        b'"pid"=[ NULL ] \n'
    )


def test_history_waits_for_numeric_columns_after_date_spills():
    from unittest.mock import PropertyMock

    from data_layer.adapters.wind.client import WindExcelClient

    anchor = MagicMock()
    anchor.raw_value = "2026-10-16"
    spill = MagicMock()
    type(spill).raw_value = PropertyMock(
        side_effect=[[["2026-10-16", ""]], [["2026-10-16", 0]], [["2026-10-16", 0]]]
    )
    client = WindExcelClient()
    client._sheet = MagicMock()
    client._sheet.range.side_effect = lambda address: spill if ":" in address else anchor
    client._col = "ZZ"
    with patch("data_layer.adapters.wind.client.time.sleep"):
        assert client._execute_wsd_once('=wsd("test")', 3) == [["2026-10-16", 0]]


def test_date_only_history_times_out_instead_of_becoming_data():
    from data_layer.adapters.wind.client import WindExcelClient
    from data_layer.adapters.wind.exceptions import WindTimeoutError

    anchor = MagicMock()
    anchor.raw_value = "2026-10-16"
    spill = MagicMock()
    spill.raw_value = [["2026-10-16", ""]]
    client = WindExcelClient()
    client._sheet = MagicMock()
    client._sheet.range.side_effect = lambda address: spill if ":" in address else anchor
    client._col = "ZZ"
    with patch("data_layer.adapters.wind.client.time.sleep"), pytest.raises(WindTimeoutError):
        client._execute_wsd_once('=wsd("test")', 1)


class _OfflineSpillRange:
    """Excel recomputes the spill after anchor assignment; no native import."""

    def __init__(self, matrix):
        self.matrix = matrix
        self.clear_calls = 0
        self.api = self

    @property
    def raw_value(self):
        return self.matrix

    @raw_value.setter
    def raw_value(self, value):
        assert value is None
        # Mac appscript assignment of None leaves the previous cells intact.

    def clear_contents(self):
        self.clear_calls += 1

    @property
    def value(self):
        return self.matrix

    @value.setter
    def value(self, value):
        raise AssertionError("xlwings converter queried shape during clear")


def test_bounded_spill_reads_only_requested_rows_columns_and_guard():
    from data_layer.adapters.wind.client import WindExcelClient

    anchor = MagicMock(raw_value="2026-10-16")
    spill = _OfflineSpillRange([["2026-10-16", 10], ["2026-10-17", 11]])
    client = WindExcelClient()
    client._sheet = MagicMock()
    client._sheet.range.side_effect = lambda address: spill if ":" in address else anchor
    client._col = "ZZ"
    with patch("data_layer.adapters.wind.client.time.sleep"):
        assert client._execute_wsd_once("=wsd()", 2, expected_columns=2, max_rows=3) == [
            ["2026-10-16", 10],
            ["2026-10-17", 11],
        ]
    client._sheet.range.assert_any_call("ZZ1000:AAB1003")
    assert not any("AAS" in call.args[0] for call in client._sheet.range.call_args_list)
    assert spill.clear_calls == 2


@pytest.mark.parametrize(
    "matrix",
    [
        [["2026-10-16", 10, "extra"]],
        [["2026-10-16", 10, 0]],
        [["2026-10-16", 10, False]],
        [["2026-10-16", 10], ["2026-10-17", 11]],
        [["2026-10-16", 10], [None, False]],
    ],
)
def test_bounded_spill_rejects_extra_column_or_row(matrix):
    from data_layer.adapters.wind.client import WindExcelClient

    anchor = MagicMock(raw_value="2026-10-16")
    spill = _OfflineSpillRange(matrix)
    client = WindExcelClient()
    client._sheet = MagicMock()
    client._sheet.range.side_effect = lambda address: spill if ":" in address else anchor
    client._col = "ZZ"
    with (
        patch("data_layer.adapters.wind.client.time.sleep"),
        patch("data_layer.adapters.wind.client.logger.error") as error_log,
        pytest.raises(Exception, match="wind_spill_overflow"),
    ):
        client._execute_wsd_once("=wsd()", 2, expected_columns=2, max_rows=1)
    assert anchor.value == "=wsd()"
    assert error_log.call_args.kwargs["excel_error"] == "wind_spill_overflow"
    assert "formula" not in error_log.call_args.kwargs


def test_spill_failure_logs_only_standard_excel_error_code():
    from data_layer.adapters.wind.client import WindExcelClient
    from data_layer.adapters.wind.exceptions import WindFormulaError

    client = WindExcelClient()
    client._col = "ZZ"
    client._sheet = MagicMock()
    anchor = MagicMock(raw_value="#N/A")
    spill = _OfflineSpillRange(None)
    client._sheet.range.side_effect = lambda address: spill if ":" in address else anchor
    with (
        patch("data_layer.adapters.wind.client.time.sleep"),
        patch("data_layer.adapters.wind.client.logger.error") as error_log,
        pytest.raises(WindFormulaError),
    ):
        client._execute_wsd_once('=wsd("private")', 2, expected_columns=2, max_rows=1)
    assert error_log.call_args.kwargs["excel_error"] == "#N/A"
    assert "formula" not in error_log.call_args.kwargs


def test_spill_clear_avoids_value_converter_shape_read():
    from data_layer.adapters.wind.client import WindExcelClient

    anchor = MagicMock(raw_value="2026-10-16")
    spill = _OfflineSpillRange([["2026-10-16", 10]])
    client = WindExcelClient()
    client._sheet = MagicMock()
    client._sheet.range.side_effect = lambda address: spill if ":" in address else anchor
    client._col = "ZZ"
    with patch("data_layer.adapters.wind.client.time.sleep"):
        assert client._execute_wsd_once("=wsd()", 2, expected_columns=2, max_rows=1) == [
            ["2026-10-16", 10]
        ]
    assert anchor.value == "=wsd()"
    assert spill.clear_calls == 2


def test_bounded_spill_waits_for_two_stable_numeric_reads_after_dates():
    from data_layer.adapters.wind.client import WindExcelClient

    class ComputingSpill(_OfflineSpillRange):
        def __init__(self):
            super().__init__(None)
            self.reads = 0

        @property
        def raw_value(self):
            self.reads += 1
            if self.reads == 1:
                return [["2026-10-16", ""]]
            return [["2026-10-16", 0]]

    anchor = MagicMock(raw_value="2026-10-16")
    spill = ComputingSpill()
    client = WindExcelClient()
    client._col = "ZZ"
    client._sheet = MagicMock()
    client._sheet.range.side_effect = lambda address: spill if ":" in address else anchor
    with patch("data_layer.adapters.wind.client.time.sleep"):
        assert client._execute_wsd_once("=wsd()", 2, expected_columns=2, max_rows=1) == [
            ["2026-10-16", 0]
        ]
    assert spill.reads == 3
    assert anchor.value == "=wsd()"
    assert spill.clear_calls == 2


def test_native_clear_removes_stale_cells_when_helper_address_is_reused():
    from data_layer.adapters.wind.client import WindExcelClient

    class Spill:
        def __init__(self):
            self.cells = [[None, None, None] for _ in range(3)]
            self.clear_calls = 0
            self.api = SimpleNamespace(clear_contents=self._native_clear)

        @property
        def raw_value(self):
            return [row.copy() for row in self.cells]

        @raw_value.setter
        def raw_value(self, value):
            assert value is None  # installed xlmac .value.set(None) is a no-op

        def clear_contents(self):
            raise AssertionError("Mac public clear wrapper changes global screen_updating")

        def _native_clear(self):
            self.clear_calls += 1
            self.cells = [[None, None, None] for _ in range(3)]

        @property
        def value(self):
            raise AssertionError("value converter must not query range shape")

        @property
        def rows(self):
            raise AssertionError("range shape metadata must not be queried")

        @property
        def columns(self):
            raise AssertionError("range shape metadata must not be queried")

    class Anchor:
        raw_value = "2026-10-16"

        def __init__(self, spill):
            self.spill = spill
            self.result = []

        @property
        def value(self):
            return self.raw_value

        @value.setter
        def value(self, formula):
            assert formula == "=wsd()"
            for index, row in enumerate(self.result):
                self.spill.cells[index][: len(row)] = row

    spill = Spill()
    anchor = Anchor(spill)
    client = WindExcelClient()
    client._col = "ZZ"
    client._sheet = MagicMock()
    client._sheet.range.side_effect = lambda address: spill if ":" in address else anchor
    with (
        patch("data_layer.adapters.wind.client.time.sleep"),
        patch("data_layer.adapters.wind.client.sys.platform", "darwin"),
    ):
        anchor.result = [["2026-10-16", 11], ["2026-10-17", 22]]
        assert (
            client._execute_wsd_once("=wsd()", 2, expected_columns=2, max_rows=2) == anchor.result
        )
        client._helper_row = 1000  # emulate ring reuse of the exact same address
        anchor.result = [["2026-10-18", 33]]
        assert (
            client._execute_wsd_once("=wsd()", 2, expected_columns=2, max_rows=2) == anchor.result
        )
    assert spill.clear_calls == 4


def test_non_mac_spill_clear_uses_standard_range_method():
    from data_layer.adapters.wind.client import _clear_spill_range

    spill = MagicMock()
    sheet = MagicMock()
    sheet.range.return_value = spill
    with patch("data_layer.adapters.wind.client.sys.platform", "win32"):
        _clear_spill_range(sheet, "ZZ1000:AAB1003")
    spill.clear_contents.assert_called_once_with()
    spill.api.clear_contents.assert_not_called()


@pytest.mark.parametrize("max_rows", [0, -1, 1001, True, 1.5, "3"])
def test_bounded_spill_rejects_invalid_row_budget_before_excel(max_rows):
    from data_layer.adapters.wind.client import WindExcelClient

    client = WindExcelClient()
    client._sheet = MagicMock()
    with pytest.raises(ValueError, match="wind_spill_row_count_invalid"):
        client._execute_wsd_once("=wsd()", 1, max_rows=max_rows)
    client._sheet.range.assert_not_called()


def test_legacy_spill_retains_default_range_without_guard():
    from data_layer.adapters.wind.client import WindExcelClient

    client = WindExcelClient()
    client._col = "ZZ"
    anchor = MagicMock(raw_value="2026-10-16")
    spill = _OfflineSpillRange([["2026-10-16", 10]])
    client._sheet = MagicMock()
    client._sheet.range.side_effect = lambda address: spill if ":" in address else anchor
    with patch("data_layer.adapters.wind.client.time.sleep"):
        assert client._execute_wsd_once("=wsd()", 2) == [["2026-10-16", 10]]
    client._sheet.range.assert_any_call("ZZ1000:AAS1999")


@pytest.mark.parametrize("failed_stage", ["preclear", "anchor", "read"])
def test_spill_failure_logs_exact_original_stage_without_replay(failed_stage):
    from data_layer.adapters.wind.client import WindExcelClient

    class Range:
        def __init__(self, *, anchor=False):
            self.anchor = anchor
            self.writes = 0
            self.api = self

        @property
        def raw_value(self):
            if failed_stage == "read" and not self.anchor:
                raise RuntimeError("read failed")
            return "2026-10-16" if self.anchor else [["2026-10-16", 10]]

        def clear_contents(self):
            if failed_stage == "preclear" and not self.anchor and self.writes == 0:
                self.writes += 1
                raise RuntimeError("preclear failed")
            self.writes += 1

        @property
        def value(self):
            return "2026-10-16"

        @value.setter
        def value(self, value):
            self.writes += 1
            if failed_stage == "anchor":
                raise RuntimeError("anchor failed")

    anchor, spill = Range(anchor=True), Range()
    client = WindExcelClient()
    client._col = "ZZ"
    client._sheet = MagicMock()
    client._sheet.range.side_effect = lambda address: spill if ":" in address else anchor
    with (
        patch("data_layer.adapters.wind.client.time.sleep"),
        patch("data_layer.adapters.wind.client.logger.error") as error_log,
        pytest.raises(RuntimeError, match=f"{failed_stage} failed"),
    ):
        client._execute_wsd_once("=wsd()", 2, expected_columns=2, max_rows=1)
    assert [call.kwargs["stage"] for call in error_log.call_args_list] == [failed_stage]
    assert all(call.kwargs["request_sha256"] for call in error_log.call_args_list)
    assert all("excel_error" not in call.kwargs for call in error_log.call_args_list)
    assert all("formula" not in call.kwargs for call in error_log.call_args_list)
    assert anchor.writes == (0 if failed_stage == "preclear" else 1)


def test_cleanup_failure_preserves_primary_and_poisoned_ownership():
    from data_layer.adapters.wind.client import WindExcelClient
    from data_layer.adapters.wind.exceptions import WindCleanupError

    class FailingSpill(_OfflineSpillRange):
        def clear_contents(self):
            self.clear_calls += 1
            if self.clear_calls == 2:
                raise RuntimeError("cleanup failed")

    class FailingAnchor:
        raw_value = "2026-10-16"
        writes = 0

        @property
        def value(self):
            return self.raw_value

        @value.setter
        def value(self, _formula):
            self.writes += 1
            raise RuntimeError("anchor failed")

    anchor = FailingAnchor()
    spill = FailingSpill([["2026-10-16", 10]])
    client = WindExcelClient()
    client._col = "ZZ"
    client._sheet = MagicMock()
    client._sheet.range.side_effect = lambda address: spill if ":" in address else anchor
    with patch("data_layer.adapters.wind.client.logger.error") as error_log:
        with pytest.raises(RuntimeError, match="anchor failed"):
            client._execute_wsd_once("=wsd()", 2, expected_columns=2, max_rows=1)
        assert [call.kwargs["stage"] for call in error_log.call_args_list] == [
            "anchor",
            "cleanup",
        ]
        with pytest.raises(WindCleanupError):
            client.close()
    assert spill.clear_calls == 2
    assert anchor.writes == 1


def test_existing_only_never_launches_when_no_excel_exists():
    from data_layer.adapters.wind.client import WindExcelClient

    xw = MagicMock(apps=[])
    with patch.dict("sys.modules", {"xlwings": xw}), pytest.raises(WindNotConnectedError):
        WindExcelClient(existing_app_only=True)._connect()
    xw.App.assert_not_called()


def test_existing_only_skips_failed_creation_only_when_inventory_unchanged():
    from data_layer.adapters.wind.client import WindExcelClient

    broken, healthy = MagicMock(), MagicMock()
    broken.books.__iter__.return_value = iter([])
    rejected = RuntimeError("creation unavailable")
    rejected.errornumber = -50
    broken.books.add.side_effect = rejected
    owned = MagicMock(sheets=[MagicMock()])
    healthy.books.add.return_value = owned
    xw = MagicMock(apps=[broken, healthy])
    with patch.dict("sys.modules", {"xlwings": xw}):
        client = WindExcelClient(existing_app_only=True)
        client._connect()
        client.close()
    owned.close.assert_called_once_with()
    healthy.quit.assert_not_called()
    broken.quit.assert_not_called()
    xw.App.assert_not_called()


def test_existing_only_unknown_creation_result_blocks_next_instance():
    from data_layer.adapters.wind.client import WindExcelClient
    from data_layer.adapters.wind.exceptions import WindCleanupError

    broken, healthy = MagicMock(), MagicMock()
    broken.books.__iter__.side_effect = [iter([]), iter([MagicMock(name="unknown")])]
    broken.books.add.side_effect = TimeoutError()
    xw = MagicMock(apps=[broken, healthy])
    client = WindExcelClient(existing_app_only=True)
    with patch.dict("sys.modules", {"xlwings": xw}), pytest.raises(WindCleanupError):
        client._connect()
    with pytest.raises(WindCleanupError):
        client.close()
    with patch.dict("sys.modules", {"xlwings": xw}), pytest.raises(WindCleanupError):
        client._connect()
    healthy.books.add.assert_not_called()
    broken.quit.assert_not_called()
    xw.App.assert_not_called()
