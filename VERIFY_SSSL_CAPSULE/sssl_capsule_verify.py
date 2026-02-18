import argparse
import csv
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_ARGS = 2
EXIT_MISSING = 3
EXIT_INVARIANT = 4

REQUIRED_ARTIFACTS = [
    "adm_result.txt",
    "collapse_check.csv",
    "eigenspectrum.txt",
    "operator_table.csv",
    "P_matrix.csv",
    "sssl_accumulation.csv",
    "sssl_states.csv",
    "summary.txt",
    "transition_counts.csv",
    "transition_ratios.csv",
    "MANIFEST.sha256",
]

A4_TOKENS = {"Z0", "Eplus", "S", "Eminus"}


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def relpath_posix(p: Path, base: Path) -> str:
    return p.relative_to(base).as_posix()


def write_manifest(dir_path: Path, manifest_name: str = "MANIFEST.sha256") -> None:
    files = []
    for p in dir_path.rglob("*"):
        if p.is_file() and p.name != manifest_name:
            files.append(p)
    files.sort(key=lambda x: relpath_posix(x, dir_path))
    lines = [f"{sha256_file(p)}  {relpath_posix(p, dir_path)}" for p in files]
    out = dir_path / manifest_name
    out.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8", newline="\n")


def ensure_clean_dir(p: Path) -> None:
    if p.exists():
        shutil.rmtree(p)
    p.mkdir(parents=True, exist_ok=True)


def require_file(p: Path) -> None:
    if not p.exists():
        raise FileNotFoundError(str(p))


def build_env():
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = "0"
    env["LC_ALL"] = "C"
    env["LANG"] = "C"
    env["TZ"] = "UTC"
    return env


def run_py(args_list, env):
    cp = subprocess.run(
        [sys.executable] + args_list,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if cp.returncode != 0:
        sys.stdout.write(cp.stdout)
        sys.stderr.write(cp.stderr)
        raise RuntimeError("subprocess failed: " + " ".join(args_list))
    return cp.stdout


def compare_dirs(a: Path, b: Path) -> bool:
    a_files = sorted([p for p in a.rglob("*") if p.is_file()], key=lambda x: relpath_posix(x, a))
    b_files = sorted([p for p in b.rglob("*") if p.is_file()], key=lambda x: relpath_posix(x, b))

    if [relpath_posix(p, a) for p in a_files] != [relpath_posix(p, b) for p in b_files]:
        return False

    for ap in a_files:
        rp = relpath_posix(ap, a)
        bp = b / rp
        if ap.stat().st_size != bp.stat().st_size:
            return False
        if sha256_file(ap) != sha256_file(bp):
            return False

    return True


def count_states(states_csv: Path):
    counts = {k: 0 for k in A4_TOKENS}
    others = set()
    with states_csv.open("r", encoding="utf-8", errors="replace", newline="") as f:
        header = f.readline()
        if not header:
            return counts, others
        cols = [c.strip() for c in header.strip().split(",")]
        idx = cols.index("a") if "a" in cols else (len(cols) - 1)
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split(",")]
            if idx >= len(parts):
                continue
            a = parts[idx]
            if a in counts:
                counts[a] += 1
            else:
                others.add(a)
    return counts, others


def read_adm(adm_path: Path) -> str:
    with adm_path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        for line in f:
            s = line.strip()
            if s.startswith("adm_E:"):
                return s.split(":", 1)[1].strip()
    return ""


def _try_float(x: str):
    try:
        return float(x)
    except Exception:
        return None


