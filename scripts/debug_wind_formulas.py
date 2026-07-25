"""测试 per-field range 公式 — 每字段独立列溢位"""
import time
import datetime as dt
import string
from data_layer.adapters.wind.client import WindExcelClient

def to_num(v):
    if isinstance(v, dt.datetime):
        return round((v - dt.datetime(1899, 12, 30)).total_seconds() / 86400, 6)
    return v

def col_name(n):
    result = ""
    while n > 0:
        n -= 1
        result = string.ascii_uppercase[n % 26] + result
        n //= 26
    return result

client = WindExcelClient(visible=False, timeout=15.0, col="AE")
client._connect()
sheet = client._sheet
client.heartbeat()
code = "600519.SH"
start, end = "2026-05-01", "2026-06-01"

# ── 测试 1: 每个字段用 range 公式放在不同列 ──
print("=== Per-field range 公式测试 ===")
# 字段 → 公式生成器
fields = [
    ("open",  f'=s_dq_open("{code}","{start}","{end}",1)'),
    ("high",  f'=s_dq_high("{code}","{start}","{end}",1)'),
    ("low",   f'=s_dq_low("{code}","{start}","{end}",1)'),
    ("close", f'=s_dq_close("{code}","{start}","{end}",1)'),
    ("vol",   f'=s_dq_volume("{code}","{start}","{end}")'),
    ("amt",   f'=s_dq_amount("{code}","{start}","{end}")'),
    ("turn",  f'=s_dq_turn("{code}","{start}","{end}")'),
    ("pct",   f'=s_dq_pctchange("{code}","{start}","{end}")'),
    ("vwap",  f'=s_dq_avgprice("{code}","{start}","{end}")'),
    ("swing", f'=s_dq_swing("{code}","{start}","{end}")'),
]

start_col = "AE"
start_num = sum((ord(ch) - ord('A') + 1) * (26 ** (len(start_col) - 1 - i)) for i, ch in enumerate(start_col))

# 清除旧数据
for i in range(len(fields)):
    c = col_name(start_num + i)
    sheet.range(f"{c}1:{c}200").value = None
time.sleep(0.3)

# 写入所有 range 公式（每列一个）
for i, (name, formula) in enumerate(fields):
    c = col_name(start_num + i)
    sheet.range(f"{c}1").value = formula
    if i == 0:
        print(f"  写入: {c}1 = {name}")

print(f"  共写入 {len(fields)} 个 range 公式到列 {start_col}-{col_name(start_num + len(fields) - 1)}")

# 等待所有公式解析
t0 = time.monotonic()
all_resolved = False
while time.monotonic() - t0 < 15.0:
    time.sleep(0.3)
    all_resolved = True
    for i in range(len(fields)):
        c = col_name(start_num + i)
        v = sheet.range(f"{c}1").value
        if v is None:
            all_resolved = False
            break
    if all_resolved:
        break

print(f"  所有公式解析完成 ({time.monotonic() - t0:.1f}s)")

# 读取每列结果（raw_value）
for i, (name, _) in enumerate(fields):
    c = col_name(start_num + i)
    try:
        col_data = sheet.range(f"{c}1:{c}50").raw_value
    except Exception:
        col_data = sheet.range(f"{c}1:{c}50").value

    if isinstance(col_data, list):
        non_none = [to_num(v) for v in col_data if v is not None]
        print(f"  [{name:6s}] col={c}: {len(non_none)} non-None values, first 5: {non_none[:5]}")
    else:
        print(f"  [{name:6s}] col={c}: single value = {to_num(col_data)}")

# 清理
for i in range(len(fields)):
    c = col_name(start_num + i)
    sheet.range(f"{c}1:{c}200").value = None

# ── 测试 2: 对比 WSD 方案 ──
print("\n=== WSD 对比测试 (raw_value 读取宽范围) ===")
wsd_formula = f'=wsd("{code}","open,high,low,close,volume,amount,turn,pct_chg,vwap,swing","{start}","{end}","")'
sheet.range(f"{start_col}1:{start_col}200").value = None
time.sleep(0.3)
sheet.range(f"{start_col}1").value = wsd_formula

t0 = time.monotonic()
while time.monotonic() - t0 < 10.0:
    time.sleep(0.3)
    v = sheet.range(f"{start_col}1").value
    if v is not None and not isinstance(v, str):
        break
time.sleep(0.5)

# 读宽范围：11 cols (date + 10 fields) × 50 rows
end_col = col_name(start_num + 11)
raw_data = sheet.range(f"{start_col}1:{end_col}50").raw_value

if isinstance(raw_data, list) and len(raw_data) > 0:
    header = raw_data[0]
    if isinstance(header, list):
        n_cols = 0
        for v in header:
            if v is not None:
                n_cols += 1
            else:
                break
        print(f"  WSD: {len([r for r in raw_data if isinstance(r, list) and any(c is not None for c in r)])} rows × {n_cols} cols")
        print(f"  Header (raw_value): {[to_num(v) if v != '' else '<empty>' for v in header[:n_cols]]}")
        if len(raw_data) > 1:
            print(f"  Row[1] (raw_value): {[to_num(v) if v != '' else '<empty>' for v in raw_data[1][:n_cols]]}")
        if len(raw_data) > 2:
            print(f"  Row[2] (raw_value): {[to_num(v) if v != '' else '<empty>' for v in raw_data[2][:n_cols]]}")

sheet.range(f"{start_col}1:{end_col}50").value = None

client.close()
print("\n=== 完成 ===")
