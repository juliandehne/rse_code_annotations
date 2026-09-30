# Inferring a mathematical formula from `@functional` code

**Question posed:** for code annotated `@functional`, are there *coder-verification
frameworks or formal methods* that can **infer the mathematical formula from the code
and print it for human inspection**?

**Short answer.** Recovering "the formula" from arbitrary code is undecidable in
general. But the useful case — a **pure, scalar, arithmetic** function — is tractable,
and there are real tools that *render* the formula. What no tool can do is *infer the
intended formula and prove the code matches it* without a human-supplied specification.
So the honest split is:

| Goal | Tool class | Can it infer the formula? |
| ---- | ---------- | ------------------------- |
| **Show what the code computes** (for review) | Symbolic execution (SymPy), AST→LaTeX (latexify, our AST backend) | **Yes**, for pure scalar arithmetic |
| **Pin non-arithmetic code** (loops, matrices, library calls) | Differential testing against a trusted reference | Not the formula — but it verifies the code agrees with a known-good implementation |
| **Prove the code equals a formula** | Formal verifiers (Dafny, Why3, Coq/Isabelle, KeY, CBMC) | **No** — *you* write the spec; they check code against it |

## What this framework implements (`rse_annotations/formula.py`)

Three inspection backends, each best-effort and independently optional; the runner
prints whatever each produces so a human can compare them:

1. **AST rendering** (no dependencies). Parses the function and pretty-prints each
   `return` expression as infix mathematics. Pure syntax, runs on anything, but only
   as faithful as the source — it shows, it does not simplify.

2. **SymPy symbolic execution** (`pip install sympy`). Calls the function with SymPy
   *symbols* substituted for its scalar parameters. Operator overloading makes the
   function assemble a symbolic expression instead of a number; SymPy simplifies it to
   a closed form and emits LaTeX. Applies only when the body is scalar arithmetic that
   tolerates symbolic inputs (no value-branching, no arrays, no library calls);
   otherwise it raises and we report *why* it did not apply.

3. **latexify** (`pip install latexify-py`). A dedicated AST→LaTeX converter for Python
   functions — publication-quality output, complements backend 1.

For code the symbolic backends cannot handle (loops over matrices, library calls — see
the Krippendorff case below), formula inference simply does not apply; the tactic there
is differential testing against a trusted reference, not formula rendering.

### Worked example (from the runner)

```
formula for normalize  (compute_icr.py:...)
  [AST]      normalize(...) = ((value - lo) / (hi - lo))
  [SymPy]    (-lo + value)/(hi - lo)
  [SymPy/TeX] \frac{- lo + value}{hi - lo}
  [latexify] \mathrm{normalize}(...) = \frac{value - lo}{hi - lo}
```

## The Krippendorff case — why it needs a different tactic

`compute_dimension_icr` computes **Krippendorff's α (nominal)** by delegating to the
`krippendorff` library over a coincidence matrix. Symbolic execution *cannot* recover α
from it: the value flows through pandas objects and a third-party call, not scalar
arithmetic, so SymPy has nothing to substitute into. This is the honest boundary of the
symbolic approach.

Two things *do* work here, and the branch ships both:

1. **A pure reference implementation** (`src/krippendorff_reference.py`,
   `alpha_nominal_reference`, annotated `@functional`) written as explicit scalar
   arithmetic over the coincidence matrix. Its **closed form is printable** and it is
   **differentially verified** against the trusted `krippendorff` library on the real
   goldstandard data (`tests`/runner) — this is the "coder verification" reading of the
   question: verify the *code that scores the coders* against an independent oracle.

2. **The canonical formula, for human inspection:**

   Krippendorff's alpha (nominal level of measurement):

   ```
   alpha = 1 - D_o / D_e
   ```

   with observed and expected disagreement built from the coincidence matrix `o`:

   ```
   D_o = (1/n) * sum_{c<k} o_{ck} * delta(c,k)          # delta(c,k)=1 for c!=k (nominal)
   D_e = (1/(n*(n-1))) * sum_{c<k} n_c * n_k * delta(c,k)
   ```

   where `n_c` is the total number of pairable values of category `c` and
   `n = sum_c n_c`. For the nominal metric `delta` is 0/1, so α reduces to
   `1 - (n-1) * (sum of off-diagonal coincidences) / (n_.. minus diagonal terms)`.

## Where formal methods fit (the honest ceiling)

Tools like **Dafny**, **Why3**, **Coq/Isabelle**, **KeY** and **CBMC** are
*verification*, not *inference* engines: you state `ensures result == <formula>` (or a
property such as `0 <= alpha <= 1`, symmetry, or agreement⇒α=1) and they prove the code
satisfies it. They are the natural *next* step once a human has confirmed the formula a
backend printed — but they cannot supply the formula themselves. That is exactly why the
`@functional` workflow here is **print-for-inspection first** (this module), with
differential testing and formal verification as follow-ons.
