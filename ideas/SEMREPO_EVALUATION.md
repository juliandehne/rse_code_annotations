# The danger zone across SemRepo — AST scan at corpus scale

Detail for §9 of `PROPOSED_ANNOTATIONS.md`. This is a **design sketch, not built** — no
notebook parsing, no clone harness, no numbers. Captured so the evaluation is on record and
the code hooks are named before anyone starts.

The one-line thesis: *the same static scan that maps hazards in one study we understand can
be pointed at a whole corpus of research software we don't, and the per-repo
"reproducibility-critical" fraction it reports is a measurable "danger zone."*

---

## 1. Why the AST scanner is already the right instrument

Everything the corpus study needs is a property the scanner *already* has, by construction:

- **It imports nothing and executes nothing.** `scan_path` (`coverage.py:875`) parses each
  file with `ast.parse` and walks the tree; a file that cannot be imported — missing deps,
  half-finished, wrong Python version — still parses. On 197k strangers' repos, "can it
  import?" would be fatal; "can it parse?" is nearly always yes, and the few that don't land
  in `report.parse_errors` instead of crashing the run.
- **No network, no LLM, no VPN.** The hazard detectors are pure token/AST pattern matching
  (`_HUMAN_DATA_TOKENS`, `_SHELL_TOKENS`, `_MODEL_CALLS`, …). This is what makes a
  hundred-thousand-repo sweep tractable and, importantly, *reproducible by anyone* — the
  measurement itself has no `@model_call` or `@external_tool` hazard of its own.
- **The unit is already a distribution-ready number.** `CoverageReport.hazard_rate`
  (`coverage.py:365`) is "fraction of eligible functions that are a hazard rather than
  plumbing." One repo → one rate. That is exactly the per-observation value a corpus study
  aggregates. `lni_study` is one such observation (0.43); the corpus question is the *shape*
  of that variable across thousands.

Nothing in `scan_path` is `lni_study`-specific. It takes any directory root. The corpus study
is not a rebuild of the scanner — it is a **harness around an unchanged scanner** plus two
additions (notebook parsing; a `critical_rate` aggregate). That is the whole engineering
delta, and it is why this is worth doing rather than a from-scratch project.

---

## 2. The corpus: what SemRepo gives us

[SemRepo](https://github.com/faerber-lab/SemRepo) (Faerber Lab, TU Dresden; ISWC'26
submission) is an **RDF knowledge graph of ~197k GitHub repositories linked to scientific
publications**: per-repo contributors, issues, dependencies, languages, interlinked to
SemOpenAlex / LPWC / MLSea. Access is a public SPARQL endpoint (`semrepo.org/sparql`) plus
Zenodo dumps. Licence CC0 (data) / MIT (pipeline).

Two things it provides that a naive "scrape GitHub" cannot:

1. **A curated sampling frame.** Every repo is already established to be *research* software
   tied to a publication — so a hazard rate measured over it is a statement about research
   software specifically, not GitHub at large. It also lets us *stratify*: draw a sample by
   field of study, by declared dependency (does importing `torch` predict a higher
   `@model_call` density?), by repo size, by whether a paper cites back.
2. **Covariates for the regression.** The danger zone is only interesting if it *correlates*
   with something. SemRepo's metadata (deps, issue counts, contributor counts, publication
   venue) are the right-hand-side variables. The scan supplies the left-hand side.

The catch, and the single biggest work item, is language mix: **~95% Jupyter notebooks,
~5% Python**. The scanner is `.py`-only today. See §4.

---

## 3. Defining the "danger zone" precisely (pin before quoting any number)

"Danger zone" must be one pre-registered definition, decided before the first sweep, or the
number is unfalsifiable. Proposed default:

> **Danger zone of a repo = its reproducibility-critical rate = (functions carrying a
> *direct*, non-inherited provenance hazard) / (eligible functions).**

- *Direct provenance hazard* = the record's own `@model_call`, `@human_input`,
  `@external_tool`, `@stochastic`, or `@statistical` — exactly what `_critical_hazard`
  (`coverage.py:942`) already returns, and it already excludes `indirect` (propagated) hits.
  Propagation is what makes the *map* complete, but the danger-zone *count* must name the
  functions that actually do the dangerous thing, or every caller three layers up inflates it.
