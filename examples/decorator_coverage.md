# Decorator coverage

Static (AST) scan of `C:\Users\julian.dehne\Documents\Quarto\IdeaProjects\juliandehne.github.io\publications\rse_code_annotations\examples` — nothing imported, nothing executed.

- files scanned: **4**
- functions/methods found: **10** (10 eligible; dunders, nested helpers and tests excluded)
- decorated: **8/10** (**80%** coverage)
- candidates for a decorator: **2**

## Coverage by review concern

| Decorator | Present | Candidates |
| --- | ---: | ---: |
| `@functional` | 3 | 0 |
| `@mapping` | 2 | 1 |
| `@data_input` | 1 | 0 |
| `@data_output` | 1 | 1 |
| `@hardware_dependency` | 1 | 0 |

## Coverage by file

| File | Functions | Decorated | Coverage | Candidates |
| --- | ---: | ---: | ---: | ---: |
| `fixtures.py` | 2 | 0 | 0% | 2 |
| `gpu_tensors.py` | 1 | 1 | 100% | 0 |
| `sample_pipeline.py` | 7 | 7 | 100% | 0 |

## Already decorated

| Function | File | Decorator |
| --- | --- | --- |
| `add_on_gpu` | `gpu_tensors.py:7` | `@hardware_dependency` |
| `normalize` | `sample_pipeline.py:25` | `@functional` |
| `mean` | `sample_pipeline.py:37` | `@functional` |
| `impure_sum` | `sample_pipeline.py:49` | `@functional` |
| `load_csv` | `sample_pipeline.py:58` | `@data_input` |
| `coerce_scores` | `sample_pipeline.py:71` | `@mapping` |
| `dump_json` | `sample_pipeline.py:83` | `@data_output` |
| `untidy` | `sample_pipeline.py:96` | `@mapping` |

## Audit hazards

A second, **orthogonal** axis (proposed — detected here, not yet enforced). The dataflow decorators answer *where does data flow?*; these answer *where can the result be wrong, and can I reproduce it?* A function has one dataflow role and zero or more hazards.

**1 of 10** eligible functions (**10%**) carry at least one hazard.

| Hazard | Found | Specialises | What it means |
| --- | ---: | --- | --- |
| `@model_call` | 0 | `@data_input` | output came from a language model: non-deterministic, unrepeatable, and not verifiable by reading the code |
| `@human_input` | 0 | `@data_input` | data was produced by a person (coding/annotation/gold standard): needs coder identity, a codebook version, and an inter-coder reliability figure |
| `@external_tool` | 0 | — | computation leaves the process (subprocess/shell): the tool and its **version** are part of the method and must be recorded |
| `@stochastic` | 0 | `@functional` | output depends on an RNG: reproducible only if the seed is an explicit parameter |
| `@statistical` | 0 | `@functional` | computes a reported statistic: must be pinned against a reference implementation or cite its definition |
| `@unit_of_analysis` | 0 | `@mapping` | changes which units are in the sample: every dropped record needs a reason |
| `@human_decision` | 0 | — | a person decides here, at run time: the judgement, the decider and the time must be recorded |
| `@validation` | 0 | — | asserts a property of the data: a guard nobody calls is worse than no guard |
| `@config` | 1 | — | supplies a threshold/hyperparameter: must land in the run's provenance record |

### Hazardous functions

`indirect` means the hazard was inherited through the call graph — the function does not touch the model/RNG itself, but everything it returns depends on one.

| Hazards | Function | Location | Role | Evidence |
| --- | --- | --- | --- | --- |
| `@config` | `add_on_gpu` | `gpu_tensors.py:7` | `@hardware_dependency` | returns a value with no inputs and no I/O: a threshold/parameter that belongs in the run's provenance record |

`*` = inherited through the call graph (indirect).

## Candidates

Heuristic suggestions from the syntax alone — a worklist for review, not a verdict.

| Suggested | Confidence | Function | Location | Why |
| --- | --- | --- | --- | --- |
| `@data_output` | high | `_load_csv_fixture` | `fixtures.py:14` | writes a file/sink: open("w"), write |
| `@mapping` | medium | `_dump_json_fixture` | `fixtures.py:26` | takes input, returns a transformed value, no I/O (calls join) |
