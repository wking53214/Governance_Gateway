"""Minimal validation boundary for Governance Gateway V0.1."""

from __future__ import annotations

from enum import Enum
import logging
from typing import Any, Callable
import re

from .dashboard import GateDashboard
from .models import Artifact, Authority, EpistemicStatus, GateReason, GateResult, Scope, _digest_fields


_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class GatewayProfile(str, Enum):
    """How strictly the gateway treats authority.

    DEVELOPMENT (the default) keeps the original behaviour: the integrity
    digest is unkeyed, so without an ``authority_verifier`` any well-formed
    ``Authority`` passes, including one on an edited and re-sealed artifact.

    PRODUCTION refuses to build a gateway without a caller-supplied callable
    ``authority_verifier``. The package ships no default verifier and no key,
    and a production gateway whose verifier is later removed refuses every
    artifact with ``MISSING_AUTHORITY``.
    """

    DEVELOPMENT = "development"
    PRODUCTION = "production"


class GovernanceGateway:
    """Validate governed artifacts without transforming them."""

    def __init__(
        self,
        dashboard: GateDashboard | None = None,
        authority_verifier: Callable[[Authority], bool] | None = None,
        *,
        profile: GatewayProfile | str = GatewayProfile.DEVELOPMENT,
    ) -> None:
        try:
            resolved = GatewayProfile(profile)
        except ValueError:
            raise ValueError(f"unknown gateway profile: {profile!r}") from None
        if resolved is GatewayProfile.PRODUCTION and not callable(authority_verifier):
            raise ValueError(
                "the production profile requires an explicit callable authority_verifier;"
                " there is no default"
            )
        self._profile = resolved
        #: Optional outcome counter. Records only; never changes a decision.
        self.dashboard = dashboard
        #: Optional check that an Authority is genuinely held (registered, not
        #: expired). None keeps the original behaviour: any Authority passes.
        #: When set, anything but a True return, or any exception, refuses the
        #: artifact with MISSING_AUTHORITY.
        self.authority_verifier = authority_verifier

    @property
    def profile(self) -> GatewayProfile:
        """The profile fixed at construction. Read-only."""
        return self._profile

    def evaluate(self, artifact: Any) -> GateResult:
        """Decide accept or reject, then record the outcome if a dashboard is attached."""
        result = self._judge(artifact)
        if self.dashboard is not None:
            # Counting is observability only. A failing dashboard is logged and
            # must never change the verdict or raise into the caller.
            try:
                self.dashboard.record(result)
            except Exception:
                logging.getLogger(__name__).exception("dashboard failed to record a decision")
        return result

    def _judge(self, artifact: Any) -> GateResult:
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

            if self._profile is GatewayProfile.PRODUCTION and not callable(self.authority_verifier):
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

            # The external verifier runs only after the artifact is well-formed
            # and its integrity matches, so invalid artifacts never reach it.
            if self.authority_verifier is not None:
                try:
                    verified = self.authority_verifier(artifact.authority) is True
                except Exception:
                    verified = False
                if not verified:
                    return GateResult.reject(GateReason.MISSING_AUTHORITY)

            return GateResult.accept(artifact)
        except Exception:
            # Any ordinary error while judging is a refusal, never a crash or an accept.
            return GateResult.reject(GateReason.INVALID_ARTIFACT)
