# Proposed annotations — beyond the dataflow four

*Recommendations grounded in the first real coverage run (`lni_study`, 29 modules,
267 functions). See [`CONCEPT.md`](CONCEPT.md) §5 for the coverage tool that produced
the evidence, and §7 for the hazard scan that now detects everything proposed here.*

---

## 1. What the testbed run revealed

Running the coverage scan on `lni_study` gave a defensible number (2% annotated, 210
candidates) — but the *interesting* finding is not the coverage. It is **what the four
annotations said about the three most important functions in the study**:

| Function | What it actually does | Current suggestion |
| --- | --- | --- |
| `classify_paper` (`annotate_lni.py:444`) | a paid, non-deterministic **network call to an LLM** whose answer *is the study's raw data* | `@mapping` — *"no I/O"* |
| `stratified_sample` (`sampling.py:134`) | decides **which papers enter the corpus**, via a seeded RNG | `@mapping` — *"no I/O"* |
| `compute_dimension_icr` (`compute_icr.py:101`) | computes **Krippendorff's α — the paper's headline number** | `@mapping` |

All three are `@mapping`. So is `_random_matrix` (reason line: *"calls randint"*), and so
is `folder_weighted_order` (reason line: *"calls Random, choices"*).

That is not a mis-classification to be fixed with a better heuristic — **the tool is
correct.** Under the current taxonomy those functions genuinely are "takes input, returns
a transformed value, does not touch a file". The taxonomy has nothing better to say about
them. `@mapping` collected **113 of the 210 candidates (54%)** because it is not a
category at all; it is the *residual* — everything that isn't a file boundary and isn't
pure arithmetic.

The blind spot has a shape. The four annotations answer **"where does data flow?"**
Auditing AI-generated research software needs a second, *orthogonal* question:

> **Where can the result be wrong, and can I reproduce it?**

Nothing in `{functional, mapping, data_input, data_output}` can express *"this function is
non-deterministic"*, *"this function's output came from a language model"*, or *"this
function decided who is in the sample"* — which are precisely the three things a reviewer
will attack.

There is direct evidence the author already felt this gap. `sampling.py:175` carries the
comment:

```python
# Deterministic: the within-folder order is a per-folder seeded shuffle and the
# folder picks use a single seeded RNG, so the whole order is reproducible.
```

That is a **load-bearing claim about reproducibility, asserted in prose, checkable by
nobody**. An annotation is exactly the machinery for turning that sentence into something
a machine can verify. The same applies to the 4 modules that call an LLM at runtime
(`annotate_lni`, `confirm_positives`, `narrow_categories`, `preflight`) and the 12 that
touch an RNG: today none of that is visible to the framework.

---

## 2. The bar an annotation must clear

More tags are not automatically better. I applied one filter to every idea below:

> **An annotation earns its place only if (a) a machine can check that it holds, and
> (b) its violation would threaten a research claim.**

Anything that fails (a) is a comment. Anything that fails (b) is bookkeeping. The four
existing annotations pass: each has a placement check and a runtime check. Every proposal
below states its check explicitly — if I could not name one, I dropped it.

---

## 3. The shape of the fix: specialisation, not a parallel taxonomy

The natural move is to bolt a second, unrelated vocabulary onto the first. That is wrong,
and seeing why is what makes the design work.

**A hazard is a *specialisation* of a dataflow role, not a competitor to it.** Each new
annotation says *"this is a `<dataflow kind>`, and specifically the dangerous sort"* — so
it **inherits the parent's contract and adds one of its own**:

```
@functional  — deterministic, pure
├── @stochastic       — pure *given the seed*
└── @statistical      — pure, and the number it returns is one the paper reports

@data_input  — data enters the system
├── @model_call       — data enters from a *model*, not a file
└── @human_input      — data enters from a *person*: coding, annotation, gold standard

@mapping     — one representation becomes another
└── @unit_of_analysis — records in, *fewer* records out

(no parent)
    @external_tool     — the computation leaves the process entirely
    @config            — supplies a threshold or hyperparameter
    @human_decision    — a person, not the machine, decides — at run time
    @validation        — asserts a property of the data
```

