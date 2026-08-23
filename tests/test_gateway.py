from dataclasses import FrozenInstanceError

import pytest

from governance_gateway import (
    Artifact,
    Authority,
    EpistemicStatus,
    GateReason,
    GovernanceGateway,
    Scope,
)


def make_artifact(**overrides):
    values = {
        "artifact_id": "a-1",
        "payload": {"message": "hello", "items": [1, 2]},
        "provenance": {"source": "human"},
        "epistemic_status": EpistemicStatus.INFERENCE,
        "authority": Authority(actor="alice", grant="review"),
        "scope": Scope.READ_ONLY,
    }
    values.update(overrides)
    return Artifact.create(**values)


def test_valid_artifact_is_accepted():
    artifact = make_artifact()
    result = GovernanceGateway().evaluate(artifact)
    assert result.accepted
    assert result.artifact is artifact
    assert result.reason is None


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("provenance", None, GateReason.MISSING_PROVENANCE),
        ("authority", None, GateReason.MISSING_AUTHORITY),
        ("epistemic_status", "FACT", GateReason.INVALID_EPISTEMIC_STATE),
        ("scope", "EXECUTE", GateReason.INVALID_SCOPE),
        ("integrity", "forged", GateReason.INTEGRITY_FAILURE),
    ],
)
def test_invalid_required_fields_are_rejected(field, value, reason):
    artifact = make_artifact()
    object.__setattr__(artifact, field, value)
    result = GovernanceGateway().evaluate(artifact)
    assert not result.accepted
    assert result.reason is reason


def test_accepted_artifact_is_unchanged():
    artifact = make_artifact()
    before = (artifact.artifact_id, artifact.payload, artifact.provenance,
              artifact.epistemic_status, artifact.authority, artifact.scope,
              artifact.integrity)
    result = GovernanceGateway().evaluate(artifact)
    after = (result.artifact.artifact_id, result.artifact.payload, result.artifact.provenance,
             result.artifact.epistemic_status, result.artifact.authority,
             result.artifact.scope, result.artifact.integrity)
    assert before == after


def test_artifact_is_immutable_at_top_level():
    artifact = make_artifact()
    with pytest.raises(FrozenInstanceError):
        artifact.payload = "changed"


@pytest.mark.parametrize(
    ("status", "forbidden"),
    [
        (EpistemicStatus.INFERENCE, EpistemicStatus.FACT),
        (EpistemicStatus.RECOMMENDATION, EpistemicStatus.DECISION),
        (EpistemicStatus.UNKNOWN, EpistemicStatus.FACT),
    ],
)
def test_no_epistemic_promotion(status, forbidden):
    artifact = make_artifact(epistemic_status=status)
    result = GovernanceGateway().evaluate(artifact)
    assert result.accepted
    assert result.artifact.epistemic_status is status
    assert result.artifact.epistemic_status is not forbidden


def test_capability_does_not_equal_authority():
    artifact = make_artifact()
    object.__setattr__(artifact, "authority", None)
    result = GovernanceGateway().evaluate(artifact)
    assert not result.accepted
    assert result.reason is GateReason.MISSING_AUTHORITY


def test_integrity_detects_mutation_after_hashing():
    artifact = make_artifact()
    original = artifact.integrity
    object.__setattr__(artifact, "payload", {"tampered": True})
    assert artifact.integrity == original
    result = GovernanceGateway().evaluate(artifact)
    assert not result.accepted
    assert result.reason is GateReason.INTEGRITY_FAILURE


def test_integrity_must_be_lowercase_hex_sha256():
    artifact = make_artifact()
    object.__setattr__(artifact, "integrity", "A" * 64)
    result = GovernanceGateway().evaluate(artifact)
    assert result.reason is GateReason.INTEGRITY_FAILURE


def test_forced_malformed_provenance_fails_closed():
    artifact = make_artifact()
    object.__setattr__(artifact, "provenance", [])
    result = GovernanceGateway().evaluate(artifact)
    assert not result.accepted


def test_forced_invalid_epistemic_value_fails_closed():
    artifact = make_artifact()
    object.__setattr__(artifact, "epistemic_status", "FACT")
    result = GovernanceGateway().evaluate(artifact)
    assert result.reason is GateReason.INVALID_EPISTEMIC_STATE


def test_forced_invalid_scope_fails_closed():
    artifact = make_artifact()
    object.__setattr__(artifact, "scope", "EXECUTE")
    result = GovernanceGateway().evaluate(artifact)
    assert result.reason is GateReason.INVALID_SCOPE
