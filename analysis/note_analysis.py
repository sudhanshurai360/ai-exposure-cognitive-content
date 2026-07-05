"""
note_analysis.py -- Reproducible analysis for the short measurement note:
"AI occupational-exposure scores are largely a relabeling of cognitive task content."

Inputs (all under ./data/raw/ relative to this repo -- see data/raw/README.md for exact download instructions
for each source; nothing here is redistributed by this repo except our own derived OEWS panel, see that README):
  - Felten ability x AI-application relatedness matrix (mapping_matrix.xlsx, 'Combined' consensus)
  - O*NET abilities (importance IM x level LV) per O*NET-SOC occupation
  - Eloundou et al. (2024) GPT-4 occupational exposure (human_rating_beta), per O*NET-SOC
  - OEWS panel (PROCESSED artifact, flagged) for occupation employment, wage level, and 2013->2019 real-wage growth
  - O*NET Work Activities/Work Context (db 10.0) -> Autor-Dorn RTI robustness check
  - Webb (2020) patent-based AI exposure score (ai_score) -> third independently-built score

Outputs: results/note_results.json  (every number the note cites)

Run:  python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
      python3 analysis/note_analysis.py
"""
import json, itertools
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW  = ROOT / "data" / "raw"
FEL  = RAW / "felten_aioe"
ONET = RAW / "onet_db_10_0"
OUT  = ROOT / "results"; OUT.mkdir(exist_ok=True)

def z(s): return (s - s.mean()) / s.std()

def se_ols(y, X, b):
    """Classical (homoskedastic) OLS standard errors: sqrt(diag(sigma^2 * (X'X)^-1))."""
    n, k = X.shape
    resid = y - X @ b
    sigma2 = (resid**2).sum() / max(n - k, 1)
    XtX_inv = np.linalg.inv(X.T @ X)
    return np.sqrt(np.diag(sigma2 * XtX_inv))

def ols(y, cols):
    """Returns (b, se, r2). b/se include the intercept as element 0."""
    X = np.column_stack([np.ones(len(y))] + cols)
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    yhat = X @ b; r2 = 1 - ((y-yhat)**2).sum()/((y-y.mean())**2).sum()
    se = se_ols(y, X, b)
    return b, se, r2

def wols(y, cols, wt):
    """Weighted least squares via the sqrt(weight) trick. Returns (b, se, r2) in the weighted metric."""
    X = np.column_stack([np.ones(len(y))] + cols)
    sw = np.sqrt(wt / wt.mean())
    Xw = X * sw[:, None]; yw = y * sw
    b = np.linalg.lstsq(Xw, yw, rcond=None)[0]
    yhat = X @ b
    ybar_w = (wt*y).sum()/wt.sum()
    ss_res = (wt*(y-yhat)**2).sum(); ss_tot = (wt*(y-ybar_w)**2).sum()
    r2 = 1 - ss_res/ss_tot
    se = se_ols(yw, Xw, b)
    return b, se, r2

def corr_ci(r, n):
    """Fisher z-transform 95% CI for a Pearson correlation r at sample size n."""
    if n <= 3 or abs(r) >= 1: return float("nan"), float("nan")
    zt = np.arctanh(r); se = 1/np.sqrt(n-3); zcrit = 1.959963984540054
    return float(np.tanh(zt - zcrit*se)), float(np.tanh(zt + zcrit*se))

