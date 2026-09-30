"""What the connector judges: ``judged_content`` and ``artifact_subject``.

Pure Python, no CNS needed, never skipped. These pin the properties the digest
rests on: the content is always something CNS can digest (so no verdict the
gateway can reach turns into an exception), it is faithful to everything the
gateway accepts (so a verdict binds to exactly what it judged, at any depth or
size), and it never depends on insertion order, sharing or hostile subclasses.
"""

from __future__ import annotations

import json
import math
import random
import subprocess
import sys
import textwrap
from enum import Enum
from pathlib import Path

import pytest

from governance_gateway import (
    Artifact,
    Authority,
    EpistemicStatus,
    GateReason,
    GovernanceGateway,
    Scope,
)
from governance_gateway.cns_connector import (
    _MAX_DEPTH,
    _MAX_EXPANDED,
    DEFAULT_SUBJECT,
    artifact_subject,
    judged_content,
)

SRC = Path(__file__).resolve().parents[1] / "src"
LONE_SURROGATE = json.loads('"\\ud800"')


class Color(str, Enum):
    RED = "red"
    BLUE = "blue"


class BadStr(str):
    def __str__(self):
        raise RuntimeError("hostile __str__")

    def __repr__(self):
        raise RuntimeError("hostile __repr__")

    def __len__(self):
        raise RuntimeError("hostile __len__")

    def __format__(self, spec):
        raise RuntimeError("hostile __format__")


class BadInt(int):
    def __str__(self):
        raise RuntimeError("hostile __str__")

    __repr__ = __format__ = __str__


class BadFloat(float):
    def __str__(self):
        raise RuntimeError("hostile __str__")

    __repr__ = __format__ = __str__


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


def nested(depth, leaf="leaf", kind=dict):
    """``depth`` containers around ``leaf``, built iteratively."""
    value = leaf
    for _ in range(depth):
        value = {"k": value} if kind is dict else [value]
    return value


def payload_of(candidate):
    return judged_content(candidate)["payload"]


def assert_digestible(value, where="content"):
    """Only what CNS can digest: exact built-ins and plain-text-keyed dicts and lists."""
    kind = type(value)
    if value is None or kind in (bool, int):
        return
    if kind is float:
        assert math.isfinite(value), where
    elif kind is str:
        value.encode("utf-8")
    elif kind is dict:
        for key, item in value.items():
            assert type(key) is str, f"{where}: key {key!r} is a {type(key).__name__}"
            key.encode("utf-8")
            assert_digestible(item, f"{where}.{key}")
    elif kind is list:
        for index, item in enumerate(value):
            assert_digestible(item, f"{where}[{index}]")
    else:
        raise AssertionError(f"{where}: {kind.__name__} is not digestible")


def run_isolated(code, timeout=60):
    """Run ``code`` in a fresh interpreter: a runaway fails the test instead of hanging it."""
    done = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(SRC), "PATH": ""},
        timeout=timeout,
    )
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


# totality: whatever the gateway can meet, the content is digestible ---------------


def cyclic():
    loop: dict = {}
    loop["self"] = loop
    return loop