- Report **two** rates side by side, never one alone:
  - `hazard_rate` — all hazards incl. `@config`/`@validation`/`@human_decision` (the broad
    "not plumbing" surface).
  - `critical_rate` — provenance-only (the tight "an auditor cannot take this on trust"
    surface).
  `lni_study` = 0.43 / (36 of ~254). The corpus study reports the **distribution** of both:
  median, IQR, tail. "The median research repo has an X% danger zone" is the headline.
- **Denominator is `eligible` functions**, not all functions — dunders, nested closures and
  test helpers are already excluded (`FunctionRecord.eligible`). Keep it; changing the
  denominator mid-study is a validity hole.
- **Per-function, not per-line.** Simpler, already what the report exposes, and robust to
  formatting. A per-line variant can be a secondary metric, not the headline.

### 3a. The "assuming code was generated" framing

The hazards bite hardest when nobody wrote down the provenance — which is the default for
LLM-generated code shipped with light review: no recorded seed, no coder pool, no tool
version, no marker of which number is the reported statistic. Treating the corpus *as if*
generated reframes the danger-zone fraction as **"the share of this repo an auditor (or the
paper's own reviewer) would have to reconstruct provenance for by hand."** It also sets up the
framework's real pitch — *the post-hoc scan is exactly the checklist a generator should have
had to satisfy up front* — and it makes the metric field-agnostic: we are not claiming the
code *is* generated, we are measuring the surface that goes dark when it is.

---

## 4. The one real code gap: notebooks are AST too

95% of the corpus is `.ipynb`. A notebook is JSON; each code cell is a list of source lines.
The scanner's contract is "give me source, I'll `ast.parse` it," so notebooks fit the AST
model perfectly once normalised. Sketch:

- **New extractor** (e.g. `discovery._iter_notebook_sources(root)` alongside
  `_iter_python_files`, `discovery.py:111`): find `*.ipynb`, `json.load`, concatenate the
  `source` of every `cell_type == "code"` cell in order into one synthetic module string.
- **`scan_path` change** (`coverage.py:893`): today it loops `_iter_python_files` then
  `ast.parse(path.read_text())`. Generalise to iterate `(logical_name, source_text)` pairs so
  a notebook becomes one virtual module. Keep `parse_errors` behaviour for cells that don't
  parse.
- **Magics and shell lines are a feature, not just noise.** `%…` line/cell magics and `!…`
  shell escapes are not valid Python and must be stripped before `ast.parse` — *but* a `!`
  line is itself an `@external_tool` signal (the notebook shells out). So the extractor should
  **strip them from the source it hands the parser yet record them as pre-detected hazards**,
  rather than silently dropping evidence. `%%bash`/`%%script` cells likewise.
- **Line-number mapping.** After concatenation, `lineno` points into the synthetic module.
  Keep a cell-offset table so a hit maps back to `notebook.ipynb#cell-7:line-3` for the
  evidence column. Without it the locations are useless to a human.
- **Notebook-shaped false positives.** Top-level cell code is not a function; the scanner is
  function/method-centric. Decide whether bare top-level cell statements count (wrap each cell
  as an implicit `def _cell_N()`? or scan only real `def`s in notebooks?). This choice moves
  the denominator, so pin it in the §3 definition.

This is the only component that touches detector semantics. Everything else in §5 is plumbing.

---

## 5. The harness (a pipeline around the unchanged scanner)

Four stages. Each is ordinary batch code; none of it belongs *inside* the package — it is an
evaluation script (candidate home: `publications/rse_code_annotations/scripts/semrepo_sweep.py`,
mirroring the existing `scripts/demo_lni_testbed.py`).

1. **Frame** — SPARQL against `semrepo.org/sparql` (or a Zenodo dump for a frozen, citable
   snapshot — prefer the dump for reproducibility) to draw the sample: repo URL + covariates
   (field, deps, size, venue). Stratify per §2. Log the exact query and snapshot date.
2. **Fetch** — shallow-clone each sampled repo to scratch. Cap per-repo size; skip and log
   giants. This is I/O-bound, not the scanner — parallelise clones, but the scan stays CPU/AST.
3. **Scan** — `report = scan_path(repo_dir)` per repo, unchanged. Reduce to one row:
   `{repo, n_eligible, hazard_rate, critical_rate, counts_by_hazard, n_parse_errors,
   n_files, n_notebooks}`. Never keep full `FunctionRecord`s across the corpus — one summary
   row per repo, or memory dies at 197k.
