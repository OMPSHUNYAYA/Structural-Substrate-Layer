# outputs/

This folder is **intentionally empty** in the public repository.

It serves as the runtime output directory for **SSSL verification executions**.

Artifacts generated here are **ephemeral runtime artifacts** and are not considered authoritative reference outputs.

---

## **What This Folder Is For**

When executing:

`python scripts\sssl_verify.py --in_csv data\sssl_smoke.csv --out_dir outputs\RUN1 --substrate`

or

`python scripts\sssl_verify.py --in_csv data\sssl_smoke.csv --out_dir outputs\RUN2 --substrate`

SSSL will generate:

- `outputs\RUN*/`
- `summary.txt`
- `P_matrix.csv`
- `eigenspectrum.txt`
- `adm_result.txt`
- `MANIFEST.sha256`

These artifacts are produced during deterministic verification runs.

They demonstrate runtime enforcement of:

- `phi((m,a,s)) = m`
- `A4 = {Z0, Eplus, S, Eminus}`
- `rho(P) <= 1`
- `B_A = B_B`

They are **not canonical reference artifacts**.

---

## **What This Folder Is NOT**

- It is **not** the canonical reference bundle  
- It does **not** contain frozen verification artifacts  
- It does **not** replace `reference_outputs/`  
- It does **not** define conformance  

Authoritative replay-verified conformance artifacts are stored under:

`reference_outputs/`

---

## **Reproducibility**

To reproduce deterministic replay identity:

`python scripts\sssl_verify.py --in_csv data\sssl_smoke.csv --out_dir outputs\RUN1 --substrate`

`python scripts\sssl_verify.py --in_csv data\sssl_smoke.csv --out_dir outputs\RUN2 --substrate`

Then compare:

`fc /b outputs\RUN1\MANIFEST.sha256 outputs\RUN2\MANIFEST.sha256`

Expected:

`No differences encountered`

This demonstrates:

`B_A = B_B`

For auditor-grade verification, use:

`VERIFY_SSSL_CAPSULE\RUN_VERIFY.bat`

Expected final line:

`CAPSULE_RESULT: PASS`

---

This separation preserves:

- **Deterministic execution discipline**  
- **Clear distinction between runtime outputs and frozen reference artifacts**  
- **Finite structural grammar clarity (`|A4| = 4`)**  
- **Conservative collapse invariant integrity (`phi((m,a,s)) = m`)**

SSSL enforces deterministic structural substrate behavior under replay identity.
