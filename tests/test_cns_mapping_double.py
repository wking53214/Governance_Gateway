"""The connector's mapping, tested against a double of ``cns.gate``.

These tests never skip and need no CNS, so they run in CI (which installs only
``.[test]``). They cover what the connector decides: the end it judges at, the
outcome of every verdict, what fails closed, what the verdict is bound to. The
digest arithmetic belongs to CNS and is covered by ``test_cns_connector.py``
when CNS is installed; ``tests/cns_gate_double.py`` says how the double relates
to the real contract and that file checks it.
"""

from __future__ import annotations

import sys

import cns_gate_double as double
import pytest

from governance_gateway import (
    Artifact,
    Authority,
    EpistemicStatus,
    GateReason,
    GateResult,
    GovernanceGateway,
    Scope,
)
from governance_gateway.cns_connector import (
    DEFAULT_SUBJECT,
    GATE_NAME,
    INCONSISTENT_VERDICT,
    NO_REASON_GIVEN,
    CnsGate,
    artifact_digest,
    artifact_subject,
    cns_available,
    cns_chain,
    evaluate_to_cns,
    judged_content,
    to_cns_result,
)


@pytest.fixture(autouse=True)
def cns_is_the_double(monkeypatch):
    """Whatever CNS is installed, the connector sees the double for these tests."""
    monkeypatch.setitem(sys.modules, "cns.gate", double)


def create_artifact(**overrides):
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


def make_artifact(**forced):
    """A valid artifact, then any fields forced past construction."""
    artifact = create_artifact()
    for name, value in forced.items():
        object.__setattr__(artifact, name, value)
    return artifact


REFUSED = [
    ("no provenance", make_artifact(provenance=None), GateReason.MISSING_PROVENANCE),
    ("no authority", make_artifact(authority=None), GateReason.MISSING_AUTHORITY),
    ("str status", make_artifact(epistemic_status="FACT"), GateReason.INVALID_EPISTEMIC_STATE),
    ("str scope", make_artifact(scope="EXECUTE"), GateReason.INVALID_SCOPE),
    ("forged integrity", make_artifact(integrity="forged"), GateReason.INTEGRITY_FAILURE),
    ("tampered payload", make_artifact(payload={"x": 1}), GateReason.INTEGRITY_FAILURE),
    ("blank id", make_artifact(artifact_id="  "), GateReason.INVALID_ARTIFACT),
    ("nan payload", make_artifact(payload=float("nan")), GateReason.INVALID_ARTIFACT),
    ("not an artifact", None, GateReason.INVALID_ARTIFACT),
    ("not an artifact either", {"payload": 1}, GateReason.INVALID_ARTIFACT),
]
CORPUS = [("valid", make_artifact(), None), *REFUSED]
IDS = [label for label, _, _ in CORPUS]


def test_the_double_is_what_the_connector_sees():
    assert cns_available() is True


# position -------------------------------------------------------------------


def test_every_verdict_is_issued_at_the_alpha_end():
    verdicts = [evaluate_to_cns(candidate) for _, candidate, _ in CORPUS]
    assert {v.position for v in verdicts} == {double.GatePosition.ALPHA}
    assert CnsGate().position is double.GatePosition.ALPHA


def test_the_chain_holds_the_gateway_at_the_alpha_end_only():
    chain = cns_chain()
    assert len(chain.alpha) == 1 and chain.omega == ()
    assert chain.alpha[0].position is double.GatePosition.ALPHA
    assert chain.complete() is False  # the gateway has no outcome end


# outcome --------------------------------------------------------------------


def test_an_accepted_artifact_maps_to_pass_with_no_reason():
    verdict = evaluate_to_cns(make_artifact())
    assert verdict.outcome is double.GateOutcome.PASS
    assert verdict.gate == GATE_NAME == "governance_gateway"
    assert verdict.reason == ""
    assert not verdict.blocking()


