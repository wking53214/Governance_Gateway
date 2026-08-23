# Governance Gateway V0.1

**Foundational / adversarial baseline.**

Governance Gateway is a deliberately small Python library establishing a reusable boundary for governed artifacts.

The V0.1 contract is:

```text
INPUT → VALIDATE → ACCEPT or REJECT → OUTPUT
```

The gateway validates structure, explicit provenance, explicit authority, epistemic status, scope, and a deterministic integrity digest. On acceptance it returns the same artifact object; it does not transform it.

## Explicitly not included

V0.1 does not implement AI/LLM behavior, policy engines, orchestration, databases, network services, authentication, UI, adapters, audit logging, distributed execution, or sophisticated authorization.

## Minimal usage

```python
from governance_gateway import (
    Artifact, Authority, EpistemicStatus, GovernanceGateway, Scope
)

artifact = Artifact.create(
    artifact_id="example-1",
    payload={"message": "hello"},
    provenance={"source": "human"},
    epistemic_status=EpistemicStatus.INFERENCE,
    authority=Authority(actor="alice", grant="review"),
    scope=Scope.READ_ONLY,
)

result = GovernanceGateway().evaluate(artifact)

if result.accepted:
    governed = result.artifact
else:
    print(result.reason)
```

## Development

```bash
python -m pip install -e ".[test]"
pytest
```

V0.1 is intentionally not described as secure, complete, or production-ready.