The `@model_call` / `@human_input` pair under `@data_input` is the second edge that earns
the design. In an AI-assisted study **every datum was produced either by a model or by a
person**, and a taxonomy that cannot say which cannot answer the one question the field is
actually arguing about. They are siblings because they are the same *kind* of boundary —
data entering from outside the code, unverifiable by reading it — and separate because
their contracts differ completely: a model call needs a model id, a prompt version and a
temperature; a human coding needs a coder identity, a codebook version and an inter-coder
reliability figure.

`@external_tool` is the one hazard with **no dataflow parent**, and that is informative
rather than untidy: a subprocess may read, write, both or neither, so it does not sit
anywhere on the dataflow axis. Which is exactly why the four annotations are blind to it.

The `@stochastic ⊂ @functional` edge is the one that earns the design. A properly seeded
sampler **is** a pure function — of its inputs *plus the seed*. That is not a weakening of
`@functional`; it is the same promise with the seed made explicit, which is exactly *why*
the seed must be a parameter and not a module-level constant. And it means `@stochastic`
inherits `@functional`'s determinism check **verbatim**: call it twice with the same seed,
assert the outputs are identical. The check already exists.

`@statistical ⊂ @functional` works the same way and explains a fact the run surfaced by
accident: `n_disagreements` is flagged as *both* a high-confidence `@functional` candidate
*and* a `@statistical` hazard. Under a parallel taxonomy that is a contradiction to be
resolved. Under this one it is simply the truth — a pure function that happens to return a
number the paper prints.

This is also why **multiple annotations per function must be allowed** (§7): a function has
*one* dataflow role and *zero or more* hazards. `stratified_sample` is `@stochastic` **and**
`@unit_of_analysis`. `check_saia` is `@model_call` **and** `@validation`. `load_coders` is
`@data_input` **and** `@human_input`.

---

## 4. Tier 1 — the five that change what the framework is for

### `@stochastic(seed=...)` ⊂ `@functional` — the output depends on an RNG

**Marks:** any function whose result depends on a random source.

**The audit question:** *"Can I regenerate your sample?"* For an empirical paper this is
not a nicety; an unreproducible corpus is an unreproducible result.

**Checks (both are real, not aspirational):**
- *Static:* the body calls an RNG (`random.*`, `np.random.*`, `.shuffle`, `.choices`,
  `.sample`, `train_test_split`) **and the function must accept a `seed`/`rng` parameter**.
  An unseeded RNG in a function that feeds the corpus is a **hard failure**, not a warning
  — it means the sample cannot be regenerated, ever.
- *Runtime:* inherited from `@functional` — call twice with the same seed, assert identical
  output. Call with different seeds → assert (usually) different output, which catches a
  seed parameter that is accepted and then silently ignored.

**In the testbed:** `stratified_sample`, `folder_weighted_order`, `_random_matrix` — all
three **correctly detected as seeded**, so the scan reports them as *"pure given the seed,
so it is checkable"* rather than as failures. `allocate_proportional` has no RNG and
correctly stays a plain `@functional`.

**One thing the detector had to learn.** `random.random()` inside an exponential backoff
(`annotate_lni.py:348`: `wait_s = backoff + backoff * 0.25 * random.random()`) is **not** a
reproducibility hazard — jitter in a sleep interval cannot change a finding. Flagging it
was not merely noisy: the false positive **propagated up the call graph** (§7) and tainted
`classify_paper` and every `main`. The rule is now that RNG whose only consumers are a
`sleep` or a `wait`/`backoff`/`jitter` variable does not count. That distinction is worth
stating in the paper — *the hazard is randomness that reaches the result*, not randomness
per se.

---

### `@model_call(model=..., temperature=...)` ⊂ `@data_input` — the answer came from an LLM

**Marks:** a call to a language model or other non-deterministic external service.

**The audit question:** *"Which of your data did a model make up, and under what
conditions?"* This is **the** annotation the stated goal needs. For research software that
*uses* AI, the model call is where unverifiable content enters the study — and the current
taxonomy calls it an in-memory transform with no I/O. That is wrong in three separate
ways: it does I/O (network), it is not deterministic, and it costs money.

