# Governance_Gateway

Adversarially tested, domain-independent **admission boundary** for governed artifacts. Version `0.1.0`. Stdlib only. Python ≥ 3.11.

## 1. Pipeline Position & Role

**ADMISSION — the door filter.** First stage of the live decision path.

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
    gateway.py    GovernanceGateway.evaluate
    models.py     Artifact, Authority, EpistemicStatus, Scope, GateResult, digest
tests/            adversarial, integrity-bypass, unit
```

## 3. What It Does NOT Do / Non-Goals

- Does **not** decide policy permission (PERCEIVE).
- Does **not** issue, revoke, or verify cryptographic authorization grants. `Authority.grant` is a non-empty string; there is no grant registry, KMS, or signature over the grant.
- Does **not** transform, normalize, or "fix" invalid artifacts.
- Does **not** authenticate the producer. SHA-256 is integrity, not authenticity. An attacker who can replace both content and digest wins.
- Does **not** persist, ledger, or hash-chain across artifacts.
- Does **not** talk to OBSERVE, zeta, Conservation Kernel, or sentinel_os directly.
- Does **not** implement identity, actor registry, or session.

## 4. Brutally Honest Current Status & Gaps

| Claim | Reality |
|---|---|
| "Authorization is explicit" | `Authority.actor` + `Authority.grant` are required non-empty strings. No check that the grant exists, is unexpired, is scoped, or was issued by a real authority. |
| Production admission door | Runnable library with CI (`tests.yml`). No network service, no authn, no rate limit, no durable log of refusals. |
| Scope enforcement | Gateway validates the enum. Downstream execution-scope binding is the orchestrator's job (`observe-perceive` scope-binding tests). This package cannot stop a caller who ignores `GateResult`. |
| Epistemic vocab | Gateway vocab (`FACT`/`INFERENCE`/…) is **not identical** to Conservation Kernel's (`FACT`/`OBSERVATION`/`ESTIMATED`/`CONFLICTED`/…). Adapters must map. Drift is a real seam. |
| `GOVERNANCE_VIOLATION` | Dead enum member. |
| Python 3.11+ | `Authority \| None` union syntax. α/ζ/β/δ advertise 3.9. Mixed floor. |

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
        │  Artifact.create(...)  — freeze + hash
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

This repo has **zero runtime imports** of sibling packages. Integration is adapter-side, in observe-perceive.

Apache-2.0. Commit discipline: the gateway is small on purpose. Do not grow it into a policy engine.
