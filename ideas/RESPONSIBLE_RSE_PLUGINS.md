# Responsible RSE — proposed analyzer plugins

Status: research proposal, no code changed (2026-09-29). Companion to
`INSPECTION_COMPONENTS.md`, which already covers energy, privacy/PII detection,
determinism, test linkage, provenance run record, dependencies/lockfile/SBOM/pip-audit,
sample accounting (pandera), mutation testing, notebooks, numerical robustness, units,
basic FAIR/citation file presence (§2.12) and a first statistical-practice sketch (§2.13).
Nothing below repeats those; where a plugin *extends* one of them, the section says so.

Every plugin is an `Analyzer` subclass (`name`, `when`, `available()`,
`analyze(target) -> AnalysisResult` with `Finding(severity, location, message, evidence)`),
registered under the entry-point group `rse_annotations.analyzers`. All plugins must
degrade to `available() == False` when their optional dependency is missing, and every
network-dependent part is `when="ci"` only, so the default run stays offline and LLM-free.

"Responsible" here means four things the existing reproducibility core does not ask:
**may** this code and data be reused (licences, consent, purpose), **is it fair and honest**
(bias, leakage, forking paths, silent failures), **is it safe** (security, dual use), and
**is it inclusive and sustainable** (accessibility, language, archiving, footprint).

## 1. Summary

| # | Analyzer | when | Detects (short) | Main tools (offline? / licence) | Hooks | Effort | Tier |
|---|---|---|---|---|---|---|---|
| 1 | `LicenceComplianceAnalyzer` | static | per-file SPDX/REUSE gaps; outbound licence incompatible with dependency or vendored-code licences | reuse (offline, GPL-3.0+ CLI), license-expression (Apache-2.0), scancode-toolkit (offline, Apache-2.0) | project; `@external_tool` binaries | S–M | **A** |
| 2 | `SilentFailureAnalyzer` | static | swallowed exceptions, `errors="coerce"`, suppressed warnings, uncounted `dropna` in annotated code | ruff S110/BLE001/E722 (offline, MIT) + own AST | `@data_input`, `@mapping`, `@unit_of_analysis`, `@statistical` | S | **A** |
| 3 | `UnjustifiedConstantAnalyzer` | static | magic numbers/thresholds in decision logic not routed through `@config` and without a rationale | ruff PLR2004 (MIT) + own AST | `@unit_of_analysis`, `@statistical`, `@mapping`, `@config` | S | **A** |
| 4 | `LLMDisclosureAnalyzer` | static | unpinned model aliases, implicit sampling params, inline unversioned prompts, missing LLM-usage statement | own AST; checklist from llm-guidelines.org, TRIPOD-LLM | `@model_call` | S | **A** |
| 5 | `ResearchSecurityAnalyzer` | static (+ci) | unsafe deserialisation of inputs, shell injection in tool calls, `eval` of model output; known-vulnerable deps offline | Bandit (offline, Apache-2.0), osv-scanner offline DB (Apache-2.0) | `@data_input`, `@external_tool`, `@model_call` | S | **A** |
| 6 | `DataTermsAnalyzer` | static | `@data_input` without licence/source/consent basis; published `@data_output` without datasheet / data statement / model card | mlcroissant incl. RAI (offline, Apache-2.0), huggingface_hub `ModelCard` (Apache-2.0) | `@data_input`, `@human_input`, `@data_output` | M | **A** |
| 7 | `DataLeakageAnalyzer` | static + test | train/test contamination: preprocessing fit before split, overlap, test set reused for selection | leakage-analysis (MIT; Py3.8 + Soufflé, heavy), own AST subset; runtime hash overlap | `@stochastic` splits, `@statistical`, `@unit_of_analysis` | M | **B** |
| 8 | `InferenceLedgerAnalyzer` | runtime + static | forking paths: number of hypothesis tests actually run, missing correction, p without effect size/CI, statcheck-style inconsistencies | statsmodels `multipletests` (BSD-3), scipy; statcheck (R, GPL-3) as model | `@statistical` | M | **B** |
| 9 | `FairnessAnalyzer` | test / runtime | disaggregated error/selection rates across declared sensitive attributes; protected attributes used as features | fairlearn (offline, MIT), aequitas (offline, MIT) | `@statistical`, `@model_call` outputs, `@data_output` | M | **B** |
| 10 | `PurposeRetentionAnalyzer` | static | personal data without declared purpose/legal basis/retention; persisted without deletion or pseudonymisation; draft Art. 30 record | own; consumes `personal_data` hazard from privacy component | `@data_input`, `@data_output`, `personal_data` | S–M | **B** |
| 11 | `FigureAccessibilityAnalyzer` | static + runtime | rainbow/red-green colormaps, colour-only encoding, CVD-indistinguishable series, tiny fonts, figures without alt text | colorspacious (MIT), daltonlens (BSD-2) — offline | `@data_output` (figures) | M | **B** |
| 12 | `ComputeFootprintAnalyzer` | runtime | CO₂e of LLM API calls (not measurable locally) + Green-Algorithms-style disclosure incl. PUE, grid, embodied | EcoLogits (offline estimation, MPL-2.0), Green Algorithms formula (CC-BY-4.0) | `@model_call`, run level | S | **B** |
| 13 | `ArchivalSustainabilityAnalyzer` | static + ci | cited version not archived/identifiable (SWHID, DOI↔tag mismatch); truck factor; OpenSSF Scorecard | swh.model `swh identify` (offline, GPL-3.0), truckfactor (offline, GPL-3.0), Scorecard (network, Apache-2.0) | project; `@external_tool` | S–M | **C** |
| 14 | `InclusiveLanguageAnalyzer` | static | non-inclusive terms in identifiers/docs; binary-only or deficit-framed categories in codebooks | woke (Go CLI, MIT), alex (Node, MIT), own list | `@human_input` codebooks, all docs | S | **C** |
| 15 | `DualUseScreeningAnalyzer` | static | prompts a human screen when code touches dual-use or AI-Act high-risk areas (crypto, intrusion, surveillance, biometrics, pathogen design) | none fit → own keyword/import map; verdict in `inspection.yaml` | project; `@model_call`, `@data_input` | S | **C** |
| 16 | `LLMEvaluationAnalyzer` | static | LLM step inside the pipeline (not generated code) whose output is used without an evaluation, or evaluated with a metric that does not fit the problem type | own AST; metric calls from scikit-learn (BSD-3), evaluate (Apache-2.0), sacrebleu (Apache-2.0); metric map from Hou et al. 2024 | `@model_call`, `@human_input` | M | **B** |