def hostile_values():
    shared = [1, 2]
    return {
        "nan": float("nan"),
        "inf": float("inf"),
        "lone surrogate value": LONE_SURROGATE,
        "lone surrogate key": {LONE_SURROGATE: 1},
        "lone surrogate key in a list": [{"ok": {LONE_SURROGATE: [1]}}],
        "lone surrogate among good keys": {"a": 1, LONE_SURROGATE: 2},
        "str enum key": {Scope.EXECUTE: 1},
        "custom str enum key": {Color.RED: 1},
        "enum and text keys": {"a": 1, Scope.READ_ONLY: 2},
        "enum key deep": nested(3, leaf={Color.BLUE: 1}),
        "int keys": {1: "a", 2: "b"},
        "mixed keys": {1: "a", "b": 2, None: 3, 2.5: 4, False: 5},
        "tuple key": {(1, 2): "t"},
        "bytes key": {b"k": 1},
        "set": {1, 2},
        "bytes": b"x",
        "object": object(),
        "huge int": 10**5000,
        "hostile int": BadInt(3),
        "hostile str value": BadStr("v"),
        "hostile str key": {BadStr("k"): 1},
        "hostile str key beside text": {"a": 1, BadStr("b"): 2},
        "hostile float": BadFloat(1.5),
        "cyclic dict": cyclic(),
        "cyclic inside a list": [cyclic()],
        "shared, not cyclic": [shared, shared, {"s": shared}],
        "5000 deep dicts": nested(5000),
        "5000 deep lists": nested(5000, kind=list),
        "authority": Authority("a", "g"),
        "tag lookalike": {"mapping": {"cycle": True}},
        "enum value": Scope.EXECUTE,
    }


HOSTILE = hostile_values()


@pytest.mark.parametrize("label", list(HOSTILE))
def test_whatever_is_in_the_payload_the_content_is_digestible(label):
    assert_digestible(judged_content(make_artifact(payload=HOSTILE[label])))


@pytest.mark.parametrize("label", list(HOSTILE))
def test_whatever_is_in_the_provenance_the_content_is_digestible(label):
    assert_digestible(judged_content(make_artifact(provenance=HOSTILE[label])))
    assert_digestible(judged_content(make_artifact(provenance={"source": HOSTILE[label]})))


def test_every_field_can_hold_anything_and_the_content_stays_digestible():
    for label, value in HOSTILE.items():
        for field in ("artifact_id", "epistemic_status", "scope", "authority", "integrity"):
            assert_digestible(judged_content(make_artifact(**{field: value})), f"{field} {label}")


def test_the_gateway_accepts_enum_keys_so_the_connector_must_describe_them():
    for payload in ({Scope.EXECUTE: 1}, {Color.RED: 1, "a": 2}, {"x": {Color.BLUE: [1]}}):
        artifact = create_artifact(payload=payload)
        assert GovernanceGateway().evaluate(artifact).accepted
        assert_digestible(judged_content(artifact))


def test_a_lone_surrogate_key_is_refused_by_the_gateway_and_described_by_the_connector():
    artifact = Artifact(
        artifact_id="a",
        payload=json.loads('{"\\ud800": 1}'),
        provenance={"s": 1},
        epistemic_status=EpistemicStatus.FACT,
        authority=Authority("a", "b"),
        scope=Scope.READ_ONLY,
        integrity="0" * 64,
    )
    assert GovernanceGateway().evaluate(artifact).reason is GateReason.INVALID_ARTIFACT
    content = judged_content(artifact)
    assert_digestible(content)
    assert "unencodable_str" in repr(content["payload"])


def test_a_non_artifact_is_judged_on_its_type_alone():
    assert judged_content(None) == {"form": "not_an_artifact", "type": "builtins.NoneType"}
    assert judged_content({}) == judged_content({"any": "dict"}) != judged_content([])

    class Meta(type):
        @property
        def __module__(cls):
            raise RuntimeError("hostile metaclass")

    class Hostile(metaclass=Meta):
        pass

    assert judged_content(Hostile()) == {"form": "not_an_artifact", "type": "unknown"}