# ---- Felten per-application exposure, aggregated to 6-digit SOC ----
mm = pd.read_excel(FEL/"mapping_matrix.xlsx", sheet_name="Combined")
abil = [c for c in mm.columns if c not in ("ability_id","abilities")]
Xrel = mm.set_index("abilities")[abil]; Xrel.index = Xrel.index.astype(str).str.strip()
on = pd.read_excel(FEL/"onet_skills_occupations.xlsx", sheet_name="Abilities")
on["ab"] = on["Element Name"].astype(str).str.strip().str.lower()
imp = on[on["Scale ID"]=="IM"].pivot_table(index="O*NET-SOC Code", columns="ab", values="Data Value")
lvl = on[on["Scale ID"]=="LV"].pivot_table(index="O*NET-SOC Code", columns="ab", values="Data Value")
common = [c.strip().lower() for c in abil if c.strip().lower() in imp.columns and c.strip().lower() in lvl.columns]
w = imp[common] * lvl[common]                                   # occ x ability  (importance x level)
Xc = Xrel.copy(); Xc.columns = [c.strip().lower() for c in Xc.columns]; Xc = Xc[common]
wsum = w.sum(axis=1).replace(0, np.nan)
app = pd.DataFrame(w.values @ Xc.values.T, index=w.index, columns=Xc.index).div(wsum.values, axis=0).dropna()
app["soc6"] = app.index.to_series().str[:7]
app6 = app.groupby("soc6").mean(numeric_only=True)             # SOC6 x 16 applications
aioe = app6.mean(axis=1).rename("aioe")                        # equal-weight ~ original AIOE
lm   = app6["language modeling"].rename("lm")

# ---- cognitive & manual ability indices (importance x level) ----
COG = ["oral comprehension","written comprehension","oral expression","written expression",
       "fluency of ideas","originality","deductive reasoning","inductive reasoning",
       "mathematical reasoning","information ordering"]
MAN = ["arm-hand steadiness","manual dexterity","finger dexterity","control precision",
       "multilimb coordination","static strength","gross body coordination"]
COG = [c for c in COG if c in w.columns]; MAN = [c for c in MAN if c in w.columns]
idx = pd.DataFrame({"cog": w[COG].mean(axis=1), "man": w[MAN].mean(axis=1)})
idx["soc6"] = idx.index.to_series().str[:7]
idx6 = idx.groupby("soc6").mean(numeric_only=True)

# ---- Autor-Dorn Routine Task Intensity (RTI), O*NET db 10.0 crosswalk ----
# Standard O*NET operationalization of Autor & Dorn (2013, AER) RTI: RTI = z(Routine) - z(NRC) - z(NRM).
# Direction of "Structured versus Unstructured Work" VERIFIED empirically (not assumed): Chief Executives (11-1011.00)
# score 4.75/5, near the scale maximum -> HIGH value = MORE unstructured/autonomous work, so this item is REVERSED
# when building the Routine component (routine = highly STRUCTURED work, i.e. low "unstructured" score).
wa = pd.read_csv(ONET/"Work Activities.txt", sep="\t")
wa["ab"] = wa["Element Name"].astype(str).str.strip().str.lower()
wa_im = wa[wa["Scale ID"]=="IM"].pivot_table(index="O*NET-SOC Code", columns="ab", values="Data Value")
wc = pd.read_csv(ONET/"Work Context.txt", sep="\t")
wc["ab"] = wc["Element Name"].astype(str).str.strip().str.lower()
wc_cx = wc[wc["Scale ID"]=="CX"].pivot_table(index="O*NET-SOC Code", columns="ab", values="Data Value")

NRC_ITEMS = ["analyzing data or information", "thinking creatively", "establishing and maintaining interpersonal relationships"]
NRM_ITEMS = ["operating vehicles, mechanized devices, or equipment"]
ROUTINE_ITEMS_CX = ["importance of repeating same tasks", "pace determined by speed of equipment"]
REVERSED_CX = ["structured versus unstructured work"]             # high value = MORE unstructured -> reverse for Routine

def zcol(df, name):
    s = df[name]
    return (s - s.mean()) / s.std()

nrc  = pd.concat([zcol(wa_im, c) for c in NRC_ITEMS if c in wa_im.columns], axis=1).mean(axis=1)
nrm  = pd.concat([zcol(wa_im, c) for c in NRM_ITEMS if c in wa_im.columns], axis=1).mean(axis=1)
rt_pos = pd.concat([zcol(wc_cx, c) for c in ROUTINE_ITEMS_CX if c in wc_cx.columns], axis=1)
rt_rev = pd.concat([-zcol(wc_cx, c) for c in REVERSED_CX if c in wc_cx.columns], axis=1)
routine = pd.concat([rt_pos, rt_rev], axis=1).mean(axis=1)

