# scripts/prepare_ssub_input.py
import argparse
import csv
from typing import Optional, List, Dict, Any

def read_csv_rows(path: str) -> List[Dict[str, str]]:
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("Input CSV has no header row.")
        rows = [r for r in reader]
    return rows

def to_float(x: Any, name: str) -> float:
    try:
        return float(str(x).strip())
    except Exception as e:
        raise ValueError(f"Cannot parse {name} as float: {x!r}") from e

def to_int01(x: Any, name: str) -> int:
    s = str(x).strip().lower()
    if s in ("1", "true", "t", "yes", "y"):
        return 1
    if s in ("0", "false", "f", "no", "n", ""):
        return 0
    # allow numeric >0 => 1
    try:
        return 1 if float(s) > 0 else 0
    except Exception as e:
        raise ValueError(f"Cannot parse {name} as 0/1: {x!r}") from e

def write_sssl_csv(out_csv: str, rows: List[Dict[str, str]], t_col: str, m_col: str, event_col: Optional[str]) -> None:
    out_rows = []
    for r in rows:
        t_s = to_float(r.get(t_col, ""), "t_s")
        e_proxy = to_float(r.get(m_col, ""), "E_proxy")
        discharge = 0
        if event_col is not None:
            discharge = to_int01(r.get(event_col, "0"), "discharge")
        out_rows.append((t_s, e_proxy, discharge))

    # Deterministic ordering: by t_s ascending, then E_proxy, then discharge
    out_rows.sort(key=lambda x: (x[0], x[1], x[2]))

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["t_s", "E_proxy", "discharge"])
        for t_s, e_proxy, discharge in out_rows:
            # stable numeric rendering
            w.writerow([f"{t_s:.12g}", f"{e_proxy:.12g}", str(int(discharge))])

def main() -> None:
    ap = argparse.ArgumentParser(description="Prepare a universal-domain trace into SSSL input format (t_s,E_proxy,discharge).")
    ap.add_argument("--in_csv", required=True)
    ap.add_argument("--out_csv", required=True)
    ap.add_argument("--t_col", required=True, help="Time column name in input CSV.")
    ap.add_argument("--m_col", required=True, help="Magnitude proxy column name in input CSV (pressure/flow/vibration/etc).")
    ap.add_argument("--event_col", default=None, help="Optional event column name (0/1). If omitted, discharge=0 for all rows.")
    args = ap.parse_args()

    rows = read_csv_rows(args.in_csv)
    write_sssl_csv(args.out_csv, rows, args.t_col, args.m_col, args.event_col)

if __name__ == "__main__":
    main()