Making it a **specialisation of `@data_input`** is the whole point: a model call *is* an
input boundary. It is the one place where data enters the study that no amount of reading
the code can verify — which is precisely why it deserves a name of its own rather than
being filed under "reads a file".

**Checks:**
- *Static:* the body reaches a model client (`openai`, `anthropic`, `client.messages.create`,
  `.completion`). Such a call must **not** appear inside a `@functional` — a straightforward
  placement check, and one the framework can enforce today.
- *Static (the valuable one):* the failure path must not fabricate. A bare
  `except: return {}` around a model call **silently invents a data point** — it turns an
  API timeout into a research observation. Flag any model call whose exception handler
  returns a default instead of raising or recording a failure.
- *Runtime/provenance:* inherited from `@data_input` (the boundary must actually be
  crossed), plus: the call must record model id, prompt version, temperature, and the raw
  response. `annotate_lni.py` already has `response_log()` and `_complete_with_retries` —
  the annotation would make that discipline *checkable* rather than merely present in one
  file and absent in the other three.

**In the testbed:** 16 functions, including `classify_paper`, `_complete_with_retries`,
`annotate_missing`, `check_saia`, and the `main` of every LLM-calling module.

**A distinction worth naming in the paper:** `@model_call` marks where a model is *in the
loop at runtime*. That is a different provenance question from *"a model wrote this
code"* — and a framework aimed at AI-generated research software should not conflate them.
Code an LLM authored is audited by reading it (which is what `@functional` + formula
inference are for). Code that *calls* an LLM produces data no amount of reading can
verify.

---

### `@human_input(coders=..., codebook=...)` ⊂ `@data_input` — the answer came from a *person*

**Marks:** a boundary where human-produced data — a coding, an annotation, a gold
standard, an adjudication — enters the study.

**The audit question:** *"Who coded this, against which codebook, and did they agree?"*
This is `@model_call`'s sibling and its necessary complement. A study that annotates with
an LLM is judged against a **human** reference, so the human boundary carries as much
methodological weight as the model boundary — and the framework was equally blind to both.
Note that the two must not be conflated even though a reviewer will call them both
"annotation": one produces the data under test, the other produces the standard it is
tested against.

**Checks:**
- *Static:* inherited from `@data_input` — the boundary must actually be crossed (the body
  must read something). A `@human_input` that reads no source is a mislabelled path helper.
- *Static (the valuable one):* **a multi-coder source must be reachable from an inter-coder
  reliability statistic.** If a function reads more than one coder's file and nothing in the
  call graph computes an agreement figure over it, the study is presenting a subjective
  coding as if it were a measurement. In the testbed `compute_icr.py` *does* close this loop
  — the annotation would make the loop **checkable** instead of merely present.
- *Provenance:* coder identity and codebook version go into the run record, exactly as model
  id and prompt version do for `@model_call`.

**In the testbed:** 18 functions, 14 of them direct — `load_coders` (`compute_icr.py:64`),
`other_coder_suggestions` (`build_goldstandard.py:77`), `_coded_paper_ids` and
`_rejected_paper_ids` (`annotate_lni.py:636`, `:653`), `collect_coder_categories`
(`sync_coder_categories.py:96`).

**A naming trap the detector is built around, and which belongs in the paper.** In this
codebase `annotations_*_checkpoint.csv` is the **LLM's** output, while `coding_*.csv` and
`gold_human_*.csv` are the **coders'**. The word *annotation* therefore means the exact
opposite of human provenance here — so the detector keys on path literals (`coding_`,
`gold_human`, `goldstandard`, `coder`, `codebook`) and never on that token. It also ignores
**prose**: the first run fired on three argparse `help=` strings that merely *mention* the
goldstandard. A filename is evidence about where data came from; a sentence about the data
is precisely the thing the hazard axis exists to stop trusting.

---

### `@external_tool(name=..., version=...)` — the computation left the process

**Marks:** a call to a subprocess, shell command, or external binary — `subprocess.run`,
`Popen`, `os.system`, `shutil.which`.

**The audit question:** *"What version of that tool did you run?"* When a pipeline shells
out to `pdftotext`, `quarto`, or its own estimator script, the invoked binary is **as much
a part of the method as the code that calls it** — and it is not in the repository, not in
`requirements.txt`, and not in the paper. A reader who reproduces the code exactly can
still get a different result.

