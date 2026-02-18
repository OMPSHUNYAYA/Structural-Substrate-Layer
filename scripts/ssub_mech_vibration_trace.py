#!/usr/bin/env python3
import argparse
import csv
from math import sin, pi

def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x

def main() -> None:
    ap = argparse.ArgumentParser(description="Deterministic mechanical vibration magnitude trace -> SSSL CSV schema.")
    ap.add_argument("--out_csv", required=True, help="Output CSV path (t_s,E_proxy,discharge).")
    ap.add_argument("--n", type=int, default=60, help="Number of samples (default: 60).")
    ap.add_argument("--dt", type=float, default=0.1, help="Time step seconds (default: 0.1).")
    args = ap.parse_args()

    n = max(10, int(args.n))
    dt = float(args.dt)

    rows = []

    # Segment plan (deterministic):
    # 0..7     : Z0 (near-zero, near-flat)
    # 8..25    : Eplus (ramp-up envelope)
    # 26..40   : S (plateau, small oscillation <= eps band)
    # 41       : Eminus (sudden drop + discharge flag)
    # 42..59   : Eplus -> S re-entry (recovery ramp, then plateau)

    for i in range(n):
        t_s = round(i * dt, 6)
        discharge = 0

        if i <= 7:
            # Quiescent: stays under tau0 and near-flat
            E = 0.03 + 0.001 * sin(2 * pi * i / 8.0)

        elif 8 <= i <= 25:
            # Ramp-up: increasing envelope (Eplus)
            r = (i - 8) / (25 - 8)
            E = 0.06 + 0.68 * r  # goes above taus eventually

        elif 26 <= i <= 40:
            # Plateau: stable high regime with tiny oscillation (S)
            # Keep |dE| small by oscillating within +/-0.008
            E = 0.74 + 0.008 * sin(2 * pi * (i - 26) / 10.0)

        elif i == 41:
            # Sudden shock/decay event: forces Eminus
            discharge = 1
            E = 0.32

        else:
            # Recovery: ramp back up, then stabilize
            if i <= 50:
                r = (i - 42) / (50 - 42)
                E = 0.34 + 0.40 * r  # 0.34 -> 0.74
            else:
                E = 0.74 + 0.007 * sin(2 * pi * (i - 51) / 8.0)

        E = clamp(E, 0.0, 1.0)
        rows.append((t_s, round(E, 6), discharge))

    with open(args.out_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t_s", "E_proxy", "discharge"])
        w.writerows(rows)

    print(f"OK: wrote mechanical vibration trace: {args.out_csv} (N={len(rows)})")

if __name__ == "__main__":
    main()