def test_a_value_that_cannot_be_inspected_is_described_not_raised():
    from collections.abc import Mapping

    class Broken(Mapping):
        def __getitem__(self, key):
            raise KeyError(key)

        def __iter__(self):
            raise RuntimeError("cannot iterate")

        def __len__(self):
            return 1

        def items(self):
            raise RuntimeError("cannot list items")

    class Opaque(Artifact):
        armed = False

        @property
        def payload(self):
            if Opaque.armed:
                raise TypeError("cannot read payload")
            return self.__dict__["_payload"]

        @payload.setter
        def payload(self, value):
            self.__dict__["_payload"] = value

    content = judged_content(make_artifact(payload=Broken()))
    assert content["payload"] == {"undescribable": True}
    assert content["provenance"] == judged_content(make_artifact())["provenance"]
    opaque = Opaque(
        artifact_id="a", payload=1, provenance={"s": 1},
        epistemic_status=EpistemicStatus.FACT, authority=Authority("a", "b"),
        scope=Scope.READ_ONLY, integrity="0" * 64,
    )
    Opaque.armed = True
    assert judged_content(opaque)["payload"] == {"undescribable": True}
    assert GovernanceGateway().evaluate(opaque).reason is GateReason.INVALID_ARTIFACT


def test_an_absent_attribute_is_missing_not_an_error():
    artifact = make_artifact()
    object.__delattr__(artifact, "payload")
    assert judged_content(artifact)["payload"] == {"missing": True}
    assert judged_content(make_artifact(payload={"missing": True}))["payload"] == {
        "mapping": {"missing": True}
    }


# subclasses are read as the plain values they hold ----------------------------------


def test_a_hostile_subclass_is_digested_as_the_plain_value_it_holds():
    plain = {"k": "v", "n": 3, "f": 1.5, "kk": ["a", 2]}
    hostile = {BadStr("k"): BadStr("v"), "n": BadInt(3), "f": BadFloat(1.5), "kk": [BadStr("a"), BadInt(2)]}
    assert payload_of(make_artifact(payload=hostile)) == payload_of(make_artifact(payload=plain))


def test_a_str_subclass_key_digests_as_its_text():
    class Label(str):
        pass

    assert payload_of(make_artifact(payload={Label("a"): 1})) == payload_of(make_artifact(payload={"a": 1}))


def test_negative_zero_is_not_zero():
    """CNS digests -0.0 like 0.0, and the gateway's integrity does not."""
    zero = payload_of(make_artifact(payload={"x": 0.0}))
    negative = payload_of(make_artifact(payload={"x": -0.0}))
    assert zero != negative
    assert zero == {"mapping": {"x": 0.0}}
    assert negative == {"mapping": {"x": {"negative_zero": True}}}
    assert payload_of(make_artifact(payload={"x": BadFloat(-0.0)})) == negative
    assert payload_of(make_artifact(payload=[nested(40, leaf=-0.0)])) != payload_of(
        make_artifact(payload=[nested(40, leaf=0.0)])
    )


def test_scalars_of_different_kinds_that_compare_equal_digest_apart():
    kinds = [1, 1.0, True, "1", None, 0, False, 0.0, ""]
    shallow = [repr(payload_of(make_artifact(payload=value))) for value in kinds]
    deep = [repr(payload_of(make_artifact(payload=nested(40, leaf=value)))) for value in kinds]
    assert len(set(shallow)) == len(kinds)
    assert len(set(deep)) == len(kinds)
    assert payload_of(make_artifact(payload=[1])) == payload_of(make_artifact(payload=(1,)))


def test_an_enum_and_the_text_it_holds_digest_apart_as_values_and_as_keys():
    assert payload_of(make_artifact(payload=Scope.EXECUTE)) != payload_of(make_artifact(payload="EXECUTE"))
    assert payload_of(make_artifact(payload={Scope.EXECUTE: 1})) != payload_of(
        make_artifact(payload={"EXECUTE": 1})
    )
    assert payload_of(make_artifact(payload={1: "a"})) != payload_of(make_artifact(payload={"1": "a"}))


def test_content_cannot_imitate_a_tagged_form():
    assert payload_of(make_artifact(payload={"cycle": True})) != payload_of(make_artifact(payload=cyclic()))
    assert payload_of(make_artifact(payload={"opaque": "builtins.set"})) != payload_of(
        make_artifact(payload={1, 2})
    )
    assert payload_of(make_artifact(payload={"subtree_sha256": "0" * 64})) != payload_of(
        make_artifact(payload=nested(60))
    )
    assert payload_of(make_artifact(payload={"negative_zero": True})) != payload_of(
        make_artifact(payload=-0.0)
    )


