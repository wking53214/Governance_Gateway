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

## Trust model

What the gateway establishes:
- The artifact is well-formed and its fields match the integrity digest it carries. Any change to a governed field after the digest was computed is detected, unless the attacker also replaces the digest.
- The decision is one of two outcomes, and every refusal carries one reason code.

What it does not establish:
- **Authenticity.** The digest is unkeyed SHA-256, so anyone can compute a valid digest for any content. An edited artifact re-sealed by anyone passes in the default profile.
- **Authority.** With no `authority_verifier`, any well-formed authority record passes. With one, the gateway trusts the verifier's answer, and the verifier is the caller's responsibility.
- **Identity, issuance, expiry, and revocation.** The gateway has no grant registry, key management, or signature checks.

Profiles:
- `DEVELOPMENT` (default): no verifier required. Use for local work and tests only.
- `PRODUCTION`: refuses to construct without a callable verifier. This is a configuration guard, not proof that the verifier is trustworthy.

Ordering: the verifier is called before the integrity check in the current code. An artifact with a bad digest can still reach the verifier. Changing that order is an open item for a separate code change.

Failure behavior: an ordinary error during judging returns `INVALID_ARTIFACT`. Dashboard recording happens after the judgment and is not covered by that handler.
