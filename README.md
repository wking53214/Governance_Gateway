# Governance_Gateway

Adversarially tested, domain-independent **admission boundary** for governed artifacts. Version `0.1.0`. Stdlib only. Python ≥ 3.11.

## Role in the STACK spine

**Purpose.** Governance_Gateway is the admission door for one kind of object, the `Artifact`: a frozen record that says what it is (`payload`), where it came from (`provenance`), how sure it is (`epistemic_status`), who claims the right to act on it (`authority`), how far it may reach (`scope`), and a SHA-256 over all of that (`integrity`). `GovernanceGateway.evaluate` answers one question: is this artifact well-formed, untampered, scoped, provenanced and carrying an authority record? The answer is `accepted` or a refusal with one `GateReason`. It never repairs, rewrites or promotes.

**Responsibilities (all in `src/governance_gateway/gateway.py` and `models.py`).**
- Refuse anything that is not an `Artifact`, has a blank id, empty provenance, a wrong-typed authority, epistemic status or scope, or a malformed or mismatched digest (recomputed, never trusted).
- Optionally ask a caller-supplied `authority_verifier(Authority) -> bool` whether the authority is genuinely held. Off by default; when set, anything other than `True`, or any exception, is `MISSING_AUTHORITY`.
- Optionally count outcomes in a `GateDashboard` (records only, changes no decision).
- Optionally (extra `cns`) express its verdict as a CNS gate result at the ALPHA end (`cns_connector.py`).

**Inputs and outputs.** In: an `Artifact` (or anything, which is refused as `INVALID_ARTIFACT`). Out: a frozen `GateResult(accepted, artifact, reason)`. With the connector: a `cns.gate.GateResult` bound to the artifact by `subject_digest`. It writes nothing durable.

**Owns.** The artifact contract and its canonical digest; the seven-member refusal vocabulary; the decision at the admission door; the translation of that decision into CNS's gate shape (`cns_connector.py`).

**Does not own.** Policy permission (PERCEIVE). Whether content is true. Issuing, registering or expiring authority (the optional verifier is the caller's, not this package's). Producer authentication (SHA-256 is integrity, not authenticity). Persistence or any ledger (CCC, sentinel_os). Whether a door actually opens after a verdict: CNS's roster decides that in the spine, and the receiver's own policy permits. The gateway judges; it does not permit.

**Relationship to companions.**

```text
 HERALD ──export──> TIE ──evidence──> Conservation_Kernel
 (reads, claims)    (records)         (judges a root before ancestry)
                                              │  (caller-written step, no repository ships it)
                                              v
                                   Governance_Gateway  <-- this repository: ALPHA, admission door
                                              │
                                              v
                                  CCC (judges ingest into its store)

 CNS: holds the shapes (gate, PASS/RETRY/TERMINAL_BREACH) and the roster that combines the five verdicts.
      Each of the five repositories above supplies one gate; CNS never replaces any of them.
```

