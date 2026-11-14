"""Optional artifact_authority_verifier(Authority, digest): binds authority to one artifact."""

import pytest

from governance_gateway import (
    Artifact,
    Authority,
    EpistemicStatus,
    GateDashboard,
    GateReason,
    GatewayProfile,
    GovernanceGateway,
    Scope,
)

ALICE = Authority(actor="alice", grant="review")


def make(payload, authority=ALICE):
    return Artifact.create(
        artifact_id="a-1",
        payload=payload,
        provenance={"source": "human"},
        epistemic_status=EpistemicStatus.INFERENCE,
        authority=authority,
        scope=Scope.READ_ONLY,
    )


class Bound:
    """Grants alice authority for exactly one artifact digest."""

    def __init__(self, digest):
        self.digest = digest
        self.calls = []

    def __call__(self, authority, digest):
        self.calls.append((authority, digest))
        return authority == ALICE and digest == self.digest


def test_valid_authority_on_an_edited_resealed_artifact_is_refused():
    honest = make({"action": "summarise"})
    edited = make({"action": "delete everything"})  # re-sealed: digest is self-consistent
    assert edited.integrity != honest.integrity
    gateway = GovernanceGateway(artifact_authority_verifier=Bound(honest.integrity))
    assert gateway.evaluate(honest).accepted is True
    result = gateway.evaluate(edited)
    assert result.accepted is False
    assert result.reason is GateReason.MISSING_AUTHORITY


def test_the_verifier_receives_the_authority_and_the_verified_digest_only():
    art = make({"x": 1})
    verifier = Bound(art.integrity)
    GovernanceGateway(artifact_authority_verifier=verifier).evaluate(art)
    assert verifier.calls == [(ALICE, art.integrity)]


def test_a_bad_digest_never_reaches_the_verifier():
    art = make({"x": 1})
    bad = Artifact(
        artifact_id=art.artifact_id,
        payload={"x": 2},
        provenance=art.provenance,
        epistemic_status=art.epistemic_status,
        authority=art.authority,
        scope=art.scope,
        integrity=art.integrity,
    )
    verifier = Bound(art.integrity)
    result = GovernanceGateway(artifact_authority_verifier=verifier).evaluate(bad)
    assert result.reason is GateReason.INTEGRITY_FAILURE
    assert verifier.calls == []


def test_it_alone_accepts_on_true():
    assert GovernanceGateway(artifact_authority_verifier=lambda a, d: True).evaluate(make({})).accepted


def test_false_is_missing_authority():
    result = GovernanceGateway(artifact_authority_verifier=lambda a, d: False).evaluate(make({}))
    assert result.reason is GateReason.MISSING_AUTHORITY


@pytest.mark.parametrize("answer", [None, 0, 1, "yes", [True], 1.0])
def test_a_non_bool_answer_is_unavailable(answer):
    result = GovernanceGateway(artifact_authority_verifier=lambda a, d: answer).evaluate(make({}))
    assert result.accepted is False
    assert result.reason is GateReason.AUTHORITY_VERIFIER_UNAVAILABLE


def test_an_exception_is_unavailable_and_its_text_is_not_leaked():
    def boom(authority, digest):
        raise RuntimeError("secret-token-123")

    result = GovernanceGateway(artifact_authority_verifier=boom).evaluate(make({}))
    assert result.reason is GateReason.AUTHORITY_VERIFIER_UNAVAILABLE
    assert "secret-token-123" not in repr(result)


@pytest.mark.parametrize(
    "first,second,reason",
    [
        (True, True, None),
        (True, False, GateReason.MISSING_AUTHORITY),
        (False, True, GateReason.MISSING_AUTHORITY),
        (True, None, GateReason.AUTHORITY_VERIFIER_UNAVAILABLE),
        (None, True, GateReason.AUTHORITY_VERIFIER_UNAVAILABLE),
    ],
)
def test_with_both_verifiers_both_must_accept(first, second, reason):
    gateway = GovernanceGateway(
        authority_verifier=lambda a: first,
        artifact_authority_verifier=lambda a, d: second,
    )
    result = gateway.evaluate(make({}))
    assert result.accepted is (reason is None)
    assert result.reason is reason


def test_with_both_verifiers_an_exception_in_either_refuses():
    def boom(*args):
        raise RuntimeError("down")

    for gateway in (
        GovernanceGateway(authority_verifier=boom, artifact_authority_verifier=lambda a, d: True),
        GovernanceGateway(authority_verifier=lambda a: True, artifact_authority_verifier=boom),
    ):
        result = gateway.evaluate(make({}))
        assert result.reason is GateReason.AUTHORITY_VERIFIER_UNAVAILABLE


def test_the_one_argument_verifier_alone_is_unchanged():
    calls = []

    def one(authority):
        calls.append(authority)
        return True

    assert GovernanceGateway(authority_verifier=one).evaluate(make({})).accepted is True
    assert calls == [ALICE]


def test_a_failing_dashboard_does_not_change_the_verdict():
    class Broken(GateDashboard):
        def record(self, result):
            raise RuntimeError("dashboard down")

    gateway = GovernanceGateway(Broken(), artifact_authority_verifier=lambda a, d: False)
    assert gateway.evaluate(make({})).reason is GateReason.MISSING_AUTHORITY


def test_production_builds_with_only_the_artifact_verifier():
    art = make({"x": 1})
    gateway = GovernanceGateway(
        artifact_authority_verifier=Bound(art.integrity), profile=GatewayProfile.PRODUCTION
    )
    assert gateway.evaluate(art).accepted is True
    assert gateway.evaluate(make({"x": 2})).accepted is False


def test_production_without_any_verifier_is_still_refused():
    with pytest.raises(ValueError, match="verifier"):
        GovernanceGateway(profile=GatewayProfile.PRODUCTION)


@pytest.mark.parametrize("not_callable", [True, "verify", 1, object()])
def test_production_refuses_a_non_callable_for_either_keyword(not_callable):
    with pytest.raises(ValueError, match="artifact_authority_verifier"):
        GovernanceGateway(artifact_authority_verifier=not_callable, profile=GatewayProfile.PRODUCTION)
    with pytest.raises(ValueError, match="authority_verifier"):
        GovernanceGateway(
            authority_verifier=not_callable,
            artifact_authority_verifier=lambda a, d: True,
            profile=GatewayProfile.PRODUCTION,
        )


def test_production_with_all_verifiers_removed_later_refuses_everything():
    gateway = GovernanceGateway(
        artifact_authority_verifier=lambda a, d: True, profile=GatewayProfile.PRODUCTION
    )
    gateway.artifact_authority_verifier = None
    result = gateway.evaluate(make({}))
    assert result.reason is GateReason.MISSING_AUTHORITY


def test_development_default_is_unchanged():
    gateway = GovernanceGateway()
    assert gateway.profile is GatewayProfile.DEVELOPMENT
    assert gateway.artifact_authority_verifier is None
    assert gateway.evaluate(make({})).accepted is True
