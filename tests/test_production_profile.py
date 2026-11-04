"""F04: a production gateway refuses to run without an explicit authority verifier.

The integrity digest is unkeyed SHA-256: anyone can edit a payload and
re-seal it. In the default (development) profile that stays the documented
behaviour. In the production profile the gateway will not even be built
without a caller-supplied ``authority_verifier``, the package ships no
default one, and a verifier removed after construction refuses everything.
"""

import pytest

from governance_gateway import (
    Artifact,
    Authority,
    EpistemicStatus,
    GateReason,
    GatewayProfile,
    GovernanceGateway,
    Scope,
)

MALLORY = Authority(actor="mallory", grant="root")
ALICE = Authority(actor="alice", grant="review")


def resealed_edit(authority):
    """An honest artifact, its payload edited, then re-sealed by the editor."""
    honest = Artifact.create(
        artifact_id="a-1",
        payload={"action": "summarise"},
        provenance={"source": "human"},
        epistemic_status=EpistemicStatus.DECISION,
        authority=ALICE,
        scope=Scope.EXECUTE,
    )
    return Artifact.create(
        artifact_id=honest.artifact_id,
        payload={"action": "delete everything"},
        provenance=dict(honest.provenance),
        epistemic_status=honest.epistemic_status,
        authority=authority,
        scope=Scope.EXECUTE,
    )


def only_alice(authority):
    return (authority.actor, authority.grant) == ("alice", "review")


def test_default_profile_is_development_and_keeps_the_original_behaviour():
    gateway = GovernanceGateway()
    assert gateway.profile is GatewayProfile.DEVELOPMENT
    assert gateway.evaluate(resealed_edit(MALLORY)).accepted is True


@pytest.mark.parametrize("profile", [GatewayProfile.PRODUCTION, "production"])
def test_production_without_a_verifier_refuses_to_be_built(profile):
    with pytest.raises(ValueError, match="authority_verifier"):
        GovernanceGateway(profile=profile)


@pytest.mark.parametrize("not_callable", [True, "verify", 1, object()])
def test_production_with_a_non_callable_verifier_refuses_to_be_built(not_callable):
    with pytest.raises(ValueError, match="authority_verifier"):
        GovernanceGateway(authority_verifier=not_callable, profile=GatewayProfile.PRODUCTION)


@pytest.mark.parametrize("bogus", ["prod", "PRODUCTION ", "", None, True, 1])
def test_an_unknown_profile_refuses_to_be_built(bogus):
    with pytest.raises(ValueError, match="profile"):
        GovernanceGateway(profile=bogus)


def test_production_refuses_a_resealed_edit_from_an_unverified_actor():
    gateway = GovernanceGateway(authority_verifier=only_alice, profile=GatewayProfile.PRODUCTION)
    result = gateway.evaluate(resealed_edit(MALLORY))
    assert result.accepted is False
    assert result.reason is GateReason.MISSING_AUTHORITY


def test_production_accepts_a_verified_actor():
    gateway = GovernanceGateway(authority_verifier=only_alice, profile=GatewayProfile.PRODUCTION)
    assert gateway.evaluate(resealed_edit(ALICE)).accepted is True


def test_production_with_the_verifier_removed_later_refuses_everything():
    gateway = GovernanceGateway(authority_verifier=only_alice, profile=GatewayProfile.PRODUCTION)
    gateway.authority_verifier = None
    result = gateway.evaluate(resealed_edit(ALICE))
    assert result.accepted is False
    assert result.reason is GateReason.MISSING_AUTHORITY


def test_the_profile_cannot_be_downgraded_after_construction():
    gateway = GovernanceGateway(authority_verifier=only_alice, profile=GatewayProfile.PRODUCTION)
    with pytest.raises(AttributeError):
        gateway.profile = GatewayProfile.DEVELOPMENT
