# ⭐ SSSL Reference Outputs (Deterministic Physical Substrate Proof)

This folder contains reference artifacts produced by executing the  
**Shunyaya Structural Substrate Layer (SSSL)** verification runs.

These artifacts demonstrate **deterministic physical substrate behavior**  
under replay discipline.

They are provided for **audit transparency and inspection only**.

They are **NOT required** to execute SSSL, and they do **NOT replace independent verification**.

---

## **What These Reference Outputs Prove**

The included bundles demonstrate SSSL’s conformance-critical property:

`B_A = B_B`

Meaning:

- Two independent executions  
- Under identical declared inputs and locked parameters  
- Produce **byte-identical sealed artifacts**

Replay determinism is enforced at the artifact level  
via **SHA256-sealed `MANIFEST` files**.

Additionally, each reference bundle enforces:

**Collapse conservation**  
`phi((m,a,s)) = m`

**Fixed structural alphabet**  
`A4 = {Z0, Eplus, S, Eminus}`

**Spectral boundedness**  
`rho(P) = 1`

**Admissibility semantics**  
`ALLOW / ABSTAIN`

This is **deterministic substrate behavior by evidence — not interpretation**.

---

## **What These Reference Outputs Contain**

Each `REFERENCE` folder includes:

- `adm_result.txt`
- `eigenspectrum.txt`
- `P_matrix.csv`
- `summary.txt`
- `MANIFEST.sha256`

These files demonstrate:

- Substrate transition matrix stability  
- Spectral bound enforcement  
- Deterministic accumulation  
- Collapse admissibility decision  
- Byte-level artifact sealing  

No external datasets are redistributed.

All included traces are deterministic control traces or publicly reproducible inputs.

---

## **What These Reference Outputs Do NOT Claim**

- No prediction is performed  
- No domain equations are modified  
- No control logic is injected  
- No probabilistic inference is used  
- No external datasets are redistributed  
- These artifacts are not medical, seismic, or engineering advice  

SSSL operates strictly at the **structural substrate layer**.

---

## **How to Reproduce (Recommended)**

From project root:

**Windows:**

`python scripts\sssl_verify.py --in_csv data\sssl_smoke.csv --out_dir outputs\RUN1 --substrate`  
`python scripts\sssl_verify.py --in_csv data\sssl_smoke.csv --out_dir outputs\RUN2 --substrate`

Then compare:

`fc /b outputs\RUN1\MANIFEST.sha256 outputs\RUN2\MANIFEST.sha256`

Expected:

`No differences encountered`

This reproduces:

`B_A = B_B`

---

## **Canonical Verification Method (Capsule)**

For auditor-grade verification:

**Windows:**

`VERIFY_SSSL_CAPSULE\RUN_VERIFY.bat`

**macOS / Linux:**

`bash VERIFY_SSSL_CAPSULE/RUN_VERIFY.sh`

Expected final line:

`CAPSULE_RESULT: PASS`

Capsule verdict artifact:

`VERIFY_SSSL_CAPSULE\CAPSULE_SUMMARY.txt`

Optional sealing:

`certutil -hashfile VERIFY_SSSL_CAPSULE\CAPSULE_SUMMARY.txt SHA256`

This seals the auditor-facing verdict fingerprint.

---

## **Deterministic Claim Level**

SSSL satisfies civilization-grade determinism on two layers:

**Core substrate replay identity:**  
`B_A = B_B`

**Auditor capsule determinism:**  
`CAPSULE_RESULT: PASS`

Therefore, **SSSL qualifies as an execution-first deterministic structural substrate standard under replay discipline.**
