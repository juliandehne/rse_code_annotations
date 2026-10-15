# Run on the testbed

The testbed is a real research pipeline: the `lni_study` repository on its branch
`feat/rse-code-annotations`. On that branch the pipeline functions are marked:

- `src/compute_icr.py`: `@data_input`, `@mapping` (twice), `@data_output`
- `src/krippendorff_reference.py`: `@calculations`, `@mapping`

The rest of its ~320 functions are unmarked. That makes it a good check of the
"detected but not marked" list: model calls to SAIA/OpenAI, seeded sampling, reading
human-coded gold-standard data, and `subprocess` calls.

## Run

```bash
python testbed/run_testbed.py                        # clone from GitHub (needs SSH access)
python testbed/run_testbed.py --repo ../lni_study    # clone from a local checkout instead
```

The script

1. clones the branch into a temporary directory (`git clone --depth 1`),
2. runs the analysis on its `src/`,
3. checks that at least 6 marked functions were found (exit code 0, otherwise 1),
4. deletes the clone.

The output ends with:

```
testbed: 6 marked functions found (ok)
```

## Options

| Flag | Effect |
|---|---|
| `--repo URL_OR_PATH` | where to clone from (default `git@github.com:juliandehne/lni_study.git`) |
| `--branch NAME` | another branch (default `feat/rse-code-annotations`) |
| `--inspect` | also start the interactive review of the marked functions |
| `--keep` | keep the clone and its `inspection.yaml`; the path is printed |

## Without the script

If you already have the branch checked out, run the runner on it directly:

```bash
git -C ../lni_study switch feat/rse-code-annotations
python -m rse_annotations ../lni_study/src
python -m rse_annotations ../lni_study/src --inspect
```

The testbed code imports `rse_annotations.differential_check`, which exists only on
`main`. This does not matter here because the scan never imports the code.
