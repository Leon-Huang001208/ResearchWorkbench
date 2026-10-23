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
