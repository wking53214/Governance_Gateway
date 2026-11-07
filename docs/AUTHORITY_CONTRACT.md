# Authority verification contract: design (draft)

Status: **decisions recorded (section 3); nothing here is implemented.** The gateway today calls an optional caller-supplied `authority_verifier(Authority) -> bool` and trusts its answer. This document defines what a real verification contract must establish, so that the production story can move past "configuration guard."

## 1. What the contract must establish

| Question | Required property | Today |
| --- | --- | --- |
| Who issued this grant? | A trusted issuer identity, pinned by the operator | Not checked |
| Is the grant genuine? | Verifiable signature from that issuer | Not checked |
| Is it still valid? | Expiry and revocation are both checked at decision time | Not checked |
| Does it cover this actor and action? | Actor and action scope are compared to the artifact's scope | Not checked |
| Can it be reused? | Replay protection where grants are reusable | Not checked |
| What if the authority service is down? | Defined failure behavior (refuse, never accept) | Verifier exception → refuse |

## 2. Where it sits

The verifier runs after the artifact's well-formedness and integrity checks (see `_judge()`, moved in the change that added this document). An artifact with a bad digest never reaches it.

## 3. Design choices

Decided 2026-11-07 by the maintainer, taking the recommended option in each case. The consequences listed under each option still apply.

**A. Who holds the trust anchor?** Decision: option 1 (operator pins issuer keys).
1. The operator pins issuer public keys in a file, the same pattern as the twin receiver's customer keys. **(Recommended)** Consequence: simple, auditable, and no network dependency; key rotation is a file edit.
2. A remote authority service is the source of truth. Consequence: revocation is immediate, but every decision depends on that service's availability and on its TLS trust.

**B. How are revocations delivered?** Decision: option 1 (short-lived grants, no revocation list).
1. Short-lived grants (minutes to hours) with no revocation list. **(Recommended)** Consequence: revocation takes effect at expiry, so the window is bounded by grant lifetime, and no revocation feed is needed.
2. A signed revocation list the verifier refreshes. Consequence: faster revocation, but another feed to keep fresh and a stale-list failure mode to design for.

**C. What happens when verification cannot be completed?** Decision: option 1 (refuse with a distinct reason code).
1. Refuse, with a distinct reason code for "verifier unavailable." **(Recommended)** Consequence: fail closed. Operators see outages as refusals, not as silent accepts.
2. Retry, then refuse. Consequence: fewer false refusals during brief blips, but a longer decision time.

## 4. Out of scope for this package

- Issuing grants and running the issuer.
- Producer authentication (who created the artifact). This is a separate contract.
- Persistence of grants or decisions.

## 5. Acceptance criteria (before any production claim)

- A test suite with a trusted issuer, a forged signature, an expired grant, a revoked grant, a grant for the wrong actor or action, and a replayed grant. Each must refuse.
- The verifier must be unreachable in at least one test, and that test must refuse.
- The README's authority section must describe the contract as implemented only after these tests pass in CI.
