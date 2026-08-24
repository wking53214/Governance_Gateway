
from governance_gateway import (
    Artifact,
    Authority,
    EpistemicStatus,
    GovernanceGateway,
    Scope,
    GateReason,
)


def make_artifact():
    return Artifact.create(
        artifact_id="a-1",
        payload={"x": "y"},
        provenance={"source": "human"},
        epistemic_status=EpistemicStatus.UNKNOWN,
        authority=Authority(actor="alice", grant="review"),
        scope=Scope.READ_ONLY,
    )


def test_subclass_integrity_bypass_blocked():

    base = make_artifact()

    class ForgedArtifact(Artifact):
        def expected_integrity(self):
            return self.integrity

    forged = ForgedArtifact(
        artifact_id=base.artifact_id,
        payload={"x": "forged"},
        provenance=base.provenance,
        epistemic_status=base.epistemic_status,
        authority=base.authority,
        scope=base.scope,
        integrity=base.integrity,
    )

    result = GovernanceGateway().evaluate(forged)

    assert not result.accepted
    assert result.reason is GateReason.INTEGRITY_FAILURE


def test_legitimate_subclass_still_works():

    class BenignArtifact(Artifact):
        pass

    base = make_artifact()

    benign = BenignArtifact(
        artifact_id=base.artifact_id,
        payload=base.payload,
        provenance=base.provenance,
        epistemic_status=base.epistemic_status,
        authority=base.authority,
        scope=base.scope,
        integrity=base.integrity,
    )

    result = GovernanceGateway().evaluate(benign)

    assert result.accepted


def test_overridden_expected_integrity_not_called():

    class EvilArtifact(Artifact):
        def expected_integrity(self):
            raise RuntimeError("should never execute")

    base = make_artifact()

    evil = EvilArtifact(
        artifact_id=base.artifact_id,
        payload=base.payload,
        provenance=base.provenance,
        epistemic_status=base.epistemic_status,
        authority=base.authority,
        scope=base.scope,
        integrity=base.integrity,
    )

    result = GovernanceGateway().evaluate(evil)

    assert result.accepted