def read_matrix_csv(p: Path):
    rows = []
    with p.open("r", encoding="utf-8", errors="replace", newline="") as f:
        r = csv.reader(f)
        for row in r:
            if not row:
                continue
            rows.append([c.strip() for c in row])

    if not rows:
        raise ValueError("empty P_matrix.csv")

    def row_numeric_count(rr):
        c = 0
        for v in rr:
            if _try_float(v) is not None:
                c += 1
        return c

    first = rows[0]
    numeric_first = row_numeric_count(first)

    drop_header = False
    drop_first_col = False

    if numeric_first < len(first):
        drop_header = True

    if len(rows) > 1:
        col0_numeric = 0
        for i in range(1 if drop_header else 0, min(len(rows), 6)):
            v = rows[i][0] if rows[i] else ""
            if _try_float(v) is not None:
                col0_numeric += 1
        if col0_numeric == 0:
            drop_first_col = True

    data_rows = rows[1:] if drop_header else rows[:]
    mat = []
    for rr in data_rows:
        rr2 = rr[1:] if drop_first_col and len(rr) > 1 else rr[:]
        nums = []
        for v in rr2:
            fv = _try_float(v)
            if fv is None:
                raise ValueError("non-numeric cell in P_matrix.csv")
            nums.append(fv)
        if nums:
            mat.append(nums)

    if not mat:
        raise ValueError("no numeric matrix rows in P_matrix.csv")

    n = len(mat)
    for rr in mat:
        if len(rr) != n:
            raise ValueError("P_matrix.csv not square")

    return mat


def spectral_radius_power_iteration(mat, iters=80):
    n = len(mat)
    v = [1.0 / n] * n
    rho = 0.0
    for _ in range(iters):
        w = [0.0] * n
        for i in range(n):
            s = 0.0
            row = mat[i]
            for j in range(n):
                s += row[j] * v[j]
            w[i] = s
        m = 0.0
        for x in w:
            ax = x if x >= 0.0 else -x
            if ax > m:
                m = ax
        if m == 0.0:
            return 0.0
        inv = 1.0 / m
        for i in range(n):
            w[i] *= inv
        v = w
        rho = m
    return rho


def require_invariants(out_dir: Path, require_adm: str):
    for name in REQUIRED_ARTIFACTS:
        require_file(out_dir / name)

    summary_path = out_dir / "summary.txt"
    txt = summary_path.read_text(encoding="utf-8", errors="replace")
    if "phi((m,a,s)) = m" not in txt:
        raise ValueError("missing or wrong collapse invariant in summary.txt")

    states_csv = out_dir / "sssl_states.csv"
    counts, others = count_states(states_csv)
    if others:
        raise ValueError("non-A4 states found: " + ",".join(sorted(list(others))))
    if sum(counts.values()) == 0:
        raise ValueError("no A4 states counted")

    pm_path = out_dir / "P_matrix.csv"
    mat = read_matrix_csv(pm_path)
    rho = spectral_radius_power_iteration(mat)
    if abs(rho - 1.0) > 1e-9:
        raise ValueError("rho(P) not equal to 1 within tolerance: " + str(rho))

    adm = read_adm(out_dir / "adm_result.txt")
    if require_adm and adm != require_adm:
        raise ValueError("adm_E mismatch: got " + adm + " expected " + require_adm)

    tr = out_dir / "transition_ratios.csv"
    pm = out_dir / "P_matrix.csv"
    if tr.exists() and pm.exists():
        if tr.stat().st_size == pm.stat().st_size:
            if sha256_file(tr) == sha256_file(pm):
                raise ValueError("artifact semantic integrity failed: transition_ratios.csv equals P_matrix.csv")


