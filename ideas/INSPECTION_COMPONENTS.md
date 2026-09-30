# Pluggable inspection components — research and proposal

*Status: proposal only, nothing here is built yet. Researched 2026-09-29. Tool facts
(latest version, release date, license, archive status) were checked on that date
against the PyPI JSON API and the GitHub REST API; anything else that was not re-checked
is marked **[unverified]**.*

This document asks which further **checkers** `rse_annotations` should be able to host,
and how they would plug in. It follows the package's rules, which are stricter than
those of most "code quality" tooling:

- **Offline, no LLM.** A checker may not call a model or need the network at inspection
  time. Tools that do (pip-audit, howfairis) can only be *optional CI steps*.
- **Static where possible.** The coverage scanner never imports target code, and research
  code often does not import cleanly. Runtime checkers are opt-in.
- **A worklist, not a verdict.** A checker reports *evidence and gaps* with a stated
  reason and confidence. It does not certify validity.
- **Wrap existing engines, don't reinvent them** (`research-annotations-NEXT_STEPS.md`).
  Our contribution is how findings attach to *annotations and hazards*, not the
  measurement technology.
- **Core stays dependency-free.** Every heavy tool is an optional extra
  (`pip install -e ".[energy]"`, `".[privacy]"`, …).
- **When is explicit.** Each checker declares `when ∈ {static, test, runtime, ci}`
  (the `Checker` protocol idea in `research-annotations-NEXT_STEPS.md`).

---

## 1. Summary

Tiers: **A** = build next (high validity value, fits the design, reuses existing
machinery); **B** = worth building once A exists; **C** = optional or domain-specific.
Effort: S ≈ ≤ 2 days, M ≈ 1 week, L ≈ several weeks.

| # | Component | Checks | When | Attaches to | Main existing tools | Effort | Validity value | Tier |
|---|---|---|---|---|---|---|---|---|
| 1 | **Test linkage ("who tests what")** | which tests actually execute each annotated/hazardous function; untested claims | test/CI | all kinds; `@functional`, `@statistical` first | coverage.py dynamic contexts, pytest-cov `--cov-context=test` | M | very high | **A** |
| 2 | **Determinism** | nondeterminism sources (static); same-seed equal and different-seed differ (test); run twice, hash outputs (CI) | static + test + CI | `@stochastic`, `@functional`, `@data_output`; new `nondeterministic` hazard | pytest-randomly, pytest-repeat, hypothesis, syrupy/pytest-regressions, diffoscope, ReproZip, torch/TF determinism flags | M | very high | **A** |
| 3 | **Provenance run record** (incl. LLM-call log) | every run records config values, model id and parameters, prompt/response hashes, tool versions, coder files, seeds | runtime | `@config`, `@model_call`, `@external_tool`, `@human_input`, `@stochastic` | own JSON-lines recorder; export via `prov`; ideas from noWorkflow, sumatra, simonw/llm, OpenTelemetry GenAI | M | very high | **A** |
| 4 | **Environment and dependency reproducibility** | lockfile or pins present; imports ⊆ declared deps; Python version pinned; SBOM; licences | static (+ optional CI) | project level; `@external_tool` (version) | deptry, FawltyDeps, uv/pip-tools, CycloneDX, pip-licenses, pip-audit (network, CI only) | S | high | **A** |
| 5 | **Privacy / personal data** | personal-data sources and sinks (static); PII in data actually read (runtime sample); hard-coded secrets | static + runtime | new `personal_data` hazard (propagates); `@data_input`, `@human_input`, `@data_output` | Presidio (+ presidio-structured), DataFog, detect-secrets, Bandit; heavy taint: CodeQL, Pysa, Semgrep/Opengrep | M | high (legal and ethical) | **A** |
| 6 | **Sample accounting + data schemas** | records in/out per `@unit_of_analysis` step, with reasons; declared `fields` hold at the boundary | runtime + test | `@unit_of_analysis`, `@data_input`, `@data_output` | built-in counter; pandera (Great Expectations is too heavy) | S–M | high | **B** |
| 7 | **Mutation testing of the maths** | do the tests of a `@functional`/`@statistical` kill mutants of *that* body? | CI | `@functional`, `@statistical` | mutmut (WSL only on Windows), Cosmic Ray | M | high (test quality) | **B** |
| 8 | **Energy consumption** | energy (and CO₂e) of a pipeline run or stage, labelled *measured* vs *estimated* | runtime | run level / pipeline stage; `@model_call` flagged "not measurable locally" | CodeCarbon (offline tracker), PowerJoular, Scaphandre, perun, Zeus; Green-Algorithms formula as fallback | S–M | medium (reporting, not validity) | **B** |
| 9 | **Notebook support** | extract `.ipynb` → scan; execution-order hygiene; re-execute and compare outputs | static + CI | everything (prerequisite for SemRepo, §9 of PROPOSED_ANNOTATIONS) | nbformat, nbQA, nbval, papermill; pynblint (dormant) | M | high for reach | **B** |
| 10 | **Numerical robustness** | FP exceptions under `np.errstate(all="raise")`; edge-case inputs; optional rewrite hints | test (+ optional external) | `@functional`, `@statistical` | numpy errstate, hypothesis; Herbie (via FPCore from `formula.py`); Verificarlo/Verrou (Linux) | S (errstate) / L (Herbie) | medium | **C** |
| 11 | **Units** | dimensional consistency of declared units | runtime/test | `@functional(units=…)` | pint | S–M | domain-dependent | **C** |
| 12 | **FAIR / citation metadata** | LICENSE, CITATION.cff, codemeta.json, README, tests present and valid | static | project level | cffconvert, codemetapy; howfairis/somef (network) | S | medium (publishing) | **C** |
| 13 | **Statistical-practice sanity** | many tests without multiple-comparison correction; hard-coded α; reported statistic not pinned to a reference | static | `@statistical` | none fit well (statcheck is R/paper-level) → own detector | M | medium–high, but hard to make precise | **C** |
| 14 | **Types / complexity as review-cost weight** | type errors in annotated code; cyclomatic complexity to rank the worklist | static | all | mypy, pyrefly, ruff, radon/xenon, vulture | S | low–medium | **C** |
| — | Performance profiling | CPU/memory per line | runtime | — | Scalene, pyinstrument, memray | — | low for *validity* → **not proposed**, except as an energy companion | — |

