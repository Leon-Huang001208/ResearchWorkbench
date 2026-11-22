# Wind Excel adapter

`data_layer/adapters/wind/client.py` owns worksheet queries and explicitly owned
workbooks/applications. `formulas.py` defines the Mac worksheet functions;
`wind_adapter.py` maps ordinary business requests onto those functions.

## macOS instance inventory

`excel_instances.py` handles the observed modern `lsappinfo` multiline PID output.
Before the Wind client creates or attaches an application, it prepares a process-local
output wrapper on the already-loaded `xlwings._xlmac.subprocess`, without enumerating
user applications. Direct inventory callers can also recover after the known integer
parser failure. The wrapper normalizes only the exact
`lsappinfo info -only pid <ASN>` read, preserving fresh positive PIDs and the
explicit stale/null record. Duplicate, malformed or unavailable identities fail
closed; they never imply that Excel is absent. Other subprocess calls and the
installed package files remain unchanged. This compatibility path also covers
xlwings' repeated PID parser during workbook activation and exit cleanup.

The client creates a new application only after a successful empty inventory,
or when the caller explicitly requests an isolated application. Report probes
use owned workbooks and close only resources that the client owns. Readiness,
formula values and historical coverage are separate evidence; a successful
heartbeat does not certify a weekly report or API entitlement.

The weekly Excel source uses `existing_app_only=True`: it creates a task-owned
workbook inside an already running Excel process, without changing application
settings or touching existing books. A newly launched Mac Excel process passed
the static heartbeat but left WSD/TDAYS at `Fetching...`; the same requests in
the existing Wind-loaded process returned actual rows, including the National
Day holiday gap. This is a transport comparison, not verification of all markets.
Only an explicit macOS parameter rejection (-50), followed by an unchanged book
inventory, permits trying the next existing instance. Timeouts, unknown results
and changed inventories raise a cleanup error and retain the worker poison gate.
No available existing application means blocked input, never implicit launch.

Mac spill ranges contain empty strings as well as `None`; both are trimmed at
the boundaries while numeric zero is preserved. Source dates, numeric identity,
market calendars and report quality still require the Host's independent checks.

The private weekly TDAYS and single-field WSD caller now supplies a validated
row budget for each request. The client reads one extra row and column to detect
contiguous spill overflow; `0` and `False` in those guard cells count as occupied.
TDAYS and ordinary WSD use at most 366 natural days per segment, while the
reviewed India segments use their expected exchange dates. Other callers keep
the legacy 1000-by-20 range when they omit the budget. Owned-range clearing uses
the native `range.api.clear_contents()` command on Mac without a range-shape
query or a global `screen_updating` change; other platforms use xlwings
`clear_contents()`. A native workbook check found that
`raw_value=None` left numeric cells unchanged, so it is not a valid clear.
Preclear, anchor, read, cleanup and close failures carry a formula hash
and range in logs; an unconfirmed bounded cleanup blocks reuse and preserves
the owned workbook for explicit recovery. This reduces Excel bridge traffic but
does not certify that a busy Wind plugin will complete a real request.

`build_wsd_formula` emits each worksheet option as a separate quoted argument.
The Mac add-in silently returned the SSE date axis when given a combined
semicolon options argument; splitting `Days`, `Fill` and `TradingCalendar`
restored the expected India dates in a bounded real comparison. This is Excel
worksheet syntax only; Client API option syntax is unchanged. The weekly
provider records the actual formula and rejects missing, duplicated or reordered
dates against the independently verified official India calendar. It uses the
single-call transport so an unknown result cannot trigger an implicit retry.

Near tests: `tests/unit/test_wind_excel_instances.py` and
`tests/unit/test_wind_adapter.py`. Real Office/Wind, Windows and Linux acceptance
remain separate from mocks.
