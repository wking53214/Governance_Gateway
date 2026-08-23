"""Minimal immutable domain model for Governance Gateway V0.1."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Any, Mapping


class EpistemicStatus(str, Enum):
    FACT = "FACT"
    INFERENCE = "INFERENCE"
    ASSUMPTION = "ASSUMPTION"
    RECOMMENDATION = "RECOMMENDATION"
    DECISION = "DECISION"
    UNKNOWN = "UNKNOWN"


class Scope(str, Enum):
    READ_ONLY = "READ_ONLY"
    EXECUTE = "EXECUTE"


class GateReason(str, Enum):
    MISSING_PROVENANCE = "MISSING_PROVENANCE"
    MISSING_AUTHORITY = "MISSING_AUTHORITY"
    INVALID_EPISTEMIC_STATE = "INVALID_EPISTEMIC_STATE"
    INVALID_SCOPE = "INVALID_SCOPE"
    INTEGRITY_FAILURE = "INTEGRITY_FAILURE"
    INVALID_ARTIFACT = "INVALID_ARTIFACT"
    GOVERNANCE_VIOLATION = "GOVERNANCE_VIOLATION"


@dataclass(frozen=True)
class Authority:
    actor: str
    grant: str

    def __post_init__(self) -> None:
        if not isinstance(self.actor, str) or not self.actor.strip():
            raise ValueError("authority actor must be a non-empty string")
        if not isinstance(self.grant, str) or not self.grant.strip():
            raise ValueError("authority grant must be a non-empty string")


def _freeze(value: Any) -> Any:
    """Freeze only JSON-like values; never silently coerce their meaning."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        frozen = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("mapping keys must be strings")
            frozen[key] = _freeze(item)
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    raise TypeError(f"unsupported value type: {type(value).__name__}")


def _canonical(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _canonical(item) for key, item in sorted(value.items())}
    if isinstance(value, tuple):
        return [_canonical(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Authority):
        return {"actor": value.actor, "grant": value.grant}
    return value


def _digest_fields(
    artifact_id: str,
    payload: Any,
    provenance: Any,
    epistemic_status: EpistemicStatus,
    authority: Authority,
    scope: Scope,
) -> str:
    material = {
        "artifact_id": artifact_id,
        "payload": _canonical(payload),
        "provenance": _canonical(provenance),
        "epistemic_status": epistemic_status.value,
        "authority": _canonical(authority),
        "scope": scope.value,
    }
    encoded = json.dumps(
        material, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False
    ).encode()
    return sha256(encoded).hexdigest()


@dataclass(frozen=True)
class Artifact:
    artifact_id: str
    payload: Any
    provenance: Any
    epistemic_status: EpistemicStatus
    authority: Authority | None
    scope: Scope | None
    integrity: str

    def __post_init__(self) -> None:
        if not isinstance(self.artifact_id, str) or not self.artifact_id.strip():
            raise ValueError("artifact_id must be a non-empty string")
        if not isinstance(self.provenance, Mapping) or not self.provenance:
            raise ValueError("provenance must be a non-empty mapping")
        if not isinstance(self.epistemic_status, EpistemicStatus):
            raise ValueError("epistemic_status must be an EpistemicStatus")
        if not isinstance(self.authority, Authority):
            raise ValueError("authority must be an Authority")
        if not isinstance(self.scope, Scope):
            raise ValueError("scope must be a Scope")
        object.__setattr__(self, "payload", _freeze(self.payload))
        object.__setattr__(self, "provenance", _freeze(self.provenance))

    @classmethod
    def create(
        cls, *, artifact_id: str, payload: Any, provenance: Any,
        epistemic_status: EpistemicStatus, authority: Authority, scope: Scope,
    ) -> "Artifact":
        if not isinstance(artifact_id, str) or not artifact_id.strip():
            raise ValueError("artifact_id must be a non-empty string")
        frozen_payload = _freeze(payload)
        frozen_provenance = _freeze(provenance)
        if not isinstance(frozen_provenance, Mapping) or not frozen_provenance:
            raise ValueError("provenance must be a non-empty mapping")
        integrity = _digest_fields(
            artifact_id, frozen_payload, frozen_provenance,
            epistemic_status, authority, scope
        )
        return cls(
            artifact_id=artifact_id, payload=frozen_payload,
            provenance=frozen_provenance, epistemic_status=epistemic_status,
            authority=authority, scope=scope, integrity=integrity,
        )

    def expected_integrity(self) -> str:
        if not isinstance(self.authority, Authority) or not isinstance(self.scope, Scope):
            return ""
        if not isinstance(self.epistemic_status, EpistemicStatus):
            return ""
        try:
            return _digest_fields(
                self.artifact_id, self.payload, self.provenance,
                self.epistemic_status, self.authority, self.scope,
            )
        except (TypeError, ValueError):
            return ""


@dataclass(frozen=True)
class GateResult:
    accepted: bool
    artifact: Artifact | None = None
    reason: GateReason | None = None

    @classmethod
    def accept(cls, artifact: Artifact) -> "GateResult":
        return cls(True, artifact=artifact)

    @classmethod
    def reject(cls, reason: GateReason) -> "GateResult":
        return cls(False, reason=reason)