Tier A: cheap, static, offline, high signal and directly tied to existing hazards. Tier B:
more value but needs a runtime hook, a declared attribute, or domain calibration. Tier C:
useful for completeness/community credibility, weaker validity payoff or high false-positive risk.

### Difficulty (student workload) and EVERSE anchors

`difficulty` is a class attribute on every stub (default 3 in `_stub.py`): 1–5 ≈ 1–5 hours
per week over a ~12–14-week semester to implement the check at a reasonable level *with
tests*. The EVERSE mapping (dimensions, indicators, RSQKit tasks, gap ideas) is in
[`EVERSE_MAPPING.md`](EVERSE_MAPPING.md).

| # | Stub | EVERSE anchor | Diff. | Rationale |
|---|---|---|---|---|
| 1 | `LicenceComplianceAnalyzer` | [software_has_license_for_file_types](https://w3id.org/everse/i/indicators/software_has_license_for_file_types), [RSQKit licensing](https://everse.software/RSQKit/licensing_software) | 3 | REUSE/SPDX off the shelf; dependency licences + compatibility table need design |
| 2 | `SilentFailureAnalyzer` | [has_no_linting_issues](https://w3id.org/everse/i/indicators/has_no_linting_issues) | 2 | AST on a fixed pattern list |
| 3 | `UnjustifiedConstantAnalyzer` | [functional_correctness](https://w3id.org/everse/i/indicators/functional_correctness) | 2 | AST + comment lookup; effort in the whitelist |
| 4 | `LLMDisclosureAnalyzer` | [RSQKit AI guidance](https://everse.software/RSQKit/ai) (adjacent) | 2 | static checks on `model_call` records + template |
| 5 | `ResearchSecurityAnalyzer` | [static_analysis_common_vulnerabilities](https://w3id.org/everse/i/indicators/static_analysis_common_vulnerabilities), [RSQKit security](https://everse.software/RSQKit/research_software_security) | 2 | Bandit/osv-scanner detect; work is filtering |
| 6 | `DataTermsAnalyzer` | none (EVERSE gap) | 3 | new kwargs, licence propagation, Croissant |
| 7 | `DataLeakageAnalyzer` | [functional_correctness](https://w3id.org/everse/i/indicators/functional_correctness) | 4 | dataflow + runtime hashing mode |
| 8 | `InferenceLedgerAnalyzer` | [functional_correctness](https://w3id.org/everse/i/indicators/functional_correctness) | 5 | runtime instrumentation of 3 libraries + recomputation |
| 9 | `FairnessAnalyzer` | none (EVERSE "fairness" = FAIRness) | 3 | fairlearn computes; capture of predictions needs design |
| 10 | `PurposeRetentionAnalyzer` | none | 3 | needs `personal_data` hazard; careful GDPR reading |
| 11 | `FigureAccessibilityAnalyzer` | dim. [interaction_capability](https://w3id.org/everse/i/dimensions/interaction_capability) | 3 | savefig hook + CVD simulation + visual fixtures |
| 12 | `ComputeFootprintAnalyzer` | [RSQKit env. sustainability](https://everse.software/RSQKit/improving_environmental_sustainability) | 2 | EcoLogits estimates; hooking + disclosure text |
| 13 | `ArchivalSustainabilityAnalyzer` | [archived_in_software_heritage](https://w3id.org/everse/i/indicators/archived_in_software_heritage), [RSQKit archiving](https://everse.software/RSQKit/archiving_software) | 3 | several sub-checks + network mocking |
| 14 | `InclusiveLanguageAnalyzer` | dim. [community](https://w3id.org/everse/i/dimensions/community) | 1 | rules file, `info` only |
| 15 | `DualUseScreeningAnalyzer` | dim. [safety](https://w3id.org/everse/i/dimensions/safety) | 2 | code is small; the keyword map is the work |
| 16 | `LLMEvaluationAnalyzer` | [functional_correctness](https://w3id.org/everse/i/indicators/functional_correctness) (adjacent; EVERSE gap) | 3 | metric map given; the work is following a model-call output to a metric call |

## 2. Plugins

### 2.1 `LicenceComplianceAnalyzer` (static, S–M, Tier A)

**Detects.** Files without `SPDX-License-Identifier`/copyright (REUSE spec); a missing or
non-SPDX project licence; *incompatibility* between the outbound licence and (a) the
licences of declared dependencies, (b) vendored/copied code (e.g. a GPL snippet in an MIT
package), (c) `@external_tool` binaries that are bundled rather than called. §2.4 of
INSPECTION_COMPONENTS only lists licences (pip-licenses); this adds the compatibility
judgement and per-file coverage. FAIR4RS R1.1 ("clear and accessible licence").
**Tools.** `reuse lint` (FSFE, GPL-3.0-or-later, offline; call as subprocess to keep the
package licence clean); `license-expression` (Apache-2.0) to parse SPDX expressions;
`scancode-toolkit` (Apache-2.0, offline, heavy) optional for detecting licence text in
vendored files; a small compatibility table seeded from the OSADL matrix (`matrix.json`,
published with the OSADL raw data under CC-BY-4.0 — attribute OSADL when bundling it;
https://www.osadl.org/Access-to-raw-data.oss-compliance-raw-data-access.0.html). **Finding example.** `ERROR pyproject: MIT outbound, depends on
GPL-3.0-only 'foo' — distribution as MIT is not possible if foo is bundled`.

### 2.2 `SilentFailureAnalyzer` (static, S, Tier A)

**Detects**, inside annotated functions only: `except: pass`, `except Exception: continue`
without logging or a counter; `pd.to_numeric(..., errors="coerce")`,
`pd.read_csv(on_bad_lines="skip")`, `warnings.filterwarnings("ignore")`,
`np.seterr(all="ignore")`, `dropna()`/`drop_duplicates()` whose row delta is not recorded.
Each silently changes the sample or the numbers — a research-integrity issue, not style.
**Hooks.** Severity rises with the hazard: `ERROR` in `@unit_of_analysis` and
`@statistical`, `WARN` in `@data_input`. Suggests the sample-accounting counter (§2.6 of
INSPECTION_COMPONENTS) as the fix. **Tools.** ruff rules S110, BLE001, E722 (MIT, offline)
can be run on the annotated file set; the pandas/numpy patterns need own AST visitors
(~150 lines, reusing `coverage.py`'s walker).

### 2.3 `UnjustifiedConstantAnalyzer` (static, S, Tier A)

**Detects** numeric literals in comparisons, slicing, `quantile`, `head(n)`, `sample(frac=)`
and filter masks inside `@unit_of_analysis`, `@statistical` and `@mapping` that are (a) not
a parameter with a `@config` default, and (b) lack a justification (inline comment,
`cites=`, or a `rationale=` kwarg the plugin proposes for `@config`). Whitelist 0, 1, −1, 2
and array axes. Broader than §2.13's "hard-coded 0.05": exclusion cut-offs (`age > 17`,
`n_tokens < 50`) are where researcher degrees of freedom hide. **Tools.** ruff PLR2004
(`magic-value-comparison`) as a baseline; own AST for the non-comparison positions.
**Output** also lists every such constant as a candidate `@config`, feeding the provenance
record.

### 2.4 `LLMDisclosureAnalyzer` (static, S, Tier A)

**Detects** in `@model_call` sites: model given as a moving alias (`"gpt-4o"`,
`"claude-sonnet-latest"`, Ollama tag without digest) instead of a dated snapshot;
`temperature`/`top_p`/`seed`/`max_tokens` left implicit; system/user prompt built from
inline f-strings rather than a versioned prompt file; no local open-weight baseline; no
human-validation link (`@model_call` output never reaches a `@human_input` comparison or an
agreement metric); missing "LLM use" statement in README/paper sources. Complements the
provenance record (§2.3), which logs what happened at runtime; this checks what *can*
be disclosed before any run. **Grounding.** Wagner et al., *Guidelines for Empirical
Studies in SE involving LLMs* (llm-guidelines.org: declare role, report version and
configuration, document prompts, include an open model, validate against humans);
TRIPOD-LLM (Nature Medicine 2025); the 2026 Nature Human Behaviour reporting checklist.
**Output.** A pre-filled disclosure paragraph (model, version, parameters, prompt file
hashes, role in the pipeline) the author edits — no LLM involved.

### 2.5 `ResearchSecurityAnalyzer` (static, optional ci, S, Tier A)

Research-specific slice of security, not a general SAST. **Detects**: `pickle.load`,
`joblib.load`, `torch.load(weights_only=False)`, `yaml.load` without SafeLoader,
`np.load(allow_pickle=True)` on `@data_input` paths (downloaded models/datasets execute
code); `subprocess(..., shell=True)` or string-concatenated argv in `@external_tool`;
`eval`/`exec` on anything reachable from a `@model_call` return value (prompt-injection to
code execution); `verify=False` on data downloads. §2.5 of INSPECTION_COMPONENTS uses
Bandit only for secrets; this uses its B301/B506/B602/B307/B501 families, filtered to
hazard-annotated code so the output stays short. **Tools.** Bandit (Apache-2.0, offline);
osv-scanner (Apache-2.0) has an official offline mode with a locally cached PyPI database,
which makes the vulnerability check of §2.4 usable offline when the DB is pre-fetched
(`when="ci"` otherwise).

### 2.6 `DataTermsAnalyzer` (static, M, Tier A)

**Inbound.** Every `@data_input` / `@human_input` should declare `source=`, `license=`
(SPDX or URL) and, for data about people, `consent=`/`legal_basis=`. Findings: missing
terms; licence forbids the use (NC licence in a commercial project, ND on a transformed
output, "research only" corpora re-published by a `@data_output`); scraped sources
(`requests.get` / `BeautifulSoup` inside `@data_input`) without a terms-of-service note.
**Outbound.** A `@data_output` that is published (declared `publish=True` or written under
a release dir) needs a datasheet (Gebru et al.), data statement (Bender & Friedman) or a
Croissant file with the RAI extension; a trained model saved via `save_pretrained`/
`joblib.dump` needs a model card (Mitchell et al.). **Tools.** `mlcroissant` (MLCommons,
Apache-2.0, offline validation of Croissant + RAI fields); `huggingface_hub.ModelCard`
(Apache-2.0) to validate/scaffold cards. Licence propagation reuses the dataflow graph:
the most restrictive input licence is propagated to each `@data_output`, the same way
provenance hazards are pushed up the call graph today.

### 2.7 `DataLeakageAnalyzer` (static + test, M, Tier B)

**Detects** the three leakage kinds of Yang et al. (ASE 2022): *preprocessing* leakage
(`fit`/`fit_transform` of scalers, imputers, vectorisers, feature selection on data before
`train_test_split`); *overlap* (same rows in train and test, e.g. after augmentation or
duplicate records); *multi-test* (the test set is evaluated repeatedly inside model
selection). Also: group leakage (same subject/author in both splits — relevant for
`@unit_of_analysis`) and temporal leakage (random split on time-stamped data). **Test
mode:** hash rows of the actual splits and report overlap. **Tools.** `leakage-analysis`
(MIT) is the reference, but it needs Python 3.8, Soufflé and a patched pyright — too heavy
to depend on; implement the preprocessing-before-split pattern in own AST first and treat
the tool as an optional external backend. LeakageDetector 2.0 (2025) is the follow-up.

### 2.8 `InferenceLedgerAnalyzer` (runtime + static, M, Tier B)

Extends §2.13 of INSPECTION_COMPONENTS from static guessing to a **runtime ledger**, which
avoids its false-positive problem. During a run, wrap `scipy.stats` / `statsmodels` /
`pingouin` test functions (import hook, only when enabled) and record every test executed,
its statistic, df, p, and the calling `@statistical` function. **Findings**: k tests on the
same outcome without `multipletests`/FDR; p reported without an effect size and CI in the
same `@data_output`; count of tests run vs tests reported (garden of forking paths);
statcheck-style consistency: recompute p from statistic and df and compare with the value
written to output tables. Static part: optional-stopping patterns (test inside a loop that
breaks on `p < alpha`). **Tools.** statsmodels (BSD-3), scipy (BSD-3); statcheck (R, GPL-3)
as the methodological model only.

### 2.9 `FairnessAnalyzer` (test/runtime, M, Tier B)

**Detects**, only when the author declares `sensitive=["gender", ...]` on a
`@data_input` or `@statistical`: disaggregated performance (accuracy, FPR/FNR, selection
rate) and the largest between-group gap, via `fairlearn.metrics.MetricFrame`; group sizes
too small to estimate a rate. Also applies to `@model_call` annotation pipelines: agreement
of LLM labels with human gold per subgroup (does the model code one group worse?). Static
part: protected-attribute-like columns used as model features without a declaration.
**Tools.** fairlearn (MIT, 0.14, offline), aequitas (MIT, offline) for a bias report.
Reports numbers and gaps; it never judges which fairness definition applies — that goes
to a human verdict in `inspection.yaml`.

### 2.10 `PurposeRetentionAnalyzer` (static, S–M, Tier B)

Builds on the `personal_data` hazard of the privacy component (§2.5 there) rather than
re-detecting PII. **Detects**: personal-data `@data_input` without `purpose=`,
`legal_basis=` (GDPR Art. 6/9) and `retention=`; flows of personal data into a
`@data_output` whose declared purpose differs (purpose limitation, Art. 5(1)(b)); personal
data persisted without pseudonymisation or a deletion step (storage limitation, Art.
5(1)(e)); special-category fields (health, ethnicity) without an Art. 9 basis. **Output**:
a draft record of processing activities (Art. 30) in Markdown/YAML for the data-protection
officer — a genuinely useful artefact for ethics-board applications.

### 2.11 `FigureAccessibilityAnalyzer` (static + runtime, M, Tier B)

**Static**: `cmap="jet"|"rainbow"|"hsv"`, explicit red/green colour pairs, legends that
distinguish series only by colour (no marker/linestyle). **Runtime**: hook
`Figure.savefig` in `@data_output` functions; simulate deuteranopia/protanopia/tritanopia
with daltonlens (BSD-2) and compute pairwise CIEDE2000/CAM02-UCS distances between series
colours with colorspacious (MIT); flag pairs below a threshold, fonts below ~8 pt at saved
size, and figures without an alt-text/caption entry (e.g. a `alt=` kwarg or Quarto
`fig-alt`). Offline throughout.

### 2.12 `ComputeFootprintAnalyzer` (runtime, S, Tier B)

The energy component (§2.8 there) measures local energy and marks `@model_call` as "not
measurable locally". This plugin closes that gap and produces a *disclosure*: EcoLogits
(started by GenAI Impact, now maintained under `mlco2/ecologits`, MPL-2.0) estimates energy, GWP and abiotic depletion per API call from
model, token counts and latency — fully offline: ecologits 0.11.2 (MPL-2.0) loads its
bundled `models.json` / `electricity_mixes.json` and imports no HTTP client; only the
separate EcoLogits web calculator and API are online services; plus a Green Algorithms-style statement (runtime × cores
× TDP × PUE × grid intensity, incl. embodied share) with explicit uncertainty. Output: a
short "computational footprint" paragraph for the paper.

### 2.13 `ArchivalSustainabilityAnalyzer` (static + ci, S–M, Tier C)

§2.12 of INSPECTION_COMPONENTS checks that CITATION.cff/DOI exist; this checks that they
**identify the code that produced the results**. Offline: compute the SWHID of the working
tree / release (`swh identify`, swh.model, GPL-3.0; SWHID is ISO 18670 since 2025); compare
`CITATION.cff` `version`/`date-released` with the latest git tag and with the commit in the
provenance record; dirty tree at release. Truck factor from `git log` (truckfactor,
GPL-3.0, offline) as a sustainability risk. CI only: is that SWHID archived on Software
Heritage, does the Zenodo DOI resolve to the same version, OpenSSF Scorecard
(Apache-2.0, GitHub API) for maintenance/branch-protection signals. FAIR4RS F1/A1/R1.2.

### 2.14 `InclusiveLanguageAnalyzer` (static, S, Tier C)

Scans identifiers, comments, docstrings and docs with a ruleset in the style of woke (MIT)
and alex (MIT) / inclusivenaming.org (`master/slave`, `whitelist`, `sanity check`, ...).
Research-specific addition: codebooks and category definitions read by `@human_input`
(e.g. gender coded as a binary 0/1 without "other/not stated", deficit framing in labels)
— a data-validity issue as much as a language one. Calling woke/alex needs Go/Node, so a
pure-Python rules file is preferable. High false-positive risk → `INFO` severity only.

### 2.15 `DualUseScreeningAnalyzer` (static, S, Tier C)

Not a classifier — a **prompt for a human screen**. An import/keyword map flags areas
covered by EU Regulation 2021/821 Annex I (cryptography, intrusion software, surveillance
/ interception) and AI-Act-sensitive uses (biometric identification, emotion recognition,
social scoring), plus biosecurity (pathogen/protein design). The finding asks the author to
record a verdict in `inspection.yaml`: "not listed", "basic scientific research" or "public
domain" (the Regulation's exemptions), or "needs export-control review". Grounding:
EU Recommendation 2021/1700 on research ICPs. Keeping it as a human verdict avoids pretending
a regex can make a legal call.

### 2.16 `LLMEvaluationAnalyzer` (static, M, Tier B)

**Scope.** An LLM as *part of the computation* of the research software: it classifies,
extracts, ranks, scores or generates on the way to a result. This is a different topic
from LLM-generated source code (covered by `human_code_inspection`) and from disclosure
(§2.4, which asks whether the LLM use *can be reported*). This plugin asks **how the LLM
step was evaluated**.

**Detects** per `@model_call` site, after establishing the problem type of the step
(declared, e.g. `problem_type="classification"`, or asked in an inspection): output
reaches a `@data_output` or a `@statistical` function with no evaluation metric on the
path; a metric from the wrong family for the problem type; `accuracy` as the only metric
of a classification step (blind to class imbalance); only lexical overlap (BLEU, ROUGE)
for a generation step, with no execution-based (Pass@k) or human check; a metric computed
without a human-labelled reference (no `@human_input` on the path); a metric computed but
never written to an output.

**Metric map (starting point).** Evaluation metrics reported per problem type in the
LLM4SE literature, with the number of studies, from Hou et al. (2024), *Large Language
Models for Software Engineering: A Systematic Literature Review*, ACM TOSEM 33(8),
doi:10.1145/3695988. It shows what is customary in software engineering, not what is
correct in every discipline; the plugin should load the map from a rules file.

| Problem type | Metrics (studies) | Total |
|---|---|---|
| Regression | MAE (1) | 1 |
| Classification | Precision (35), Recall (34), F1-score (33), Accuracy (23), AUC (9), ROC (4), FPR (4), FNR (3), MCC (2) | 147 |
| Recommendation | MRR (15), Precision/Precision@k (6), MAP/MAP@k (6), F-score/F-score@k (5), Recall/Recall@k (4), Accuracy (3) | 39 |
| Generation | BLEU/BLEU-4/BLEU-DC (62), Pass@k (54), Accuracy/Accuracy@k (39), EM (36), CodeBLEU (29), ROUGE/ROUGE-L (22), Precision (18), METEOR (16), Recall (15), F1-score (15), MRR (6), ES (6), ED (5), MAR (4), ChrF (3), CrystalBLEU (3), CodeBERTScore (2), MFR (1), PP (1) | 338 |

**Output.** Per LLM step: problem type, metrics found, reference data used, and a
finding where one of the above is missing. **Open question for the student:** which
metric families count as fitting outside SE (e.g. agreement coefficients for LLM-coded
qualitative data), and how to cite the evidence for that choice.

## 3. How they fit the existing model

- **New decorator kwargs, not new decorators**: `license=`, `source=`, `consent=`,
  `purpose=`, `retention=`, `sensitive=`, `publish=`, `rationale=`, `alt=`. The analyzers
  warn when they are missing; nothing is enforced.
- **New hazards** worth adding to `HAZARDS`: `personal_data` (from the privacy component,
  consumed by #10), `ml_split` (train/test split, #7) and `hypothesis_test` (#8), all
  specialising `@statistical`/`@unit_of_analysis`.
- **Propagation**: licences (#6) and personal data (#10) propagate along dataflow edges the
  way provenance hazards already do.
- **Human verdicts**: fairness definition (#9), dual use (#15) and licence edge cases (#1)
  end in `inspection.yaml` verdicts, keeping the tool a reviewer's aid, not a judge.
- **Report section**: a "Responsible RSE" block in the Markdown report grouping these
  findings by the four questions (may / fair and honest / safe / inclusive and sustainable).

## 4. Suggested order

1. #2 SilentFailure, #3 UnjustifiedConstant — pure AST, reuse the existing walker, days.
2. #4 LLMDisclosure, #5 ResearchSecurity — small, high relevance to the AI-assisted-study use case.
3. #1 LicenceCompliance, #6 DataTerms — introduce the kwargs and licence propagation.
4. #8 InferenceLedger and #7 DataLeakage — the strongest *validity* additions; need runtime hooks.
5. #9–#12, then Tier C.

## 5. Sources

- FAIR4RS: Barker et al., *Introducing the FAIR Principles for research software*, Sci Data 9:622 (2022) — https://www.nature.com/articles/s41597-022-01710-x ; ReSA summary https://www.researchsoft.org/blog/2022-08/
- REUSE tool — https://codeberg.org/fsfe/reuse-tool , docs https://reuse.readthedocs.io/en/latest/readme.html
- scancode-toolkit — https://github.com/aboutcode-org/scancode-toolkit ; license-expression — https://github.com/aboutcode-org/license-expression
- OpenSSF Scorecard — https://github.com/ossf/scorecard , checks https://github.com/ossf/scorecard/blob/main/docs/checks.md
- Software Heritage SWHID — https://docs.softwareheritage.org/devel/swh-model/persistent-identifiers.html , swh-model https://github.com/SoftwareHeritage/swh-model
- truckfactor — https://github.com/HelgeCPH/truckfactor ; Avelino et al., *A Novel Approach for Estimating Truck Factors* https://arxiv.org/abs/1604.06766
- Bandit — https://github.com/PyCQA/bandit ; OSV-Scanner offline mode — https://google.github.io/osv-scanner/usage/offline-mode/
- Ruff rules: blind-except https://docs.astral.sh/ruff/rules/blind-except/ , S110, PLR2004 (https://docs.astral.sh/ruff/rules/)
- Yang et al., *Data Leakage in Notebooks: Static Detection and Better Processes*, ASE 2022 — https://arxiv.org/abs/2209.03345 , tool https://github.com/malusamayo/leakage-analysis ; LeakageDetector 2.0 https://arxiv.org/html/2509.15971
- statcheck — https://github.com/MicheleNuijten/statcheck ; statsmodels multipletests — https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html
- Fairlearn — https://github.com/fairlearn/fairlearn ; Aequitas — https://github.com/dssg/aequitas
- Croissant and Croissant RAI — https://docs.mlcommons.org/croissant/docs/croissant-rai-spec.html , https://github.com/mlcommons/croissant
- Gebru et al., *Datasheets for Datasets* https://arxiv.org/abs/1803.09010 ; Bender & Friedman, *Data Statements for NLP* https://aclanthology.org/Q18-1041/ ; Mitchell et al., *Model Cards for Model Reporting* https://arxiv.org/abs/1810.03993 ; HF model cards https://huggingface.co/docs/hub/model-cards
- LLM reporting: Wagner et al., *Guidelines for Empirical Studies in SE involving LLMs* https://arxiv.org/abs/2508.15503 , https://llm-guidelines.org/ ; TRIPOD-LLM https://www.nature.com/articles/s41591-024-03425-5 ; reporting checklist for LLMs in behavioural science https://www.nature.com/articles/s41562-026-02492-7
- EcoLogits — https://github.com/mlco2/ecologits ; Green Algorithms — https://www.green-algorithms.org/
- Colour vision: colorspacious https://github.com/njsmith/colorspacious ; DaltonLens https://github.com/DaltonLens/DaltonLens-Python ; Matplotlib colormap guidance https://matplotlib.org/stable/users/explain/colors/colormaps.html
- Inclusive language: woke https://github.com/get-woke/woke ; alex https://github.com/get-alex/alex ; Inclusive Naming Initiative https://inclusivenaming.org/
- GDPR (Reg. 2016/679) Art. 5, 6, 9, 30 — https://eur-lex.europa.eu/eli/reg/2016/679/oj
- EU Dual-Use Regulation 2021/821 — https://eur-lex.europa.eu/eli/reg/2021/821/oj/eng ; Recommendation (EU) 2021/1700 on research ICPs — https://eur-lex.europa.eu/eli/reco/2021/1700/oj ; EU AI Act 2024/1689 — https://eur-lex.europa.eu/eli/reg/2024/1689/oj

Items marked **[unverified]** were not confirmed against the primary source during this
research pass; versions/licences not marked were taken from the project pages above.
