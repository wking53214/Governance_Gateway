"""Optional authority_verifier: off by default, fail-closed when set."""

import pytest

from governance_gateway import (
    Artifact,
    Authority,
    EpistemicStatus,
    GateReason,
    GovernanceGateway,
    Scope,
)


def make_artifact(authority):
    return Artifact.create(
        artifact_id="a-1",
        payload={"message": "hello"},
        provenance={"source": "human"},
        epistemic_status=EpistemicStatus.INFERENCE,
        authority=authority,
        scope=Scope.READ_ONLY,
    )


REGISTERED = {("alice", "review")}


def registry_verifier(authority):
    return (authority.actor, authority.grant) in REGISTERED


UNREGISTERED = Authority(actor="mallory", grant="root")
EXPIRED = Authority(actor="alice", grant="EXPIRED")
GOOD = Authority(actor="alice", grant="review")


@pytest.mark.parametrize("authority", [UNREGISTERED, EXPIRED], ids=["unregistered", "expired"])
def test_with_no_verifier_any_authority_is_accepted(authority):
    assert GovernanceGateway().evaluate(make_artifact(authority)).accepted is True


@pytest.mark.parametrize("authority", [UNREGISTERED, EXPIRED], ids=["unregistered", "expired"])
def test_with_a_verifier_an_unverified_grant_is_refused_as_missing_authority(authority):
    result = GovernanceGateway(authority_verifier=registry_verifier).evaluate(make_artifact(authority))
    assert result.accepted is False
    assert result.reason is GateReason.MISSING_AUTHORITY


def test_with_a_verifier_a_registered_grant_is_accepted():
    result = GovernanceGateway(authority_verifier=registry_verifier).evaluate(make_artifact(GOOD))
    assert result.accepted is True


def test_a_verifier_that_raises_refuses_the_artifact():
    def boom(authority):
        raise RuntimeError("registry down")

    result = GovernanceGateway(authority_verifier=boom).evaluate(make_artifact(GOOD))
    assert result.accepted is False
    assert result.reason is GateReason.MISSING_AUTHORITY


@pytest.mark.parametrize("answer", [None, 1, "yes", [True]], ids=repr)
def test_only_a_true_answer_counts_as_verified(answer):
    result = GovernanceGateway(authority_verifier=lambda a: answer).evaluate(make_artifact(GOOD))
    assert result.accepted is False
    assert result.reason is GateReason.MISSING_AUTHORITY


def test_the_verifier_does_not_override_an_earlier_refusal():
    tampered = make_artifact(GOOD)
    object.__setattr__(tampered, "payload", {"message": "tampered"})
    result = GovernanceGateway(authority_verifier=registry_verifier).evaluate(tampered)
    assert result.reason is GateReason.INTEGRITY_FAILURE


def test_verifier_is_not_called_for_an_artifact_with_a_bad_digest():
    calls = []

    def recording_verifier(authority):
        calls.append(authority)
        return True

    artifact = Artifact.create(
        artifact_id="order-1",
        payload={"k": "v"},
        provenance={"src": "t"},
        epistemic_status=EpistemicStatus.FACT,
        authority=Authority("actor", "grant"),
        scope=Scope.READ_ONLY,
    )
    object.__setattr__(artifact, "integrity", "0" * 64)
    result = GovernanceGateway(authority_verifier=recording_verifier).evaluate(artifact)
    assert result.accepted is False
    assert result.reason is GateReason.INTEGRITY_FAILURE
    assert calls == []
