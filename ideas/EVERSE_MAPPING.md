# EVERSE mapping — how rse_annotations relates to EVERSE

Status: research note, 2026-09-30. Companion to `RESPONSIBLE_RSE_PLUGINS.md` (the 15
Responsible-RSE stubs) and `INSPECTION_COMPONENTS.md` (proposed inspection components).
Figures (counts, versions) were read from the live EVERSE APIs / packages on this date;
anything not checked against a primary source is marked **[unverified]**.

## 1. What EVERSE is

**EVERSE — European Virtual Institute for Research Software Excellence** (https://everse.software/).
Horizon Europe, grant 101129744 (HORIZON-INFRA-2023-EOSC-01-02), 1 Mar 2024 – 28 Feb 2027
(per [CORDIS](https://cordis.europa.eu/project/id/101129744)), coordinated by CERTH and BSC,
with the five EOSC Science Clusters. Goal: a framework for research-software quality and
recognition of software as a first-class research output.

| Component | What it is | Where |
|---|---|---|
| **RSQKit** | Research Software Quality Kit: ~39 task pages (licensing, testing, security, archiving, …), roles, research-software stories, AI guidance, indicator and tool index | https://everse.software/RSQKit/ ; tasks: https://everse.software/RSQKit/tasks |
| **Three-tier model** | RSQKit's classes of research software: *analysis code*, *prototype tools*, *research software infrastructure* — quality expectations scale with the tier | https://everse.software/RSQKit/three_tier_view |
| **Quality dimensions** | 13 dimensions (v1.0, updated 2026-09-09): ISO/IEC 25010 characteristics (functional suitability, performance efficiency, compatibility, interaction capability, reliability, security, maintainability, flexibility, safety) plus FAIRness, open source software, community, sustainability | https://w3id.org/everse/i/dimensions/ ; JSON: https://everse.software/indicators/api/dimensions.json |
| **Quality indicators** | 47 indicators, each with an IRI `https://w3id.org/everse/i/indicators/<id>` and one dimension (e.g. `software_has_license`, `no_leaked_credentials`, `functional_correctness`) | https://github.com/EVERSE-ResearchSoftware/indicators ; JSON: https://everse.software/indicators/api/indicators.json |
| **TechRadar** | Curated catalogue of 71 quality tools (JSON-LD per tool: `hasQualityDimension`, `improvesQualityIndicator`, `howToUse`, `license`) | https://everse.software/TechRadar/ ; JSON: https://everse.software/TechRadar/api/tools.json ; repo https://github.com/EVERSE-ResearchSoftware/TechRadar |
| **resqui** (QualityPipelines) | CLI (`pip install resqui`, 0.2.0, MIT) that checks indicators on a repository URL via plugins and writes JSON in the EVERSE assessment schema; GitHub Action `resqui-github-action` | https://github.com/EVERSE-ResearchSoftware/QualityPipelines ; docs https://everse.software/QualityPipelines/ |
| **DashVERSE** | Dashboard for assessment results | https://everse.software/services/dashverse/ |
| **schemas / reference-framework** | Metadata schemas for indicators, dimensions and assessments; the EVERSE reference framework | https://github.com/EVERSE-ResearchSoftware/schemas , …/reference-framework |
| **Training / TeSS** | Training material (CC-BY-4.0) and a TeSS catalogue | https://github.com/EVERSE-ResearchSoftware/training |
| **Deliverables** | D2.1 software-quality aspects ([10.5281/zenodo.14978234](https://doi.org/10.5281/zenodo.14978234)); D3.1 tools & services ([10.5281/zenodo.14978326](https://doi.org/10.5281/zenodo.14978326)); D3.2 RSQKit tools catalogue ([10.5281/zenodo.17091643](https://doi.org/10.5281/zenodo.17091643)); MS9 metadata framework for indicators and pipelines ([10.5281/zenodo.16940413](https://doi.org/10.5281/zenodo.16940413)); D2.2 knowledge hub ([10.5281/zenodo.17241346](https://doi.org/10.5281/zenodo.17241346)) | https://everse.software/resources/deliverables_milestones/ |

**resqui 0.2.0 plugins** (read from the wheel): `HowFairIs` → `has_license`;
`CFFConvert` → `has_citation`; `Gitleaks` → `has_no_security_leak`; `SuperLinter` →
`has_no_linting_issues`; `OpenSSFScorecard` → `has_ci_tests`, `human_code_review_requirement`,
`has_published_package`, `project_is_active`, `static_analysis_common_vulnerabilities`,
`dependency_management`, `no_critical_vulnerability`, `uses_fuzzing`; `RSFC` →
`persistent_and_unique_identifier`, `software_has_documentation`, `requirements_specified`,
`has_releases`, `software_has_license`, `descriptive_metadata`, `versioning_standards_use`,
`version_control_use`, `software_has_tests`, `software_has_citation`, `repository_workflows`,
`archived_in_software_heritage`, `has_contribution_guidelines`. A plugin is a class with an
`indicators` list and one method per indicator taking `(url, branch_hash_or_tag)` — close
to our `Analyzer` idea, but repository-level and network-first.

### The key difference

EVERSE measures the **software as a product** — repository-level signals about metadata,
process, security posture and community, mostly checkable from a URL. rse_annotations
measures the **research validity of the code** — function-level checks keyed by role
annotations (`@functional`, `@data_input`, `@statistical`, …), offline by default, ending
in human verdicts. The only EVERSE indicator aimed at the correctness of analysis code,
`functional_correctness`, asks whether a quantifiable correctness measure is *reported*;
it does not inspect how results are computed. The two are complementary: our tool is a
natural provider of evidence for a handful of EVERSE indicators, and EVERSE is the
obvious community vocabulary to report against.

## 2. EVERSE dimensions → our analyzers

Built-ins: Math, IO, Convention, Coverage, Hazard. Stubs by number from
`RESPONSIBLE_RSE_PLUGINS.md`. "IC §x" = proposal in `INSPECTION_COMPONENTS.md` (not built).

| EVERSE dimension | Relevant EVERSE indicators | Built-in analyzers | Stubs | Planned (IC) |
|---|---|---|---|---|
| [functional_suitability](https://w3id.org/everse/i/dimensions/functional_suitability) | `functional_correctness`, `passed_tests_ok`, `human_code_review_requirement` | **Math** (formula for human check), **IO** (boundaries really read/write) | #3 UnjustifiedConstant, #7 DataLeakage, #8 InferenceLedger | IC §2.1 test linkage, §2.7 mutation testing |
| [reliability](https://w3id.org/everse/i/dimensions/reliability) | `software_has_tests` | **IO**, **Hazard** (unseeded randomness) | #2 SilentFailure | IC §2.2 determinism, §2.10 numerical robustness |
| [maintainability](https://w3id.org/everse/i/dimensions/maintainability) | `has_no_linting_issues`, `uses_tool_for_warnings_and_mistakes`, complexity/duplication/cohesion/coupling indicators, `requirements_specified`, `has_ci-tests` | **Convention** (annotation fits code), **Coverage** (annotation coverage) | #2, #3 | IC §2.4 dependencies, §2.14 complexity as review cost |
| [security](https://w3id.org/everse/i/dimensions/security) | `static_analysis_common_vulnerabilities`, `no_critical_vulnerability`, `no_leaked_credentials`, `has_no_binary_artifacts` | — | #5 ResearchSecurity, #10 PurposeRetention (data protection) | IC §2.5 privacy + secrets, §2.4 pip-audit |
| [safety](https://w3id.org/everse/i/dimensions/safety) (risk identification, hazard warning) | `uses_fuzzing` | **Hazard** (model calls, human input, external tools, statistics) | #15 DualUse, #10 | IC §2.10 (Hypothesis) |
| [fairness](https://w3id.org/everse/i/dimensions/fairness) (= *FAIRness*) | `software_has_license(_for_file_types)`, `software_has_citation`, `codemeta_completeness`, `descriptive_metadata`, `persistent_and_unique_identifier`, `archived_in_software_heritage`, `archived_in_scholarly_repository`, `has_releases`, `versioning_standards_use`, `code_documentation_coverage_ok` | **Coverage** (closest analogue of documentation coverage) | #1 Licence, #6 DataTerms, #13 Archival | IC §2.12 FAIR/citation files |
| [sustainability](https://w3id.org/everse/i/dimensions/sustainability) | `software_test_coverage`, `software_is_containerized` | — | #13 (truck factor) | IC §2.1, §2.4 |
| [open_source_software](https://w3id.org/everse/i/dimensions/open_source_software) | `has_active_contributors`, `has_contribution_guidelines`, `response_timeframe_ok`, `has_active_communication_channels` | — | #13 (Scorecard, ci) | — (gap G2) |
| [community](https://w3id.org/everse/i/dimensions/community) | (no indicator yet) | — | #14 InclusiveLanguage | — |
| [interaction_capability](https://w3id.org/everse/i/dimensions/interaction_capability) (incl. *inclusivity*) | `software_has_documentation` | — | #11 FigureAccessibility, #14 | — |
| [performance_efficiency](https://w3id.org/everse/i/dimensions/performance_efficiency) | (none) | — | #12 ComputeFootprint | IC §2.8 energy |
| [compatibility](https://w3id.org/everse/i/dimensions/compatibility) | `dependency_management` | — | #1 (licence compatibility) | IC §2.4 lockfile/SBOM |
| [flexibility](https://w3id.org/everse/i/dimensions/flexibility) | `has_published_package` | — | — | — |

No EVERSE dimension or indicator covers: algorithmic fairness (#9), data licensing and
consent (#6), GDPR purpose/retention (#10), LLM use inside the research pipeline (#4),
inferential practice (#8), data leakage (#7), or dual use (#15).

## 3. RSQKit tasks → analyzers

| RSQKit task | Ours |
|---|---|
| [Licensing software](https://everse.software/RSQKit/licensing_software) (REUSE, SPDX; discusses dependency/copyleft compatibility) | #1 Licence |
| [Improving research software security](https://everse.software/RSQKit/research_software_security) (Scorecard, gitleaks, Bandit, OWASP Dependency-Check, Dependabot/Renovate) | #5 ResearchSecurity; IC §2.4/§2.5 |
| [Using static analysis](https://everse.software/RSQKit/static_analysis), [Writing readable code](https://everse.software/RSQKit/writing_readable_code) | Convention; #2, #3 |
| [Testing software](https://everse.software/RSQKit/testing_software) | IO, Math; #7; IC §2.1, §2.7 |
| [Performing a code review](https://everse.software/RSQKit/code_review) | Math (formula for the reviewer), `inspection.yaml` verdicts |
| [Documenting code](https://everse.software/RSQKit/documenting_code), [Creating a good README](https://everse.software/RSQKit/creating_good_readme) | Coverage (partial); gap G5 |
| [Archiving software](https://everse.software/RSQKit/archiving_software), [Software identifiers](https://everse.software/RSQKit/software_identifiers), [Citing software](https://everse.software/RSQKit/citing_software), [Releasing software](https://everse.software/RSQKit/releasing_software) | #13 Archival; IC §2.12 |
| [Software metadata](https://everse.software/RSQKit/software_metadata), [CodeMeta](https://everse.software/RSQKit/complete_software_metadata_codemeta), [FAIR RS](https://everse.software/RSQKit/fair_rs) | IC §2.12; #6 (for *data*); gap G3 |
| [Reproducible software environments](https://everse.software/RSQKit/reproducible_software_environments), [Using containers](https://everse.software/RSQKit/using_containers) | Hazard (external tools); IC §2.4; gap G4 |
| [Improving environmental sustainability](https://everse.software/RSQKit/improving_environmental_sustainability) (Green Algorithms, CodeCarbon, carbontracker) | #12 ComputeFootprint; IC §2.8 |
| [Creating and enforcing a code of conduct](https://everse.software/RSQKit/code_of_conduct) | #14 (adjacent); gap G2 |
| [Computational workflows](https://everse.software/RSQKit/computational_workflows) | Hazard, provenance (IC §2.3) |
| [Software Management Planning](https://everse.software/RSQKit/software_management_planning), [three-tier model](https://everse.software/RSQKit/three_tier_view) | — (gap G6) |
| [AI guidance](https://everse.software/RSQKit/ai) (gen-AI intensity levels 0–10 in *development*) | #4 is adjacent (LLMs in the *pipeline*); gap G7 |
| [CI/CD](https://everse.software/RSQKit/ci_cd), [GitHub Actions](https://everse.software/RSQKit/task_automation_github_actions) | — (gap G8) |

## 4. Stubs: EVERSE anchors, tools to reuse or cite, difficulty

`difficulty` (class attribute on each stub, defined in `_stub.py`): expected student
workload of 1–5 hours per week over a ~12–14-week semester to implement the check at a
reasonable level with tests. Total for all 15: 40 h/week-equivalents, i.e. a group of
~10–13 students at 3–4 h/week.

| # | Stub | EVERSE anchor | Reuse / cite from EVERSE | Diff. | Rationale |
|---|---|---|---|---|---|
| 1 | `LicenceComplianceAnalyzer` | [software_has_license_for_file_types](https://w3id.org/everse/i/indicators/software_has_license_for_file_types), [RSQKit licensing](https://everse.software/RSQKit/licensing_software) | TechRadar: REUSE, Choose a License; resqui HowFairIs/RSFC check presence only | 3 | SPDX/REUSE are off the shelf; dependency licences + a compatibility table (OSADL, CC-BY-4.0) need design and fixtures |
| 2 | `SilentFailureAnalyzer` | [has_no_linting_issues](https://w3id.org/everse/i/indicators/has_no_linting_issues), dim. reliability | TechRadar: Ruff; RSQKit static analysis | 2 | pure AST on a fixed pattern list |
| 3 | `UnjustifiedConstantAnalyzer` | [functional_correctness](https://w3id.org/everse/i/indicators/functional_correctness) (closest) | RSQKit writing readable code | 2 | AST + comment lookup; effort is in the whitelist |
| 4 | `LLMDisclosureAnalyzer` | [RSQKit AI guidance](https://everse.software/RSQKit/ai) (adjacent) | cite intensity spectrum as the *development-side* counterpart | 2 | static checks on existing `model_call` records + a template |
| 5 | `ResearchSecurityAnalyzer` | [static_analysis_common_vulnerabilities](https://w3id.org/everse/i/indicators/static_analysis_common_vulnerabilities), [RSQKit security](https://everse.software/RSQKit/research_software_security) | TechRadar: bandit, Gitleaks, OpenSSF Scorecard, Dependabot; resqui Gitleaks/Scorecard plugins | 2 | Bandit/osv-scanner detect; work is filtering to annotated code |
| 6 | `DataTermsAnalyzer` | none (EVERSE gap); [RSQKit FAIR RS](https://everse.software/RSQKit/fair_rs) | — | 3 | new kwargs + licence propagation + Croissant/model-card validation |
| 7 | `DataLeakageAnalyzer` | [functional_correctness](https://w3id.org/everse/i/indicators/functional_correctness) | RSQKit testing software | 4 | intra-procedural dataflow + runtime hashing; tools too heavy to reuse |
| 8 | `InferenceLedgerAnalyzer` | [functional_correctness](https://w3id.org/everse/i/indicators/functional_correctness) | — | 5 | runtime instrumentation of 3 libraries + matching to outputs + recomputation |
| 9 | `FairnessAnalyzer` | none (EVERSE "fairness" = FAIRness) | — | 3 | fairlearn computes; capturing predictions and groups needs design |
| 10 | `PurposeRetentionAnalyzer` | none; dim. [security](https://w3id.org/everse/i/dimensions/security) loosely | — | 3 | depends on a `personal_data` hazard; careful GDPR reading |
| 11 | `FigureAccessibilityAnalyzer` | dim. [interaction_capability](https://w3id.org/everse/i/dimensions/interaction_capability) (inclusivity) | — | 3 | savefig hook, colour extraction, CVD simulation, visual fixtures |
| 12 | `ComputeFootprintAnalyzer` | [RSQKit environmental sustainability](https://everse.software/RSQKit/improving_environmental_sustainability) | cite Green Algorithms, CodeCarbon as RSQKit recommends | 2 | EcoLogits (offline) estimates; work is hooking + disclosure text |
| 13 | `ArchivalSustainabilityAnalyzer` | [archived_in_software_heritage](https://w3id.org/everse/i/indicators/archived_in_software_heritage), [RSQKit archiving](https://everse.software/RSQKit/archiving_software) | TechRadar: Software Heritage, Zenodo, OpenSSF Scorecard; resqui RSFC (`archived_in_software_heritage`, `has_releases`, `versioning_standards_use`) | 3 | several sub-checks + network parts that need mocking |
| 14 | `InclusiveLanguageAnalyzer` | dim. [community](https://w3id.org/everse/i/dimensions/community), [RSQKit code of conduct](https://everse.software/RSQKit/code_of_conduct) | — | 1 | rules file + tokenizer scan, `info` only |
| 15 | `DualUseScreeningAnalyzer` | dim. [safety](https://w3id.org/everse/i/dimensions/safety) (risk identification, hazard warning) | — | 2 | code is a keyword map; building a defensible map is the work |

Every stub should, once implemented, declare the EVERSE indicator IRIs it provides
evidence for (see G1), so findings can be aggregated in EVERSE terms.

## 5. Gaps: plugin ideas EVERSE suggests that we do not cover

Not covered by a built-in, a stub, or an `INSPECTION_COMPONENTS.md` proposal.

| # | Idea | Difficulty |
|---|---|---|
| G1 | **`EverseExport`** — write audit findings as an EVERSE assessment (JSON-LD, indicator IRIs), optionally run resqui as a `ci` backend, so results show up in DashVERSE. Needs a mapping `Analyzer → indicator IRI` and the schema from `EVERSE-ResearchSoftware/schemas`. | 3 |
| G2 | **`CommunityHealthAnalyzer`** (`ci`) — contribution guidelines, code of conduct, issue tracker, communication channels, response time (`has_contribution_guidelines`, `support_issue_tracking`, `response_timeframe_ok`, …). Mostly files + GitHub/GitLab API; reuse resqui's RSFC/Scorecard results. | 2 |
| G3 | **`MetadataConsistencyAnalyzer`** — `CITATION.cff`, `codemeta.json`, `pyproject.toml` and the git tag agree on version, authors, licence (`codemeta_completeness`, `metadata_is_up_to_date`, `versioning_standards_use`). IC §2.12 only checks presence. Tools: somesy, cffconvert, codemetapy. | 2 |
| G4 | **`ContainerReproducibilityAnalyzer`** — Dockerfile/Apptainer/Nix/Guix present for `@external_tool` pipelines; base images pinned by digest, unpinned `apt`/`pip` installs (`software_is_containerized`, RSQKit containers/environments). Tools: Hadolint (TechRadar). | 2 |
| G5 | **`AnnotatedDocumentationAnalyzer`** — docstring coverage *of annotated functions* and of what matters there (units, assumptions, `cites=`), plus README sections per RSQKit (`code_documentation_coverage_ok`). Tool: interrogate. | 1 |
| G6 | **`TierProfile`** — author declares the RSQKit tier (analysis code / prototype tool / infrastructure) and optionally a Software Management Plan; the audit selects checks and scales severities accordingly. Touches the audit core, so it needs coordination. | 2 |
| G7 | **`AIAssistedDevelopmentAnalyzer`** — record the RSQKit gen-AI *intensity level* used to write the code; detect traces (`CLAUDE.md`, `AGENTS.md`, `.github/copilot-instructions.md`, co-author trailers) and require a human-review verdict for AI-written annotated functions (`human_code_review_requirement`). | 2 |
| G8 | **`CIIntegrationAnalyzer`** — the audit and the tests actually run in CI (`has_ci-tests`, `repository_workflows`); parse workflow YAML. | 1 |

Already covered elsewhere (not gaps): secrets (`no_leaked_credentials`) in IC §2.5 — add
gitleaks for git *history*; complexity indicators in IC §2.14; tests/coverage in IC §2.1;
fuzzing (`uses_fuzzing`, aimed at memory-unsafe languages) roughly by Hypothesis in IC §2.10.

## 6. What rse_annotations does that EVERSE does not

- **Function-level, role-aware checks.** EVERSE indicators are per repository; ours are per
  annotated function and escalate with hazard (a swallowed exception in `@statistical` is
  worse than in a CLI helper).
- **Validity of the analysis itself**: formula extraction for review (Math), boundary
  truthfulness (IO), reproducibility hazards (Hazard), leakage, multiple testing,
  unjustified cut-offs — EVERSE's `functional_correctness` only asks whether a measure is reported.
- **Responsible-research questions** EVERSE does not address: data licences and consent,
  GDPR purpose/retention, algorithmic fairness, LLMs *inside* the research pipeline,
  dual use, accessible figures.
- **Human verdicts as first-class output** (`inspection.yaml`) rather than pass/fail scores.
- **Offline, LLM-free by default**; network checks are `ci` only. resqui is network- and
  Docker-first.

## 7. Verification notes

Verified on 2026-09-30 against: the EVERSE site and RSQKit pages linked above; the
indicator/dimension/TechRadar JSON APIs (counts 47 / 13 / 71); the `resqui-0.2.0` wheel
(plugin classes and indicator methods); CORDIS (via search snippet) for dates and grant.
Discrepancy noted: TechRadar lists REUSE as `GPL-3.0-only`; the `reuse` 6.2.0 package
metadata says `GPL-3.0-or-later` (plus Apache-2.0/CC0/CC-BY-SA for parts).
**[unverified]**: the RSQKit task count (~39) is from the task index on this date and
changes often; DashVERSE's exact input format was not inspected.