---

## 2. Components

### 2.1 Test linkage — which tests cover which annotated function (Tier A)

**What it checks.** For every annotated function and every hazard-bearing function
(`FunctionRecord`), which test functions *execute* it, and whether any of them
*reference it directly*. Typical findings:

- `@functional normalize: 0 tests execute it` → **fail** (a claim with no evidence).
- `@statistical compute_icr: executed only by test_pipeline_end_to_end (transitive)` →
  **warn**: covered, but no test targets it.
- `@functional f: the only linked test is the generated stub, which still calls pytest.skip()`
  → **warn**. This works well with `stubs.py`: a stub that is still skipped counts as
  "no evidence".
- `inspection.yaml` says *accepted*, but no test exists → **warn**: a human read the
  formula, but nothing pins it.

**When.** Test/CI. It needs one instrumented test run; after that, the analysis is
offline.

**Tools (verified 2026-09-29).**
- [coverage.py](https://coverage.readthedocs.io/en/latest/contexts.html) 7.16.2
  (2026-09-27), Apache-2.0, all OSes. `dynamic_context = test_function` records
  coverage separately for each test. The `.coverage` file is SQLite, and
  `CoverageData.contexts_by_lineno(filename)` returns line → contexts
  (API name from the coverage.py API docs **[not re-checked today]**).
- [pytest-cov](https://pypi.org/project/pytest-cov/) 7.1.0 (2026-03-21), MIT:
  `pytest --cov=src --cov-context=test`.
- [pytest-testmon](https://github.com/tarpas/pytest-testmon) 2.2.0 (2025-12-01), MIT:
  stores the same test-to-code mapping for test selection. It is an alternative data
  source, but we do not need it.

**Plug-in.** Add a new module `rse_annotations/testlink.py` with a `TestLinkInspector`
(`when="test"`):
1. Run pytest under `--cov-context=test`, or read an existing `.coverage` file.
2. Map covered lines to functions by line range. `FunctionRecord` needs
   **`end_lineno`** (a one-line addition in `coverage.py`, since `ast` provides it).
3. Classify each test as *direct* or *transitive*. The static rule: the test body names
   the function; this reuses `_called_names` from `checks.py`.
4. Emit `Finding`s and add a "tests" column to `annotation_coverage.md`.

**Effort** M. **Value** very high: this turns `@functional` from a label into the claim
"this function has evidence". That is the enforcement step the NEXT_STEPS file calls
the package's novelty.

### 2.2 Determinism (Tier A)

**What it checks**, in three layers:

1. **Static: sources of nondeterminism that are not an RNG.** The `stochastic`
   hazard already covers RNG calls and `_is_seeded`. These sources are missing:
   - iteration over a `set` of strings, or `hash()` of strings. The result depends on
     `PYTHONHASHSEED`.
   - unordered filesystem enumeration: `os.listdir`, `glob.glob`, `Path.iterdir`,
     `os.scandir` without `sorted(...)`.
   - wall-clock values flowing into results: `time.time`, `datetime.now`, `uuid1`.
   - concurrency: `multiprocessing`, `concurrent.futures`, `joblib` with `n_jobs`,
     threads. Reduction order and float sums then vary between runs.
   - GPU frameworks imported without the determinism switches:
     `torch.use_deterministic_algorithms(True)` together with `CUBLAS_WORKSPACE_CONFIG`
     and `cudnn.benchmark=False`, or TensorFlow's
     `tf.config.experimental.enable_op_determinism()`.
   - global legacy seeding (`np.random.seed`, `random.seed` at module level) used in
     place of an explicit `Generator` parameter. This counts as seeded, but the seed is
     hidden state.

   Proposal: add a new hazard **`nondeterministic`**, a sibling of `stochastic`
   (parent `functional`), which **propagates** like the other provenance hazards.
2. **Test: a stronger stub for `@stochastic`.** Next to "same input → same output", the
   stub checks **same seed → equal** *and* **different seed → different**. The second
   assertion catches the common generated-code bug where a `seed` parameter is accepted
   and then ignored.
   [hypothesis](https://github.com/HypothesisWorks/hypothesis) (6.168.3, 2026-09-28,
   MPL-2.0) can supply the inputs.
   [pytest-randomly](https://pypi.org/project/pytest-randomly/) (5.0.0, 2026-09-01, MIT)
   shuffles test order and reseeds `random`/NumPy for each test, which exposes order
   dependence. [pytest-repeat](https://pypi.org/project/pytest-repeat/) (0.9.4,
   2025-04-07, MPL-2.0) adds `--count=N`. Snapshot tools
   ([syrupy](https://pypi.org/project/syrupy/) 6.1.1, MIT;
   [pytest-regressions](https://pypi.org/project/pytest-regressions/) 2.11.0, MIT) pin
   `@data_output` artefacts.
3. **CI: run twice, then diff.** Run the pipeline entry point twice, with *different*
   `PYTHONHASHSEED` values and the same declared seeds. Hash every file the
   `@data_output` functions wrote (the `_OpenTracer` in `checks.py` already observes
   writes) and report which outputs differ. For the drill-down, use
   [diffoscope](https://diffoscope.org/) (release 332, 2026-09-28, GPL-3+; Linux and
   macOS, Windows only through WSL **[unverified]**) or, better for the offline
   dependency-free core, a built-in CSV/JSON diff that reports the first differing
   row. To capture the environment for a rerun elsewhere:
   [ReproZip](https://github.com/VIDA-NYU/reprozip) 1.3.2 (2026-01-18), BSD-3.
   Packing uses ptrace and runs on **Linux only**; unpacking works on Windows and macOS
   through Docker or Vagrant **[per ReproZip docs, not re-checked]**.
   [repro-catalogue](https://pypi.org/project/repro-catalogue/) (1.0.0, 2020, MIT,
   dormant) hashes inputs, code and outputs into a catalogue. Reimplementing that idea
   is cheaper than depending on the tool.

**`@model_call` special case.** LLM output is not reproducible, even at temperature 0.
Determinism checks should therefore not *rerun* model calls. They should
**record and replay** them: cache responses keyed by a hash of the request, as vcrpy
does. Tests are then deterministic, and the cache becomes provenance (§2.3).

**Plug-in.** Static detectors go into `coverage._hazards` (or the pluggable
`HazardDetector` in §3). The stub change goes into `stubs.py`. A `DeterminismRunner`
(`when="ci"`) goes into a new `rse_annotations/determinism.py` and writes
`determinism.json` with per-output hashes.

**Effort** M. **Value** very high: "can the numbers be regenerated" is the core
reproducibility question, and `stochastic` is currently detected but never enforced.

### 2.3 Provenance run record, including LLM-call logging (Tier A)

**What it checks and records.** PROPOSED_ANNOTATIONS §8 lists "provenance records" as
the missing *enforcement* of the existing hazards. A lightweight runtime recorder, active
only when enabled (`RSE_RECORD=1`), appends one JSON line for each event:

| Hazard | Recorded |
|---|---|
| `@config` | name and value of every threshold, hyperparameter or path actually used |
| `@model_call` | provider, **model id and version string returned by the API**, temperature, top_p, max_tokens, SHA-256 of the prompt and of the response, timestamp, latency, token counts; optionally the full text into a local cache |
| `@external_tool` | the argv, the `--version` output of the tool (captured once), the exit code |
| `@human_input` | file path and content hash of each coder or codebook file read; codebook version |
| `@stochastic` | the seed actually passed |
| all | git commit, dirty flag, Python version, platform, lockfile hash |

It also *checks* one thing: a run whose record has no entry for a statically detected
hazard means that hazard was never exercised (or the recorder was bypassed). That gap
is a finding.

**Tools.**
- [prov](https://github.com/trungdong/prov) 3.2.2 (2026-09-18), MIT: W3C-PROV
  serialisation. Use it as an *export* format, not as the internal store.
- [noWorkflow](https://github.com/gems-uff/noworkflow) 2.1.3 (2026-07-15), MIT, active:
  full script-level provenance through tracing. It is heavy, and its Windows support is
  **[unverified]**. It is prior art to cite, not a dependency.
- [Sumatra](https://pypi.org/project/sumatra/) 0.8.1 (2025-07), BSD-2: a
  project-level run log. Prior art.
- [recipy](https://pypi.org/project/recipy/) 0.3.0 (2016): **dead**, cite only.
- LLM logging: [simonw/llm](https://github.com/simonw/llm) (0.36, Apache-2.0) logs
  prompts and responses to SQLite, a good schema reference.
  [opentelemetry-instrumentation-openai-v2](https://pypi.org/project/opentelemetry-instrumentation-openai-v2/)
  (2.4b0, beta, Apache-2.0) implements the OpenTelemetry GenAI semantic conventions.
  Aligning field names with those conventions costs nothing and keeps records
  interoperable.

**Plug-in.** Add `rse_annotations/provenance.py`. It provides a `Recorder` context
manager, plus runtime `when="runtime"` wrappers that the (future) hazard decorators
attach: `@model_call(model=..., temperature=...)` wraps and records. The static scanner
already knows *where* these calls are, so the report can show recorded vs expected.

**Effort** M. **Value** very high: the hazards stop being a map and become an audit
trail. It also makes the package more attractive for LLM-generated and LLM-using
research code.

### 2.4 Environment and dependency reproducibility (Tier A)

**What it checks (static, offline).**
- A lockfile or fully pinned requirements exist: `uv.lock`, `poetry.lock`, `pylock.toml`,
  or `requirements*.txt` with `==`. `requires-python` is set.
- **Every imported third-party module is declared, and every declared one is used.**
  This is the most common failure in generated code.
- A `@external_tool` that has no recorded or declared version → finding (ties into §2.3).
- Optional: an SBOM for the paper's artefact, and a licence inventory. Both are offline,
  from the installed environment.

**Tools.**
- [deptry](https://github.com/fpgmaas/deptry) 0.25.1 (2026-03-18), MIT: missing, unused
  and transitive deps; offline.
- [FawltyDeps](https://pypi.org/project/fawltydeps/) 0.20.0 (2025-06-05), MIT: similar,
  and also reads notebooks.
- [uv](https://github.com/astral-sh/uv) 0.12.20 / [pip-tools](https://pypi.org/project/pip-tools/)
  7.6.1: produce lockfiles. We recommend them; we don't run them.
- [cyclonedx-bom](https://github.com/CycloneDX/cyclonedx-python) 7.4.0 (2026-09-15),
  Apache-2.0: SBOM.
- [pip-licenses](https://pypi.org/project/pip-licenses/) 5.5.5 (2026-03-28), MIT.
- [pip-audit](https://github.com/pypa/pip-audit) 2.10.1 (2026-06-10), Apache-2.0: known
  CVEs. **It needs the network** (PyPI/OSV), so it can only be an opt-in CI step.
  [osv-scanner](https://github.com/google/osv-scanner) (Apache-2.0) has an offline
  database mode **[unverified for Python lockfiles]**.

**Plug-in.** A project-level `EnvironmentInspector` (`when="static"`, target = root).
Import collection reuses `coverage._alias_map`. Shelling out to deptry is optional; a
minimal built-in "imports vs `pyproject`/requirements" check keeps the core
dependency-free.

**Effort** S. **Value** high: without a working environment, no other check can be
reproduced by a third party.

### 2.5 Privacy — was personal data used? (Tier A)

**What it checks.**
1. **Static source/sink map (new hazard `personal_data`, which propagates).**
   - *Sources*: reads whose path literal or column names match a personal-data
     vocabulary (`name`, `email`, `birth`, `address`, `phone`, `ip`, `participant`,
     `subject_id`, `student`, `matrikel`, `gender`, `age`, `free_text`, …). Also
     `input()`/form handlers, survey and LMS exports, and `@human_input` files. The
     **coder identity in a gold-standard file is itself personal data**: `coding_<user>.csv`
     in lni_study is an example.
   - *Sinks*: `@data_output` writes, logging, and network egress (`requests.post`,
     `httpx`, `boto3`, `smtplib`). **`@model_call` counts as a sink**, because sending
     participant text to a hosted LLM is a data transfer to a third party.
   - The finding is a *pair*: "personal-data source X reaches sink Y through f → g → h".
     It reuses the existing call-graph propagation (`_propagate_hazards`), so it is a
     coarse function-level taint. It is not precise, and it doesn't need to be for a
     worklist.
2. **Runtime/data scan (opt-in).** Sample the value returned by each `@data_input`
   (DataFrame, list of dicts, text). Run a PII analyser per column and report entity
   types and hit rates: "column `comment`: PERSON in 34% of 200 sampled rows". Report
   only counts and entity types, **never the values**, so the report does not leak.
3. **Secrets.** Hard-coded API keys and passwords. This matters for LLM code, where
   keys are often pasted inline.
4. **Declarative GDPR metadata** (not enforceable, metadata only):
   `@data_input(personal_data=True, legal_basis="consent", anonymised=False)`. The
   checker flags a mismatch between the declaration and the evidence from 1 or 2. No
   tool can certify GDPR compliance, and the report should say so.

**Tools (runtime / data).**
- [Microsoft Presidio](https://github.com/data-privacy-stack/presidio) (presidio-analyzer
  2.2.364, 2026-07-22, MIT; the repo now lives under `data-privacy-stack`, active):
  NER plus pattern recognisers, multilingual through spaCy models, **offline once the
  model is installed**. **presidio-structured** (0.0.8, MIT) handles DataFrames and JSON
  directly, which is the right fit for `@data_input`.
- [DataFog](https://github.com/DataFog/datafog-python) 4.9.0 (2026-09-29), MIT on
  GitHub (PyPI classifier says Apache): regex-first, fast, with optional GLiNER NER.
- [pii-codex](https://pypi.org/project/pii-codex/) 0.6.1 (2026-02), BSD-3: builds on
  Presidio and adds PII categorisation and severity, which is useful for ranking.
- [scrubadub](https://github.com/LeapBeyond/scrubadub) 2.0.1 (2023-09): low maintenance.
- [piicatcher](https://github.com/tokern/piicatcher): **archived**. Don't use it.
- Recall caveat: NER-based PII detection misses names in non-English free text and
  flags false positives. That is fine for a worklist, not for a guarantee.

**Tools (static / secrets).**
- [detect-secrets](https://github.com/Yelp/detect-secrets) 1.5.0 (2024-05-06, repo
  active 2026-04), Apache-2.0: offline, with a baseline file.
- [Bandit](https://github.com/PyCQA/bandit) 1.9.4 (2026-02-25), Apache-2.0: hard-coded
  password checks (B105–B107) and more.
- Heavy interprocedural taint, all **optional and external**:
  - [CodeQL](https://github.com/github/codeql) (queries MIT, CLI under the GitHub CodeQL
    terms). **Free for academic research and open-source code**, but *not* for automated
    analysis of closed or private code. Good Python dataflow, but a large install.
  - [Pysa](https://pyre-check.org/docs/pysa-basics/) (MIT): the `pyre-check` repo was
    **archived on 2026-06-26**, and Pysa moved to
    [facebook/Pysa](https://github.com/facebook/Pysa) with Pyrefly as its type backend.
    It is Linux/macOS only **[Windows unsupported per past Pyre docs, not re-checked]**.
    Treat it as volatile.
  - [Semgrep CE](https://github.com/semgrep/semgrep) 1.178.0, LGPL-2.1: taint mode is
    **intraprocedural only** in CE; cross-function taint needs Semgrep Pro. The
    registry rules fall under the Semgrep Rules License (fine for internal and research
    use). [Opengrep](https://github.com/opengrep/opengrep) (LGPL-2.1, active) is the
    community fork **[its interprocedural claims unverified]**.
  - [Privado](https://github.com/Privado-Inc/privado) (LGPL-3.0, last push 2025-11): a
    privacy-specific dataflow scanner. Its Python support and maintenance are uncertain
    **[unverified]**. HoundDog.ai: no open licence.

**Plug-in.** A `personal_data` detector in the static hazard pipeline, which
propagates. A `PiiDataInspector` (`when="runtime"`, extra `[privacy]`) that attaches to
`@data_input` and `@human_input`. A `SecretsInspector` (`when="static"`, a thin wrapper
around detect-secrets when installed, otherwise a small built-in key-pattern set).
External taint engines are exposed only as "import SARIF results and map them to
`FunctionRecord`s". That keeps them optional and makes SARIF the single integration
format.

**Effort** M (static + Presidio). SARIF import would add another S. **Value** high:
ethics boards and GDPR make this a hard requirement for studies with human participants,
and the `@human_input` / `@model_call` pairing is a distinctive contribution.

### 2.6 Sample accounting and data schemas (Tier B)

**What it checks.**
- `@unit_of_analysis` (already detected, 39 hits in lni_study): at runtime, count
  records in and out and require a *reason* for every drop. The hazard help text already
  demands this ("every dropped record needs a reason"). Output is a CONSORT-style flow
  table: 1 200 → 1 031 (dropped 169: 120 duplicate, 49 missing abstract). No external
  tool is needed.
- `@data_input(fields=...)` / `@data_output`: validate the declared fields, dtypes and
  ranges at the boundary. The declared `fields=` can **generate a pandera schema stub**,
  analogous to the pytest stubs.

**Tools.** [pandera](https://github.com/unionai-oss/pandera) 0.33.1 (2026-09-01), MIT,
lightweight, with its own `@check_input`/`@check_output` decorators.
[Great Expectations](https://pypi.org/project/great-expectations/) 1.23.2, Apache-2.0,
is too heavy for this package's style.

**Plug-in.** A runtime wrapper for the (future) `@unit_of_analysis` decorator, records
into the provenance log (§2.3), and stub generation in `stubs.py`.
**Effort** S–M. **Value** high: silent sample shrinkage is a classic source of wrong
results.

### 2.7 Mutation testing, restricted to the maths (Tier B)

**What it checks.** Whether the tests linked to a `@functional`/`@statistical` function
(§2.1) *kill* mutants of that function's body: swapped operators, off-by-one errors,
changed constants. A formula with 100% line coverage and a 20% kill rate is effectively
untested. Restricting mutation to the small annotated subset makes it affordable. This
is the same "finite review" argument the README makes.

**Tools.**
- [mutmut](https://github.com/boxed/mutmut) 3.8.0 (2026-09-12), BSD-3. The README says
  **"to run on Windows, you must run inside WSL"**. Supports
  `mutate_only_covered_lines` and `# pragma: no mutate`.
- [Cosmic Ray](https://github.com/sixty-north/cosmic-ray) 8.7.0 (2026-08-09), MIT: more
  configurable filters; native Windows support **[unverified]**.

**Plug-in.** A `MutationInspector` (`when="ci"`). It generates the mutmut or Cosmic Ray
config restricted to the files and line ranges of the annotated functions (needs
`end_lineno`, as in §2.1) and parses the per-mutant results back into per-function kill
rates. **Effort** M. **Value** high as *test-quality* evidence. It is slow, so it runs
only in CI.

### 2.8 Energy consumption (Tier B)

**What it checks.** The energy (kWh) and optionally CO₂e of a run or pipeline stage,
**explicitly labelled with the measurement method**: hardware counter, OS interface, or
TDP×load estimate. Per-function energy for short functions is mostly noise: CodeCarbon
samples every ~15 s by default, and RAPL counters are package-wide. The honest
granularity is **run level or pipeline stage**. Energy is *reporting* (a growing
expectation for ML papers), not validity.

**Framework comparison (checked 2026-09-29).**

| Tool | Latest release | License | OS | Per-process? | GPU | Privileges | Maintenance |
|---|---|---|---|---|---|---|---|
| [CodeCarbon](https://github.com/mlco2/codecarbon) | 3.3.1 (2026-09-09) | MIT | Linux (RAPL), **Windows 11 bare metal through the Energy Meter Interface, no admin**; on Win10/VMs/unsupported hardware it falls back to a CPU-load × TDP estimate; macOS (powermetrics, sudo **[unverified]**) | `tracking_mode="process"` attributes power by the process's CPU-time share and RAM ("lower-bound estimate"); `"machine"` is the default | NVIDIA (NVML), AMD (AMDSMI), **always device-level** | Linux RAPL needs read access to `/sys/class/powercap` (root or a udev/chmod rule since kernel 5.10) | very active; `OfflineEmissionsTracker` needs no network |
| [PowerJoular](https://github.com/joular/powerjoular) | 1.1.1 (2025-09-19); README describes a "version 2" with macOS/Windows **[whether released unverified]** | **GPL-3.0** (a CLI, so wrapping it via subprocess is fine) | Linux, Windows, macOS, Raspberry Pi | **yes, `-p PID`** | NVIDIA (NVML), AMD (amdgpu / ADLX), Apple | Linux sudo for RAPL; Windows none with EMI; macOS sudo | active |
| [Scaphandre](https://github.com/hubblo-org/scaphandre) | v1.0.3 (2026-07-17) | Apache-2.0 | Linux (powercap), Windows 10/11/Server (own signed RAPL kernel driver) | yes, per-process attribution by CPU-time share **[mechanism per docs, not re-checked]** | no **[unverified]** | root, or installing the driver | active; an agent/exporter (Prometheus), not a library |
| [perun](https://github.com/Helmholtz-AI-Energy/perun) | 1.0.0 (2026-08-31) | BSD-3 | Linux (HPC, MPI) | node/job level | NVIDIA | RAPL access | active |
| [Zeus](https://github.com/ml-energy/zeus) (PyPI `zeus`) | 0.16.0 (2026-07-07) | Apache-2.0 | Linux (Windows **[unverified]**) | GPU-window level | NVIDIA, AMD; CPU via RAPL | RAPL access | active, GPU-centric |
| [carbontracker](https://github.com/saintslab/carbontracker) | 2.4.7 (2026-08-27) | MIT | Linux, Apple silicon | machine | NVIDIA | root for RAPL | active, DL-epoch oriented |
| [eco2AI](https://github.com/sb-ai-lab/Eco2AI) | 0.3.12 (2025-03-10) | Apache-2.0 | cross-platform (estimate) | process (utilisation × TDP database) | NVIDIA | none | low activity |
| [Tracarbon](https://pypi.org/project/tracarbon/) | 0.13.0 (2026-09-28) | Apache-2.0 | Linux/macOS **[Windows unverified]** | machine | — | — | active |
| [pyJoules](https://github.com/powerapi-ng/pyJoules) | 0.5.1 (**2020**) | MIT | Linux only (RAPL) | no (package domain) | NVIDIA | RAPL access | no release since 2020 |
| pyRAPL | 0.2.3.1 (2019) | MIT | Linux | no | — | — | dead |
| [experiment-impact-tracker](https://github.com/Breakend/experiment-impact-tracker) | 0.1.8 (2020) | MIT | Linux | — | NVIDIA | — | **archived** |
| Linux `perf stat -e power/energy-pkg/` | kernel | GPL | Linux | **no**, system-wide only (`-a`) | no | root or `perf_event_paranoid` | — |
| [Green Algorithms](https://github.com/Cambridge-Sustainable-Computing-Lab/Green-Algorithms-calculator) | calculator (web + formula) | CC-BY-4.0 | any | estimate only | by TDP | none | active |

**Recommendation.**
1. Default backend: **CodeCarbon `OfflineEmissionsTracker(tracking_mode="process")`**.
   It is the only mature library that works on this machine (Windows 11) without admin
   rights, it is offline, and it is MIT-licensed.
2. Built-in fallback with no dependencies: a **Green-Algorithms-style estimate**,
   E ≈ t · (n_cores · P_core · u + mem_GB · P_mem) · PUE, computed from wall time,
   `psutil` CPU time and RSS. It is always labelled *estimated*.
3. Optional high-fidelity backend: **PowerJoular -p PID** as a subprocess, for true
   per-PID measurement including GPU on Linux or Windows.
4. **`@model_call` → "energy external, not measurable locally"**, reported with the
   token counts from §2.3. For LLM-heavy research code the dominant energy is invisible
   to every local meter, and the report should say so rather than print a misleadingly
   small number.

**Plug-in.** An `EnergyInspector` (`when="runtime"`, extra `[energy]`) with a
context-manager API around the pipeline entry point or around functions tagged as
stages. It writes to the provenance record. **Effort** S–M. **Value** medium.

### 2.9 Notebook support (Tier B)

About 95% of SemRepo is notebooks (PROPOSED_ANNOTATIONS §9), so this component decides
the package's *reach*. What it covers:
- **Static.** `.ipynb` → code cells → the existing AST scan, with the cell index kept in
  `location`. Execution counts that are non-monotonic or missing mean
  "run out of order" (a pure JSON check). Outputs committed without being re-run.
- **CI.** Re-execute the notebook and compare outputs. That is determinism (§2.2)
  applied to notebooks.

**Tools.** nbformat (stdlib-like, BSD);
[nbQA](https://github.com/nbQA-dev/nbQA) 1.9.1, MIT, runs any linter on notebooks;
[nbval](https://github.com/computationalmodelling/nbval) 0.11.0 (2024), BSD, re-executes
and compares outputs; papermill 2.7.0, BSD;
[pynblint](https://github.com/collab-uniba/pynblint) 0.1.6 (2024), MIT, low activity,
a good source of hygiene rules to cite.

**Plug-in.** A notebook source adapter in `coverage.scan_path` (the scan stays static)
and an `nbval`-backed CI inspector. **Effort** M.

### 2.10 Numerical robustness (Tier C)

- **Cheap (S).** Generated `@functional` stubs run the call inside
  `np.errstate(all="raise")` and use hypothesis float strategies that include 0, ±inf,
  nan, subnormals and huge magnitudes. A division like `(v-lo)/(hi-lo)` then fails when
  `hi == lo`. That is a real bug class in generated normalisation and statistics code.
- **Expensive (L).** `formula.py` already reconstructs the expression.
  Exporting it as **FPCore** would let a local [Herbie](https://github.com/herbie-fp/herbie)
  installation (Racket, active) propose more accurate rewrites. That is offline, but it
  needs Racket.
- Stochastic arithmetic ([Verificarlo](https://github.com/verificarlo/verificarlo),
  [Verrou](https://github.com/edf-hpc/verrou), GPL-3.0, Linux only; the
  `significantdigits` PyPI package post-processes their results) estimates the number
  of significant digits. That is valuable for simulation codes, but too heavy here.
  Cite it only.

### 2.11 Units (Tier C)

`@functional(units={"v": "m/s", "return": "J"})`, checked at runtime or in tests with
[pint](https://github.com/hgrecco/pint) 0.26.1 (2026-09-10, BSD). It is a declarative
claim with an optional runtime check, which fits the `when` model exactly. It matters
for physics and engineering code and is mostly irrelevant for social-science pipelines
like lni_study. **Effort** S–M.

### 2.12 FAIR and citation metadata (Tier C)

An offline project check covering LICENSE, README, `CITATION.cff` (validated with
[cffconvert](https://github.com/citation-file-format/cffconvert), Apache-2.0; release
2.0.0 is from 2021, repo active 2025), `codemeta.json`
([codemetapy](https://pypi.org/project/codemetapy/) 3.0.4, GPL-3.0), a test directory,
and a DOI/Zenodo badge.
[howfairis](https://github.com/fair-software/howfairis) (0.14.2, 2022, Apache-2.0) and
[somef](https://github.com/KnowledgeCaptureAndDiscovery/somef) (0.11.4, MIT) query
GitHub or remote services, so they are CI-only. **Effort** S. This is publishing
hygiene rather than validity, but cheap, and it matches the RSE audience.

### 2.13 Statistical-practice sanity (Tier C)

Static hints on `@statistical` functions: several `scipy.stats` tests in a loop with no
`multipletests` or other correction; a hard-coded `0.05`; a one-sided test without a
comment; `@statistical` without `cites=` or without a `differential_check` against a
reference (the Krippendorff pattern). No existing Python tool fits (statcheck is R and
works on paper text). It is hard to make precise without false positives, so it belongs
in the research agenda rather than the next release.

### 2.14 Types and complexity as review cost (Tier C)

Run mypy (2.3.1, MIT) or Pyrefly (MIT) only on annotated modules. Use radon (6.0.1,
2023) or ruff's `C901` complexity as a *weight* on the worklist, so the costliest
functions are reviewed first. vulture (2.16) finds dead code, which complements the
existing "`@validation` nobody calls" finding. It is cheap but adds little to validity.

---

## 3. Plugin interface sketch

This is consistent with the existing types: `CheckResult` (checks.py), `Hazard`,
`FunctionRecord` and `CoverageReport` (coverage.py), `AnnotationInfo` (registry.py) and
`Runner`/`Report` (runner.py). Two extension points are enough: **static hazard
detectors** that run inside `scan_path` (no import), and **inspectors** that produce
findings at a declared time.

```python
# rse_annotations/plugins.py  (proposal)
from __future__ import annotations
import ast
from dataclasses import dataclass, field
from typing import Iterable, Literal, Optional, Protocol, Sequence, Union, runtime_checkable

from .checks import CheckResult
from .coverage import CoverageReport, FunctionRecord, Hazard
from .registry import AnnotationInfo

When = Literal["static", "test", "runtime", "ci"]
Status = Literal["pass", "warn", "fail", "info"]
Target = Union[AnnotationInfo, FunctionRecord, "ProjectTarget"]


@dataclass
class ProjectTarget:
    """Project-level target (dependencies, FAIR metadata, notebooks)."""
    root: str
    coverage: Optional[CoverageReport] = None   # static scan, if already computed


@dataclass
class Finding:
    """Superset of CheckResult: also says *where* and *on what evidence*.

    ``evidence`` must never contain raw personal data (privacy checker: counts and
    entity types only).
    """
    checker: str                   # e.g. "determinism.seed_ignored"
    status: Status
    message: str
    location: str = ""             # file:line, or file#cell for notebooks
    target: str = ""               # qualname, or "<project>"
    confidence: str = "medium"     # same vocabulary as Hazard / FunctionRecord
    method: str = ""               # e.g. "measured:rapl", "estimated:tdp" (energy)
    evidence: dict = field(default_factory=dict)

    def to_check_result(self) -> CheckResult:
        # "info" findings don't affect PASS/WARN/FAIL
        return CheckResult(self.checker, "pass" if self.status == "info" else self.status,
                           self.message)


@dataclass
class InspectionContext:
    root: str
    options: dict = field(default_factory=dict)     # per-inspector config (pyproject)
    coverage_file: Optional[str] = None             # .coverage with test contexts (2.1)
    record_path: Optional[str] = None               # provenance JSONL (2.3)


# -- extension point 1: static, runs inside coverage.scan_path, never imports ------
@runtime_checkable
class HazardDetector(Protocol):
    kind: str                  # new or existing hazard kind, e.g. "personal_data"
    parent: Optional[str]      # dataflow annotation it specialises (HAZARD_PARENT)
    propagates: bool           # travels up the call graph like model_call/stochastic
    critical: bool             # counts towards CRITICAL_HAZARDS
    help: str                  # HAZARD_HELP text

    def detect(self, node: ast.AST, *, name: str, params: Sequence[str],
               called: set, dotted: Sequence[str]) -> Optional[Hazard]: ...


# -- extension point 2: inspectors with an explicit "when" --------------------------
@runtime_checkable
class Inspector(Protocol):
    name: str
    when: When
    attaches_to: frozenset     # annotation kinds and/or hazard kinds, or {"<project>"}
    extras: tuple              # optional deps, e.g. ("codecarbon",); core = ()

    def available(self) -> tuple[bool, str]:
        """(ok, reason): missing extra, wrong OS, no RAPL access, no network, ..."""

    def applies(self, target: Target) -> bool: ...

    def inspect(self, target: Target, ctx: InspectionContext) -> Iterable[Finding]: ...


@runtime_checkable
class RuntimeInspector(Inspector, Protocol):
    """when == "runtime": may wrap the function. Only these add call overhead, and
    only when enabled (env RSE_RUNTIME_CHECKS=1), so a normal run is unaffected."""
    def wrap(self, func, info: AnnotationInfo): ...


@runtime_checkable
class StubContributor(Protocol):
    """when == "test": contributes pytest stub fragments to stubs.py
    (e.g. seed-sensitivity test, errstate wrapper, pandera schema from fields=)."""
    def stub_fragments(self, info: AnnotationInfo) -> list[str]: ...
```

**Registration.** Through entry points, so third-party checkers need no core change:

```toml
[project.entry-points."rse_annotations.hazards"]
personal_data   = "rse_annotations.privacy:PersonalDataDetector"
nondeterministic = "rse_annotations.determinism:NondeterminismDetector"

[project.entry-points."rse_annotations.inspectors"]
testlink   = "rse_annotations.testlink:TestLinkInspector"
energy     = "rse_annotations.energy:EnergyInspector"      # extra [energy]
pii        = "rse_annotations.privacy:PiiDataInspector"    # extra [privacy]
```

**Integration points in the existing code.**
- `coverage.py`: `HAZARDS`, `HAZARD_PARENT`, `HAZARD_HELP` and `CRITICAL_HAZARDS` are
  extended from the registered `HazardDetector`s. `_hazards()` calls them, and
  `_propagate_hazards()` uses `detector.propagates` in place of the hard-coded set.
  `FunctionRecord` gains `end_lineno` (needed by 2.1 and 2.7).
- `runner.py`: `Runner(..., inspectors=[...], when={"static","test"})` runs the selected
  inspectors and appends `Finding.to_check_result()` to each `FunctionReport.checks`.
  Project-level findings go to a new `Report.project` list. `available() == False` is
  reported as `info` ("energy: skipped, no RAPL access; using estimate"). A check that
  was skipped is never silent, as with the pytest stubs.
- `cli.py`: add a menu option 4, "Run inspectors", plus `--inspect-with energy,testlink`.
- `inspection.yaml`: store only human verdicts. Machine evidence goes to
  `rse_evidence.json` (hashes, test links, energy, PII counts), so human judgement and
  machine output are never mixed.
- SARIF import (`rse_annotations/sarif.py`): one adapter that maps CodeQL, Semgrep,
  Bandit or Pysa results onto `FunctionRecord`s by file and line range. The heavy
  analysers then stay external and optional.

---

## 4. Recommended build order

1. **Plugin skeleton** (S): `Finding`, `Inspector`, `HazardDetector`, entry-point
   loading, `FunctionRecord.end_lineno`, `rse_evidence.json`. Port one existing
   check (placement) onto it to prove the interface.
2. **Test linkage** (2.1, M): this directly enforces `@functional`. The static half
   ("does any test name this function?") can ship first, with no pytest run.
3. **Determinism, static + stubs** (2.2 layers 1–2, M): the `nondeterministic` hazard
   and the seed-sensitivity stub. Regression tests on lni_study, following the
   "evidence, not vocabulary" rule from §8.
4. **Environment check** (2.4, S): offline imports vs declared deps, and lockfile
   presence.
5. **Provenance recorder** (2.3, M): together with the first real hazard decorators
   (`@model_call`, `@config`). This is the "enforcement is the contribution" step. It
   includes record-and-replay for model calls, which layer 3 of determinism then relies
   on.
6. **Privacy** (2.5, M): the static `personal_data` hazard first (no deps), then the
   Presidio data scan behind `[privacy]`, then detect-secrets.
7. **Determinism run-twice-and-hash** (2.2 layer 3) and **sample accounting** (2.6).
8. **Mutation testing restricted to annotated maths** (2.7), in CI only.
9. **Energy** (2.8): the CodeCarbon offline backend plus a built-in estimate. Cheap,
   and it can come earlier if a paper needs it.
10. **Notebook adapter** (2.9): required before the SemRepo "danger zone" study.
11. Tier C as needed (errstate stubs are nearly free and can ride along with step 3).

---

## 5. Sources

Package metadata (version, date, license) came from `https://pypi.org/pypi/<name>/json`,
and repository status (last push, license, archived flag) from
`https://api.github.com/repos/<owner>/<repo>`, both queried 2026-09-29.

- CodeCarbon: https://github.com/mlco2/codecarbon ·
  configuration and tracking modes: https://docs.codecarbon.io/latest/how-to/configuration/ ·
  methodology: https://docs.codecarbon.io/latest/explanation/methodology/ ·
  RAPL: https://docs.codecarbon.io/latest/how-to/enable-rapl/
- PowerJoular: https://github.com/joular/powerjoular
- Scaphandre: https://github.com/hubblo-org/scaphandre
- perun: https://github.com/Helmholtz-AI-Energy/perun · Zeus: https://github.com/ml-energy/zeus ·
  carbontracker: https://github.com/saintslab/carbontracker · eco2AI: https://github.com/sb-ai-lab/Eco2AI ·
  pyJoules: https://github.com/powerapi-ng/pyJoules · experiment-impact-tracker (archived):
  https://github.com/Breakend/experiment-impact-tracker
- Green Algorithms calculator: https://github.com/Cambridge-Sustainable-Computing-Lab/Green-Algorithms-calculator
- Energy tool survey: "Calculating Software's Energy Use and Carbon Emissions: A Survey…",
  https://arxiv.org/html/2506.09683v1
- Presidio: https://github.com/data-privacy-stack/presidio · DataFog: https://github.com/DataFog/datafog-python ·
  pii-codex: https://pypi.org/project/pii-codex/ · scrubadub: https://github.com/LeapBeyond/scrubadub ·
  piicatcher (archived): https://github.com/tokern/piicatcher
- detect-secrets: https://github.com/Yelp/detect-secrets · Bandit: https://github.com/PyCQA/bandit
- CodeQL CLI terms: https://github.com/github/codeql-cli-binaries/blob/main/LICENSE.md
- Pysa: https://pyre-check.org/docs/pysa-basics/ · https://github.com/facebook/Pysa ·
  pyre-check (archived): https://github.com/facebook/pyre-check
- Semgrep taint mode: https://semgrep.dev/docs/writing-rules/data-flow/taint-mode/overview ·
  Rules License: https://semgrep.dev/legal/rules-license/ · Opengrep: https://github.com/opengrep/opengrep
- Privado: https://github.com/Privado-Inc/privado
- coverage.py contexts: https://coverage.readthedocs.io/en/latest/contexts.html ·
  pytest-cov: https://pypi.org/project/pytest-cov/ · pytest-testmon: https://github.com/tarpas/pytest-testmon
- mutmut: https://github.com/boxed/mutmut · Cosmic Ray: https://github.com/sixty-north/cosmic-ray
- pytest-randomly: https://pypi.org/project/pytest-randomly/ · pytest-repeat: https://pypi.org/project/pytest-repeat/ ·
  hypothesis: https://github.com/HypothesisWorks/hypothesis · syrupy: https://pypi.org/project/syrupy/ ·
  pytest-regressions: https://pypi.org/project/pytest-regressions/
- PyTorch reproducibility: https://pytorch.org/docs/stable/notes/randomness.html **[not re-fetched]**
- diffoscope: https://diffoscope.org/ · ReproZip: https://github.com/VIDA-NYU/reprozip ·
  repro-catalogue: https://pypi.org/project/repro-catalogue/
- prov: https://github.com/trungdong/prov · noWorkflow: https://github.com/gems-uff/noworkflow ·
  Sumatra: https://pypi.org/project/sumatra/ · recipy: https://pypi.org/project/recipy/ ·
  simonw/llm: https://github.com/simonw/llm ·
  OpenTelemetry OpenAI instrumentation: https://pypi.org/project/opentelemetry-instrumentation-openai-v2/
- deptry: https://github.com/fpgmaas/deptry · FawltyDeps: https://pypi.org/project/fawltydeps/ ·
  CycloneDX: https://github.com/CycloneDX/cyclonedx-python · pip-licenses: https://pypi.org/project/pip-licenses/ ·
  pip-audit: https://github.com/pypa/pip-audit · osv-scanner: https://github.com/google/osv-scanner
- pandera: https://github.com/unionai-oss/pandera · Great Expectations: https://pypi.org/project/great-expectations/
- nbQA: https://github.com/nbQA-dev/nbQA · nbval: https://github.com/computationalmodelling/nbval ·
  pynblint: https://github.com/collab-uniba/pynblint
- Herbie: https://github.com/herbie-fp/herbie · Verificarlo: https://github.com/verificarlo/verificarlo ·
  Verrou: https://github.com/edf-hpc/verrou · pint: https://github.com/hgrecco/pint
- cffconvert: https://github.com/citation-file-format/cffconvert · codemetapy: https://pypi.org/project/codemetapy/ ·
  howfairis: https://github.com/fair-software/howfairis · somef: https://github.com/KnowledgeCaptureAndDiscovery/somef
- Internal: `README.md`, `CONCEPT.md`, `PROPOSED_ANNOTATIONS.md` §7–9, `rse_annotations/coverage.py`,
  `checks.py`, `runner.py`; `../../research-annotations-NEXT_STEPS.md` (Checker/`when` idea).