@pytest.mark.parametrize("reason", list(GateReason), ids=lambda r: r.value)
def test_every_refusal_maps_to_terminal_breach_and_keeps_the_reason_value(reason):
    verdict = to_cns_result(GateResult.reject(reason), make_artifact())
    assert verdict.outcome is double.GateOutcome.TERMINAL_BREACH
    assert verdict.reason == reason.value  # the value, not "GateReason.X"
    assert verdict.blocking()


def test_no_verdict_is_ever_a_retry():
    outcomes = {evaluate_to_cns(candidate).outcome for _, candidate, _ in CORPUS}
    assert outcomes == {double.GateOutcome.PASS, double.GateOutcome.TERMINAL_BREACH}


@pytest.mark.parametrize("label,candidate,reason", CORPUS, ids=IDS)
def test_the_connector_agrees_with_the_gateways_own_decision(label, candidate, reason):
    native = GovernanceGateway().evaluate(candidate)
    assert native.reason is reason, label
    verdict = evaluate_to_cns(candidate)
    assert (verdict.outcome is double.GateOutcome.PASS) is native.accepted
    if not native.accepted:
        assert verdict.outcome is double.GateOutcome.TERMINAL_BREACH
        assert verdict.reason == native.reason.value


# fail closed ----------------------------------------------------------------


def test_a_verdict_that_contradicts_itself_is_never_a_pass():
    artifact = make_artifact()
    other = make_artifact(artifact_id="other")
    contradictions = {
        "accepted without an artifact": GateResult(True),
        "accepted with a reason": GateResult(True, artifact=artifact, reason=GateReason.INVALID_SCOPE),
        "accepted for a different artifact": GateResult(True, artifact=other),
        "accepted is 1, not True": GateResult(1, artifact=artifact),  # type: ignore[arg-type]
        "accepted is 'yes'": GateResult("yes", artifact=artifact),  # type: ignore[arg-type]
        "accepted is None": GateResult(None, artifact=artifact),  # type: ignore[arg-type]
    }
    for label, native in contradictions.items():
        verdict = to_cns_result(native, artifact)
        assert verdict.outcome is double.GateOutcome.TERMINAL_BREACH, label
        assert verdict.reason == INCONSISTENT_VERDICT, label
        assert verdict.blocking(), label


def test_an_accept_for_something_that_is_not_an_artifact_is_never_a_pass():
    """The gateway refuses non-artifacts first, so no accept for one came from it."""
    thing = object()
    for candidate, native in (
        (None, GateResult(True)),
        (thing, GateResult(True, artifact=thing)),
        ("text", GateResult(True, artifact="text")),  # type: ignore[arg-type]
    ):
        verdict = to_cns_result(native, candidate)
        assert verdict.outcome is double.GateOutcome.TERMINAL_BREACH
        assert verdict.reason == INCONSISTENT_VERDICT


def test_a_refusal_with_no_reason_is_still_a_refusal():
    verdict = to_cns_result(GateResult(False), make_artifact())
    assert verdict.outcome is double.GateOutcome.TERMINAL_BREACH
    assert verdict.reason == NO_REASON_GIVEN


def test_a_reason_that_is_not_a_gate_reason_is_kept_as_text():
    verdict = to_cns_result(GateResult(False, reason="custom"), make_artifact())  # type: ignore[arg-type]
    assert verdict.outcome is double.GateOutcome.TERMINAL_BREACH
    assert verdict.reason == "custom"


def test_something_that_is_not_a_native_verdict_is_an_error_not_a_pass():
    with pytest.raises(TypeError):
        to_cns_result(None, make_artifact())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        to_cns_result(
            double.GateResult("g", double.GatePosition.ALPHA, double.GateOutcome.PASS),
            make_artifact(),  # type: ignore[arg-type]
        )


