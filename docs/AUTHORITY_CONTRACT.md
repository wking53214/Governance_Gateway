# Authority verification contract

Status legend used throughout: **IMPLEMENTED** (code and a test in this repository), **PARTIAL** (some of it), **NOT IMPLEMENTED** (design only, or deferred), **DECIDED** (a design choice recorded by the maintainer, not a capability).

## 1. Current implementation (IMPLEMENTED)

- `GovernanceGateway(authority_verifier=f)` calls `f(authority)` once per artifact that has passed the well-formedness and integrity checks. `authority` is an `Authority(actor, grant)` and nothing else. This one-argument verifier does **not** receive the artifact, its scope, its payload or its digest.
- `GovernanceGateway(artifact_authority_verifier=g)` (optional, added 2026-11-14, R14) calls `g(authority, digest)` at the same point, where `digest` is the artifact's verified integrity digest (the SHA-256 hex string the gateway recomputed and matched). Nothing else is passed: not the payload, scope or action. A verifier can bind an authority to exactly one artifact by checking the digest. The answer semantics below apply to it unchanged.
- If both verifiers are supplied, both must accept. Either one refusing refuses the artifact, with that verifier's reason. The one-argument verifier is called first, and the artifact-aware verifier is not called once it has refused.
- The verifier's answer counts only if it is literally `True`.
  - Literal `False` refuses the artifact with `MISSING_AUTHORITY`.
  - Any other return value (`None`, `0`, `1`, `"yes"`, a list) is a malformed response. It refuses the artifact with `AUTHORITY_VERIFIER_UNAVAILABLE`: a verifier that does not answer correctly is treated as failed, not as a verdict on the grant.
  - An exception raised by the verifier refuses the artifact with `AUTHORITY_VERIFIER_UNAVAILABLE`. The exception's text is not included in the verdict, because it may contain secrets. An outage is not evidence that the grant is invalid, so it is kept separate from `MISSING_AUTHORITY`.
- Every refusal here is fail-closed. No verifier outcome leads to acceptance.
- The verifier is not called for an artifact with a bad digest or a malformed field.
- `GatewayProfile.PRODUCTION` refuses to construct without at least one callable verifier (either keyword), refuses a non-callable value for either keyword at construction, and refuses every artifact with `MISSING_AUTHORITY` if all verifiers are removed later. The default profile stays `DEVELOPMENT`.

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

**D. Does the verifier receive more than the `Authority`? (recorded 2026-11-08, maintainer choice A)** Keep the `Authority`-only interface, `authority_verifier(Authority) -> bool`.
- Consequence: no public API change. The verifier cannot see the artifact, its scope, or the requested action, so it cannot make decisions that depend on them. A verifier that needs that context must be built outside this package.
- Status: DECIDED. Requirement R14 (verifier request object) was deferred on this basis.
- **Note, 2026-11-14: partly overturned by the owner.** The owner added an optional second verifier, `artifact_authority_verifier(Authority, digest) -> bool`, that also receives the artifact's verified digest. The one-argument `authority_verifier(Authority) -> bool` interface is left intact and behaves exactly as before when used alone. R14 is IMPLEMENTED for this interface only (see section 3): there is still no request object, and no scope, payload or action is passed.

## 3. Requirements and status

| # | Requirement | Status | Notes |
|---|---|---|---|
| R1 | Trusted issuer identity is pinned by the operator | NOT IMPLEMENTED | No issuer concept in the package. Deferred to the verifier the caller supplies. |
| R2 | Grant signature is verified against that issuer | NOT IMPLEMENTED | `Authority.grant` is an opaque string. No signature checks. |
| R3 | Expired grants are refused | NOT IMPLEMENTED in the package | Expiry is the verifier's check. The gateway can only refuse what the verifier refuses. |
| R4 | Revoked grants are refused at decision time | NOT IMPLEMENTED; **contract changed** | Revocation is bounded by grant lifetime (decision B). Not immediate. |
| R5 | The grant covers this actor | IMPLEMENTED (caller-supplied) | The verifier receives the actor and decides. Tested with a stub verifier only. |
| R6 | The grant covers this action | NOT IMPLEMENTED | No action is modelled in `Artifact`. The verifier receives no action. |
| R7 | The grant covers this artifact's scope | NOT IMPLEMENTED | Neither verifier receives the artifact's scope. Declared scope is validated and preserved, not enforced (see README). |
| R8 | Replay protection | NOT IMPLEMENTED | No nonce or replay store. |
| R9 | Verifier unavailable refuses | IMPLEMENTED | `AUTHORITY_VERIFIER_UNAVAILABLE`. |
| R10 | Verifier exception does not prove the grant invalid | IMPLEMENTED | Separate reason code from `MISSING_AUTHORITY`. |
| R11 | Malformed verifier response refuses | IMPLEMENTED | Refused as `AUTHORITY_VERIFIER_UNAVAILABLE`, treated as verifier failure. Literal `False` is `MISSING_AUTHORITY`. |
| R12 | Tampered artifact never reaches the verifier | IMPLEMENTED | Tested by `test_verifier_is_not_called_for_an_artifact_with_a_bad_digest`. |
| R13 | Production profile refuses to run without a verifier | IMPLEMENTED | Checks only that a callable exists (either keyword). |
| R14 | Verifier receives artifact context | IMPLEMENTED (interface only) | Optional `artifact_authority_verifier(Authority, digest)` receives the verified integrity digest, so a caller's verifier can bind authority to one artifact. The one-argument interface is unchanged (section 2, D, note 2026-11-14). Not a request object: no scope, payload or action. The package ships no verifier and no key handling; the binding is only as good as the caller's verifier. |

