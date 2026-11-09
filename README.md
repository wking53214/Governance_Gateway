# Governance_Gateway

An adversarially tested, domain-independent **admission boundary** for governed artifacts. Version `0.1.0`. Stdlib only. Python ≥ 3.11. Apache-2.0.

It answers one question: is this artifact well-formed, untampered, and carrying the fields it claims? It never repairs, rewrites or promotes an artifact.

## Authority: read this first

- **An authority record is a claim, not proof.** `Authority(actor, grant)` holds two non-empty strings. Their presence does not show that the grant was issued, is current, or permits the operation.
- **Admission is not authorization.** Admission means the artifact passed the gateway's checks. Authorization means permission to perform a specific operation. This package does not grant it.
- **DEVELOPMENT** (default) accepts any well-formed authority record without verification.
- **PRODUCTION** (`profile=GatewayProfile.PRODUCTION`) refuses to run without a caller-supplied `authority_verifier` that the caller trusts. The package ships no verifier and no key.
- **The verifier receives only the `Authority`**, not the artifact, its scope, or the requested action.
- **Not implemented:** issuer signatures, grant expiry, revocation, action or scope binding, replay protection. See `docs/AUTHORITY_CONTRACT.md` for each item's status.

See `ARCHITECTURE.md` (trust model), `SECURITY.md` (threat model and reporting), and `INVARIANTS.md` (what is guaranteed).

## Where it sits in STACK

Three terms are used with these meanings throughout:

- **Live decision path**: the sequence in which `observe-perceive` runs its gates. Governance_Gateway is its **first** stage, the early admission boundary.
- **Evidence SPINE**: the sequence in which a document passes through five repositories. Governance_Gateway is its **fourth** stage.
- **CNS**: the coordinating contract. It holds the gate shapes and the roster that combines the five verdicts. It does not replace any of the five repositories.

These are two different workflows. Do not call either one simply "the pipeline".

### The evidence SPINE (canonical order)

| Order | Repository | Responsibility |
|---|---|---|
| 1 | HERALD | Reads source material and extracts claims. |
| 2 | TIE | Records and connects evidence. |
| 3 | Conservation_Kernel | Evaluates the evidence root and conservation requirements. |
| 4 | **Governance_Gateway** (this repository) | Judges artifact admission and returns acceptance or refusal. |
| 5 | CCC | Evaluates admission into its evidence store and handles its own write boundary. |

CNS coordinates the five gate judgments: it binds each to the subject and coordinates the resulting decision. It is not a replacement for any of the five.

`chains/evidence_spine.py` in the CNS repository runs the spine end to end. That script, not this repository, wires it.

### The STACK live decision path

```text
ADMISSION (this repository)
    → OBSERVATION   OBSERVE / interconnected_alpha
    → INTERLOCKS    interconnected_zeta
    → POLICY        PERCEIVE (observe-perceive)
    → DECISION      interconnected_beta
    → CONSERVATION  Conservation_Kernel
    → EXECUTION     caller-supplied callable / GSA-815
    → CUSTODY       interconnected_delta / sentinel_os
```

