# Runtime hazards: record, then analyse

Status: proposal (2026-09-30), nothing implemented yet. It covers the `when = "runtime"` plugins:
`footprint` (energy / CO2e, including remote LLM calls) and `inference_ledger` (how many tests,
models and prompts were tried before the reported one), plus any future hazard that can only be
measured while the code runs.

## The problem

Every other hazard can be judged from the source tree (`static`), from a test run (`test`) or from
the repository metadata (`ci`). Energy use, LLM tokens, the number of fitted models or the random
seeds actually drawn only exist **during a real run of the pipeline**. `Audit.run()` cannot start
that run: it does not know the command, the data or the hardware, and a full research run may take
days.

## Proposal: split measuring from judging

```
  producer's real run                          any later audit
┌─────────────────────────┐   ledger file   ┌──────────────────────────────┐
│ annotated code          │ ──────────────▶ │ runtime plugin.analyze()     │
│  + probes (opt-in)      │ .rse_runtime.   │  reads the ledger, reports   │
│                         │    jsonl        │  findings like any plugin    │
└─────────────────────────┘                 └──────────────────────────────┘
```

1. **Record.** The probes sit in the decorator wrappers the annotations already install
   (`annotations/decorators.py` wraps every annotated function). They are **off by default**
   and switched on with an environment variable, so annotated code costs nothing in normal use:

   ```bash
   RSE_ANNOTATIONS_PROBES=time,energy,model_calls python run_pipeline.py
   ```

   Each probe appends one JSON line per event to `<root>/.rse_runtime.jsonl`: function
   qualname, annotation kind, wall time, and probe-specific fields (joules from
   CodeCarbon / pyRAPL, tokens and model name from an LLM client hook, the estimator class
   and score from a `fit` hook). Code that is not annotated can still be measured through
   explicit hooks (`model_call`, `run`) that the stubs already list in their `hooks` attribute.
   A pytest plugin (`pytest -p rse_annotations.probes`) sets the variable for test runs, so
   `when = "test"` hazards get the same mechanism.

2. **Analyse.** A runtime plugin is an ordinary `Plugin` with `when = "runtime"`. Its
   `analyze(target)` reads the ledger through a shared helper (a new top-level folder,
   `runtime/`, next to `scan/`, holding the probe registry, the ledger format and the reader),
   aggregates, and returns findings. For example: "412 Wh, ≈ 150 g CO2e (±40 %), 38 % from
   remote LLM calls", or "@functional `fit_model` ran with 27 different hyper-parameter sets;
   the paper reports one".

3. **No ledger, no verdict.** `available()` is true, but `analyze()` returns
   `self.result(skipped="no runtime ledger: run the pipeline with RSE_ANNOTATIONS_PROBES=…")`.
   That way `--analyze` stays green on a fresh checkout and tells the producer exactly what to do.
   A stale ledger (older than the newest source change) gives a `warn`.

## Why this shape

- **Same abstraction level.** Runtime hazards stay plugins with one `analyze(target)`; only
  where their evidence comes from differs. The general entry point needs no new mode.
- **Reusable machinery.** Probes and the ledger live outside any plugin, like `scan/` and
  `inspection/`, so `footprint` and `inference_ledger` share one recording mechanism.
- **Annotations earn their keep.** The marks tell the probes *which* functions matter:
  energy per `@functional`, I/O volume per `@data_input` / `@data_output`, number of calls
  per `@mapping`. That is the "producers support the inspection" idea applied at runtime.
- **Reproducible evidence.** The ledger is a plain file that can be committed with the results
  or attached to the paper, so the reported footprint can be checked later.

## Open questions

- Probe overhead: energy counters need sampling; keep them per function call, or per process?
- Ledger size for long runs: aggregate on write (counters per qualname) instead of one line per call?
- Privacy: prompts must never be logged, only token counts and model names.
- Several runs: key the ledger by a run id and let plugins pick the latest or compare runs.