rti = pd.DataFrame({"rti": routine - nrc - nrm})
rti["soc6"] = rti.index.to_series().str[:7]
rti6 = rti.groupby("soc6").mean(numeric_only=True)["rti"]

# ---- Eloundou GPT-4 exposure (human_rating_beta), SOC6 ----
el = pd.read_csv(RAW/"eloundou"/"occ_level.csv")
el["soc6"] = el["O*NET-SOC Code"].astype(str).str[:7]
elo6 = el.groupby("soc6")["human_rating_beta"].mean().rename("elo")

# ---- Webb (2020) patent-based AI exposure (ai_score), SOC6 (a THIRD independently-built score:
# built from patent-text/O*NET-task overlap, a completely different methodology from AIOE's crowd-relatedness ratings
# and Eloundou's LLM/human task ratings). Source: Webb's own published data (final_df_out.dta, "Version 0.1"). ----
webb = pd.read_stata(RAW / "webb_2020" / "final_df_out.dta")
webb["soc6"] = webb["onetsoccode"].astype(str).str[:7]
webb6 = webb.groupby("soc6")["ai_score"].mean().rename("webb")
webb6_all = webb.groupby("soc6")[["ai_score","software_score","robot_score"]].mean()   # for the sub-score collinearity check (§5), SAME soc6 aggregation as everywhere else

# ---- OEWS panel (PROCESSED artifact, flagged, our own derived crosswalk, included in this repo): emp, wage level,
# 2013->2019 real-wage growth. See data/raw/README.md for how this was built + validated against published BLS OEWS.
pan = pd.read_parquet(RAW / "oews_processed" / "panel_crosswalked_lm_aioe.parquet",
                      columns=["soc_code","year","tot_emp","a_mean","log_wage_real"])
last = pan["year"].max()
emp  = pan[pan.year==last].groupby("soc_code")["tot_emp"].sum().rename("emp")
lwage= np.log(pan[pan.year==last].groupby("soc_code")["a_mean"].mean()).rename("lwage")
g13  = pan[pan.year==2013].groupby("soc_code")["log_wage_real"].mean()
g19  = pan[pan.year==2019].groupby("soc_code")["log_wage_real"].mean()
growth = (g19 - g13).rename("wage_growth_1319")               # pre-ChatGPT real-wage growth per occ

D = pd.concat([aioe, lm, elo6, webb6, idx6, rti6, emp, lwage, growth], axis=1)

R = {}
# R1: are the 16 application columns one factor?
A = app6.copy(); Zc = (A - A.mean())/A.std()
ev = np.linalg.svd(Zc.fillna(0).values, compute_uv=False)**2; ev = ev/ev.sum()
Cm = A.corr(); prs = np.array([Cm.iloc[i,j] for i,j in itertools.combinations(range(Cm.shape[0]),2)])
R["felten_apps_pc1_share"] = float(ev[0])
R["felten_apps_pc12_share"] = float(ev[:2].sum())
R["felten_apps_pair_share_r_gt_0p9"] = float((prs>0.9).mean())
R["felten_apps_pair_median_r"] = float(np.median(prs))
R["n_applications"] = int(A.shape[1])

# R1b: Webb (2020) sub-score collinearity (for §5) -- at the SAME soc6 aggregation as everywhere else in this script
webb_corr = webb6_all.corr()
webb_pairs = np.array([webb_corr.iloc[i,j] for i,j in itertools.combinations(range(webb_corr.shape[0]),2)])
R["webb_subscore_pair_r_lo"] = float(webb_pairs.min())
R["webb_subscore_pair_r_hi"] = float(webb_pairs.max())

# R2: what are the exposure scores? correlations (Pearson + Spearman + Fisher-z 95% CI on Pearson)
def corr(a,b):
    j = pd.concat([D[a],D[b]],axis=1).dropna()
    r = float(j.iloc[:,0].corr(j.iloc[:,1])); n = int(len(j))
    return r, n

