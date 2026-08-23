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