4. **Aggregate** — the corpus statistics: distribution of `critical_rate` (median/IQR/tail),
   the per-hazard breakdown, and the covariate regressions. Emit a table + figures. Report
   **what was dropped** (unclonable, all-notebook-and-notebook-parsing-off, 0 eligible
   functions, parse-error-heavy) — silent attrition reads as coverage it didn't have.

New public surface needed on `CoverageReport` (tiny): a `critical_rate` property mirroring
`hazard_rate` (`coverage.py:365`) but counting `_critical_hazard(r) is not None` over
`eligible`. Right now the reproducibility-critical count lives only in the renderer; the
harness needs it as a number, not scraped from text.

---

## 6. Where each piece hooks in (file → change)

| Piece | Lives in | Change |
|---|---|---|
| `critical_rate` aggregate | `coverage.py` `CoverageReport` (~`:365`) | add property: `len([r for r in self.eligible if _critical_hazard(r)]) / len(self.eligible)` |
| `--exclude` glob (backups/vendored) | `coverage.py` `scan_path` + `_skip_file` (`:870`) / `discovery._iter_python_files` (`:111`) | accept an exclude-glob list; at corpus scale a `*.fix.py`/`*.prebak.py` skew is systematic, not cosmetic (already flagged in §8) |
| Notebook extraction | new `discovery._iter_notebook_sources`; `scan_path` loop (`:893`) generalised to `(name, source)` pairs | §4 — the only detector-semantic change |
| Magics/`!` handling | notebook extractor | strip before parse, but emit `@external_tool` for `!`/`%%bash` |
| Cell→line mapping | notebook extractor + `FunctionRecord.file`/`lineno` display | offset table for the evidence column |
| Corpus harness | new `scripts/semrepo_sweep.py` | SPARQL/dump → clone → `scan_path` → summary row → aggregate; **stays outside the package** |

---

## 7. Sequenced next steps (smallest first)

- [ ] **Add `critical_rate` to `CoverageReport`** + a unit test. One-line property, unblocks
      every downstream number. Trivial, do first.
- [ ] **Land the `--exclude` glob** (already owed from §8). Verify on `lni_study` that
      excluding the 3 backup modules moves the counts (254 → ~251 eligible).
- [ ] **Notebook extractor, offline, tested on a handful of real `.ipynb`.** This is the
      research-risky part — validate hit locations map back to the right cell before trusting
      any corpus number. Decide the top-level-cell denominator question (§4) here and record it.
- [ ] **Single-repo end-to-end** on one cloned SemRepo repo (one `.py`-heavy, one
      notebook-heavy) — prove `scan_path` → summary row works on a stranger's code.
- [ ] **Pin the danger-zone definition** (§3) in writing before any sweep. Pre-register.
- [ ] **Pilot sweep, N≈100 stratified repos**, from a frozen Zenodo dump (citable). Sanity
      the distribution; find the pathologies (all-notebook repos, 0-eligible repos, parse
      storms) on a small N before scaling.
- [ ] **Full sweep + regression** against SemRepo covariates; figures; attrition table.
- [ ] Only then: the write-up angle (RSE / reproducibility venue), separate from the
      habilitation like the rest of this package.

---

## 8. Threats to validity (what makes the number honest or not)

- **Notebook denominator.** If top-level cell code isn't counted, notebook-heavy repos look
  artificially clean (all the risky code is at module top level, not in `def`s). This could
  *invert* the finding. Must be resolved in §4, not hand-waved.
- **Detector precision at scale.** The detectors were tuned to zero direct false positives on
  *one* codebase (`lni_study`). Strangers' naming conventions will differ. Hand-audit a random
  sample of hits per hazard from the pilot; report precision, don't assume it transfers.
- **Selection.** SemRepo is publication-linked repos — already better-curated than GitHub
  median. The danger zone measured here is a **lower bound** on research software at large;
  say so.
- **"As if generated" is a framing, not a measurement.** We are not detecting generated code.
  The metric measures the provenance surface that goes dark *when* provenance isn't recorded;
  the generation angle motivates why that surface matters, and the paper must not overclaim it
  as evidence that the corpus *is* generated.
- **Snapshot drift.** Quote the Zenodo dump version + date; the SPARQL endpoint moves.

---

*Status: not started, not generating. Offline / no-LLM / no-network by construction — the
whole point is that the instrument carries none of the hazards it measures.*
