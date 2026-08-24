"""Minimal validation boundary for Governance Gateway V0.1."""

from __future__ import annotations

from typing import Any
import re

from .models import Artifact, Authority, EpistemicStatus, GateReason, GateResult, Scope, _digest_fields


_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class GovernanceGateway:
    """Validate governed artifacts without transforming them."""

    def evaluate(self, artifact: Any) -> GateResult:
        if not isinstance(artifact, Artifact):
            return GateResult.reject(GateReason.INVALID_ARTIFACT)

        try:
            if not isinstance(artifact.artifact_id, str) or not artifact.artifact_id.strip():
                return GateResult.reject(GateReason.INVALID_ARTIFACT)

            if not isinstance(artifact.provenance, dict) and not hasattr(artifact.provenance, "items"):
                return GateResult.reject(GateReason.MISSING_PROVENANCE)
            if not artifact.provenance:
                return GateResult.reject(GateReason.MISSING_PROVENANCE)

            if not isinstance(artifact.authority, Authority):
                return GateResult.reject(GateReason.MISSING_AUTHORITY)

            if not isinstance(artifact.epistemic_status, EpistemicStatus):
                return GateResult.reject(GateReason.INVALID_EPISTEMIC_STATE)

            if not isinstance(artifact.scope, Scope):
                return GateResult.reject(GateReason.INVALID_SCOPE)

            if not isinstance(artifact.integrity, str) or not _HEX64.fullmatch(artifact.integrity):
                return GateResult.reject(GateReason.INTEGRITY_FAILURE)

            expected = _digest_fields(
                artifact.artifact_id,
                artifact.payload,
                artifact.provenance,
                artifact.epistemic_status,
                artifact.authority,
                artifact.scope,
            )

            if artifact.integrity != expected:
                return GateResult.reject(GateReason.INTEGRITY_FAILURE)

            return GateResult.accept(artifact)
        except (TypeError, ValueError, AttributeError, OverflowError):
            return GateResult.reject(GateReason.INVALID_ARTIFACT)