def test_an_error_inside_the_gateway_propagates_and_is_never_a_pass():
    class Exploding:
        def evaluate(self, candidate):
            raise RuntimeError("the gateway itself failed")

    for call in (
        lambda: evaluate_to_cns(make_artifact(), Exploding()),
        lambda: CnsGate(Exploding()).check(make_artifact()),  # type: ignore[arg-type]
    ):
        with pytest.raises(RuntimeError):
            call()


def test_a_wrapped_gateway_that_accepts_the_wrong_artifact_is_never_a_pass():
    artifact = make_artifact()
    other = make_artifact(artifact_id="other")

    class Swapping:
        def evaluate(self, candidate):
            return GateResult.accept(other)

    assert evaluate_to_cns(artifact, Swapping()).outcome is double.GateOutcome.TERMINAL_BREACH  # type: ignore[arg-type]
    assert CnsGate(Swapping()).check(artifact).outcome is double.GateOutcome.TERMINAL_BREACH  # type: ignore[arg-type]


# binding --------------------------------------------------------------------


@pytest.mark.parametrize("label,candidate,reason", CORPUS, ids=IDS)
def test_every_verdict_is_bound_to_the_candidate_it_judged(label, candidate, reason):
    verdict = evaluate_to_cns(candidate)
    assert verdict.bound()
    assert verdict.subject_digest == double.subject_digest(judged_content(candidate))
    assert verdict.binds(artifact_subject(candidate), artifact_digest(candidate))


def test_a_verdict_does_not_bind_to_another_artifact_or_a_drifted_one():
    artifact = make_artifact()
    verdict = evaluate_to_cns(artifact)
    other = make_artifact(payload={"message": "other"})
    assert not verdict.binds(artifact_subject(other), artifact_digest(other))
    assert not verdict.binds("a-2", artifact_digest(artifact))
    object.__setattr__(artifact, "payload", {"message": "drifted"})
    assert not verdict.binds(artifact_subject(artifact), artifact_digest(artifact))


def test_a_pass_does_not_bind_to_a_copy_with_a_forged_integrity():
    good, forged = make_artifact(), make_artifact(integrity="f" * 64)
    assert evaluate_to_cns(good).outcome is double.GateOutcome.PASS
    assert not evaluate_to_cns(good).binds(artifact_subject(forged), artifact_digest(forged))


def test_each_governed_field_changes_the_digest():
    base = artifact_digest(make_artifact())
    variants = [
        make_artifact(artifact_id="a-9"),
        make_artifact(payload={"message": "x"}),
        make_artifact(provenance={"source": "model"}),
        make_artifact(epistemic_status=EpistemicStatus.FACT),
        make_artifact(authority=Authority(actor="alice", grant="admin")),
        make_artifact(scope=Scope.EXECUTE),
        make_artifact(integrity="0" * 64),
    ]
    digests = [artifact_digest(candidate) for candidate in variants]
    assert base not in digests
    assert len(set(digests)) == len(digests)


# the Gate shape ---------------------------------------------------------------


def test_a_cns_gate_judges_the_same_way_as_the_gateway_it_wraps():
    for _, candidate, _ in CORPUS:
        inner = GovernanceGateway()
        gate = CnsGate(inner)
        assert gate.name == GATE_NAME
        assert gate.check(candidate) == to_cns_result(inner.evaluate(candidate), candidate)
        assert gate.check(candidate) == evaluate_to_cns(candidate)


def test_the_subject_defaults_to_the_artifact_id_and_can_be_named():
    artifact = make_artifact()
    assert evaluate_to_cns(artifact).subject == "a-1"
    assert evaluate_to_cns(artifact, subject="intake-7").subject == "intake-7"
    assert CnsGate(subject="intake-7").check(artifact).subject == "intake-7"
    assert cns_chain(subject="intake-7").alpha[0].check(artifact).subject == "intake-7"
    assert evaluate_to_cns(make_artifact(artifact_id="   ")).subject == DEFAULT_SUBJECT
    assert evaluate_to_cns(None).subject == DEFAULT_SUBJECT
