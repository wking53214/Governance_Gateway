# Architecture

V0.1 intentionally has one boundary and one responsibility:

```text
caller
  ↓
Artifact
  ↓
GovernanceGateway.evaluate()
  ↓
validation
  ├── invalid → REJECT + machine-readable reason
  └── valid   → ACCEPT + same Artifact
```

The gateway validates rather than transforms.

The artifact carries:
- identity (`artifact_id`)
- payload
- provenance
- epistemic status
- explicit authority
- explicit scope
- deterministic integrity digest

The integrity digest covers all governed fields except the digest itself. This lets the gateway detect post-construction tampering without pretending that hashing provides authentication or authorization.

Future governance capabilities may be added around this boundary, but V0.1 deliberately contains no adapters on the admission path, and nothing on that path knows about other repositories.

The one thing that sits beside the boundary, not in it, is the optional `cns_connector` (see the README). It is the only module that knows another repository exists: it knows the shape of CNS's gate contract (`cns.gate`). The gateway never imports it, it loads CNS only when one of its functions is called, and it changes no verdict: it only re-expresses the gateway's `GateResult` as a CNS gate result at the admission (`ALPHA`) end.

## Position in STACK

This repository is one of five gates on the evidence SPINE, in this order: HERALD, TIE, Conservation_Kernel, **Governance_Gateway**, CCC. Governance_Gateway is the fourth. It judges whether an artifact may be admitted; it does not extract, record, evaluate the evidence root, or write to any store.

CNS is the coordinating contract. It holds the gate shapes and combines the five verdicts into one decision, binding each to its subject. It does not replace any of the five repositories. The optional `cns_connector` is how this gateway's verdict takes its place in that contract, at the admission (`ALPHA`) end.

This is separate from the live decision path, where Governance_Gateway is the first stage (`ADMISSION`) of `observe-perceive`. The two sequences are different workflows and should not be read as one pipeline.

## Trust model

What the gateway establishes:
- The artifact is well-formed and its fields match the integrity digest it carries. Any change to a governed field after the digest was computed is detected, unless the attacker also replaces the digest.
- The decision is one of two outcomes, and every refusal carries one reason code.

What it does not establish:
- **Authenticity.** The digest is unkeyed SHA-256, so anyone can compute a valid digest for any content. An edited artifact re-sealed by anyone passes in the default profile.
- **Authority.** With no `authority_verifier`, any well-formed authority record passes. With one, the gateway trusts the verifier's answer, and the verifier is the caller's responsibility. The verifier receives only the `Authority`, not the artifact. Expiry, revocation and issuer checks are not in this package.
- **Identity, issuance, expiry, and revocation.** The gateway has no grant registry, key management, or signature checks.

Profiles:
- `DEVELOPMENT` (default): no verifier required. Use for local work and tests only.
- `PRODUCTION`: refuses to construct without a callable verifier. This is a configuration guard, not proof that the verifier is trustworthy.

Ordering: the integrity check runs before the verifier. The checks run in this order: artifact type, identity, provenance, authority type, epistemic state, scope, integrity format, integrity recomputation and comparison, then the verifier. An artifact with a bad digest never reaches the verifier. The verifier's answer counts only if it is literally `True`. Literal `False` refuses with `MISSING_AUTHORITY`. Any other return value (a malformed response) and any exception refuse with `AUTHORITY_VERIFIER_UNAVAILABLE`. The verifier itself is supplied by the caller and is not checked by this package.

Failure behavior: an ordinary error during judging returns `INVALID_ARTIFACT`. An exception from the verifier returns `AUTHORITY_VERIFIER_UNAVAILABLE`, and its text is not included in the verdict. A verifier answer of literal `False` returns `MISSING_AUTHORITY`; any other answer returns `AUTHORITY_VERIFIER_UNAVAILABLE`. Dashboard recording happens after the judgment; an exception from it is logged and never changes the verdict or reaches the caller.
