"""
verify_oews_benchmark.py -- independently confirm the processed OEWS panel against the raw BLS release.

The processed panel (oews_processed/panel_crosswalked_lm_aioe.parquet) is bundled in this repo rather than
rebuilt from scratch here (see data/raw/README.md for why: the original crosswalk code belongs to a separate,
retired project and isn't a clean fit for this repo). This script closes the resulting trust gap cheaply: it
reads the actual raw BLS state-level release (bls_oes_raw/state_M2025_dl.xlsx, an unmodified public BLS file,
also bundled here) and checks a handful of benchmark occupation/state combinations against the processed panel
for an EXACT match, not just a plausible one.

Run: python3 data/raw/verify_oews_benchmark.py
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW_XLSX = ROOT / "data" / "raw" / "bls_oes_raw" / "state_M2025_dl.xlsx"
PROCESSED = ROOT / "data" / "raw" / "oews_processed" / "panel_crosswalked_lm_aioe.parquet"

# (state, SOC code, human-readable label) -- a small, deliberately varied set of benchmark checks.
BENCHMARKS = [
    ("California", "29-1141", "Registered Nurses"),
    ("Texas", "15-1252", "Software Developers"),
    ("New York", "13-2011", "Accountants and Auditors"),
]

def main():
    raw = pd.read_excel(RAW_XLSX)
    proc = pd.read_parquet(PROCESSED)

    print("=== OEWS benchmark spot-check: raw BLS release vs. this repo's processed panel ===\n")
    all_pass = True
    for state, soc, label in BENCHMARKS:
        r = raw[(raw["AREA_TITLE"] == state) & (raw["OCC_CODE"] == soc)]
        p = proc[(proc["state_name"] == state) & (proc["soc_code"] == soc) & (proc["year"] == 2025)]
        if r.empty or p.empty:
            print(f"  [SKIP] {label} ({state}, {soc}) not found in one of the two files.")
            continue
        r_emp, r_wage = float(r["TOT_EMP"].iloc[0]), float(r["A_MEAN"].iloc[0])
        p_emp, p_wage = float(p["tot_emp"].iloc[0]), float(p["a_mean"].iloc[0])
        ok = (r_emp == p_emp) and (r_wage == p_wage)
        all_pass &= ok
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {label} ({state}, {soc}): "
              f"raw BLS emp={r_emp:,.0f} wage=${r_wage:,.0f}  |  "
              f"processed panel emp={p_emp:,.0f} wage=${p_wage:,.0f}")

    print(f"\n{'All benchmarks match exactly.' if all_pass else 'MISMATCH FOUND -- investigate before trusting the processed panel.'}")

if __name__ == "__main__":
    main()
