#!/usr/bin/env python3
import argparse
import csv
from math import sin, pi

def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x

def main() -> None:
    ap = argparse.ArgumentParser(description="Deterministic fluid pressure magnitude trace -> SSSL CSV schema.")
    ap.add_argument("--out_csv", required=True, help="Output CSV path (t_s,E_proxy,discharge).")
    ap.add_argument("--n", type=int, default=70, help="Number of samples (default: 70).")
    ap.add_argument("--dt", type=float, default=0.1, help="Time step seconds (default: 0.1).")
    args = ap.parse_args()

    n = max(10, int(args.n))
    dt = float(args.dt)

    rows = []

    # Segment plan (deterministic):
    # 0..9     : Z0 (low pressure idle)
    # 10..30   : Eplus (pump ramp-up)
    # 31..48   : S (regulated plateau with very small ripple)
    # 49       : Eminus (valve release / pressure dump + discharge flag)
    # 50..69   : recovery (Eplus -> S)

    for i in range(n):
        t_s = round(i * dt, 6)
        discharge = 0

        if i <= 9:
            # Idle: under tau0 and near-flat
            E = 0.04 + 0.001 * sin(2 * pi * i / 10.0)

        elif 10 <= i <= 30:
            # Pump ramp: monotonic increase (Eplus)
            r = (i - 10) / (30 - 10)
            E = 0.06 + 0.70 * r  # reaches ~0.76

        elif 31 <= i <= 48:
            # Regulated plateau (S): ripple within eps band
            E = 0.75 + 0.009 * sin(2 * pi * (i - 31) / 12.0)

        elif i == 49:
            # Valve release: sudden drop forces Eminus
            discharge = 1
            E = 0.28

        else:
            # Recovery and stabilization
            if i <= 60:
                r = (i - 50) / (60 - 50)
                E = 0.30 + 0.45 * r  # 0.30 -> 0.75
            else:
                E = 0.75 + 0.008 * sin(2 * pi * (i - 61) / 9.0)

        E = clamp(E, 0.0, 1.0)
        rows.append((t_s, round(E, 6), discharge))

    with open(args.out_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t_s", "E_proxy", "discharge"])
        w.writerows(rows)

    print(f"OK: wrote fluid pressure trace: {args.out_csv} (N={len(rows)})")

if __name__ == "__main__":
    main()
