import pytest

from governance_gateway import (
    Artifact,
    Authority,
    EpistemicStatus,
    GateReason,
    GovernanceGateway,
    Scope,
)


def valid():
    return Artifact.create(
        artifact_id="adv-1",
        payload={"x": "y"},
        provenance={"source": "test"},
        epistemic_status=EpistemicStatus.UNKNOWN,
        authority=Authority(actor="tester", grant="inspect"),
        scope=Scope.READ_ONLY,
    )


def test_an_unexpected_error_while_judging_is_a_refusal_not_a_crash():
    class Boom(dict):
        def __bool__(self):
            raise RuntimeError("unexpected inspection failure")

    artifact = valid()
    object.__setattr__(artifact, "provenance", Boom({"source": "test"}))
    result = GovernanceGateway().evaluate(artifact)
    assert result.accepted is False
    assert result.reason is GateReason.INVALID_ARTIFACT


@pytest.mark.parametrize(
    "candidate",
    [None, 1, "", object(), {}, []],
)
def test_malformed_inputs_never_accept(candidate):
    result = GovernanceGateway().evaluate(candidate)
    assert not result.accepted
    assert result.reason is GateReason.INVALID_ARTIFACT


@pytest.mark.parametrize("provenance", [None, "", "   "])
def test_missing_or_empty_provenance_is_not_accepted(provenance):
    artifact = valid()
    object.__setattr__(artifact, "provenance", provenance)
    result = GovernanceGateway().evaluate(artifact)
    assert not result.accepted


@pytest.mark.parametrize("field", ["authority", "scope", "epistemic_status", "integrity"])
def test_null_governance_state_is_rejected(field):
    artifact = valid()
    object.__setattr__(artifact, field, None)
    result = GovernanceGateway().evaluate(artifact)
    assert not result.accepted


def test_whitespace_identifier_is_rejected():
    artifact = valid()
    object.__setattr__(artifact, "artifact_id", "   ")
    assert not GovernanceGateway().evaluate(artifact).accepted


def test_payload_tampering_is_rejected():
    artifact = valid()
    object.__setattr__(artifact, "payload", {"x": "different"})
    result = GovernanceGateway().evaluate(artifact)
    assert result.reason is GateReason.INTEGRITY_FAILURE


def test_provenance_tampering_is_rejected():
    artifact = valid()
    object.__setattr__(artifact, "provenance", {"source": "forged"})
    result = GovernanceGateway().evaluate(artifact)
    assert result.reason is GateReason.INTEGRITY_FAILURE


def test_authority_tampering_is_rejected():
    artifact = valid()
    object.__setattr__(artifact, "authority", Authority(actor="forger", grant="admin"))
    result = GovernanceGateway().evaluate(artifact)
    assert result.reason is GateReason.INTEGRITY_FAILURE


def test_scope_broadening_is_rejected():
    artifact = valid()
    object.__setattr__(artifact, "scope", Scope.EXECUTE)
    result = GovernanceGateway().evaluate(artifact)
    assert result.reason is GateReason.INTEGRITY_FAILURE


def test_forged_integrity_is_rejected():
    artifact = valid()
    object.__setattr__(artifact, "integrity", "0" * 64)
    result = GovernanceGateway().evaluate(artifact)
    assert result.reason is GateReason.INTEGRITY_FAILURE


def test_repeated_assertion_does_not_raise_status():
    artifact = valid()
    for _ in range(100):
        result = GovernanceGateway().evaluate(artifact)
        assert result.artifact.epistemic_status is EpistemicStatus.UNKNOWN


def test_gateway_does_not_create_authority():
    artifact = valid()
    object.__setattr__(artifact, "authority", None)
    result = GovernanceGateway().evaluate(artifact)
    assert result.reason is GateReason.MISSING_AUTHORITY