def corr_full(a,b,key,R):
    j = pd.concat([D[a],D[b]],axis=1).dropna()
    r = float(j.iloc[:,0].corr(j.iloc[:,1])); n = int(len(j))
    rho = float(j.iloc[:,0].corr(j.iloc[:,1], method="spearman"))
    lo, hi = corr_ci(r, n)
    R[f"{key}"] = r; R[f"{key}_n"] = n; R[f"{key}_spearman"] = rho
    R[f"{key}_ci_lo"] = lo; R[f"{key}_ci_hi"] = hi
    return r, n

for s in ["aioe","lm","elo","webb"]:
    corr_full(s,"cog",f"{s}_corr_cognitive",R)
    corr_full(s,"man",f"{s}_corr_manual",R)
    corr_full(s,"lwage",f"{s}_corr_logwage",R)
corr_full("aioe","elo","aioe_corr_eloundou",R); R["n_aioe_eloundou"] = R["aioe_corr_eloundou_n"]
corr_full("aioe","webb","aioe_corr_webb",R)
corr_full("elo","webb","elo_corr_webb",R)
R["aioe_corr_manual_abs"] = abs(R["aioe_corr_manual"])

# R3: wage-LEVEL horse-race -- does the score survive controlling for cognitive content?
for s in ["aioe","elo"]:
    d = D[[s,"cog","lwage"]].dropna()
    b1,se1,r1 = ols(z(d["lwage"]).values, [z(d[s]).values])
    b2,se2,r2 = ols(z(d["lwage"]).values, [z(d[s]).values, z(d["cog"]).values])
    R[f"{s}_wagelevel_beta_alone"]      = float(b1[1]); R[f"{s}_wagelevel_se_alone"] = float(se1[1]); R[f"{s}_wagelevel_r2_alone"]=float(r1)
    R[f"{s}_wagelevel_beta_ctrl_cog"]   = float(b2[1]); R[f"{s}_wagelevel_se_ctrl_cog"] = float(se2[1])
    R[f"{s}_wagelevel_beta_cog"]        = float(b2[2]); R[f"{s}_wagelevel_se_cog"] = float(se2[2]); R[f"{s}_wagelevel_r2_ctrl"]=float(r2)
    R[f"{s}_wagelevel_n"]               = int(len(d))

# R3b: incremental R² and VIF for AIOE given cognitive content (for §3.3)
d_vif = D[["aioe","cog","lwage"]].dropna()
_,_, r2_cog_only = ols(z(d_vif["lwage"]).values, [z(d_vif["cog"]).values])
r2_full = R["aioe_wagelevel_r2_ctrl"]
R["r2_cog_only"]          = float(r2_cog_only)
R["r2_aioe_incremental"]  = float(r2_full - r2_cog_only)
_,_, r2_aioe_on_cog = ols(z(d_vif["aioe"]).values, [z(d_vif["cog"]).values])
R["vif_aioe_in_cog"]      = float(1 / (1 - r2_aioe_on_cog))

# R4: pre-ChatGPT real-wage GROWTH (2013->2019) horse-race
for s in ["aioe","elo"]:
    d = D[[s,"cog","wage_growth_1319"]].dropna()
    b1,se1,r1 = ols(z(d["wage_growth_1319"]).values, [z(d[s]).values])
    b2,se2,r2 = ols(z(d["wage_growth_1319"]).values, [z(d[s]).values, z(d["cog"]).values])
    R[f"{s}_pregrowth_beta_alone"]    = float(b1[1]); R[f"{s}_pregrowth_se_alone"] = float(se1[1]); R[f"{s}_pregrowth_r2_alone"]=float(r1)
    R[f"{s}_pregrowth_beta_ctrl_cog"] = float(b2[1]); R[f"{s}_pregrowth_se_ctrl_cog"] = float(se2[1])
    R[f"{s}_pregrowth_beta_cog"]      = float(b2[2]); R[f"{s}_pregrowth_r2_ctrl"] = float(r2)
    R[f"{s}_pregrowth_n"]             = int(len(d))

