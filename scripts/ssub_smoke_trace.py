# scripts/ssub_smoke_trace.py
import argparse
import csv

def main() -> None:
    ap = argparse.ArgumentParser(description="Generate a deterministic smoke-test trace in SSSL input format.")
    ap.add_argument("--out_csv", required=True)
    args = ap.parse_args()

    # Deterministic pattern: ramp up -> plateau -> sharp drop (event) -> ramp up
    # This is a functional smoke-test trace, not a physical simulation claim.
    rows = []
    t = 0.0

    # ramp up
    v = 0.0
    for _ in range(10):
        rows.append((t, v, 0))
        t += 1.0
        v += 0.08

    # plateau
    for _ in range(6):
        rows.append((t, v, 0))
        t += 1.0

    # sharp drop with event flag
    v = max(0.0, v - 0.6)
    rows.append((t, v, 1))
    t += 1.0

    # ramp up again
    for _ in range(8):
        rows.append((t, v, 0))
        t += 1.0
        v += 0.07

    with open(args.out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["t_s", "E_proxy", "discharge"])
        for t_s, e_proxy, discharge in rows:
            w.writerow([f"{t_s:.12g}", f"{e_proxy:.12g}", str(int(discharge))])

if __name__ == "__main__":
    main()
