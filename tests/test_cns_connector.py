"""The connected half: what the gateway's verdicts become when CNS is installed.

Skipped when CNS is absent. The independence half, which must hold in both
environments, is in ``test_cns_independence.py`` and never skips.
"""

from __future__ import annotations

import dataclasses
import json
from enum import Enum

import cns_gate_double as double
import pytest

cns_gate = pytest.importorskip(
    "cns.gate", reason="cns not installed; run in an environment with governance-gateway[cns]"
)

from governance_gateway import (  # noqa: E402
    Artifact,
    Authority,
    EpistemicStatus,
    GateReason,
    GateResult,
    GovernanceGateway,
    Scope,
)
from governance_gateway.cns_connector import (  # noqa: E402
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
from governance_gateway.cns_connector import _MAX_DEPTH, _MAX_EXPANDED  # noqa: E402
from governance_gateway.models import _digest_fields  # noqa: E402

LONE_SURROGATE = json.loads('"\\ud800"')


class Color(str, Enum):
    RED = "red"
    BLUE = "blue"


class BadInt(int):
    def __str__(self):
        raise RuntimeError("hostile __str__")

    __repr__ = __format__ = __str__


class BadStr(str):
    def __str__(self):
        raise RuntimeError("hostile __str__")

    __repr__ = __format__ = __len__ = __str__


def create_artifact(**overrides):
    """A valid artifact built the way a producer builds one."""
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
    """A valid artifact, then any fields forced past construction (as the repo's own tests do)."""
    artifact = create_artifact()
    for name, value in forced.items():
        object.__setattr__(artifact, name, value)
    return artifact


def cyclic():
    loop: dict = {}
    loop["self"] = loop
    return loop


def nested(depth, leaf="leaf", kind=dict):
    """``depth`` containers around ``leaf``, built iteratively."""
    value = leaf
    for _ in range(depth):
        value = {"k": value} if kind is dict else [value]
    return value


def corpus():
    """(label, candidate, the reason the gateway gives, None when it accepts)."""
    R = GateReason
    forged_subclass = type("Forged", (Artifact,), {"expected_integrity": lambda self: self.integrity})
    base = make_artifact()
    forged = forged_subclass(
        artifact_id=base.artifact_id,
        payload={"message": "forged"},
        provenance=base.provenance,
        epistemic_status=base.epistemic_status,
        authority=base.authority,
        scope=base.scope,
        integrity=base.integrity,
    )
    deleted = make_artifact()
    object.__delattr__(deleted, "payload")
    int_keys = make_artifact(payload={1: "a"})
    object.__setattr__(
        int_keys,
        "integrity",
        _digest_fields(
            int_keys.artifact_id, int_keys.payload, int_keys.provenance,
            int_keys.epistemic_status, int_keys.authority, int_keys.scope,
        ),
    )
    looped_authority = Authority("x", "y")
    object.__setattr__(looped_authority, "actor", looped_authority)
    shared_forever = ()
    for _ in range(60):
        shared_forever = (shared_forever, shared_forever)
    surrogate_key = Artifact(
        artifact_id="a", payload=json.loads('{"\\ud800": 1}'), provenance={"s": 1},
        epistemic_status=EpistemicStatus.FACT, authority=Authority("a", "b"),
        scope=Scope.READ_ONLY, integrity="0" * 64,
    )
    rows = [
        ("valid", make_artifact(), None),
        ("valid execute fact", Artifact.create(
            artifact_id="a-2", payload=[1, {"k": None}], provenance={"s": "m"},
            epistemic_status=EpistemicStatus.FACT,
            authority=Authority(actor="bob", grant="run"), scope=Scope.EXECUTE), None),
        ("valid unknown empty payload", Artifact.create(
            artifact_id="a-3", payload={}, provenance={"s": "m"},
            epistemic_status=EpistemicStatus.UNKNOWN,
            authority=Authority(actor="bob", grant="run"), scope=Scope.READ_ONLY), None),
        ("no provenance", make_artifact(provenance=None), R.MISSING_PROVENANCE),
        ("empty provenance", make_artifact(provenance={}), R.MISSING_PROVENANCE),
        ("no authority", make_artifact(authority=None), R.MISSING_AUTHORITY),
        ("str epistemic status", make_artifact(epistemic_status="FACT"), R.INVALID_EPISTEMIC_STATE),
        ("str scope", make_artifact(scope="EXECUTE"), R.INVALID_SCOPE),
        ("forged integrity", make_artifact(integrity="forged"), R.INTEGRITY_FAILURE),
        ("uppercase integrity", make_artifact(integrity="A" * 64), R.INTEGRITY_FAILURE),
        ("tampered payload", make_artifact(payload={"tampered": True}), R.INTEGRITY_FAILURE),
        ("broadened scope", make_artifact(scope=Scope.EXECUTE), R.INTEGRITY_FAILURE),
        ("blank id", make_artifact(artifact_id="   "), R.INVALID_ARTIFACT),
        ("nan payload", make_artifact(payload=float("nan")), R.INVALID_ARTIFACT),
        ("set payload", make_artifact(payload={1, 2}), R.INVALID_ARTIFACT),
        ("bytes payload", make_artifact(payload=b"x"), R.INVALID_ARTIFACT),
        ("lone surrogate payload", make_artifact(payload="\ud800"), R.INVALID_ARTIFACT),
        ("huge int payload", make_artifact(payload=10**5000), R.INVALID_ARTIFACT),
        ("deleted payload", deleted, R.INVALID_ARTIFACT),
        ("forged subclass", forged, R.INTEGRITY_FAILURE),
        ("int-keyed payload, matching integrity", int_keys, None),
        ("payload nested 100 deep, accepted", create_artifact(payload=nested(100)), None),
        ("enum-keyed payload, accepted", create_artifact(payload={Scope.EXECUTE: 1, "a": 2}), None),
        ("custom str-enum-keyed provenance, accepted",
         create_artifact(provenance={Color.RED: {Color.BLUE: [1]}}), None),
        ("negative zero for zero", make_artifact(payload={"x": -0.0}), R.INTEGRITY_FAILURE),
        ("lone surrogate key", surrogate_key, R.INVALID_ARTIFACT),
        ("authority that contains itself", make_artifact(authority=looped_authority), R.INVALID_ARTIFACT),
        ("hostile int subclass in the payload", make_artifact(payload={"n": BadInt(3)}), R.INTEGRITY_FAILURE),
        ("exponentially shared payload, refused before it is read",
         make_artifact(payload=shared_forever, authority=None), R.MISSING_AUTHORITY),
        ("cyclic payload, refused before it is read", make_artifact(payload=cyclic(), authority=None),
         R.MISSING_AUTHORITY),
    ]
    rows += [
        (f"not an artifact: {type(candidate).__name__} {index}", candidate, R.INVALID_ARTIFACT)
        for index, candidate in enumerate((None, 1, "", "text", object(), {}, [], b"x"))
    ]
    return rows


CORPUS = corpus()
IDS = [label for label, _, _ in CORPUS]


def test_cns_is_seen_as_available():
    assert cns_available() is True


def test_the_corpus_reflects_what_the_gateway_really_decides():
    """Guards the corpus: the reason each row is filed under is the gateway's own."""
    for label, candidate, reason in CORPUS:
        native = GovernanceGateway().evaluate(candidate)
        assert native.reason is reason, label
        assert native.accepted is (reason is None), label


def test_the_corpus_reaches_every_reason_the_gateway_can_give():
    reached = {reason for _, _, reason in CORPUS if reason is not None}
    # GOVERNANCE_VIOLATION is defined and never produced by evaluate(): README section 2.
    assert reached == set(GateReason) - {GateReason.GOVERNANCE_VIOLATION}


# position -------------------------------------------------------------------


def test_the_gateway_judges_at_the_alpha_end():
    verdicts = [evaluate_to_cns(candidate) for _, candidate, _ in CORPUS]
    assert {v.position for v in verdicts} == {cns_gate.GatePosition.ALPHA}
    assert CnsGate().position is cns_gate.GatePosition.ALPHA


def test_the_chain_is_admission_only_and_says_so():
    chain = cns_chain()
    assert chain.misplaced() == ()
    assert len(chain.alpha) == 1
    assert chain.omega == ()
    assert chain.complete() is False  # the gateway has no outcome end


# outcome --------------------------------------------------------------------


def test_an_accepted_artifact_maps_to_pass():
    verdict = evaluate_to_cns(make_artifact())
    assert verdict.outcome is cns_gate.GateOutcome.PASS
    assert verdict.gate == GATE_NAME == "governance_gateway"
    assert verdict.reason == ""
    assert not verdict.blocking()


@pytest.mark.parametrize("reason", list(GateReason), ids=lambda r: r.value)
def test_every_refusal_reason_maps_to_terminal_breach_and_keeps_its_value(reason):
    verdict = to_cns_result(GateResult.reject(reason), make_artifact())
    assert verdict.outcome is cns_gate.GateOutcome.TERMINAL_BREACH
    assert verdict.reason == reason.value  # the value, not "GateReason.X"
    assert verdict.blocking()


def test_the_gateway_never_models_a_retry_so_no_verdict_is_one():
    outcomes = {evaluate_to_cns(candidate).outcome for _, candidate, _ in CORPUS}
    assert outcomes == {cns_gate.GateOutcome.PASS, cns_gate.GateOutcome.TERMINAL_BREACH}


# fail closed ----------------------------------------------------------------


def test_a_self_contradicting_native_verdict_never_maps_to_pass():
    artifact = make_artifact()
    other = make_artifact(artifact_id="other")
    contradictions = {
        "accepted without an artifact": GateResult(True),
        "accepted with a reason": GateResult(True, artifact=artifact, reason=GateReason.INVALID_SCOPE),
        "accepted for a different artifact": GateResult(True, artifact=other),
        "accepted is truthy, not True": GateResult("yes", artifact=artifact),  # type: ignore[arg-type]
        "accepted is None": GateResult(None, artifact=artifact),  # type: ignore[arg-type]
    }
    for label, native in contradictions.items():
        verdict = to_cns_result(native, artifact)
        assert verdict.outcome is cns_gate.GateOutcome.TERMINAL_BREACH, label
        assert verdict.reason == INCONSISTENT_VERDICT, label
        assert verdict.blocking(), label
    thing = object()
    for candidate, native in ((None, GateResult(True)), (thing, GateResult(True, artifact=thing))):
        verdict = to_cns_result(native, candidate)  # the gateway refuses non-artifacts first
        assert verdict.outcome is cns_gate.GateOutcome.TERMINAL_BREACH
        assert verdict.reason == INCONSISTENT_VERDICT


def test_a_refusal_with_no_reason_is_still_a_refusal():
    verdict = to_cns_result(GateResult(False), make_artifact())
    assert verdict.outcome is cns_gate.GateOutcome.TERMINAL_BREACH
    assert verdict.reason == NO_REASON_GIVEN


def test_a_reason_that_is_not_a_gate_reason_is_kept_as_text():
    verdict = to_cns_result(GateResult(False, reason="custom"), make_artifact())  # type: ignore[arg-type]
    assert verdict.outcome is cns_gate.GateOutcome.TERMINAL_BREACH
    assert verdict.reason == "custom"


def test_something_that_is_not_a_native_verdict_is_an_error_not_a_pass():
    with pytest.raises(TypeError):
        to_cns_result(None, make_artifact())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        to_cns_result(cns_gate.GateResult("g", cns_gate.GatePosition.ALPHA, cns_gate.GateOutcome.PASS),
                      make_artifact())  # type: ignore[arg-type]


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


# agreement ------------------------------------------------------------------


@pytest.mark.parametrize("label,candidate,reason", CORPUS, ids=IDS)
def test_the_connector_agrees_with_the_gateways_own_decision(label, candidate, reason):
    """The translation must not change what the gateway decided."""
    native = GovernanceGateway().evaluate(candidate)
    verdict = evaluate_to_cns(candidate)
    passed = verdict.outcome is cns_gate.GateOutcome.PASS
    assert passed is native.accepted
    assert cns_gate.resolve([verdict]) is verdict.outcome
    if native.accepted:
        assert verdict.reason == ""
    else:
        assert verdict.outcome is cns_gate.GateOutcome.TERMINAL_BREACH
        assert verdict.reason == native.reason.value


def test_translating_leaves_the_artifact_untouched():
    artifact = make_artifact()
    before = (artifact.payload, artifact.provenance, artifact.integrity, artifact_digest(artifact))
    native = GovernanceGateway().evaluate(artifact)
    evaluate_to_cns(artifact)
    assert native.artifact is artifact
    assert before == (artifact.payload, artifact.provenance, artifact.integrity, artifact_digest(artifact))


# binding --------------------------------------------------------------------


@pytest.mark.parametrize("label,candidate,reason", CORPUS, ids=IDS)
def test_every_verdict_is_bound_to_the_candidate_it_judged(label, candidate, reason):
    verdict = evaluate_to_cns(candidate)
    assert verdict.bound()
    assert cns_gate.unbound([verdict]) == ()
    assert verdict.binds(artifact_subject(candidate), artifact_digest(candidate))


def test_a_verdict_does_not_bind_to_a_different_artifact():
    artifact = make_artifact()
    verdict = evaluate_to_cns(artifact)
    other = make_artifact(artifact_id="a-1", payload={"message": "other"})
    assert artifact_subject(other) == artifact_subject(artifact)
    assert not verdict.binds(artifact_subject(other), artifact_digest(other))
    assert not verdict.binds("a-2", artifact_digest(artifact))


def test_content_drifting_after_the_verdict_no_longer_binds():
    artifact = make_artifact()
    verdict = evaluate_to_cns(artifact)
    assert verdict.binds(artifact_subject(artifact), artifact_digest(artifact))
    object.__setattr__(artifact, "payload", {"message": "drifted"})
    assert not verdict.binds(artifact_subject(artifact), artifact_digest(artifact))


def test_a_pass_on_a_valid_artifact_does_not_bind_to_a_copy_with_a_forged_integrity():
    """The stored integrity is judged content: the gateway refuses the copy."""
    good = make_artifact()
    forged = make_artifact(integrity="f" * 64)
    verdict = evaluate_to_cns(good)
    assert verdict.outcome is cns_gate.GateOutcome.PASS
    assert artifact_digest(good) != artifact_digest(forged)
    assert not verdict.binds(artifact_subject(forged), artifact_digest(forged))


def test_each_governed_field_changes_the_digest():
    base = artifact_digest(make_artifact())
    variants = {
        "artifact_id": make_artifact(artifact_id="a-9"),
        "payload": make_artifact(payload={"message": "x"}),
        "provenance": make_artifact(provenance={"source": "model"}),
        "epistemic_status": make_artifact(epistemic_status=EpistemicStatus.FACT),
        "authority": make_artifact(authority=Authority(actor="alice", grant="admin")),
        "scope": make_artifact(scope=Scope.EXECUTE),
        "integrity": make_artifact(integrity="0" * 64),
    }
    digests = {name: artifact_digest(candidate) for name, candidate in variants.items()}
    assert all(digest != base for digest in digests.values()), digests
    assert len(set(digests.values())) == len(digests)


def test_an_enum_the_gateway_accepts_and_the_string_it_refuses_do_not_digest_alike():
    as_enum = create_artifact(epistemic_status=EpistemicStatus.FACT)
    as_text = create_artifact(epistemic_status=EpistemicStatus.FACT)
    object.__setattr__(as_text, "epistemic_status", "FACT")
    assert GovernanceGateway().evaluate(as_enum).accepted
    assert GovernanceGateway().evaluate(as_text).reason is GateReason.INVALID_EPISTEMIC_STATE
    assert artifact_digest(as_enum) != artifact_digest(as_text)


def test_content_cannot_imitate_a_tagged_form():
    """A plain mapping shaped like a tag and the thing the tag stands for digest apart."""
    assert artifact_digest(make_artifact(payload={"missing": True})) != artifact_digest(
        _without_payload()
    )
    assert artifact_digest(make_artifact(payload={"cycle": True})) != artifact_digest(
        make_artifact(payload=cyclic())
    )
    assert artifact_digest(make_artifact(payload={"opaque": "builtins.set"})) != artifact_digest(
        make_artifact(payload={1, 2})
    )


def _without_payload():
    artifact = make_artifact(payload={"missing": True})
    object.__delattr__(artifact, "payload")
    return artifact


def test_a_non_artifact_is_judged_on_its_type_alone():
    assert judged_content(None) == {"form": "not_an_artifact", "type": "builtins.NoneType"}
    assert artifact_subject(None) == DEFAULT_SUBJECT
    assert artifact_digest({}) == artifact_digest({"any": "dict"}) != artifact_digest([])


def test_a_payload_mapping_with_non_string_keys_is_not_its_stringified_twin():
    natively_same = make_artifact(payload={"1": "a"})
    integer_keyed = next(c for label, c, _ in CORPUS if label.startswith("int-keyed"))
    assert GovernanceGateway().evaluate(integer_keyed).accepted  # the gateway accepts it
    assert artifact_digest(integer_keyed) != artifact_digest(natively_same)
    assert evaluate_to_cns(integer_keyed).outcome is cns_gate.GateOutcome.PASS


HOSTILE_PAYLOADS = [
    pytest.param(float("nan"), id="nan"),
    pytest.param(float("inf"), id="inf"),
    pytest.param(float("-inf"), id="-inf"),
    pytest.param("\ud800", id="lone-surrogate"),
    pytest.param(10**5000, id="huge-int"),
    pytest.param(-(10**5000), id="huge-negative-int"),
    pytest.param({1, 2}, id="set"),
    pytest.param(b"x", id="bytes"),
    pytest.param(object(), id="object"),
    pytest.param(cyclic(), id="cyclic-mapping"),
    pytest.param([cyclic()], id="cyclic-inside-list"),
    pytest.param({1: "a", "b": 2}, id="mixed-keys"),
    pytest.param({(1, 2): "t"}, id="tuple-key"),
    pytest.param({"deep": [{"deeper": (1, 2.5, None, True, "s")}]}, id="deep-json-like"),
    pytest.param(nested(5000), id="5000-deep-dict"),
    pytest.param(nested(5000, kind=list), id="5000-deep-list"),
    pytest.param(Scope.EXECUTE, id="enum"),
    pytest.param(Authority("a", "g"), id="authority"),
    pytest.param({Scope.EXECUTE: 1}, id="enum-key"),
    pytest.param({Color.RED: 1, "a": 2}, id="custom-enum-key-beside-text"),
    pytest.param({LONE_SURROGATE: 1}, id="lone-surrogate-key"),
    pytest.param([{"a": {LONE_SURROGATE: [1]}}], id="lone-surrogate-key-nested"),
    pytest.param({"a": 1, LONE_SURROGATE: 2}, id="lone-surrogate-key-beside-text"),
    pytest.param({BadStr("k"): BadStr("v"), "n": BadInt(3)}, id="hostile-subclasses"),
    pytest.param(nested(40, leaf={Color.BLUE: LONE_SURROGATE}), id="hostile-below-the-bound"),
    pytest.param({"x": -0.0, "y": [0.0]}, id="negative-zero"),
]


@pytest.mark.parametrize("payload", HOSTILE_PAYLOADS)
def test_content_the_gateway_meets_is_always_expressible_as_cns_content(payload):
    """No input makes the digest raise: real hostile content is described, not refused."""
    artifact = make_artifact(payload=payload)
    digest = artifact_digest(artifact)
    assert len(digest) == 64
    assert digest == artifact_digest(artifact)
    assert digest == cns_gate.subject_digest(judged_content(artifact))


def test_a_payload_nested_past_what_cns_can_render_is_still_judged_and_bound():
    """The gateway accepts it (measured: dicts 400 deep on 3.11), so the connector must."""
    artifact = create_artifact(payload=nested(150))
    assert GovernanceGateway().evaluate(artifact).accepted
    verdict = evaluate_to_cns(artifact)
    assert verdict.outcome is cns_gate.GateOutcome.PASS
    assert verdict.binds(artifact_subject(artifact), artifact_digest(artifact))
    assert "subtree_sha256" in repr(judged_content(artifact))


def test_artifacts_that_differ_only_below_the_depth_bound_still_digest_apart():
    """The stored integrity pins the summarized part, so a PASS cannot move."""
    one = create_artifact(payload=nested(150, leaf="one"))
    two = create_artifact(payload=nested(150, leaf="two"))
    assert one.integrity != two.integrity
    assert GovernanceGateway().evaluate(one).accepted
    assert GovernanceGateway().evaluate(two).accepted
    assert artifact_digest(one) != artifact_digest(two)
    assert not evaluate_to_cns(one).binds(artifact_subject(two), artifact_digest(two))


@pytest.mark.parametrize("depth", [1, 20, 31, _MAX_DEPTH, _MAX_DEPTH + 1, 34, 40, 150])
def test_a_pass_never_binds_to_a_copy_that_drifted_at_any_depth(depth):
    """Content changed below the depth bound after the verdict is detected, as above it."""
    good = create_artifact(payload=nested(depth, "one"))
    tampered = create_artifact(payload=nested(depth, "one"))
    object.__setattr__(tampered, "payload", nested(depth, "TWO"))
    verdict = evaluate_to_cns(good)
    assert verdict.outcome is cns_gate.GateOutcome.PASS
    assert GovernanceGateway().evaluate(tampered).reason is GateReason.INTEGRITY_FAILURE
    assert verdict.binds(artifact_subject(good), artifact_digest(good))
    assert not verdict.binds(artifact_subject(tampered), artifact_digest(tampered))


def test_a_pass_never_binds_to_a_copy_that_drifted_inside_a_payload_larger_than_the_bound():
    values = list(range(_MAX_EXPANDED * 3))
    good = create_artifact(payload=values)
    verdict = evaluate_to_cns(good)
    assert verdict.outcome is cns_gate.GateOutcome.PASS
    for index in (0, len(values) // 2, len(values) - 1):
        tampered = create_artifact(payload=values)
        edited = list(values)
        edited[index] = -1
        object.__setattr__(tampered, "payload", edited)
        assert GovernanceGateway().evaluate(tampered).reason is GateReason.INTEGRITY_FAILURE
        assert not verdict.binds(artifact_subject(tampered), artifact_digest(tampered))


def test_a_pass_on_zero_never_binds_to_negative_zero():
    """CNS digests -0.0 like 0.0 and the gateway's integrity does not, so the connector must."""
    good = create_artifact(payload={"x": 0.0})
    tampered = create_artifact(payload={"x": 0.0})
    object.__setattr__(tampered, "payload", {"x": -0.0})
    assert GovernanceGateway().evaluate(good).accepted
    assert GovernanceGateway().evaluate(tampered).reason is GateReason.INTEGRITY_FAILURE
    assert cns_gate.subject_digest({"x": 0.0}) == cns_gate.subject_digest({"x": -0.0})  # CNS alone cannot tell
    verdict = evaluate_to_cns(good)
    assert verdict.binds(artifact_subject(good), artifact_digest(good))
    assert not verdict.binds(artifact_subject(tampered), artifact_digest(tampered))


def test_an_artifact_with_enum_keys_gets_a_pass_the_gateway_gave_it():
    """The gateway accepts it; the connector must not raise where CNS stringifies keys."""
    artifact = create_artifact(payload={Scope.EXECUTE: 1, Color.RED: [2]})
    assert GovernanceGateway().evaluate(artifact).accepted
    verdict = evaluate_to_cns(artifact)
    assert verdict.outcome is cns_gate.GateOutcome.PASS
    assert verdict.binds(artifact_subject(artifact), artifact_digest(artifact))
    as_text = create_artifact(payload={"EXECUTE": 1, "red": [2]})
    assert artifact_digest(artifact) != artifact_digest(as_text)  # stricter than the gateway's integrity


def test_the_digest_is_stable():
    """Pinned: changing what is judged, or how CNS renders it, is a visible change."""
    artifact = make_artifact()
    assert judged_content(artifact) == {
        "form": "artifact",
        "artifact_id": "a-1",
        "payload": {"mapping": {"message": "hello", "items": [1, 2]}},
        "provenance": {"mapping": {"source": "human"}},
        "epistemic_status": {"enum": "governance_gateway.models.EpistemicStatus.INFERENCE"},
        "authority": {"authority": {"actor": "alice", "grant": "review"}},
        "scope": {"enum": "governance_gateway.models.Scope.READ_ONLY"},
        "integrity": artifact.integrity,
    }
    assert artifact_digest(artifact) == (
        "94f40a16d9f359dde2ffd02b0b969aa7b552a4d1e87fdb9a1b71a0ce84652a66"
    )


# the Gate protocol ------------------------------------------------------------


def test_a_cns_gate_satisfies_the_cns_gate_protocol():
    gate = CnsGate()
    assert isinstance(gate, cns_gate.Gate)
    assert gate.name == "governance_gateway"
    assert gate.position is cns_gate.GatePosition.ALPHA


@pytest.mark.parametrize("label,candidate,reason", CORPUS, ids=IDS)
def test_a_cns_gate_judges_the_same_way_as_the_gateway_it_wraps(label, candidate, reason):
    inner = GovernanceGateway()
    gate = CnsGate(inner)
    assert gate.check(candidate) == to_cns_result(inner.evaluate(candidate), candidate)
    assert gate.check(candidate) == evaluate_to_cns(candidate)


def test_a_cns_gate_refuses_a_non_artifact_as_the_gateway_does_instead_of_raising():
    verdict = CnsGate().check(None)
    assert verdict.outcome is cns_gate.GateOutcome.TERMINAL_BREACH
    assert verdict.reason == GateReason.INVALID_ARTIFACT.value
    assert verdict.bound()


def test_the_chain_runs_through_cns_resolution():
    chain = cns_chain()
    passing = [g.check(make_artifact()) for g in chain.alpha]
    refused = [g.check(make_artifact(integrity="forged")) for g in chain.alpha]
    assert cns_gate.resolve(passing) is cns_gate.GateOutcome.PASS
    assert cns_gate.resolve(refused) is cns_gate.GateOutcome.TERMINAL_BREACH
    assert cns_gate.resolve(passing + refused) is cns_gate.GateOutcome.TERMINAL_BREACH


def test_the_subject_defaults_to_the_artifact_id_and_can_be_named():
    artifact = make_artifact()
    assert evaluate_to_cns(artifact).subject == "a-1"
    assert evaluate_to_cns(artifact, subject="intake-7").subject == "intake-7"
    assert CnsGate(subject="intake-7").check(artifact).subject == "intake-7"
    assert cns_chain(subject="intake-7").alpha[0].check(artifact).subject == "intake-7"
    assert evaluate_to_cns(make_artifact(artifact_id="   ")).subject == DEFAULT_SUBJECT
    assert artifact_subject(make_artifact(artifact_id=None)) == DEFAULT_SUBJECT


# the test double -------------------------------------------------------------------


def _accepts(function, content):
    try:
        function(content)
    except Exception:
        return False
    return True


def test_the_test_double_is_no_looser_than_the_real_contract():
    """``tests/cns_gate_double.py`` stands in for CNS in the CNS-free suite; keep it honest."""
    for name in ("GatePosition", "GateOutcome"):
        real, fake = getattr(cns_gate, name), getattr(double, name)
        assert {m.name: m.value for m in fake} == {m.name: m.value for m in real}, name
    for name in ("GateResult", "GateChain"):
        real, fake = getattr(cns_gate, name), getattr(double, name)
        assert [(f.name, f.default) for f in dataclasses.fields(fake)] == [
            (f.name, f.default) for f in dataclasses.fields(real)
        ], name

    fine = [
        {}, {"a": 1}, {"a": [1, 2.5, None, True, "s", {"b": {}}]}, [], [[]], "text", 0, -1, 2**70,
        0.0, -0.0, 1.5, True, None, {"mapping": {"k": "v"}}, {"enum": "x.Y.Z"}, {"subtree_sha256": "0" * 64},
        {"unencodable_str": "'\\ud800'"}, {"é": "日本"}, ["a", ["b", ["c"]]],
    ]
    hazards = [
        {Scope.EXECUTE: 1}, {Color.RED: 1}, {1: "a"}, {(1, 2): "t"}, {b"k": 1}, {None: 1},
        {LONE_SURROGATE: 1}, LONE_SURROGATE, [LONE_SURROGATE], {"a": LONE_SURROGATE},
        float("nan"), float("inf"), {1, 2}, b"x", object(), Authority("a", "b"),
        {"a": {1, 2}}, [object()], {"k": float("-inf")},
    ]
    stricter = [Scope.EXECUTE, Color.RED, {"a": Color.BLUE}, BadStr("v"), {"a": BadInt(3)}]  # CNS tolerates these
    for content in fine:
        assert _accepts(double.subject_digest, content), content
        assert _accepts(cns_gate.subject_digest, content), content
    for content in fine + hazards + stricter:
        # never looser: whatever the double takes, the real function takes too
        assert not (
            _accepts(double.subject_digest, content) and not _accepts(cns_gate.subject_digest, content)
        ), content
    for content in hazards:
        assert not _accepts(double.subject_digest, content), content
        assert not _accepts(cns_gate.subject_digest, content), content
    for content in stricter:
        assert not _accepts(double.subject_digest, content), content