# R5: Autor-Dorn RTI horse-race -- is the homemade cognitive index just re-deriving Routine Task Intensity?
corr_full("rti","cog","rti_corr_cognitive",R)
corr_full("rti","man","rti_corr_manual",R)
for s in ["aioe","elo"]:
    corr_full(s,"rti",f"{s}_corr_rti",R)
corr_full("webb","rti","webb_corr_rti",R)   # completes the 6x6 correlation matrix (Figure 1)
corr_full("cog","man","cog_corr_man",R)     # completes the 6x6 correlation matrix (Figure 1)

for s in ["aioe","elo"]:
    d = D[[s,"rti","lwage"]].dropna()
    b1,se1,r1 = ols(z(d["lwage"]).values, [z(d[s]).values])
    b2,se2,r2 = ols(z(d["lwage"]).values, [z(d[s]).values, z(d["rti"]).values])
    R[f"{s}_wagelevel_beta_ctrl_rti"] = float(b2[1]); R[f"{s}_wagelevel_se_ctrl_rti"] = float(se2[1])
    R[f"{s}_wagelevel_beta_rti"] = float(b2[2]); R[f"{s}_wagelevel_r2_ctrl_rti"] = float(r2)
    R[f"{s}_wagelevel_rti_n"]         = int(len(d))

    d2 = D[[s,"rti","wage_growth_1319"]].dropna()
    b1,se1,r1 = ols(z(d2["wage_growth_1319"]).values, [z(d2[s]).values])
    b2,se2,r2 = ols(z(d2["wage_growth_1319"]).values, [z(d2[s]).values, z(d2["rti"]).values])
    R[f"{s}_pregrowth_beta_ctrl_rti"] = float(b2[1]); R[f"{s}_pregrowth_se_ctrl_rti"] = float(se2[1])
    R[f"{s}_pregrowth_beta_rti"] = float(b2[2])
    R[f"{s}_pregrowth_rti_n"]         = int(len(d2))

# R6: Webb (2020) as a THIRD independently-built score
d = D[["webb","cog","lwage"]].dropna()
b1,se1,r1 = ols(z(d["lwage"]).values, [z(d["webb"]).values])
b2,se2,r2 = ols(z(d["lwage"]).values, [z(d["webb"]).values, z(d["cog"]).values])
R["webb_wagelevel_beta_alone"] = float(b1[1]); R["webb_wagelevel_se_alone"] = float(se1[1]); R["webb_wagelevel_r2_alone"] = float(r1)
R["webb_wagelevel_beta_ctrl_cog"] = float(b2[1]); R["webb_wagelevel_se_ctrl_cog"] = float(se2[1])
R["webb_wagelevel_beta_cog"] = float(b2[2]); R["webb_wagelevel_r2_ctrl"] = float(r2)
R["webb_wagelevel_n"] = int(len(d))

d2 = D[["webb","cog","wage_growth_1319"]].dropna()
b1,se1,r1 = ols(z(d2["wage_growth_1319"]).values, [z(d2["webb"]).values])
b2,se2,r2 = ols(z(d2["wage_growth_1319"]).values, [z(d2["webb"]).values, z(d2["cog"]).values])
R["webb_pregrowth_beta_alone"] = float(b1[1]); R["webb_pregrowth_se_alone"] = float(se1[1]); R["webb_pregrowth_r2_alone"] = float(r1)
R["webb_pregrowth_beta_ctrl_cog"] = float(b2[1]); R["webb_pregrowth_se_ctrl_cog"] = float(se2[1])
R["webb_pregrowth_beta_cog"] = float(b2[2]); R["webb_pregrowth_r2_ctrl"] = float(r2)
R["webb_pregrowth_n"] = int(len(d2))