def test_non_string_mapping_keys_cannot_be_silently_coerced():
    with pytest.raises(TypeError):
        Artifact.create(
            artifact_id="key-attack",
            payload={1: "one", "1": "different"},
            provenance={"source": "test"},
            epistemic_status=EpistemicStatus.UNKNOWN,
            authority=Authority(actor="tester", grant="inspect"),
            scope=Scope.READ_ONLY,
        )


def test_nested_payload_is_immutable():
    artifact = valid()
    assert isinstance(artifact.payload, dict) or hasattr(artifact.payload, "items")
    with pytest.raises(TypeError):
        artifact.payload["x"] = "tampered"


def test_empty_provenance_cannot_be_constructed():
    with pytest.raises(ValueError):
        Artifact.create(
            artifact_id="prov-attack",
            payload={},
            provenance={},
            epistemic_status=EpistemicStatus.UNKNOWN,
            authority=Authority(actor="tester", grant="inspect"),
            scope=Scope.READ_ONLY,
        )


def test_nan_payload_is_rejected_instead_of_getting_ambiguous_integrity():
    with pytest.raises(ValueError):
        Artifact.create(
            artifact_id="nan-attack",
            payload=float("nan"),
            provenance={"source": "test"},
            epistemic_status=EpistemicStatus.UNKNOWN,
            authority=Authority(actor="tester", grant="inspect"),
            scope=Scope.READ_ONLY,
        )


def test_a_failing_dashboard_does_not_change_the_verdict_or_raise():
    class BrokenDashboard:
        def record(self, result):
            raise RuntimeError("dashboard down")

    gateway = GovernanceGateway(dashboard=BrokenDashboard())
    accepted = gateway.evaluate(valid())
    assert accepted.accepted is True
    refused = gateway.evaluate("not an artifact")
    assert refused.accepted is False
    assert refused.reason is GateReason.INVALID_ARTIFACT


def test_a_payload_that_contains_itself_cannot_be_sealed():
    cycle = []
    cycle.append(cycle)
    with pytest.raises(RecursionError):
        Artifact.create(
            artifact_id="cycle-1",
            payload=cycle,
            provenance={"source": "test"},
            epistemic_status=EpistemicStatus.UNKNOWN,
            authority=Authority(actor="tester", grant="inspect"),
            scope=Scope.READ_ONLY,
        )


def test_a_payload_nested_past_the_recursion_limit_cannot_be_sealed():
    deep = {}
    cursor = deep
    for _ in range(5000):
        cursor["n"] = {}
        cursor = cursor["n"]
    with pytest.raises(RecursionError):
        Artifact.create(
            artifact_id="deep-1",
            payload=deep,
            provenance={"source": "test"},
            epistemic_status=EpistemicStatus.UNKNOWN,
            authority=Authority(actor="tester", grant="inspect"),
            scope=Scope.READ_ONLY,
        )


def test_an_oversized_payload_is_judged_and_a_change_to_one_element_is_refused():
    big = {"items": list(range(200_000))}
    artifact = valid()
    sealed = Artifact.create(
        artifact_id="big-1",
        payload=big,
        provenance={"source": "test"},
        epistemic_status=EpistemicStatus.UNKNOWN,
        authority=Authority(actor="tester", grant="inspect"),
        scope=Scope.READ_ONLY,
    )
    assert GovernanceGateway().evaluate(sealed).accepted is True
    object.__setattr__(sealed, "payload", {"items": list(range(1, 200_001))})
    assert GovernanceGateway().evaluate(sealed).reason is GateReason.INTEGRITY_FAILURE
    assert artifact.artifact_id == "adv-1"


def test_a_mapping_subclass_whose_items_raise_cannot_be_sealed():
    class Hostile(dict):
        def items(self):
            raise RuntimeError("hostile items")

    with pytest.raises(RuntimeError):
        Artifact.create(
            artifact_id="hostile-1",
            payload=Hostile(a=1),
            provenance={"source": "test"},
            epistemic_status=EpistemicStatus.UNKNOWN,
            authority=Authority(actor="tester", grant="inspect"),
            scope=Scope.READ_ONLY,
        )