def write_negative_control_csv(out_csv: Path, n: int = 400):
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    lines = ["t_s,E_proxy,discharge"]
    for i in range(n):
        e = 1.0 if (i % 2 == 0) else 0.0
        d = 1 if (i % 3 == 0) else 0
        lines.append(f"{i},{e},{d}")
    out_csv.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def run_case(case_name: str, repo_root: Path, work_dir: Path, env, require_adm: str):
    scripts_dir = repo_root / "scripts"
    data_dir = repo_root / "data"
    out_root = repo_root / "VERIFY_SSSL_CAPSULE" / "OUT"

    sssl_verify = scripts_dir / "sssl_verify.py"
    require_file(sssl_verify)

    if case_name == "SMOKE":
        in_csv = data_dir / "sssl_smoke.csv"
        require_file(in_csv)
    elif case_name == "MECH":
        in_csv = data_dir / "sssl_mech_vibration.csv"
        require_file(in_csv)
    elif case_name == "FLUID":
        in_csv = data_dir / "sssl_fluid_pressure.csv"
        require_file(in_csv)
    elif case_name == "NEGCTL_ABSTAIN":
        in_csv = work_dir / "negctl_abstain.csv"
        write_negative_control_csv(in_csv)
    else:
        raise ValueError("unknown case: " + case_name)

    out_a = out_root / (case_name + "_REPLAY_A")
    out_b = out_root / (case_name + "_REPLAY_B")
    ensure_clean_dir(out_a)
    ensure_clean_dir(out_b)

    run_py([str(sssl_verify), "--in_csv", str(in_csv), "--out_dir", str(out_a), "--substrate"], env)
    run_py([str(sssl_verify), "--in_csv", str(in_csv), "--out_dir", str(out_b), "--substrate"], env)

    write_manifest(out_a)
    write_manifest(out_b)

    require_invariants(out_a, require_adm=require_adm)
    require_invariants(out_b, require_adm=require_adm)

    ok = compare_dirs(out_a, out_b)
    if not ok:
        raise ValueError("replay mismatch: B_A != B_B for " + case_name)

    return out_a, out_b


def parse_args():
    ap = argparse.ArgumentParser(prog="sssl_capsule_verify.py")
    ap.add_argument("--repo_root", default="..")
    ap.add_argument("--cases", default="core", choices=["core"])
    return ap.parse_args()


def main():
    try:
        args = parse_args()
    except SystemExit:
        return EXIT_ARGS

    repo_root = Path(args.repo_root).resolve()
    env = build_env()

    try:
        require_file(repo_root / "scripts" / "sssl_verify.py")
        require_file(repo_root / "data" / "sssl_smoke.csv")
        require_file(repo_root / "data" / "sssl_mech_vibration.csv")
        require_file(repo_root / "data" / "sssl_fluid_pressure.csv")

        capsule_dir = repo_root / "VERIFY_SSSL_CAPSULE"
        ensure_clean_dir(capsule_dir / "OUT")
        ensure_clean_dir(capsule_dir / "_WORK")

        run_case("SMOKE", repo_root, capsule_dir / "_WORK", env, require_adm="ALLOW")
        run_case("MECH", repo_root, capsule_dir / "_WORK", env, require_adm="ALLOW")
        run_case("FLUID", repo_root, capsule_dir / "_WORK", env, require_adm="ALLOW")
        run_case("NEGCTL_ABSTAIN", repo_root, capsule_dir / "_WORK", env, require_adm="ABSTAIN")

        (capsule_dir / "CAPSULE_SUMMARY.txt").write_text(
            "\n".join(
                [
                    "SSSL_VERIFY_CAPSULE",
                    "CASES: SMOKE, MECH, FLUID, NEGCTL_ABSTAIN",
                    "INVARIANTS:",
                    "phi((m,a,s)) = m",
                    "A4 = {Z0, Eplus, S, Eminus}",
                    "|A4| = 4",
                    "rho(P) = 1",
                    "B_A = B_B",
                    "RESULT: PASS",
                ]
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )

        sys.stdout.write("CAPSULE_RESULT: PASS\n")
        return EXIT_OK

    except FileNotFoundError as e:
        sys.stderr.write("MISSING: " + str(e) + "\n")
        sys.stdout.write("CAPSULE_RESULT: FAIL\n")
        return EXIT_MISSING
    except RuntimeError as e:
        sys.stderr.write("FAIL: " + str(e) + "\n")
        sys.stdout.write("CAPSULE_RESULT: FAIL\n")
        return EXIT_FAIL
    except Exception as e:
        sys.stderr.write("INVARIANT: " + repr(e) + "\n")
        sys.stdout.write("CAPSULE_RESULT: FAIL\n")
        return EXIT_INVARIANT


if __name__ == "__main__":
    raise SystemExit(main())
