# Execution report: Governance_Gateway documentation and contract closure

Date: 2026-11-07. Branch: `race/governance-gateway-closure-2026-11-07` (created from `main` at `d7b2749`). **No commits, no pushes.** All changes are in the working tree for owner review.

Status labels: EXECUTED, INSPECTED, INFERRED, UNKNOWN, NOT IMPLEMENTED.

## 1. Baseline (Phase 0)

- Repository: `wking53214/governance_gateway` (remote `origin`), local path `/home/claude/governance_gateway`. EXECUTED.
- Start state: branch `main` synced to `origin/main` at `d7b2749`, working tree clean, no stashes. EXECUTED.
- Python 3.13.18. CNS 2.3.0 installed in this environment. ruff 0.15.22 installed to match CI. EXECUTED.
- Baseline results at `d7b2749`:
  - `python -m pytest` with CNS: 452 passed, 0 failed.
  - With `sys.modules['cns'] = None`: 261 passed, 1 skipped (`tests/test_cns_connector.py`, module-level skip).
  - `ruff check .`: all checks passed. EXECUTED.

### Documentation inventory (every file)

| File | Type | Read completely |
|---|---|---|
| README.md | Markdown | Yes |
| ARCHITECTURE.md | Markdown | Yes |
| INVARIANTS.md | Markdown | Yes |
| SECURITY.md | Markdown | Yes |
| docs/AUTHORITY_CONTRACT.md | Markdown | Yes |
| LICENSE, NOTICE | Text | NOTICE read; LICENSE is the Apache-2.0 text, not inspected line by line |
| .github/workflows/tests.yml | CI config | Yes |
| pyproject.toml | Package metadata | Yes |
| Module and class docstrings in src/governance_gateway/*.py | Embedded docs | Yes (cns_connector.py in full, gateway.py, models.py, dashboard.py, __init__.py) |
| Docstrings in tests/*.py | Embedded docs | Headers and test names read; not every line |
| .ghost_baseline.json | Tool data, not documentation | Not read |

Generated and untracked (not documentation): `src/governance_gateway.egg-info/`, `__pycache__/`.

## 2. Files inspected

All of the above, plus every test module under `tests/` (names and structure) and `tests/test_cns_connector.py` and `test_authority_verifier.py` in full.

## 3. Findings and resolutions

| # | Finding | Evidence | Resolution | Status |
|---|---|---|---|---|
| F1 | Revocation contract contradicted itself (decision-time checks vs. short-lived grants) | docs/AUTHORITY_CONTRACT.md section 1 vs. section 3 | Rewrote the contract. Decision B (short-lived grants, no revocation list) is the only one stated. Revocation is bounded by grant lifetime and is not immediate. No registry added. | EXECUTED (docs). Revocation itself: NOT IMPLEMENTED. |
| F2 | Verifier exception was reported as `MISSING_AUTHORITY`, which implies the grant is invalid | gateway.py: `except Exception: verified = False` | Exceptions now return new reason `AUTHORITY_VERIFIER_UNAVAILABLE`. Exception text is not in the verdict. | EXECUTED; tested. |
| F3 | Verifier input is only `Authority`, not artifact context | gateway.py call site | Not changed. A new request object would change the public signature `authority_verifier(Authority) -> bool`. Documented as NOT IMPLEMENTED (R14). | Deferred; see Section 6. |
| F4 | Non-literal-True answers | gateway.py `answer is not True` | Behaviour unchanged: refused as `MISSING_AUTHORITY`. Documented. The "malformed response" category has no separate code. | EXECUTED; tested. |
| F5 | ARCHITECTURE.md described the old verifier order | ARCHITECTURE.md line 49 | Rewritten to the actual order. | EXECUTED. |
| F6 | README: scope wording "cannot be executed by omission" overstated enforcement | README | Reworded: gateway validates and preserves scope; enforcement belongs to the orchestrator. | EXECUTED. |
| F7 | README: four measurement snapshots mixed; test counts out of date (450/259) | README maturity, release, CI sections | One snapshot now: base `cd9cc62` plus uncommitted changes, 2026-11-07. Counts updated: 459 with CNS, 268 passed and 1 skipped without. The spine run keeps its own labelled commit (`1bede83`). | EXECUTED. |
| F8 | CNS minimum version: connector error text said "v1.4.0 or newer", its comments said subject_digest arrived in 1.2.0, and the code checks only for names | cns_connector.py, README | Error text now says the connector checks names, not a version. README states the version is not verified; the only tested CNS version is 2.3.0. | EXECUTED. CNS 1.2.0 and 1.4.0 claims: UNKNOWN. |
| F9 | Authority, verification, authorization and admission used loosely | README, ARCHITECTURE | README defines the four terms. | EXECUTED. |
| F10 | No production deployment requirements in SECURITY.md | SECURITY.md | Added "Deployment requirements" section. | EXECUTED. |
| F11 | Caller can ignore a refusal; PRODUCTION does not prove verifier trust | INVARIANTS, SECURITY | Stated in INVARIANTS ("What the gateway cannot enforce") and SECURITY. | EXECUTED. |
| F12 | INVARIANTS did not give the exact canonical form or verifier failure semantics | INVARIANTS | Added canonical form, verifier failure semantics, dashboard isolation. | EXECUTED. |
| F13 | Deep, cyclic and oversized payloads: behaviour undocumented | Probes (see Section 5) | Documented in INVARIANTS and README. Tests added. | EXECUTED; tested. |
| F14 | `GOVERNANCE_VIOLATION` is defined and never produced | models.py; README | Removed from `GateReason` on maintainer decision (option A). README and tests updated. This is a public-API removal. | **Decision needed** (Section 6). |
| F15 | Stale claim: README says CI was green at `c8b0afd` | README | Replaced with `cd9cc62`, and a note that the working-tree changes have not been through CI. | EXECUTED. |
| F16 | README Python-floor claim about sibling repos ("checked 2026-11-06") | README | Not re-verified in this run. | UNKNOWN. |
| F17 | README spine-run claim (56 scenarios, exit 0 on 2026-11-07) | README | Not re-executed; CNS's evidence_spine.py was not run here. | UNKNOWN (historical record). |

## 4. Code changes

| File | Change | Public API effect |
|---|---|---|
| src/governance_gateway/models.py | Added `GateReason.AUTHORITY_VERIFIER_UNAVAILABLE` | Additive enum member |
| src/governance_gateway/gateway.py | Verifier exception returns the new reason; non-True returns `MISSING_AUTHORITY`; comment updated | Behaviour change: a raising verifier now reports `AUTHORITY_VERIFIER_UNAVAILABLE` instead of `MISSING_AUTHORITY`. Refusal still occurs. |
| src/governance_gateway/cns_connector.py | Error message for an incompatible CNS only | Message text only |

No signatures changed. No function was removed. No dependency was added.

## 5. Tests

### Test changes (existing assertions)

1. `tests/test_authority_verifier.py`: `test_a_verifier_that_raises_refuses_the_artifact` renamed to `..._as_unavailable`; its expected reason changed from `MISSING_AUTHORITY` to `AUTHORITY_VERIFIER_UNAVAILABLE`. Intended change (F2).
2. `tests/test_cns_connector.py`: `test_the_corpus_reaches_every_reason_the_gateway_can_give` now excludes `AUTHORITY_VERIFIER_UNAVAILABLE`, with a comment. The corpus has no verifier, so it cannot produce that reason; the reason is tested in `test_authority_verifier.py`.

No test was removed.

### Tests added

- `tests/test_authority_verifier.py` (3): outage does not leak exception text; a `False` answer is `MISSING_AUTHORITY` not an outage; a production outage refuses and never accepts.
- `tests/test_adversarial.py` (4): a self-containing payload cannot be sealed (`RecursionError`); a payload nested 5,000 levels cannot be sealed; an oversized payload (200,000 elements) is accepted as sealed and refused after a one-element change; a mapping subclass whose `items()` raises cannot be sealed.
- Parametrized cases from the new enum member: 2 (`test_cns_connector`, `test_cns_mapping_double`).

### Results (EXECUTED)

| Command | Baseline `d7b2749` | This branch |
|---|---|---|
| `python -m pytest` (CNS 2.3.0 installed) | 452 passed | **459 passed**, 0 failed |
| `GOVERNANCE_GATEWAY_REQUIRE_CNS=1 python -m pytest -rs` | not run at baseline | **459 passed** |
| `sys.modules['cns']=None; pytest` (CNS absent) | 261 passed, 1 skipped | **268 passed, 1 skipped** (skip: `tests/test_cns_connector.py:20`, module needs CNS) |
| `ruff check .` (ruff 0.15.22) | passed | **passed** |

Per-file counts were compared; every change is accounted for by the tests listed above.

### README examples (EXECUTED)

Both Python blocks in README.md were extracted and executed. The first block (`Artifact` example) ran unchanged. The second (CNS example) referred to an undefined `artifact`; I added its construction, and it now runs.

### Adversarial probes (EXECUTED, not all added as tests)

| Input | Result |
|---|---|
| Payload nested 200 deep, judged | Accepted |
| Payload nested 5,000 deep | `RecursionError` at construction |
| Self-containing list or dict | `RecursionError` at construction |
| Mapping subclass with raising `items()` | `RuntimeError` at construction |
| String subclass with raising `__str__` and `__eq__` as a value | Accepted; its text is digested through the built-in string type (connector) |
| 200,000-element list | Accepted |

## 6. Decisions needed and deferred work

### Decision taken

- **D1. `GOVERNANCE_VIOLATION` removed** (maintainer chose option A, 2026-11-07). It was never produced and had no admission-boundary purpose. Consequence: a public enum member is gone. Consumers that refer to it will break. I have not checked the sibling repositories for references to it.

### Deferred (NOT IMPLEMENTED)

- Trusted issuer identity, signature verification, expiry field, revocation registry, action binding, scope-to-artifact binding in the verifier, replay protection, a verifier request object (R14).
- Each is listed in `AUTHORITY_REQUIREMENTS_MATRIX.md` with the dependency it needs.

### Assumptions made (narrowest safe choice)

- A verifier answer that is not `True` stays `MISSING_AUTHORITY` (no separate malformed-response code). This avoids another enum member without a stated need.
- The verifier interface stays `Authority -> bool`. Changing it is a public-API break, so I did not do it.
- The revocation decision (B) is taken as recorded by the maintainer on 2026-11-07.

## 7. Remaining limitations and risks

- Not run through GitHub CI (the branch is not pushed). Only local runs.
- CNS versions other than 2.3.0 are not tested. The CNS minimum version is UNKNOWN.
- The cross-repository spine script (`chains/evidence_spine.py` in CNS) was not run.
- Bandit was not run. It is not part of this repository's CI.
- The `cns` extra installs from a git tag over the network; this run used a pre-installed CNS 2.3.0.
- `AUTHORITY_VERIFIER_UNAVAILABLE` is a new refusal code. Consumers that match on `MISSING_AUTHORITY` for verifier exceptions will see a different code.
- Immutability is an API guarantee only (unchanged).
- Declared scope is not enforced by the package (unchanged).

## 8. Files modified (uncommitted)

Also changed in the final step: `src/governance_gateway/models.py` (removed `GOVERNANCE_VIOLATION`), `tests/test_cns_connector.py` (reached-set exclusion now only the verifier reason).

ARCHITECTURE.md, INVARIANTS.md, README.md, SECURITY.md, docs/AUTHORITY_CONTRACT.md, src/governance_gateway/models.py, src/governance_gateway/gateway.py, src/governance_gateway/cns_connector.py, tests/test_adversarial.py, tests/test_authority_verifier.py, tests/test_cns_connector.py.

New (uncommitted): EXECUTION_REPORT.md, DOCUMENTATION_CROSSWALK.md, AUTHORITY_REQUIREMENTS_MATRIX.md.

No CNS, PERCEIVE, Conservation_Kernel, CCC, sentinel_os, or other repository was changed. No user changes were overwritten.

## 9. Exit criteria

1. Every discovered documentation file inspected: MET (see inventory; tests/ docstrings checked by name only).
2. Every substantive claim checked or marked: PARTIAL. F16 and F17 are UNKNOWN.
3. Authority contract contradictions resolved: MET (F1).
4. Verifier input and failure behaviour coherent and tested: MET for failure behaviour; input contract deferred (R14).
5. Dashboard failure semantics documented and tested: MET (existing tests `test_a_failing_dashboard...`, `test_dashboard_never_changes_the_decision`).
6. CNS connector claims match implementation: MET for claims checked; the version claim is UNKNOWN (F8).
7. Dead or misleading API resolved: MET for `GOVERNANCE_VIOLATION` (removed). Other public symbols reviewed; none removed.
8. README examples match the API: MET.
9. Tests pass with and without CNS: MET.
10. CI-equivalent checks pass: MET locally, not on GitHub.
11. No unrelated changes: MET.
12. No user changes overwritten: MET.

**Status: all exit criteria met locally.** Items marked UNKNOWN (F16, F17, and the CNS version claim) are labelled, not verified. Nothing is committed, pushed, or run through GitHub CI.
