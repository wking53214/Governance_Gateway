# Authority verification contract

Status legend used throughout: **IMPLEMENTED** (code and a test in this repository), **PARTIAL** (some of it), **NOT IMPLEMENTED** (design only, or deferred), **DECIDED** (a design choice recorded by the maintainer, not a capability).

## 1. Current implementation (IMPLEMENTED)

- `GovernanceGateway(authority_verifier=f)` calls `f(authority)` once per artifact that has passed the well-formedness and integrity checks. `authority` is an `Authority(actor, grant)` and nothing else. The verifier does **not** receive the artifact, its scope, its payload or its digest.
- The verifier's answer counts only if it is literally `True`.
  - Any other return value (`None`, `False`, `1`, `"yes"`, a list) refuses the artifact with `MISSING_AUTHORITY`.
  - An exception raised by the verifier refuses the artifact with `AUTHORITY_VERIFIER_UNAVAILABLE`. The exception's text is not included in the verdict, because it may contain secrets. An outage is not evidence that the grant is invalid, so it is kept separate from `MISSING_AUTHORITY`.
- Every refusal here is fail-closed. No verifier outcome leads to acceptance.
- The verifier is not called for an artifact with a bad digest or a malformed field.
- `GatewayProfile.PRODUCTION` refuses to construct without a callable verifier, and refuses every artifact with `MISSING_AUTHORITY` if the verifier is removed later.

## 2. Decisions (DECIDED, 2026-11-07, by the maintainer)

Each decision below was taken as the recommended option. Its consequences still apply.

**A. Who holds the trust anchor?** Option 1: the operator pins issuer public keys in a file.
- Consequence: simple, auditable, no network dependency; key rotation is a file edit.
- Status: NOT IMPLEMENTED in this package. The package has no key handling at all.

**B. How are revocations delivered?** Option 1: short-lived grants, no revocation list.
- Consequence: a revoked grant stays valid until its expiry. The maximum revocation delay is the grant lifetime chosen by the issuer. Revocation is **not** immediate.
- Status: NOT IMPLEMENTED in this package. `Authority` has no expiry field, and no revocation registry exists. Expiry is the verifier's responsibility.

**C. What happens when verification cannot be completed?** Option 1: refuse with a distinct reason code.
- Consequence: fail closed; outages appear as refusals with `AUTHORITY_VERIFIER_UNAVAILABLE`.
- Status: IMPLEMENTED (section 1).

## 3. Requirements and status

| # | Requirement | Status | Notes |
|---|---|---|---|
| R1 | Trusted issuer identity is pinned by the operator | NOT IMPLEMENTED | No issuer concept in the package. Deferred to the verifier the caller supplies. |
| R2 | Grant signature is verified against that issuer | NOT IMPLEMENTED | `Authority.grant` is an opaque string. No signature checks. |
| R3 | Expired grants are refused | NOT IMPLEMENTED in the package | Expiry is the verifier's check. The gateway can only refuse what the verifier refuses. |
| R4 | Revoked grants are refused at decision time | NOT IMPLEMENTED; **contract changed** | Revocation is bounded by grant lifetime (decision B). Not immediate. |
| R5 | The grant covers this actor | IMPLEMENTED (caller-supplied) | The verifier receives the actor and decides. Tested with a stub verifier only. |
| R6 | The grant covers this action | NOT IMPLEMENTED | No action is modelled in `Artifact`. The verifier receives no action. |
| R7 | The grant covers this artifact's scope | NOT IMPLEMENTED | The verifier does not receive the artifact or its scope. Declared scope is validated and preserved, not enforced (see README). |
| R8 | Replay protection | NOT IMPLEMENTED | No nonce or replay store. |
| R9 | Verifier unavailable refuses | IMPLEMENTED | `AUTHORITY_VERIFIER_UNAVAILABLE`. |
| R10 | Verifier exception does not prove the grant invalid | IMPLEMENTED | Separate reason code from `MISSING_AUTHORITY`. |
| R11 | Non-boolean verifier answer refuses | IMPLEMENTED | Refused as `MISSING_AUTHORITY`. Not a separate "malformed response" code. |
| R12 | Tampered artifact never reaches the verifier | IMPLEMENTED | Tested by `test_verifier_is_not_called_for_an_artifact_with_a_bad_digest`. |
| R13 | Production profile refuses to run without a verifier | IMPLEMENTED | Checks only that a callable exists. |
| R14 | Verifier request object carrying artifact context | NOT IMPLEMENTED | Changing the signature would break `authority_verifier(Authority) -> bool`. Deferred as a public-API decision. |

## 4. Verifier interface

Current (IMPLEMENTED):

- Input: one `Authority` (`actor: str`, `grant: str`), both non-empty strings.
- Output: `True` to accept the authority; anything else refuses.
- Exceptions: refuse as `AUTHORITY_VERIFIER_UNAVAILABLE`.
- Called: synchronously, once per judged artifact, after integrity succeeds.
- Migration: none needed; this is the current interface.

## 5. Error and outage semantics (IMPLEMENTED)

| Situation | Verdict |
|---|---|
| No verifier, development profile | Accepted if the authority is well-formed |
| No verifier, production profile | Refused at construction (`ValueError`); if removed later, refused `MISSING_AUTHORITY` |
| Verifier returns `True` | Accepted |
| Verifier returns any other value | Refused, `MISSING_AUTHORITY` |
| Verifier raises | Refused, `AUTHORITY_VERIFIER_UNAVAILABLE`; text not in verdict |
| Artifact fails integrity | Refused before the verifier is called |

## 6. Acceptance tests and traceability

Tests are in `tests/test_authority_verifier.py`, `tests/test_production_profile.py` and `tests/test_adversarial.py`. Each requirement with a test is listed in `AUTHORITY_REQUIREMENTS_MATRIX.md`.

Requirements that cannot be tested in this repository because they are NOT IMPLEMENTED (issuer trust, signatures, expiry, revocation, action binding, replay) have no test that pretends otherwise. They become tests when the capability exists.

## 7. Out of scope for this package

- Issuing grants and running an issuer.
- Key management and key rotation.
- Producer authentication (who created the artifact).
- Persistence of grants or decisions.
- A revocation registry or revocation feed.

Do not describe any NOT IMPLEMENTED item as a security property of this package.
