# Raw data: sources and setup

None of the third-party inputs below are bundled in this repo (each remains under its original source's terms).
Download each and place it at the path shown so `analysis/note_analysis.py` finds it without any path changes.

## 1. Felten AIOE inputs → `data/raw/felten_aioe/`
- `mapping_matrix.xlsx` and `onet_skills_occupations.xlsx`
- From Felten, Raj & Seamans (2021), "Occupational, Industry, and Geographic Exposure to Artificial Intelligence:
  A Novel Dataset and Its Potential Uses," *Strategic Management Journal*. Replication files are deposited on
  openICPSR (accession 114437). Search "Felten Raj Seamans AI occupational exposure openICPSR" if the direct link
  has moved.
- Expected files: `mapping_matrix.xlsx` (sheet `Combined`), `onet_skills_occupations.xlsx` (sheet `Abilities`).

## 2. O*NET database 10.0 → `data/raw/onet_db_10_0/`
- `Work Activities.txt`, `Work Context.txt` (tab-separated)
- From the O*NET Resource Center (onetcenter.org), "Database" → "Download" → select **version 10.0** specifically
  (the RTI construction is version-pinned; a later O*NET version will have different item wording/IDs).

## 3. Eloundou et al. (2024) GPT-4 exposure → `data/raw/eloundou/occ_level.csv`
- `human_rating_beta` occupational exposure scores, keyed by O\*NET-SOC code.
- From Eloundou, Manning, Mishkin & Rock (2024), "GPTs are GPTs: Labor Market Impact Potential of LLMs," published
  alongside the paper's public replication data.

## 4. Webb (2020) patent-based AI exposure → `data/raw/webb_2020/final_df_out.dta`
- Webb, M. (2020), "The Impact of Artificial Intelligence on the Labor Market," SSRN 3482150.
- `ai_score` (plus `software_score`, `robot_score`), keyed by `onetsoccode`. From the author's own published
  replication data ("Version 0.1").

## 5. OEWS processed panel → `data/raw/oews_processed/panel_crosswalked_lm_aioe.parquet`
This one **is** included in this repo (not a third-party redistribution restriction: it's our own derived
crosswalk of public BLS government data, which is public domain). It merges BLS OEWS occupation employment/wage
data (bls.gov/oes, all years 2013–2025 releases) onto the O\*NET-SOC/Felten occupation coding.

**Honest limitation:** the actual crosswalk code that built this panel from raw BLS files belongs to a separate,
retired project (a multi-year SOC-code crosswalk built for a different, now-abandoned causal-design paper) and
isn't a clean fit to include here as-is. So this repo gives you the processed panel directly, not the code that
built it. **What closes most of that gap cheaply:** `verify_oews_benchmark.py` (below) independently checks this
panel against the actual raw BLS release for a handful of benchmark occupations, so you don't have to take our
crosswalk on faith for at least those data points.

## 6. Raw BLS OEWS release (for independent spot-checking) → `data/raw/bls_oes_raw/state_M2025_dl.xlsx`
An unmodified copy of BLS's own May 2025 state-level OEWS release (bls.gov/oes/tables.htm), bundled here (public
domain, 7.3MB) so `verify_oews_benchmark.py` can run standalone with no extra download. Run it with:
`python3 data/raw/verify_oews_benchmark.py`: it checks Registered Nurses (California), Software Developers
(Texas), and Accountants and Auditors (New York) against the processed panel above and reports an exact
employment/wage match for each, or flags a mismatch if one exists.

## A note on why raw data isn't bundled here
Felten/Raj/Seamans, Eloundou et al., and Webb's data are each another researcher's own published output; this
repo links to their original source rather than re-hosting it, both out of respect for their own distribution
terms and so you always get the authoritative, current version of their data rather than a copy that could go stale.
