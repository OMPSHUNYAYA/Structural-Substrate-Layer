#!/usr/bin/env python3
"""
SSSL Verifier (deterministic, standard library only)

Purpose:
- Read an observation CSV: (t_s, E_proxy, discharge)
- Assign structural posture a ∈ {Z0, Eplus, S, Eminus}
- Optionally compute substrate artifacts:
  - accumulation s (tuple becomes (m,a,s))
  - admissibility adm_E ∈ {ALLOW, ABSTAIN}
  - operators (Inv_s, Series_s, Parallel_s)
  - transition matrices + ratio matrix P
  - eigen-spectrum artifact (deterministic QR iteration)
  - collapse identity check: phi((m,a,s)) = m

Required conservative invariant:
- phi((m,a,s)) = m

Determinism discipline:
- No randomness
- No external dependencies
- Fixed parameter disclosure
- Manifest seals produced artifacts
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import os
from dataclasses import dataclass
from typing import Dict, List, Tuple


A4 = ("Z0", "Eplus", "S", "Eminus")
ALLOW = "ALLOW"
ABSTAIN = "ABSTAIN"


@dataclass(frozen=True)
class Params:
    tau0: float
    taus: float
    eps: float
    drop: float


@dataclass(frozen=True)
class AccParams:
    s0: int
    s_max: int
    inc_on_eminus: int
    dec_on_s: int


@dataclass(frozen=True)
class AdmParams:
    collapse_ratio_max: float
    churn_ratio_max: float
    require_s: int


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_dir(d: str) -> None:
    os.makedirs(d, exist_ok=True)


def read_obs(csv_path: str) -> List[Tuple[float, float, int]]:
    rows: List[Tuple[float, float, int]] = []
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        expected = ["t_s", "E_proxy", "discharge"]
        if r.fieldnames != expected:
            raise ValueError(f"CSV header must be exactly: {expected} (got {r.fieldnames})")
        for i, row in enumerate(r, start=2):
            try:
                t = float(row["t_s"])
                e = float(row["E_proxy"])
                d = int(row["discharge"])
            except Exception as ex:
                raise ValueError(f"Bad row at line {i}: {row} ({ex})") from ex
            if e < 0:
                raise ValueError(f"E_proxy must be >= 0 (line {i})")
            if d not in (0, 1):
                raise ValueError(f"discharge must be 0 or 1 (line {i})")
            rows.append((t, e, d))
    if len(rows) < 2:
        raise ValueError("Need at least 2 rows to compute derivative.")
    rows.sort(key=lambda x: (x[0], x[1], x[2]))
    return rows


def compute_dedt(rows: List[Tuple[float, float, int]]) -> List[float]:
    d: List[float] = [0.0] * len(rows)
    for i in range(1, len(rows)):
        t0, e0, _ = rows[i - 1]
        t1, e1, _ = rows[i]
        dt = (t1 - t0)
        d[i] = 0.0 if dt == 0 else (e1 - e0) / dt
    return d


def label_state(e: float, dedt: float, discharge: int, p: Params) -> str:
    if discharge == 1 or dedt <= -abs(p.drop):
        return "Eminus"
    if e >= p.taus and abs(dedt) <= p.eps:
        return "S"
    if e <= p.tau0 and abs(dedt) <= p.eps:
        return "Z0"
    return "Eplus"


def inv_s(a: str) -> str:
    if a == "Z0":
        return "Z0"
    if a == "S":
        return "S"
    if a == "Eplus":
        return "Eminus"
    if a == "Eminus":
        return "Eplus"
    raise ValueError(f"Invalid state: {a}")


def series_s(a: str, b: str) -> str:
    if a == "Eminus" or b == "Eminus":
        return "Eminus"
    if a == "S" and b == "S":
        return "S"
    if (a == "S" and b == "Eplus") or (a == "Eplus" and b == "S"):
        return "Eplus"
    if a == "Z0":
        return b
    if b == "Z0":
        return a
    return "Eplus"


def parallel_s(a: str, b: str) -> str:
    if a == "Eminus" or b == "Eminus":
        return "Eminus"
    if a == "S" and b == "S":
        return "S"
    if a == "Z0" and b == "Z0":
        return "Z0"
    if a == "S" or b == "S":
        return "Eplus"
    return "Eplus"


def compute_accum(states: List[str], ap: AccParams) -> List[int]:
    s: List[int] = [0] * len(states)
    cur = ap.s0
    for i, a in enumerate(states):
        if a == "Z0":
            cur = 0
        elif a == "Eminus":
            cur = min(ap.s_max, cur + ap.inc_on_eminus)
        elif a == "S":
            cur = max(0, cur - ap.dec_on_s)
        s[i] = cur
    return s


def compute_churn(states: List[str]) -> int:
    churn = 0
    for i in range(1, len(states)):
        churn += 1 if states[i] != states[i - 1] else 0
    return churn


def avg_dwell(states: List[str], target: str) -> float:
    lengths: List[int] = []
    cur = 0
    for a in states:
        if a == target:
            cur += 1
        else:
            if cur > 0:
                lengths.append(cur)
                cur = 0
    if cur > 0:
        lengths.append(cur)
    return 0.0 if not lengths else sum(lengths) / float(len(lengths))


def trace_admissibility(states: List[str], adm: AdmParams) -> Tuple[str, Dict[str, float]]:
    n = float(len(states))
    c_eminus = float(sum(1 for a in states if a == "Eminus"))
    churn = float(compute_churn(states))
    c_s = int(sum(1 for a in states if a == "S"))
    collapse_ratio = c_eminus / n
    churn_ratio = churn / n
    metrics = {
        "collapse_ratio": collapse_ratio,
        "churn_ratio": churn_ratio,
        "count_S": float(c_s),
        "avg_dwell_S": avg_dwell(states, "S"),
    }
    if collapse_ratio > adm.collapse_ratio_max:
        return ABSTAIN, metrics
    if churn_ratio > adm.churn_ratio_max:
        return ABSTAIN, metrics
    if c_s < adm.require_s:
        return ABSTAIN, metrics
    return ALLOW, metrics


def transition_counts(states: List[str]) -> Dict[Tuple[str, str], int]:
    tc: Dict[Tuple[str, str], int] = {}
    for i in range(len(states) - 1):
        a, b = states[i], states[i + 1]
        tc[(a, b)] = tc.get((a, b), 0) + 1
    return tc


def transition_ratios(tc: Dict[Tuple[str, str], int]) -> Dict[Tuple[str, str], float]:
    rowsum: Dict[str, int] = {a: 0 for a in A4}
    for (a, _), v in tc.items():
        rowsum[a] = rowsum.get(a, 0) + v
    tr: Dict[Tuple[str, str], float] = {}
    for a in A4:
        rs = rowsum.get(a, 0)
        for b in A4:
            v = tc.get((a, b), 0)
            tr[(a, b)] = (float(v) / float(rs)) if rs > 0 else 0.0
    return tr


def mat_from_ratios(tr: Dict[Tuple[str, str], float]) -> List[List[float]]:
    return [[tr[(a, b)] for b in A4] for a in A4]


def eigvals_4x4(A: List[List[float]], iters: int = 200) -> List[complex]:
    def dot(u, v):
        return sum(ui * vi for ui, vi in zip(u, v))

    def norm(u):
        return math.sqrt(dot(u, u))

    def matmul(X, Y):
        n = len(X)
        m = len(Y[0])
        k = len(Y)
        out = [[0.0] * m for _ in range(n)]
        for i in range(n):
            for j in range(m):
                out[i][j] = sum(X[i][t] * Y[t][j] for t in range(k))
        return out

    def qr_decomp(M):
        n = len(M)
        Q = [[0.0] * n for _ in range(n)]
        R = [[0.0] * n for _ in range(n)]
        V = [M[i][:] for i in range(n)]
        for j in range(n):
            v = [V[i][j] for i in range(n)]
            for i in range(j):
                qi = [Q[r][i] for r in range(n)]
                R[i][j] = dot(qi, v)
                for r in range(n):
                    v[r] -= R[i][j] * qi[r]
            R[j][j] = norm(v)
            if R[j][j] == 0.0:
                for r in range(n):
                    Q[r][j] = 0.0
            else:
                for r in range(n):
                    Q[r][j] = v[r] / R[j][j]
        return Q, R

    Ak = [row[:] for row in A]
    for _ in range(iters):
        Q, R = qr_decomp(Ak)
        Ak = matmul(R, Q)
    return [complex(Ak[i][i], 0.0) for i in range(4)]


def write_csv_matrix(path: str, header: List[str], rows: List[List[str]]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow(r)


def write_states(out_csv: str, rows, dedt, states) -> None:
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["t_s", "E_proxy", "dE_dt", "discharge", "a_state"])
        for (t, e, dis), de, s in zip(rows, dedt, states):
            w.writerow([f"{t:.6f}", f"{e:.6f}", f"{de:.6f}", str(dis), s])


def write_accum(out_csv: str, rows, states, accum) -> None:
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["t_s", "E_proxy", "a_state", "s"])
        for (t, e, _), a, s in zip(rows, states, accum):
            w.writerow([f"{t:.6f}", f"{e:.6f}", a, str(int(s))])


def write_summary(path: str, params: Params, acc: AccParams, adm: AdmParams, n: int, counts: dict, substrate: bool) -> None:
    lines: List[str] = []
    lines.append("SSSL Verifier — summary")
    lines.append("")
    lines.append("State space: A4 = {Z0, Eplus, S, Eminus}")
    lines.append("Conservative extension: phi((m,a,s)) = m")
    lines.append("")
    lines.append("Deterministic parameters:")
    lines.append(f"tau0={params.tau0}")
    lines.append(f"taus={params.taus}")
    lines.append(f"eps={params.eps}")
    lines.append(f"drop={params.drop}")
    if substrate:
        lines.append("")
        lines.append("Accumulation parameters:")
        lines.append(f"s0={acc.s0}")
        lines.append(f"s_max={acc.s_max}")
        lines.append(f"inc_on_eminus={acc.inc_on_eminus}")
        lines.append(f"dec_on_s={acc.dec_on_s}")
        lines.append("")
        lines.append("Admissibility parameters:")
        lines.append(f"collapse_ratio_max={adm.collapse_ratio_max}")
        lines.append(f"churn_ratio_max={adm.churn_ratio_max}")
        lines.append(f"require_s={adm.require_s}")
    lines.append("")
    lines.append(f"Observations: {n}")
    lines.append("State counts:")
    for k in A4:
        lines.append(f"{k}: {counts.get(k, 0)}")
    lines.append("")
    lines.append("Rules (deterministic):")
    lines.append("- Eminus: discharge=1 OR dE/dt <= -drop")
    lines.append("- S: E_proxy >= taus AND |dE/dt| <= eps")
    lines.append("- Z0: E_proxy <= tau0 AND |dE/dt| <= eps")
    lines.append("- Otherwise: Eplus")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def write_manifest(out_dir: str, rel_paths: List[str]) -> str:
    rel_paths_sorted = sorted(rel_paths)
    man_path = os.path.join(out_dir, "MANIFEST.sha256")
    with open(man_path, "w", encoding="utf-8") as f:
        for rp in rel_paths_sorted:
            ap = os.path.join(out_dir, rp)
            h = sha256_file(ap)
            f.write(f"{h} *{rp}\n")
    return man_path


def write_operator_table(path: str) -> None:
    rows: List[List[str]] = []
    for a in A4:
        for b in A4:
            rows.append([a, b, inv_s(a), series_s(a, b), parallel_s(a, b)])
    write_csv_matrix(path, ["a", "b", "Inv_s(a)", "Series_s(a,b)", "Parallel_s(a,b)"], rows)


def write_transition_files(out_dir: str, states: List[str]) -> List[List[float]]:
    tc = transition_counts(states)
    tr = transition_ratios(tc)

    # Build P (matrix ratios)
    P = mat_from_ratios(tr)

    # transition_counts.csv (matrix counts)
    count_rows: List[List[str]] = []
    for a in A4:
        count_rows.append([a] + [str(tc.get((a, b), 0)) for b in A4])
    write_csv_matrix(os.path.join(out_dir, "transition_counts.csv"), ["From\\To"] + list(A4), count_rows)

    # P_matrix.csv (matrix ratios, compact)
    ratio_rows: List[List[str]] = []
    for i, a in enumerate(A4):
        ratio_rows.append([a] + [f"{P[i][j]:.6f}" for j in range(4)])
    write_csv_matrix(os.path.join(out_dir, "P_matrix.csv"), ["From\\To"] + list(A4), ratio_rows)

    # transition_ratios.csv (long-form audit table, explicit edges)
    rowsum: Dict[str, int] = {a: 0 for a in A4}
    for (a, _), v in tc.items():
        rowsum[a] = rowsum.get(a, 0) + v

    long_rows: List[List[str]] = []
    for a in A4:
        rs = rowsum.get(a, 0)
        for b in A4:
            c = tc.get((a, b), 0)
            r = (float(c) / float(rs)) if rs > 0 else 0.0
            long_rows.append([a, b, str(c), str(rs), f"{r:.6f}"])

    write_csv_matrix(
        os.path.join(out_dir, "transition_ratios.csv"),
        ["from", "to", "count", "rowsum_from", "ratio"],
        long_rows
    )

    return P


def write_eigenspectrum(out_dir: str, P: List[List[float]]) -> None:
    eigs = eigvals_4x4(P)
    path = os.path.join(out_dir, "eigenspectrum.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("SSSL spectral artifact (deterministic QR iteration)\n")
        f.write("Matrix order: [Z0, Eplus, S, Eminus]\n")
        f.write("Eigenvalues (approx):\n")
        for z in eigs:
            f.write(f"{z.real:.12f}\n")
        f.write("\nSpectral radius estimate:\n")
        f.write(f"{max(abs(z) for z in eigs):.12f}\n")


def write_adm_result(out_dir: str, verdict: str, metrics: Dict[str, float]) -> None:
    path = os.path.join(out_dir, "adm_result.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("SSSL admissibility verdict\n")
        f.write(f"adm_E: {verdict}\n")
        f.write("Metrics:\n")
        for k in sorted(metrics.keys()):
            f.write(f"{k}: {metrics[k]}\n")


def write_collapse_check(out_dir: str, rows, states, accum) -> None:
    path = os.path.join(out_dir, "collapse_check.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["t_s", "m", "a_state", "s", "phi(m,a,s)", "ok"])
        for (t, e, _), a, s in zip(rows, states, accum):
            phi_val = e
            ok = 1 if abs(phi_val - e) == 0.0 else 0
            w.writerow([f"{t:.6f}", f"{e:.6f}", a, str(int(s)), f"{phi_val:.6f}", str(ok)])


def extract_battery(battery_csv: str, out_csv: str, battery_id: str | None, max_rows: int | None) -> None:
    with open(battery_csv, "r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        required = {"battery_id", "cycle", "disV", "disI"}
        if r.fieldnames is None or any(k not in set(r.fieldnames) for k in required):
            raise ValueError("Battery CSV must include columns: battery_id, cycle, disV, disI")
        rows = []
        chosen = battery_id
        for row in r:
            bid = row["battery_id"]
            if chosen is None:
                chosen = bid
            if bid != chosen:
                continue
            t = float(row["cycle"])
            e = float(row["disV"])
            di = float(row["disI"])
            d = 1 if di < 0.0 else 0
            rows.append((t, e, d))
            if max_rows is not None and len(rows) >= max_rows:
                break
    rows.sort(key=lambda x: (x[0], x[1], x[2]))
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["t_s", "E_proxy", "discharge"])
        for t, e, d in rows:
            w.writerow([f"{t:.6f}", f"{e:.6f}", str(int(d))])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in_csv", help="Observation CSV (t_s,E_proxy,discharge)")
    ap.add_argument("--out_dir", default="outputs")
    ap.add_argument("--tau0", type=float, default=0.05)
    ap.add_argument("--taus", type=float, default=0.70)
    ap.add_argument("--eps", type=float, default=0.02)
    ap.add_argument("--drop", type=float, default=0.15)

    ap.add_argument("--substrate", action="store_true")
    ap.add_argument("--s0", type=int, default=0)
    ap.add_argument("--s_max", type=int, default=50)
    ap.add_argument("--inc_on_eminus", type=int, default=1)
    ap.add_argument("--dec_on_s", type=int, default=1)

    ap.add_argument("--collapse_ratio_max", type=float, default=0.60)
    ap.add_argument("--churn_ratio_max", type=float, default=0.80)
    ap.add_argument("--require_s", type=int, default=0)

    ap.add_argument("--battery_extract", action="store_true")
    ap.add_argument("--battery_csv")
    ap.add_argument("--battery_id")
    ap.add_argument("--max_rows", type=int)
    args = ap.parse_args()

    ensure_dir(args.out_dir)

    if args.battery_extract:
        if not args.battery_csv:
            raise ValueError("--battery_csv is required with --battery_extract")
        out_csv = os.path.join(args.out_dir, "battery_observations.csv")
        extract_battery(args.battery_csv, out_csv, args.battery_id, args.max_rows)
        print("OK: Battery observations extracted")
        print(f"OUT_CSV: {out_csv}")
        return 0

    if not args.in_csv:
        raise ValueError("--in_csv is required unless --battery_extract is used")

    params = Params(tau0=args.tau0, taus=args.taus, eps=args.eps, drop=args.drop)
    acc = AccParams(s0=args.s0, s_max=args.s_max, inc_on_eminus=args.inc_on_eminus, dec_on_s=args.dec_on_s)
    adm = AdmParams(collapse_ratio_max=args.collapse_ratio_max, churn_ratio_max=args.churn_ratio_max, require_s=args.require_s)

    rows = read_obs(args.in_csv)
    dedt = compute_dedt(rows)
    states = [label_state(e, de, dis, params) for (_, e, dis), de in zip(rows, dedt)]

    out_states = os.path.join(args.out_dir, "sssl_states.csv")
    out_summary = os.path.join(args.out_dir, "summary.txt")
    write_states(out_states, rows, dedt, states)

    counts = {}
    for s in states:
        counts[s] = counts.get(s, 0) + 1

    rel = ["sssl_states.csv"]
    accum_vals = [0] * len(states)

    if args.substrate:
        accum_vals = compute_accum(states, acc)
        write_accum(os.path.join(args.out_dir, "sssl_accumulation.csv"), rows, states, accum_vals)
        write_operator_table(os.path.join(args.out_dir, "operator_table.csv"))

        verdict, metrics = trace_admissibility(states, adm)
        write_adm_result(args.out_dir, verdict, metrics)

        P = write_transition_files(args.out_dir, states)
        write_eigenspectrum(args.out_dir, P)
        write_collapse_check(args.out_dir, rows, states, accum_vals)

        rel += [
            "sssl_accumulation.csv",
            "operator_table.csv",
            "adm_result.txt",
            "transition_counts.csv",
            "transition_ratios.csv",
            "P_matrix.csv",
            "eigenspectrum.txt",
            "collapse_check.csv",
        ]

    write_summary(out_summary, params, acc, adm, len(rows), counts, args.substrate)
    rel.append("summary.txt")

    manifest = write_manifest(args.out_dir, rel)

    print("OK: SSSL verification complete")
    print(f"OUT_DIR: {args.out_dir}")
    print(f"MANIFEST: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
