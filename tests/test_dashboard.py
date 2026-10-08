"""Gate dashboard: accept and reject counts, and gateway wiring."""

from __future__ import annotations

from governance_gateway import (
    Artifact,
    Authority,
    EpistemicStatus,
    GateDashboard,
    GateReason,
    GateResult,
    GovernanceGateway,
    Scope,
)


def make_artifact(**overrides):
    values = {
        "artifact_id": "a-1",
        "payload": {"message": "hello"},
        "provenance": {"source": "human"},
        "epistemic_status": EpistemicStatus.INFERENCE,
        "authority": Authority(actor="alice", grant="review"),
        "scope": Scope.READ_ONLY,
    }
    values.update(overrides)
    return Artifact.create(**values)


def test_empty_snapshot_is_all_zero():
    snap = GateDashboard().snapshot()
    assert snap["total_evaluations"] == 0
    assert snap["accepted"] == 0
    assert snap["rejected"] == 0
    assert snap["accept_rate"] == 0.0
    assert snap["rejections_by_reason"] == {}


def test_accept_is_counted():
    dash = GateDashboard()
    GovernanceGateway(dashboard=dash).evaluate(make_artifact())
    snap = dash.snapshot()
    assert snap["accepted"] == 1
    assert snap["rejected"] == 0
    assert snap["accept_rate"] == 1.0


def broken(field, value):
    artifact = make_artifact()
    object.__setattr__(artifact, field, value)
    return artifact


def test_rejection_is_counted_by_reason():
    dash = GateDashboard()
    gateway = GovernanceGateway(dashboard=dash)
    gateway.evaluate(broken("provenance", None))
    gateway.evaluate(broken("provenance", None))
    gateway.evaluate("not an artifact")
    snap = dash.snapshot()
    assert snap["total_evaluations"] == 3
    assert snap["rejected"] == 3
    assert snap["rejections_by_reason"] == {
        GateReason.MISSING_PROVENANCE.value: 2,
        GateReason.INVALID_ARTIFACT.value: 1,
    }


def test_rejections_sum_to_rejected_total():
    dash = GateDashboard()
    gateway = GovernanceGateway(dashboard=dash)
    gateway.evaluate(make_artifact())
    gateway.evaluate(broken("authority", None))
    gateway.evaluate(broken("scope", "SOMETHING"))
    snap = dash.snapshot()
    assert sum(snap["rejections_by_reason"].values()) == snap["rejected"]


def test_rejection_without_reason_is_labelled():
    dash = GateDashboard()
    dash.record(GateResult(accepted=False, reason=None))
    assert dash.snapshot()["rejections_by_reason"] == {"NO_REASON": 1}


def test_dashboard_never_changes_the_decision():
    artifact = make_artifact()
    plain = GovernanceGateway().evaluate(artifact)
    watched = GovernanceGateway(dashboard=GateDashboard()).evaluate(artifact)
    assert plain.accepted == watched.accepted
    assert plain.reason == watched.reason
    assert plain.artifact is watched.artifact


def test_no_dashboard_by_default():
    assert GovernanceGateway().dashboard is None