# faithful at any depth and any size -----------------------------------------------


@pytest.mark.parametrize("depth", [1, 5, 31, 32, 33, 34, 40, 150, 3000])
@pytest.mark.parametrize("kind", [dict, list])
def test_a_change_anywhere_in_a_nested_payload_changes_the_content(depth, kind):
    one = payload_of(make_artifact(payload=nested(depth, "one", kind)))
    assert one == payload_of(make_artifact(payload=nested(depth, "one", kind)))
    assert one != payload_of(make_artifact(payload=nested(depth, "two", kind)))
    assert ("subtree_sha256" in repr(one)) is (depth > _MAX_DEPTH)


def test_the_bounds_are_the_documented_ones():
    """The README and the connector docstring say 32 levels and 10,000 values."""
    assert (_MAX_DEPTH, _MAX_EXPANDED) == (32, 10_000)


def test_the_bound_is_exactly_the_documented_depth():
    assert "subtree_sha256" not in repr(payload_of(make_artifact(payload=nested(_MAX_DEPTH))))
    assert "subtree_sha256" in repr(payload_of(make_artifact(payload=nested(_MAX_DEPTH + 1))))


def test_a_deep_artifact_the_gateway_accepts_does_not_let_a_tampered_copy_bind():
    for depth in (20, 31, 32, 33, 40, 150):
        good = create_artifact(payload=nested(depth, "one"))
        tampered = create_artifact(payload=nested(depth, "one"))
        object.__setattr__(tampered, "payload", nested(depth, "TWO"))
        assert GovernanceGateway().evaluate(good).accepted
        assert GovernanceGateway().evaluate(tampered).reason is GateReason.INTEGRITY_FAILURE
        assert judged_content(good) != judged_content(tampered), depth


@pytest.mark.parametrize("change", ["value", "key", "type", "order", "length", "zero"])
def test_a_change_below_the_depth_bound_of_any_kind_changes_the_content(change):
    def build(**options):
        leaf = options.get("leaf", {"a": 1, "b": [1, 2]})
        return {"top": nested(_MAX_DEPTH + 5, leaf)}

    base = payload_of(make_artifact(payload=build()))
    changed = {
        "value": {"a": 2, "b": [1, 2]},
        "key": {"c": 1, "b": [1, 2]},
        "type": {"a": 1.0, "b": [1, 2]},
        "order": {"a": 1, "b": [2, 1]},
        "length": {"a": 1, "b": [1, 2, 3]},
        "zero": {"a": 1, "b": [1, -0.0]},
    }[change]
    assert payload_of(make_artifact(payload=build(leaf=changed))) != base


def test_a_large_payload_is_digested_whole_and_a_change_anywhere_in_it_shows():
    just_inside = [0] * (_MAX_EXPANDED - 1)
    just_outside = [0] * _MAX_EXPANDED
    assert payload_of(make_artifact(payload=just_inside)) == just_inside
    assert set(payload_of(make_artifact(payload=just_outside))) == {"subtree_sha256"}
    base = payload_of(make_artifact(payload=list(range(30_000))))
    assert base == payload_of(make_artifact(payload=list(range(30_000))))
    for index in (0, 14_999, 29_999):
        edited = list(range(30_000))
        edited[index] = -1
        assert payload_of(make_artifact(payload=edited)) != base
    assert payload_of(make_artifact(payload=list(range(29_999)))) != base


SUMMARY_PIN = "36f619cf8f3f1c86a27b47e18abd3a331d353f1ec27a2892a2b3446739fef2cb"


