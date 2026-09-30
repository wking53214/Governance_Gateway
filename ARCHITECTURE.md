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

Future governance capabilities may be added around this boundary, but V0.1 deliberately contains no adapters on the admission path, and nothing on that path knows about other ArnoldAI repositories.

The one thing that sits beside the boundary, not in it, is the optional `cns_connector` (see the README). It is the only module that knows another repository exists: it knows the shape of CNS's gate contract (`cns.gate`). The gateway never imports it, it loads CNS only when one of its functions is called, and it changes no verdict: it only re-expresses the gateway's `GateResult` as a CNS gate result at the admission (`ALPHA`) end.
