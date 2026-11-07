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


class _RaisingDashboard:
    def __init__(self):
        self.calls = 0

    def record(self, result):
        self.calls += 1
        raise RuntimeError("dashboard storage down: internal-detail-123")


def _accepted_artifact():
    from governance_gateway import Artifact, Authority, EpistemicStatus, Scope

    return Artifact.create(
        artifact_id="dash-ok",
        payload={"k": "v"},
        provenance={"src": "t"},
        epistemic_status=EpistemicStatus.FACT,
        authority=Authority("actor", "grant"),
        scope=Scope.READ_ONLY,
    )


def test_a_failing_dashboard_keeps_an_accepted_verdict_and_logs_it(caplog):
    from governance_gateway import GovernanceGateway

    dashboard = _RaisingDashboard()
    gateway = GovernanceGateway(dashboard=dashboard)
    with caplog.at_level("ERROR", logger="governance_gateway.gateway"):
        result = gateway.evaluate(_accepted_artifact())
    assert result.accepted is True
    assert result.reason is None
    assert dashboard.calls == 1
    assert any("dashboard failed to record a decision" in r.getMessage() for r in caplog.records)
    assert any(r.exc_info is not None for r in caplog.records)


def test_a_failing_dashboard_keeps_a_rejected_verdict_and_logs_it(caplog):
    from governance_gateway import GateReason, GovernanceGateway

    dashboard = _RaisingDashboard()
    gateway = GovernanceGateway(dashboard=dashboard)
    with caplog.at_level("ERROR", logger="governance_gateway.gateway"):
        result = gateway.evaluate("not an artifact")
    assert result.accepted is False
    assert result.reason is GateReason.INVALID_ARTIFACT
    assert dashboard.calls == 1
    assert any("dashboard failed to record a decision" in r.getMessage() for r in caplog.records)


def test_the_dashboard_exception_text_does_not_reach_the_caller_or_the_verdict(caplog):
    from governance_gateway import GovernanceGateway

    gateway = GovernanceGateway(dashboard=_RaisingDashboard())
    with caplog.at_level("ERROR", logger="governance_gateway.gateway"):
        result = gateway.evaluate(_accepted_artifact())
    assert "internal-detail-123" not in repr(result)