def test_the_summary_of_a_deep_payload_is_pinned():
    """Changing how a subtree is hashed is a visible change, like the digest pin."""
    assert payload_of(make_artifact(payload=nested(_MAX_DEPTH + 8, "leaf"))) != payload_of(
        make_artifact(payload=nested(_MAX_DEPTH + 8, "leaf!"))
    )
    summary = payload_of(make_artifact(payload=nested(_MAX_DEPTH + 8, "leaf")))
    for _ in range(_MAX_DEPTH):
        summary = summary["mapping"]["k"]
    assert summary == {"subtree_sha256": SUMMARY_PIN}


# order, sharing and cycles ----------------------------------------------------------


def test_insertion_order_never_reaches_the_content():
    orders = [
        ({1: "a", 2: "b", 3: "c"}, {3: "c", 1: "a", 2: "b"}),
        ({"a": 1, Scope.EXECUTE: 2, 3: 3}, {3: 3, Scope.EXECUTE: 2, "a": 1}),
        ({"a": 1, "b": 2, "c": 3}, {"c": 3, "a": 1, "b": 2}),
        ({(1, 2): "x", (3,): "y"}, {(3,): "y", (1, 2): "x"}),
        ({"z": nested(40, "x"), "y": nested(40, "w")}, {"y": nested(40, "w"), "z": nested(40, "x")}),
        (nested(40, {"a": 1, "b": 2}), nested(40, {"b": 2, "a": 1})),
        (nested(40, {1: "a", 2: "b"}), nested(40, {2: "b", 1: "a"})),
    ]
    for first, second in orders:
        assert payload_of(make_artifact(payload=first)) == payload_of(make_artifact(payload=second)), first


def test_insertion_order_does_not_reach_the_content_of_a_mapping_larger_than_the_bound():
    keys = [f"key-{index}" for index in range(_MAX_EXPANDED + 500)]
    shuffled = list(keys)
    random.Random(7).shuffle(shuffled)
    first = {key: index for index, key in enumerate(keys)}
    second = {key: first[key] for key in shuffled}
    assert list(first) != list(second)
    assert payload_of(make_artifact(payload=first)) == payload_of(make_artifact(payload=second))
    second[shuffled[0]] += 1
    assert payload_of(make_artifact(payload=first)) != payload_of(make_artifact(payload=second))


def test_where_the_expansion_bound_falls_depends_only_on_content():
    """Many sibling mappings, each inside the bound but together over it."""
    keys = [f"row-{index:04d}" for index in range(60)]
    shuffled = list(keys)
    random.Random(3).shuffle(shuffled)

    def rows(order):
        return {key: {f"field-{n}": n for n in range(400)} for key in order}

    assert payload_of(make_artifact(payload=rows(keys))) == payload_of(make_artifact(payload=rows(shuffled)))


def test_a_shared_value_is_not_a_cycle_and_digests_like_its_copies():
    shared = [1, 2]
    assert payload_of(make_artifact(payload=[shared, shared])) == payload_of(
        make_artifact(payload=[[1, 2], [1, 2]])
    )
    mapping = {"x": 1}
    assert payload_of(make_artifact(payload={"a": mapping, "b": mapping})) == payload_of(
        make_artifact(payload={"a": {"x": 1}, "b": {"x": 1}})
    )
    assert "cycle" not in repr(payload_of(make_artifact(payload=[shared, shared])))
    deep = nested(40, "x")
    assert payload_of(make_artifact(payload={"a": deep, "b": deep})) == payload_of(
        make_artifact(payload={"a": nested(40, "x"), "b": nested(40, "x")})
    )
    twin = ()
    for _ in range(12):
        twin = (twin, twin)
    copy = ()
    for _ in range(12):
        copy = (copy, tuple(copy))
    assert payload_of(make_artifact(payload=twin)) == payload_of(make_artifact(payload=copy))


