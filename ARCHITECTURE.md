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

Future governance capabilities may be added around this boundary, but V0.1 deliberately contains no adapters or knowledge of other ArnoldAI repositories.