[`observe-perceive`](https://github.com/wking53214/observe-perceive) wires this repository in through `gateway_admission_adapter.py`, which imports `GovernanceGateway` and calls `evaluate`. It passes no `authority_verifier`. A refusal here is `NOT_ADMITTED`: the artifact never reached policy. It is not a policy `REJECTED`.

Question this repository answers: *is this artifact well-formed, untampered, scoped, provenanced, and carrying an authority record?*
Question it does **not** answer: *is this request permitted under policy?* That is PERCEIVE.

### Companion repositories

- [CNS](https://github.com/wking53214/CNS): the shared gate contract. This package's optional connector (section 6) produces its gate shape.
- [Conservation_Kernel](https://github.com/wking53214/Conservation_Kernel): judges a root built from evidence. Its epistemic vocabulary differs from this gateway's, so a caller maps between them.
- [CCC](https://github.com/wking53214/CCC): the store behind the door. It has its own write-permission gate. This gateway writes nothing, so it has no write to gate.
- [HERALD](https://github.com/wking53214/HERALD) and [TIE](https://github.com/wking53214/TIE): upstream of the gateway in the spine. This package imports neither and does not read their output.
- [observe-perceive](https://github.com/wking53214/observe-perceive): the live-path consumer described above.

This repository has no runtime imports of sibling packages. The one exception is the optional CNS connector, which loads `cns.gate` only when one of its functions is called.

## What the gateway validates

### Artifact contract

| Field | Type | Requirement |
|---|---|---|
| `artifact_id` | `str` | Non-empty. Identity. |
| `payload` | JSON-like | Frozen recursively (`MappingProxyType` / tuples). |
| `provenance` | non-empty `Mapping` | Origin. An empty mapping is `MISSING_PROVENANCE`. |
| `epistemic_status` | `EpistemicStatus` | Closed vocabulary: `FACT`, `INFERENCE`, `ASSUMPTION`, `RECOMMENDATION`, `DECISION`, `UNKNOWN`. |
| `authority` | `Authority(actor, grant)` | Both strings non-empty. Presence is not issuance (section above). |
| `scope` | `Scope` | `READ_ONLY` or `EXECUTE`. Validated and preserved; enforcement belongs to the consuming orchestrator. |
| `integrity` | 64-char lowercase hex SHA-256 | Recomputed independently; a mismatch is `INTEGRITY_FAILURE`. |

Integrity is `SHA-256(canonical_json({artifact_id, payload, provenance, epistemic_status, authority, scope}))`. Canonical JSON sorts keys, uses compact separators, `ensure_ascii=False`, and `allow_nan=False`. The digest is **recomputed** on every evaluation, never trusted as a stored string.

`Artifact.create(...)` freezes, hashes, and returns a frozen artifact. `GovernanceGateway.evaluate(artifact)` re-validates types and recomputes the digest. Any ordinary error during evaluation is returned as `INVALID_ARTIFACT`, never as an accept.

Building an artifact can also raise, before any verdict exists: a payload that contains itself, a payload nested beyond the Python recursion limit (about 5,000 levels measured), or a mapping subclass whose inspection raises. No artifact is produced, so nothing can be accepted.

### Refusal vocabulary

`MISSING_PROVENANCE` · `MISSING_AUTHORITY` · `INVALID_EPISTEMIC_STATE` · `INVALID_SCOPE` · `INTEGRITY_FAILURE` · `INVALID_ARTIFACT` · `AUTHORITY_VERIFIER_UNAVAILABLE`

Seven reason codes. `GOVERNANCE_VIOLATION` was removed on 2026-11-07: nothing produced it, and it had no admission-boundary purpose.

### Layout

```
src/governance_gateway/
    gateway.py        GovernanceGateway.evaluate
    models.py         Artifact, Authority, EpistemicStatus, Scope, GateResult, digest
    dashboard.py      GateDashboard, outcome counts only
    cns_connector.py  optional CNS adapter, loaded on demand
tests/                adversarial, integrity-bypass, unit, dashboard, authority verifier,
                      production profile; CNS tests (independence, judged content, mapping
                      against a stand-in, connector against real CNS)
```

## What acceptance and refusal mean

- **Accepted** means the artifact passed the gateway's checks: it is well-formed, its digest matches its content, and, if a verifier is set, the verifier returned literal `True`. It does **not** mean the artifact is authenticated, that the actor is authorized to act, or that the content is true. `GateResult.artifact` is the same object that was presented, unchanged.
- **Refused** means one `GateReason` says why. Nothing is repaired.
- **Caller obligation.** A refusal is a return value. The gateway cannot stop a caller from ignoring it. Downstream enforcement of refusals and of declared scope belongs to the consuming system.

## Security model and limitations

| Claim | Reality |
|---|---|
| Integrity | Unkeyed SHA-256. Detects edits that do not also replace the digest. Anyone who can replace both content and digest passes. |
| Authority | Presence check by default. With a verifier, the verifier decides; the package does not check the verifier. |
| Verifier failure | A raised exception, or any reply other than literal `True` or `False`, refuses as `AUTHORITY_VERIFIER_UNAVAILABLE`. Literal `False` refuses as `MISSING_AUTHORITY`. No verifier outcome accepts. Exception text is kept out of the verdict. |
| Production profile | Checks only that a callable exists. It does not establish that the callable is trustworthy. |
| Scope | Validated and preserved. Enforcement against downstream operations is the orchestrator's job. |
| Refusal enforcement | The gateway cannot force a caller to honour a refusal. |
| Writes and logging | Writes nothing durable. No refusal log. The optional `GateDashboard` keeps outcome counts only, which an operator may use but which are not evidence of decisions. |
| Immutability | Frozen objects are an API guarantee. They do not protect against code running in the same process. |
| Runtime | No protection against a compromised runtime. |
| Not implemented | Issuer trust, signatures, expiry, revocation, action and scope binding, replay protection, producer authentication, any service, authn, or rate limit. |

The gateway does not authenticate producers, does not persist or hash-chain across artifacts, and does not implement identity or an actor registry.

Full threat model: `SECURITY.md`. Guarantees and their limits: `INVARIANTS.md`. Verifier contract and status of each requirement: `docs/AUTHORITY_CONTRACT.md`.

## Inputs, outputs and an example

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

In: an `Artifact`, or anything else, which is refused as `INVALID_ARTIFACT`. Out: a frozen `GateResult(accepted, artifact, reason)`. `accepted=True` implies `artifact` is the input and `reason is None`.

Epistemic vocabulary: this gateway's `FACT`/`INFERENCE`/… is **not identical** to Conservation_Kernel's `FACT`/`OBSERVATION`/`ESTIMATED`/`CONFLICTED`/…. Adapters must map between them.

## CNS integration and compatibility (optional)

The package runs without CNS. Nothing is imported from CNS when the package loads, and the suite passes with CNS absent. With CNS present, `governance_gateway.cns_connector` expresses the verdict as a CNS gate result, so it can be resolved alongside other gates.

```
pip install '.[cns]'    # from a checkout of this repository
```

```python
from governance_gateway import Artifact, Authority, EpistemicStatus, Scope
from governance_gateway.cns_connector import evaluate_to_cns
from cns.gate import resolve

artifact = Artifact.create(
    artifact_id="a-1", payload={"message": "hello"}, provenance={"source": "human"},
    epistemic_status=EpistemicStatus.INFERENCE,
    authority=Authority(actor="alice", grant="review"), scope=Scope.READ_ONLY,
)
verdict = evaluate_to_cns(artifact)   # a cns.gate.GateResult, bound to the artifact
resolve([verdict])                    # PASS or TERMINAL_BREACH, fail-closed
```

| Governance_Gateway | CNS |
|---|---|
| Judges the admission door (ALPHA), before policy, decision or execution exist for the artifact. | `ALPHA` gate. The connector produces no outcome end, so `cns_chain(...).complete()` is `False` by design. |
| `accepted` | `PASS`, empty `reason`. |
| Refused, any `GateReason` | `TERMINAL_BREACH`, `reason` is the `GateReason` value unchanged. Never `RETRY`: the gateway never repairs or re-renders. |
| Native verdict that contradicts itself, or is bound to another artifact, or has a non-bool `accepted` | `TERMINAL_BREACH` with reason `INCONSISTENT_VERDICT`. A refusal with no reason is still a refusal (`NO_REASON_GIVEN`). |
| Judged content | `subject` is the `artifact_id` (or `"artifact"`). `subject_digest` covers the six governed fields **and the stored `integrity`**, at any depth or size up to the bounds below. |

How content is made digestible: scalars are read as the plain built-in values they hold, never through a subclass's methods. A mapping key that is not plain text is described, not stringified, and insertion order never reaches the digest. Containers nested more than 32 levels deep, or holding more than 10,000 values in one field, are replaced by a SHA-256 of the whole subtree, computed without recursion, with each shared node visited once. Drift below the bound is still caught. What cannot be described faithfully gets a tagged stand-in, never an exception: a non-artifact (its type), NaN, an over-long integer, a lone surrogate, an unsupported type, a missing attribute, a circular structure (the whole field), and a value whose inspection raises. The digest is tamper-evidence, not authentication.

The connector translates and decides nothing. If the gateway itself raises, the connector raises too. That is never a `PASS`.

Without CNS, the connector's functions raise `CnsNotInstalled` with the install command. The same error appears when CNS is installed but cannot be imported or lacks the names the connector uses. The connector checks for `GateChain`, `GateOutcome`, `GatePosition`, `GateResult` and `subject_digest`. It does not check a version number.

**CNS compatibility, three separate facts:**
- **Tested and pinned:** CNS v2.3.0 (`pyproject.toml`). The only version the tests run against.
- **Declared minimum interface:** none declared as a version number. The connector declares the names above. A code comment says `subject_digest` arrived in CNS 1.2.0. That is **not verified** here.
- **Verified compatibility range:** v2.3.0 only.

| Test file | Needs CNS? | Runs in CI? |
|---|---|---|
| `test_cns_independence.py`, `test_cns_judged_content.py`, `test_cns_mapping_double.py` | No (mapping tests use `tests/cns_gate_double.py`, a stand-in) | Yes, everywhere |
| `test_cns_connector.py` | Yes; skips without CNS. Also checks the stand-in is no looser than the real contract. | Yes, in the `cns` job |

With `GOVERNANCE_GATEWAY_REQUIRE_CNS=1`, a missing CNS fails the run instead of skipping it.

## Installation, examples and testing

```
pip install -e ".[test]" && pytest
```

Runnable library. Not a deployed service.

## Maturity, gaps and release status

Snapshot labels, 2026-11-07. Each result below states where it was produced.

| What | Source and state |
|---|---|
| **Current main** `d7b2749` | CI green on Python 3.11 and 3.12, with and without CNS, checked against GitHub check runs. |
| **Branch measured locally** `95e5015` plus uncommitted changes | Local runs only, not through CI. With CNS installed: 465 passed, 0 failed. With `GOVERNANCE_GATEWAY_REQUIRE_CNS=1`: 465 passed. With the `cns` import blocked: 274 passed, 1 skipped (the real-CNS connector module). |
| **Historical** `cd9cc62` | Counts were 459 and 268 at that commit. Earlier CI green there. Not a current result. |
| **Historical** evidence-spine run, 2026-11-07 | CNS's `chains/evidence_spine.py`, 56 scenarios, exit 0, 3 recorded GAPs, with Governance_Gateway at `1bede83`. **Not re-run** in this documentation pass. Not evidence of the current integration state. |
| Version and release | `0.1.0`, untagged. Tagging is the owner's decision. |
| CNS pin | The optional `cns` extra is pinned to v2.3.0 in `pyproject.toml`. |
| Branch CI | The branch measured locally has not been through CI. |
| Python floor | `Authority \| None` union syntax requires 3.11. Sibling projects declare 3.10 or newer in their project files (checked 2026-11-06, not re-checked). |

Known gaps: the authority items listed under "Security model and limitations"; the evidence-spine run is historical; CNS versions other than 2.3.0 are unverified.