This is the one hazard with **no dataflow parent**, and that is the finding: `subprocess.run`
reads no file and writes no file *from the caller's point of view*, so the four annotations
classify a shell-out as an in-memory transform — the same failure mode as `classify_paper`,
in a different disguise.

**Checks:**
- *Static:* the body reaches a subprocess API. `shell=True` is reported separately, because
  it makes the *shell* part of the method too.
- *Static:* the exit status must be checked. A `subprocess.run` whose `returncode` is never
  inspected turns a failed tool into a silently truncated dataset.
- *Provenance:* the tool's name and resolved **version** must land in the run record, and a
  missing binary must fail loudly rather than degrade.

**In the testbed:** 6 functions, 3 of them direct — `run_estimator` (`pool_manager.py:143`)
and the `main`s of `pipeline_menu.py` and `topup_goldstandard.py`. Propagation does real
work here: `pool_manager.main` inherits `@external_tool` two levels up from `run_estimator`,
through `ensure_final` and `draw_pretest`.

---

### `@statistical(defines=..., cites=...)` ⊂ `@functional` — this computes a reported number

**Marks:** a function computing a statistic, metric, or effect size that the paper reports.

**The audit question:** *"Is your α actually Krippendorff's α?"*

**Check:** a `@statistical` function **must be pinned by a `differential_check` against a
reference implementation, or carry a citation to its definition** — and the runner can
*fail* one that has neither. This is the proposal with the least new machinery:
`differential_check` already exists, `krippendorff_reference.py` already *is* the pattern,
and the whole `FORMULA_INFERENCE.md` argument (isolate the maths, render it, pin it against
a trusted implementation) is written up. The library has the verification harness and **no
annotation that triggers it**. `@statistical` is the missing trigger.

**In the testbed:** 7 functions — `compute_dimension_icr`, `alpha_nominal`,
`alpha_from_matrix`, `coincidence_stats`, `_library_alpha`, `gate_agreement`,
`n_disagreements` — currently 4 `@mapping` and 1 `@functional`, i.e. the pipeline's most
result-bearing functions are labelled with its least informative tag.

**The detector must insist on an actual computation.** A name hint alone is not evidence:
`write_icr_outputs` *writes* the α, `load_icr_progress` *reads* it, and `_ask_fix_icr` is a
menu prompt that mentions it. None of them compute anything. Requiring arithmetic or an
aggregation call in the body (and excluding file boundaries) cut the false positives from
14 hits to 7 real ones.

---

## 5. Tier 2 — worth having

### `@unit_of_analysis` ⊂ `@mapping` — this changes *which units* are in the dataset

**Marks:** a function that drops, filters, or subsets records — anything where
`n_out < n_in`. It is a `@mapping` (a collection goes in, a collection comes out) whose
*cardinality changes*, and that change is a methodological decision, not a transformation.

**The audit question:** *"How did you get from N=1200 to N=87?"* Every reviewer of an
empirical study asks this, and the answer is currently scattered across 18 modules that
call `.drop`/`filter`/`.isin`. Marking the boundary lets the runner **emit an attrition
trace automatically** — a CONSORT-style flow diagram assembled from the pipeline itself
rather than reconstructed by hand at writing time.

**Check:** wrap the function, compare input/output cardinality, and require that any drop
be logged with a reason. A `@unit_of_analysis` that silently drops rows fails.

**In the testbed:** 39 functions — the largest hazard class, across `filter_positives.py`,
`select_candidates.py`, `narrow_categories.py`, `prepare_workingset.py`.

This is the proposal with the highest novelty — it is aimed squarely at *research* auditing
rather than software auditing, and I am not aware of an annotation framework that does it.

### `@config` — a threshold, hyperparameter, or path

**Marks:** the constant/config providers. The coverage run found **26 functions that return
a value, take no input, and do no I/O** — and the framework has no annotation for a single
one of them. They are currently invisible.

**The audit question:** *"What thresholds did you use?"* Research results hinge on a
`0.67` α cutoff or a `max_text_chars` truncation, and those numbers are exactly what a
replication needs and what a paper's methods section forgets.