# R7: employment-weighted robustness
def wcorr(a, b, wcol):
    j = pd.concat([D[a], D[b], D[wcol]], axis=1).dropna()
    x, y, wt = j.iloc[:,0].values, j.iloc[:,1].values, j.iloc[:,2].values
    wt = wt / wt.sum()
    mx, my = (wt*x).sum(), (wt*y).sum()
    cov = (wt*(x-mx)*(y-my)).sum()
    vx, vy = (wt*(x-mx)**2).sum(), (wt*(y-my)**2).sum()
    return float(cov/np.sqrt(vx*vy)), int(len(j))

for s in ["aioe","elo"]:
    R[f"{s}_corr_cognitive_empwt"], _ = wcorr(s, "cog", "emp")
    R[f"{s}_corr_manual_empwt"], _    = wcorr(s, "man", "emp")

    d = D[[s,"cog","lwage","emp"]].dropna()
    b1,se1,r1 = wols(z(d["lwage"]).values, [z(d[s]).values], d["emp"].values)
    b2,se2,r2 = wols(z(d["lwage"]).values, [z(d[s]).values, z(d["cog"]).values], d["emp"].values)
    R[f"{s}_wagelevel_beta_alone_empwt"] = float(b1[1]); R[f"{s}_wagelevel_beta_ctrl_cog_empwt"] = float(b2[1])
    R[f"{s}_wagelevel_n_empwt"] = int(len(d))

    d2 = D[[s,"cog","wage_growth_1319","emp"]].dropna()
    b1,se1,r1 = wols(z(d2["wage_growth_1319"]).values, [z(d2[s]).values], d2["emp"].values)
    b2,se2,r2 = wols(z(d2["wage_growth_1319"]).values, [z(d2[s]).values, z(d2["cog"]).values], d2["emp"].values)
    R[f"{s}_pregrowth_beta_alone_empwt"] = float(b1[1]); R[f"{s}_pregrowth_beta_ctrl_cog_empwt"] = float(b2[1])
    R[f"{s}_pregrowth_n_empwt"] = int(len(d2))

meta = {"_meta": {
    "description": "Reproducible numbers for the AI-exposure measurement note.",
    "n_occupations_felten": int(app6.shape[0]),
    "oews_year_levels": int(last),
    "panel_note": "OEWS panel is a processed artifact (crosswalked to SOC6, merged with Felten/Eloundou coverage); validated via anchor checks against published BLS OEWS figures (benchmark occupation mean wages match to the dollar). See data/raw/README.md for provenance detail. Core result (R1/R2 cognitive/manual) uses only raw Felten+O*NET+Eloundou.",
    "abilities_in_cog_index": COG, "abilities_in_man_index": MAN,
    "rti_construction": "Autor-Dorn (2013, AER) style RTI = z(Routine) - z(NRC) - z(NRM), O*NET db 10.0 crosswalk: NRC = mean(z(Analyzing Data or Information), z(Thinking Creatively), z(Establishing and Maintaining Interpersonal Relationships)) [Work Activities, IM scale]; NRM = z(Operating Vehicles, Mechanized Devices, or Equipment) [Work Activities, IM scale]; Routine = mean(z(Importance of Repeating Same Tasks), z(Pace Determined by Speed of Equipment), -z(Structured versus Unstructured Work)) [Work Context, CX scale; last item reverse-coded, direction verified empirically against Chief Executives = 4.75/5].",
    "webb_source": "Webb (2020), 'The Impact of Artificial Intelligence on the Labor Market' (SSRN 3482150). ai_score from the author's own published data (final_df_out.dta, Version 0.1), keyed by onetsoccode, aggregated to SOC6 by simple mean.",
    "se_note": "Regression SEs are classical (homoskedastic) OLS standard errors on standardized (z-scored) variables; correlation CIs are Fisher z-transform 95% intervals. This is a descriptive note (N=656-773, large effect sizes); inference is reported for completeness, not as the basis of the claim.",
    "empwt_note": "empwt suffix = occupation-employment-weighted version (weight = total OEWS employment in the occupation), added as a robustness check alongside the unweighted headline numbers.",
}}
out = {**meta, **{k: round(v,4) if isinstance(v,float) else v for k,v in R.items()}}
(OUT/"note_results.json").write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=2))