def test_a_container_that_contains_itself_makes_its_whole_field_a_cycle():
    loop: list = []
    loop.append([loop])
    long_loop = nested(_MAX_DEPTH + 10, "x")
    node = long_loop
    while isinstance(node["k"], dict):
        node = node["k"]
    node["k"] = long_loop  # closes the loop below the depth bound
    for payload in (cyclic(), loop, {"a": cyclic()}, [1, [2, loop]], long_loop):
        artifact = make_artifact(payload=payload)
        assert payload_of(artifact) == {"cycle": True}
        assert judged_content(artifact)["provenance"] == judged_content(make_artifact())["provenance"]


def test_an_authority_is_described_and_one_that_contains_itself_is_a_cycle():
    assert judged_content(make_artifact())["authority"] == {
        "authority": {"actor": "alice", "grant": "review"}
    }
    looped = Authority("x", "y")
    object.__setattr__(looped, "actor", looped)
    assert judged_content(make_artifact(authority=looped))["authority"] == {"cycle": True}
    chain = Authority("x", "y")
    tail = chain
    for _ in range(5000):
        link = Authority("x", "y")
        object.__setattr__(tail, "grant", link)
        tail = link
    deep_chain = judged_content(make_artifact(authority=chain))["authority"]
    assert_digestible(deep_chain)
    assert "subtree_sha256" in repr(deep_chain)
    cut = Authority("x", "y")
    object.__delattr__(cut, "grant")
    assert judged_content(make_artifact(authority=cut))["authority"] == {
        "authority": {"actor": "x", "grant": {"missing": True}}
    }


def test_work_is_bounded_by_what_is_distinct_not_by_what_is_shared():
    """An exponentially shared payload, in every place the connector reads, finishes at once."""
    assert run_isolated(
        """
        from governance_gateway import Artifact, Authority, EpistemicStatus, Scope
        from governance_gateway.cns_connector import judged_content

        def artifact(**forced):
            made = Artifact.create(
                artifact_id="a", payload={"x": 1}, provenance={"s": 1},
                epistemic_status=EpistemicStatus.FACT,
                authority=Authority("a", "b"), scope=Scope.READ_ONLY,
            )
            for name, value in forced.items():
                object.__setattr__(made, name, value)
            return made

        dag = ()
        for _ in range(60):
            dag = (dag, dag)
        listy = []
        for _ in range(60):
            listy = [listy, listy]
        lonely = ()
        for _ in range(60):
            lonely = {"a": lonely, "b": lonely}

        # refused before the payload is read, so the gateway is O(1) and so must the connector be
        for shared in (dag, listy, lonely):
            content = judged_content(artifact(payload=shared, authority=None))
            assert content["authority"] is None and len(repr(content)) < 10 ** 7
        content = judged_content(artifact(provenance={"s": dag}, payload=[dag, listy], authority=None))
        assert content["authority"] is None and len(repr(content)) < 10 ** 7

        # a cycle found after a large shared structure has been walked
        root = []
        root.append(dag)
        root.append([root])
        assert judged_content(artifact(payload=root))["payload"] == {"cycle": True}
        print("ok")
        """
    ) == "ok"


# the subject label -------------------------------------------------------------------


def test_the_subject_is_the_artifact_id_when_there_is_a_usable_one():
    assert artifact_subject(make_artifact()) == "a-1"
    assert artifact_subject(make_artifact(artifact_id=Color.RED)) == "red"  # the text it holds
    assert artifact_subject(make_artifact(artifact_id=BadStr("hostile"))) == "hostile"
    assert type(artifact_subject(make_artifact(artifact_id=BadStr("hostile")))) is str


@pytest.mark.parametrize(
    "candidate",
    [
        make_artifact(artifact_id="   "),
        make_artifact(artifact_id=None),
        make_artifact(artifact_id=7),
        make_artifact(artifact_id=LONE_SURROGATE),
        None,
        "a-1",
        object(),
    ],
    ids=["blank", "none", "int", "lone-surrogate", "none-candidate", "text-candidate", "object"],
)
def test_without_a_usable_artifact_id_the_subject_is_the_default(candidate):
    assert artifact_subject(candidate) == DEFAULT_SUBJECT