**Check:** dump every `@config` value into the run's provenance record. Optionally, flag
magic numbers in `@statistical`/`@unit_of_analysis` bodies that are not reachable from a
`@config`.

---

## 6. Tier 3 — defensible, lower priority

**`@human_decision`** — a step where a *person*, not the machine, decides **at run time**
(`build_goldstandard.py`, `confirm_positives.py`, `compute_icr.py`, `pipeline_menu.py` all
call `input()`; 25 functions in total). It is the run-time twin of `@human_input`: that one
marks where a human *judgement already made* is read back from disk, this one marks where
the program **stops and asks**. They co-occur — `record_new_category` carries both — and the
distinction matters because only the second can be answered differently on a re-run, which
is why the decision, the decider and the timestamp must be logged.

**`@validation`** — a guard asserting a property of the data (`check_schema_integrity.py`,
`preflight.py`; 7 functions). This one has an unusually satisfying static check: **a
validation function that is never called on the main path is a silent hole**, and the AST
can prove it. A `@validation` nobody invokes is worse than no validation at all, because it
looks like safety. The scan already reports this (it appends *"never called anywhere in the
tree"* to the reason).

---

## 7. Two structural changes the proposals imply

**Split `@mapping`, don't extend it.** At 54% of candidates it is a junk drawer, and every
proposal above carves a *checkable claim* out of it. What remains after the carve — genuine
format shuffling — is fine, and *deserves* to be the boring residual. That is the point:
after this change, `@mapping` meaning "nothing interesting happens here" becomes
informative, because the interesting things now have names.

**Allow multiple annotations per function.** The registry is currently one-kind-per-function,
and the proposals break that immediately: `stratified_sample` is `@stochastic` **and**
`@unit_of_analysis`; `check_saia` is `@model_call` **and** `@validation`. The two axes are
orthogonal by construction —

- **dataflow role**: `functional` / `mapping` / `data_input` / `data_output` — *where does data flow?*
- **audit hazard**: `model_call` / `human_input` / `external_tool` / `stochastic` / `statistical` / `unit_of_analysis` / `human_decision` / `validation` / `config` — *where can the result be wrong?*

— so a function has **one dataflow role and zero or more hazards**, not one tag in total.
This is the single change that makes the framework about *research* software rather than
software in general, and it is worth stating as the contribution.

---

## 8. Status: Tier-1 detection is implemented

The cheapest high-value increment was **detection before enforcement**: report the hazards
in `coverage.py` without yet writing a decorator, a registry change, or a runtime check.
That is now done (`scan_path` populates `FunctionRecord.hazards`; both renderers show the
tables), and it answers the question that decides whether the taxonomy split is worth the
paper:

```
Audit hazards (109/254 eligible functions, 43%)
hazard             n   specialises
@model_call        16  @data_input
@human_input       18  @data_input
@external_tool      6  --
@stochastic        11  @functional
@statistical        7  @functional
@unit_of_analysis  39  @mapping
@human_decision    25  --
@validation         7  --
@config            26  --

Reproducibility-critical (36)
```

**43% of `lni_study` is an audit hazard rather than plumbing** — and the four dataflow
annotations can see none of it. The 36 "reproducibility-critical" functions (those carrying
a *direct*, non-inherited provenance hazard: `@model_call`, `@human_input`, `@external_tool`,
`@stochastic` or `@statistical`) are the shortlist a reviewer would actually want, and the
framework could not previously produce it.

The two provenance boundaries are of comparable size — **16 model calls and 18 human
inputs** — which is the empirical case for making them siblings rather than folding either
into `@data_input`. Half this study's data was produced by a machine and half by people, and
until now the framework could see neither.

Three further mechanisms fell out of the implementation and are worth keeping:

- **Provenance hazards propagate along the call graph.** `classify_paper` never touches the
  OpenAI client — it calls `_complete_with_retries`, which does. A caller inherits the
  hazard, marked `indirect`. This is what makes the map usable on real code, where the
  dangerous call is always three layers down. Only the four "where did this value come from?"
  hazards travel (model, person, subprocess, RNG); `@config` and `@validation` are properties
  of the function itself and do not contaminate a caller.
- **Annotated functions are still screened.** Carrying `@mapping` does not exempt you: the
  scan flags `compute_dimension_icr` as `@statistical` *even though it is already
  annotated*, and `load_coders` as `@human_input` on top of its `@data_input` — the
  orthogonality of the two axes showing up as a concrete result.
- **Evidence, not vocabulary.** Each detector was tightened until every direct hit was real:
  RNG that only feeds a retry backoff is not `@stochastic`; a file boundary named after a
  statistic does not compute one; prose mentioning the goldstandard is not `@human_input`;
  and a local helper called `run` is not a shell-out. Each of those false positives is now a
  regression test.

**What is not yet built:** the decorators themselves, the registry change that allows
multiple kinds per function, and the runtime checks (same-seed determinism, cardinality
tracing, provenance records). Detection is a worklist; enforcement is the contribution.

*(Housekeeping, unrelated to the taxonomy: the scan currently includes `src/annotate_lni.fix.py`,
`src/confirm_positives.fix.py` and `src/confirm_positives.prebak.py`, which inflates every
count — 3 of the 29 modules are backups. `coverage.py` should grow an `--exclude` glob.)*

## 9. Idea (not yet built): the "danger zone" across SemRepo

`lni_study` is a single testbed — one study we happen to know intimately. It answers
*"does the scan find real hazards in code we understand?"* but not *"how large is the
reproducibility-critical surface across research software in general?"* The scanner is
already the right instrument for that second question: it is pure static AST, imports
nothing, calls no network and needs no LLM, so it runs unchanged on any checkout.

**The corpus.** [SemRepo](https://github.com/faerber-lab/SemRepo) (Faerber Lab, TU Dresden)
is an RDF knowledge graph of ~197k GitHub repositories linked to scientific publications —
fine-grained per-repo metadata (contributors, issues, dependencies, languages), a public
SPARQL endpoint, and Zenodo dumps. It is ~95% Jupyter / ~5% Python. That gives a *sampling
frame of already-curated research software* plus the metadata to slice it (by field, by
dependency, by whether a paper links back).

**The measurement — the "danger zone."** For a sampled repo, run `scan_path` and report the
audit-hazard density: fraction of eligible functions that are hazards, and the tighter
"reproducibility-critical" fraction (direct `@model_call` / `@human_input` /
`@external_tool` / `@stochastic` / `@statistical`). `lni_study` sits at 43% / 36 functions;
the open question is where a *distribution* of research repos sits, and how the
reproducibility-critical fraction correlates with field, size, or dependency set. That
per-repo critical fraction is the "danger zone": the share of the code an auditor cannot take
on trust.

**The "assuming code was generated" framing.** The hazards matter most when the code was
LLM-generated and shipped with little review — nobody wrote down the seed, the coder pool,
the tool version, or which number is the reported statistic. Treating the whole corpus *as
if* generated turns the danger-zone fraction into an estimate of the per-repo provenance
surface an auditor (or the paper's own reviewer) would have to reconstruct by hand. It also
sets up the framework's actual pitch: the same scan a human runs post-hoc is the checklist a
generator should have to satisfy up front.

**What it needs first (why it is not started):**
- `.ipynb` → source extraction, since ~95% of the corpus is notebooks (the scanner is
  `.py`-only today).
- The `--exclude` glob from §8 — at corpus scale, backup/vendored files would skew every
  distribution.
- A clone/scan/aggregate harness over a SemRepo sample (SPARQL to pick the frame, then
  per-repo scan → one hazard-density row), with clear reporting of what was sampled and
  what was dropped (unparseable files, empty repos).
- A precise, pre-registered definition of "danger zone" (which hazards, direct-only vs
  inherited, per-function vs per-line) before any number is quoted.

Standalone from the habilitation, like the rest of this package. Not yet generating — captured
here so the evaluation design is on record.

**Detail:** the full sketch — why the AST scanner is already a corpus instrument, the precise
danger-zone definition, the notebook-parsing gap (95% of SemRepo is `.ipynb`), the
clone/scan/aggregate harness, exact code hook points, sequenced next steps and threats to
validity — is in [`SEMREPO_EVALUATION.md`](SEMREPO_EVALUATION.md).