## 4. Verifier interface

Current (IMPLEMENTED), two optional forms that may be combined:

- `authority_verifier`: input is one `Authority` (`actor: str`, `grant: str`), both non-empty strings.
- `artifact_authority_verifier`: inputs are that `Authority` and the artifact's verified integrity digest (`str`, 64 lowercase hex characters).
- Output (both forms): `True` to accept the authority; anything else refuses.
- Exceptions: refuse as `AUTHORITY_VERIFIER_UNAVAILABLE`.
- Called: synchronously, once per judged artifact, after integrity succeeds. With both set, both must accept.
- Migration: none needed; the one-argument form is unchanged and the new keyword is optional.

## 5. Error and outage semantics (IMPLEMENTED)

| Situation | Verdict |
|---|---|
| No verifier, development profile | Accepted if the authority is well-formed |
| No verifier, production profile | Refused at construction (`ValueError`); if all removed later, refused `MISSING_AUTHORITY` |
| Verifier returns `True` | Accepted |
| Verifier returns literal `False` | Refused, `MISSING_AUTHORITY` |
| Verifier returns any other value | Refused, `AUTHORITY_VERIFIER_UNAVAILABLE` (malformed response) |
| Verifier raises | Refused, `AUTHORITY_VERIFIER_UNAVAILABLE`; text not in verdict |
| Artifact fails integrity | Refused before the verifier is called |

## 6. Acceptance criteria

Criteria for the parts of this contract that are IMPLEMENTED. A criterion is met only when the named test runs and passes in CI.

- A verifier that raises refuses with `AUTHORITY_VERIFIER_UNAVAILABLE`, and its text is not in the verdict.
- A verifier that returns literal `False` refuses with `MISSING_AUTHORITY`.
- A verifier that returns any other value refuses with `AUTHORITY_VERIFIER_UNAVAILABLE`.
- An artifact with a bad digest never reaches the verifier.
- A production gateway refuses to construct without a callable verifier, and builds with only `artifact_authority_verifier`.
- A valid authority on an edited, re-sealed artifact is refused by an artifact-bound verifier, which receives exactly the verified digest.
- With both verifiers set, both must accept.
- A failing dashboard does not change the verdict and is logged.

Criteria for the **deferred** design (not testable until built, and not claimed):

- Issuer identity pinned and grant signature verified.
- Expiry enforced by the package.
- Revocation: under decision B, revocation takes effect no later than grant expiry. No revoked-grant test is required, because there is no revocation mechanism to test. Do not claim immediate revocation.
- Action binding and scope binding in the verifier request.
- Replay protection.

## 6a. Acceptance tests and traceability

Tests are in `tests/test_authority_verifier.py`, `tests/test_artifact_authority_verifier.py`, `tests/test_production_profile.py` and `tests/test_adversarial.py`. Each requirement with a test is listed in `AUTHORITY_REQUIREMENTS_MATRIX.md`.

Requirements that cannot be tested in this repository because they are NOT IMPLEMENTED (issuer trust, signatures, expiry, revocation, action binding, replay) have no test that pretends otherwise. They become tests when the capability exists.

## 7. Out of scope for this package

- Issuing grants and running an issuer.
- Key management and key rotation.
- Producer authentication (who created the artifact).
- Persistence of grants or decisions.
- A revocation registry or revocation feed.

Do not describe any NOT IMPLEMENTED item as a security property of this package.