# random accepted artifacts ---------------------------------------------------------------


def _random_value(rng, depth):
    pick = rng.random()
    if depth <= 0 or pick < 0.3:
        return rng.choice(
            ["", "a", "é", 0, 1, -1, 2**70, 0.0, -0.0, 1.5, 1e300, True, False, None, Scope.EXECUTE, Color.RED]
        )
    if pick < 0.6:
        items = [_random_value(rng, depth - 1) for _ in range(rng.randint(0, 4))]
        return tuple(items) if rng.random() < 0.3 else items
    if pick < 0.8:
        return {rng.choice(["a", "b", "c", "mapping", "cycle"]): _random_value(rng, depth - 1)
                for _ in range(rng.randint(0, 4))}
    if pick < 0.9:
        return {rng.choice([Scope.EXECUTE, Color.BLUE, "a", "z"]): _random_value(rng, depth - 1)
                for _ in range(rng.randint(1, 3))}
    return {rng.randint(0, 5): _random_value(rng, depth - 1) for _ in range(rng.randint(1, 3))}


def _reordered(value, rng):
    if isinstance(value, dict):
        items = list(value.items())
        rng.shuffle(items)
        return {key: _reordered(item, rng) for key, item in items}
    if isinstance(value, list):
        return [_reordered(item, rng) for item in value]
    if isinstance(value, tuple):
        return tuple(_reordered(item, rng) for item in value)
    return value


def _edited(value, rng):
    """The same value with one scalar changed, or None when there is nothing to change."""
    spots = []

    def walk(node, path):
        if isinstance(node, dict):
            for key, item in node.items():
                walk(item, path + [key])
        elif isinstance(node, (list, tuple)):
            for index, item in enumerate(node):
                walk(item, path + [index])
        else:
            spots.append(path)

    def plain(node):
        if isinstance(node, dict):
            return {key: plain(item) for key, item in node.items()}
        if isinstance(node, (list, tuple)):
            return [plain(item) for item in node]
        return node

    walk(value, [])
    spots = [path for path in spots if path]
    if not spots:
        return None
    copy = plain(value)
    path = rng.choice(spots)
    holder = copy
    for step in path[:-1]:
        holder = holder[step]
    old = holder[path[-1]]
    if isinstance(old, bool):
        new = not old
    elif isinstance(old, Enum):
        new = "changed"
    elif isinstance(old, str):
        new = old + "x"
    elif isinstance(old, int):
        new = old + 1
    elif isinstance(old, float):
        new = old * 2 if old else (0.0 if math.copysign(1, old) < 0 else -0.0)
    else:
        new = 0
    holder[path[-1]] = new
    return copy


def test_random_accepted_artifacts_are_described_faithfully():
    rng = random.Random(20260930)
    checked = tampered = 0
    for _ in range(700):
        payload = _random_value(rng, rng.randint(1, 5))
        if rng.random() < 0.25:
            payload = nested(rng.choice([20, 33, 40, 80]), payload, rng.choice([dict, list]))
        try:
            artifact = create_artifact(payload=payload)
        except (TypeError, ValueError):
            continue
        assert GovernanceGateway().evaluate(artifact).accepted
        content = judged_content(artifact)
        assert_digestible(content)
        checked += 1
        assert judged_content(create_artifact(payload=_reordered(payload, rng))) == content
        edit = _edited(payload, rng)
        if edit is None:
            continue
        copy = create_artifact(payload=payload)
        object.__setattr__(copy, "payload", edit)
        if GovernanceGateway().evaluate(copy).accepted:
            continue  # the gateway cannot tell it apart either
        tampered += 1
        assert judged_content(copy) != content, (payload, edit)
    assert checked > 400 and tampered > 150, (checked, tampered)
