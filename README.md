# Do AI Occupational-Exposure Scores Measure AI?

Reproducibility package for: *"Do AI Occupational-Exposure Scores Measure AI? AIOE and Eloundou (2024) Largely
Capture Cognitive Content; Webb (2020) Does Not"* (Sudhanshu Rai, 2026).

**One-sentence finding:** the two most-used AI-exposure scores (AIOE, Eloundou et al.'s GPT-4 measure) are each
dominated by a single cognitive-ability factor rather than a distinct "AI" dimension, and their wage associations
collapse once cognitive content is controlled for, but a third, differently-built score (Webb 2020, patent-based)
does *not* share this problem, showing the confound is specific to how a score is constructed, not universal to
all AI-exposure measurement.

**Paper:** https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7062679
**Citation (code/data):** Rai, S. (2026). *ai-exposure-cognitive-content* (v1.0.0) [Code and data]. Zenodo. https://doi.org/10.5281/zenodo.21211349

## What's in this repo
```
analysis/
  note_analysis.py            # the entire analysis, start to finish -- every number in the paper traces to this file
data/
  raw/
    README.md                 # exactly where to get each third-party input (see below)
    verify_oews_benchmark.py  # independently spot-checks the processed OEWS panel against the raw BLS release
    bls_oes_raw/               # the raw BLS release used by the script above (public domain, bundled)
    oews_processed/            # the processed OEWS panel used by the main analysis (public-domain derived, bundled)
results/
  note_results.json      # the committed output of note_analysis.py -- every number cited in the paper
requirements.txt
LICENSE
```

## Reproducing the results
1. Get the raw inputs: see `data/raw/README.md` for exact sources and where each file goes. (Not bundled here;
   see that file for why.)
2. `python3 -m venv .venv && source .venv/bin/activate`
3. `pip install -r requirements.txt`
4. `python3 analysis/note_analysis.py`

**Optional, extra trust check:** the OEWS panel used above is a bundled, processed artifact rather than something
rebuilt from raw BLS files in this repo (see `data/raw/README.md` for why). Run
`python3 data/raw/verify_oews_benchmark.py` to independently confirm it against the actual raw BLS release for a
few benchmark occupations, no need to take the crosswalk on faith for at least those data points.

This regenerates `results/note_results.json` from scratch. It should be **byte-for-byte identical** to the
committed version in this repo; that's the actual reproducibility claim, not just an assertion.

## What this is NOT
This repo is the analysis code and its output, not a general-purpose package. It's released alongside the paper
specifically so every number in it can be independently checked.

## License
Code in this repo (`analysis/note_analysis.py`) is released under the MIT License (see `LICENSE`). Third-party raw
data referenced in `data/raw/README.md` remains under each original source's own terms; this repo does not
redistribute it directly except where explicitly noted.