- [CNS](https://github.com/wking53214/CNS): shared gate contract. `chains/evidence_spine.py` runs HERALD, TIE, Conservation_Kernel, this gateway and CCC on one document and imports `governance_gateway.cns_connector.CnsGate` (`chains/evidence_spine.py:142`). That script, not this repository, wires the spine.
- [Conservation_Kernel](https://github.com/wking53214/Conservation_Kernel): judges a root artifact built from evidence. Its epistemic vocabulary differs from this gateway's; a caller maps between them.
- [CCC](https://github.com/wking53214/CCC): the store behind the door. It has its own write-permission gate; this gateway has no write to gate.
- [HERALD](https://github.com/wking53214/HERALD) and [TIE](https://github.com/wking53214/TIE): upstream. This package imports neither and does not read their output.
- [observe-perceive](https://github.com/wking53214/observe-perceive): the other consumer. `gateway_admission_adapter.py` imports `GovernanceGateway` and the models (lines 58-64) and calls `evaluate` (line 111). It does not pass an `authority_verifier`.
- CCCb and Link: no import, reference or code path in this repository. No relationship is claimed.

**CNS interaction: PARTIAL.** Implemented as an optional adapter, not part of the core and not on the default path.

| Evidence | Status |
|---|---|
| `src/governance_gateway/cns_connector.py:190-204` imports `cns.gate` on demand (`importlib.import_module`); `:525` `CnsGate`, `:557` `cns_chain`, `:568` `evaluate_to_cns`, `:482` `to_cns_result` | implemented, optional |
| `src/governance_gateway/__init__.py` imports no CNS; `tests/test_cns_independence.py` checks it | implemented |
| `cns_interop` (UAI-1 signed messages), `cns_composition` (roster, super gate, decision guard) | absent: no import in `src/` or `tests/` (grep, 2026-10-31) |
| An omega end, `RETRY` outcome, or a complete CNS chain | absent by design (`cns_chain(...).complete()` is `False`) |
| Gateway receiving or emitting UAI-1 envelopes itself | absent |

It is partial because only the gate shape is used. A real spine seat is exercised by CNS's own script, not by a test here.

**Maturity and limitations (measured 2026-10-31 on main `4339185`, Python 3.13, pytest 9.2.0, CNS 2.3.0 from a local checkout).**
- `python -m pytest`: 432 passed, 0 failed, 0 skipped. `GOVERNANCE_GATEWAY_REQUIRE_CNS=1 python -m pytest`: 432 passed.
- With the `cns` import blocked (`sys.modules['cns'] = None`): 241 passed, 1 skipped (the real-CNS connector module).
- Version `0.1.0`, untagged. Library only: no service, no authn, no refusal log. Without an `authority_verifier`, any non-empty actor and grant string passes. `GOVERNANCE_VIOLATION` is never produced.

## 1. Pipeline Position & Role

**ADMISSION: the door filter.** First stage of the live decision path.

```text
ADMISSION (this repo)
    → OBSERVATION   OBSERVE / interconnected_alpha
    → INTERLOCKS    interconnected_zeta
    → POLICY        PERCEIVE (observe-perceive)
    → DECISION      interconnected_beta
    → CONSERVATION  Conservation_Kernel
    → EXECUTION     caller-supplied callable / GSA-815
    → CUSTODY       interconnected_delta / sentinel_os
```

Wired into the live path by [`observe-perceive`](https://github.com/wking53214/observe-perceive) via `gateway_admission_adapter.py`. Refusal here is **`NOT_ADMITTED`** (artifact never reached policy), **not** a policy `REJECTED`.

Question it answers: *is this artifact well-formed, untampered, and explicitly scoped, provenanced, and authorized-as-metadata?*  
Question it does **not** answer: *is this request permitted under policy?* That is PERCEIVE.

## 2. Full System Scope & Architectural Depth

The gateway is a **non-transforming validation boundary**. It evaluates an immutable `Artifact` and returns `ACCEPT` or `REJECT` with an explicit `GateReason`. It never repairs, promotes, rewrites, or silently coerces.

### Artifact contract

| Field | Type | Requirement |
|---|---|---|
| `artifact_id` | `str` | Non-empty. Identity. |
| `payload` | JSON-like | Frozen recursively (`MappingProxyType` / tuples). |
| `provenance` | non-empty `Mapping` | Origin. Empty mapping is `MISSING_PROVENANCE`. |
| `epistemic_status` | `EpistemicStatus` | Closed vocab: `FACT`, `INFERENCE`, `ASSUMPTION`, `RECOMMENDATION`, `DECISION`, `UNKNOWN`. |
| `authority` | `Authority(actor, grant)` | Both strings non-empty. Presence of a grant string is **not** issuance of authorization. |
| `scope` | `Scope` | `READ_ONLY` or `EXECUTE`. A read-scoped artifact cannot be executed by omission. |
| `integrity` | 64-char lowercase hex SHA-256 | Independently recomputed; mismatch → `INTEGRITY_FAILURE`. |

Integrity is `SHA-256(canonical_json({artifact_id, payload, provenance, epistemic_status, authority, scope}))`. Canonicalization sorts keys, uses compact separators, `ensure_ascii=False`, `allow_nan=False`. Equivalent governed data must hash identically. The digest is **recomputed**, never trusted as a stored string.

`Artifact.create(...)` freezes, hashes, and returns a frozen dataclass. `GovernanceGateway.evaluate(artifact)` re-validates types and recomputes the digest. Unexpected exceptions fail closed as `INVALID_ARTIFACT`.

### Rejection vocabulary

`MISSING_PROVENANCE` · `MISSING_AUTHORITY` · `INVALID_EPISTEMIC_STATE` · `INVALID_SCOPE` · `INTEGRITY_FAILURE` · `INVALID_ARTIFACT` · `GOVERNANCE_VIOLATION`

`GOVERNANCE_VIOLATION` is defined and unused by `evaluate()` today. It exists for a future caller-supplied policy hook that this package does not implement.

### Layout

```
src/governance_gateway/
    gateway.py        GovernanceGateway.evaluate
    models.py         Artifact, Authority, EpistemicStatus, Scope, GateResult, digest
    dashboard.py      GateDashboard, outcome counts only
    cns_connector.py  optional CNS adapter, loaded on demand (section 8)
tests/                adversarial, integrity-bypass, unit, dashboard, authority_verifier; CNS independence, judged content,
                      mapping (against tests/cns_gate_double.py) and connector (real CNS)
```

## 3. What It Does NOT Do / Non-Goals

- Does **not** decide policy permission (PERCEIVE).
- Does **not** issue, revoke, or verify cryptographic authorization grants. `Authority.grant` is a non-empty string; there is no grant registry, KMS, or signature over the grant. A caller may supply `authority_verifier` (a callable) to check that an `Authority` is held; the package ships none, and unset means any `Authority` passes.
- Does **not** transform, normalize, or "fix" invalid artifacts.
- Does **not** authenticate the producer. SHA-256 is integrity, not authenticity. An attacker who can replace both content and digest wins.
- Does **not** persist, ledger, or hash-chain across artifacts.
- Does **not** talk to OBSERVE, zeta, Conservation Kernel, or sentinel_os directly.
- Does **not** implement identity, actor registry, or session.

## 4. Brutally Honest Current Status & Gaps

| Claim | Reality |
|---|---|
| "Authorization is explicit" | `Authority.actor` + `Authority.grant` are required non-empty strings. By default no check that the grant exists, is unexpired, is scoped, or was issued by a real authority. An optional caller-supplied `authority_verifier` can refuse (fail-closed); nothing is bundled and `observe-perceive` does not set one. |
| Production admission door | Runnable library with CI (`tests.yml`). No network service, no authn, no rate limit, no durable log of refusals. |
| Scope enforcement | Gateway validates the enum. Downstream execution-scope binding is the orchestrator's job (`observe-perceive` scope-binding tests). This package cannot stop a caller who ignores `GateResult`. |
| Epistemic vocab | Gateway vocab (`FACT`/`INFERENCE`/…) is **not identical** to Conservation Kernel's (`FACT`/`OBSERVATION`/`ESTIMATED`/`CONFLICTED`/…). Adapters must map. Drift is a real seam. |
| `GOVERNANCE_VIOLATION` | Dead enum member. |
| Python 3.11+ | `Authority \| None` union syntax. α/ζ/β/δ advertise 3.9. Mixed floor. |

### Release and test status

Measured 2026-10-31 at main `4339185`. Commands and counts: see "Role in the STACK spine" above.

| What | State |
|---|---|
| Version | 0.1.0 (`pyproject.toml`) |
| Tag and GitHub Release | None yet. Tagging is the owner's decision. |
| CI on main | Green on 2026-10-30 (tests on Python 3.11 and 3.12, with and without CNS, plus ruff 0.15.22) |
| Tests | 241 passed and 1 skipped without CNS, 432 passed with CNS installed |
| CNS pin | The optional `cns` extra is pinned to the tag v2.3.0 in `pyproject.toml` |

### Which doors write

None that create a governed record. `GovernanceGateway.evaluate` judges and returns a result; it stores nothing. The one thing that keeps state is the optional `GateDashboard`, whose `record` method any holder of a reference can call, so its counts are a convenience for an operator and not evidence of what the gateway decided. That is why this repository has no write permission to gate, unlike CCC.

Runnable: `pip install -e ".[test]" && pytest`. Tests cover adversarial integrity bypass. Not a deployed service.

## 5. Core Invariants & Guarantees

- **Fail-closed:** malformed, missing, or contradictory governance state is `REJECT`, never silent `ACCEPT`.
- **Recomputation over trust:** integrity is always recalculated from canonical fields.
- **Non-transformation:** accepted artifact is the same object that was presented.
- **Immutability after freeze:** payload/provenance cannot be mutated without breaking the digest (and `frozen=True` dataclasses).
- **Explicit rejection:** every refusal carries a `GateReason`.

Does **not** guarantee: authenticity, non-repudiation, authorization, availability, or protection against a fully compromised runtime.

## 6. Inputs, Outputs & Type Contracts

```python
from governance_gateway import (
    Artifact, Authority, EpistemicStatus, Scope,
    GovernanceGateway, GateResult, GateReason,
)

artifact = Artifact.create(
    artifact_id="admit-001",
    payload={"action": "discharge", "subject_id": "p1"},
    provenance={"source": "ehr", "extracted_at": "2026-09-01T00:00:00Z"},
    epistemic_status=EpistemicStatus.INFERENCE,
    authority=Authority(actor="nurse.jsmith", grant="grant:shift-lead:2026-09-01"),
    scope=Scope.EXECUTE,
)
result: GateResult = GovernanceGateway().evaluate(artifact)
# result.accepted: bool
# result.artifact: Artifact | None
# result.reason: GateReason | None
```

`GateResult` is frozen. `accepted=True` implies `artifact` is the input artifact and `reason is None`.

## 7. Stack Integration Topology

```text
producer (human / model / system)
        │  Artifact.create(...)  : freeze and hash
        ▼
GovernanceGateway.evaluate
        │
        ├── REJECT  →  NOT_ADMITTED  (observe-perceive gateway_admission_adapter)
        └── ACCEPT  →  orchestrator preserves seal; PERCEIVE/Conservation never see unsealed junk
                            │
                            ▼
                   observe-perceive.GovernanceOrchestrator
                            │
                            ├── OBSERVE / α Keys
                            ├── ζ Locks
                            ├── PERCEIVE gates
                            ├── ConservationKernel.submit
                            ├── execution_guard.authorize_execution
                            └── δ / sentinel_os ledger
```

This repo has **zero runtime imports** of sibling packages. Integration is adapter-side, in observe-perceive. The one exception is the optional CNS connector (section 8), which loads `cns.gate` only when one of its functions is called.

### Place in the evidence spine

The evidence spine is the five repositories a document passes through in order: HERALD reads it and extracts claims, TIE records the evidence, Conservation_Kernel decides whether a root may be admitted, Governance_Gateway judges the admission door, and CCC takes the document into its store. CNS holds the roster that makes the decision, the check that every seat judged the same document, and the one-use guard that lets an approved decision open only the door it judged. `chains/evidence_spine.py` in CNS runs all of it end to end. A 2026-10-30 run of that script (30 results, all ok, one recorded GAP) is reported by an earlier version of this README; it was not re-run for this revision and is not a result of this repository's tests.

Governance_Gateway judges the admission door (the ALPHA end). It decides accept or refuse and nothing else: the refusal reason travels in the CNS verdict, and the decision about whether the door then opens belongs to the roster.

## 8. Connecting to CNS (optional)

Governance_Gateway stands alone: no runtime dependency, nothing imported from CNS when the package loads, and the whole suite passes with CNS absent. If CNS is present, `governance_gateway.cns_connector` expresses the gateway's verdict as a CNS gate result, so it can be resolved alongside gates from other repositories. The package `__init__` does not import the connector, and no module here imports `cns` by statement.

```
pip install '.[cns]'    # from a checkout of this repository; CNS is pinned to v2.3.0
```

```python
from governance_gateway.cns_connector import evaluate_to_cns
from cns.gate import resolve

verdict = evaluate_to_cns(artifact)   # a cns.gate.GateResult, bound to the artifact
resolve([verdict])                    # PASS or TERMINAL_BREACH, fail-closed
```

| Governance_Gateway | CNS |
|---|---|
| where it judges | `ALPHA`: the admission door, before policy, decision or execution exist for the artifact. A refusal is `NOT_ADMITTED` (section 1). There is no outcome end and the connector does not invent one, so `cns_chain().complete()` is `False` by design. |
| `accepted` | `PASS`, empty `reason` |
| refused, any `GateReason` | `TERMINAL_BREACH`, `reason` is the `GateReason` value unchanged. Never `RETRY`: the gateway never repairs or re-renders, and nothing here models a re-attempt. |
| a native verdict that contradicts itself (accepted with a reason, accepted for another artifact or for something that is not an `Artifact`, `accepted` not a bool) | `TERMINAL_BREACH`, `reason` is `INCONSISTENT_VERDICT`. A refusal with no reason is still a refusal (`NO_REASON_GIVEN`). |
| judged content | `subject` is the `artifact_id` (or `"artifact"`), and `subject_digest` covers the six governed fields **and the stored `integrity`**. For every artifact the gateway accepts, the digest changes if the content changes anywhere, at any depth or size (`-0.0` for `0.0` included), so a `PASS` cannot be moved onto another artifact, a forged copy, or content that drifted after the verdict. |

How the content is made digestible, without losing what the gateway accepts. Scalars are read as the plain built-in values they hold, never through a subclass's own methods. A mapping key that is not plain text (an int, an enum, a string CNS cannot encode) is described, not stringified, and insertion order never reaches the digest. Containers nested more than 32 levels deep, or holding more than 10,000 values in one field, are replaced by a SHA-256 of the whole subtree, computed without recursion and visiting each shared node once, so drift below the bound is still caught by `binds`. What cannot be described faithfully gets a tagged stand-in and never an exception: a non-artifact (its type), NaN, an over-long integer, a lone surrogate, an unsupported type, a missing attribute, a circular structure (the whole field), and a value whose inspection itself raises. The gateway refuses each of these but the last, so none of them is content a `PASS` rests on. The digest is tamper-evidence, not authentication (section 3).

The connector translates and decides nothing. If the gateway itself raises (for example `RecursionError` on a circular payload that is otherwise valid), the connector raises too; that is never a `PASS`.

Without CNS installed, the connector's functions raise `CnsNotInstalled` with the install command. The same error says so when CNS is installed but cannot be imported or lacks what the connector uses from `cns.gate`. The connector needs CNS v1.4.0 or newer. Nothing else in the package changes.

Tests: `tests/test_cns_independence.py`, `tests/test_cns_judged_content.py` and `tests/test_cns_mapping_double.py` need no CNS and run everywhere, CI included (the mapping tests run against a stand-in for `cns.gate`, `tests/cns_gate_double.py`). `tests/test_cns_connector.py` runs against the real CNS and skips when it is not installed; it also checks that the stand-in is no looser than the real contract. With `GOVERNANCE_GATEWAY_REQUIRE_CNS=1` a missing CNS fails the run instead of skipping it; CI's `cns` job installs the extra and sets it.

Apache-2.0. Commit discipline: the gateway is small on purpose. Do not grow it into a policy engine.
