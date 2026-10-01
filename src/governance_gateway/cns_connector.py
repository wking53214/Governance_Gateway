"""Optional connector to CNS (``cns.gate``).

governance_gateway is independent. It has no runtime dependency, imports
nothing from CNS when it loads, and its whole suite passes with CNS absent.
This module is the one place that knows CNS exists, and it asks for CNS only
when one of its functions is called. Without CNS installed those calls raise
:class:`CnsNotInstalled` with the install command; nothing else in the
package is affected. The package ``__init__`` does not import this module.

What connecting means
---------------------
The gateway keeps its own :class:`~governance_gateway.models.GateResult`
(``accepted``, ``artifact``, ``reason``). CNS's shared gate contract is
``cns.gate.GateResult`` (``gate``, ``position``, ``outcome``, ``reason``,
``subject``, ``subject_digest``). This module translates one into the other
without changing either, so a consumer that speaks CNS can use the gateway
as a gate and resolve its verdict alongside gates from other repositories.

The mapping, and why
--------------------
=====================  =================================================
governance_gateway     CNS
=====================  =================================================
where it judges        ``ALPHA``. The gateway is the admission door: it
                       judges the artifact before policy, decision,
                       conservation or execution exist for it, and a
                       refusal means the artifact never reaches them
                       (README: ``NOT_ADMITTED``). It has no outcome end
                       and this connector does not invent one.
``accepted`` is True   ``PASS`` (only when the verdict is coherent, see
                       below), ``reason`` is empty
refused, any           ``TERMINAL_BREACH``, ``reason`` is the native
``GateReason``         ``GateReason`` value, unchanged. Never ``RETRY``:
                       the gateway "never repairs, promotes, rewrites, or
                       silently coerces", and nothing in the package
                       models a re-attempt or a delta that would mend a
                       refused artifact.
judged content         ``subject`` (the artifact id, or ``"artifact"``)
                       and ``subject_digest``, which is
                       ``cns.gate.subject_digest(judged_content(x))``
=====================  =================================================

Fail closed. A native verdict that contradicts itself is never ``PASS``. It
is ``TERMINAL_BREACH`` with reason ``INCONSISTENT_VERDICT`` when ``accepted``
is not a bool, when an accepted verdict carries a reason, when its
``artifact`` is not the object being translated (a verdict lifted off the
artifact it was issued for), or when the candidate is not an ``Artifact`` at
all (the gateway refuses those before anything else, so an accept for one
cannot have come from it). A refusal (``accepted is False``) with no reason is
still a refusal, with reason ``NO_REASON_GIVEN``.

What the digest covers
----------------------
The judged content is the whole candidate as the gateway sees it: the six
governed fields the gateway's own integrity digest covers **and the stored
``integrity`` string itself**, because the gateway judges that string too.
Without it, a valid artifact and a copy with a forged digest would digest
alike and a PASS on one would bind to the other.

Everything the gateway can accept is described without loss, so a verdict
binds to exactly the content it judged and to nothing that differs from it
anywhere, at any depth or size:

* a scalar becomes an exact built-in (``str``, ``int``, ``float``, ``bool``,
  ``None``), read through the built-in type's own methods, never through an
  override a subclass might carry. ``-0.0`` is tagged ``{"negative_zero":
  True}`` because CNS digests it like ``0.0`` and the gateway does not
* enums are tagged, never passed raw: on Python 3.11
  ``f"{EpistemicStatus.FACT}"`` is ``'EpistemicStatus.FACT'``, and the
  ``FACT`` the gateway accepts must not digest like the ``"FACT"`` it refuses
* a mapping whose keys are all plain text is wrapped as ``{"mapping":
  {...}}``, so no tagged form can be imitated by content. A mapping with any
  other key (an int, an enum, a string CNS cannot encode) is described as
  ``{"mapping_pairs": [[key, value], ...]}``, ordered by key, so insertion
  order never reaches the digest and ``{1: "a"}`` never collides with
  ``{"1": "a"}``
* a container is expanded up to 32 levels deep and 10,000 values per field.
  Anything deeper or larger is replaced by ``{"subtree_sha256": ...}``, a
  SHA-256 of the whole subtree computed without recursion, visiting each
  shared node once. CNS's encoder recurses, and the gateway accepts payloads
  far deeper than it can render (a dict nested 200 deep on Python 3.11), so
  this is what keeps the digest computable while content changed anywhere
  below the bound still changes it

What cannot be described faithfully is described by a tagged stand-in, never
refused, so every decision stays expressible and :func:`judged_content` never
raises on any input whose inspection raises an ordinary exception: a
candidate that is not an ``Artifact`` (its type name), a missing attribute
(``{"missing": True}``), NaN or an infinity, a lone surrogate, an integer too
long for CPython to print, a value of an unsupported type (its type name), a
container that contains itself (the whole field becomes ``{"cycle": True}``),
and a value whose inspection itself raises (``{"undescribable": True}``). The
gateway refuses each of these except the last, so none of them is content a
``PASS`` rests on.

Two things this connector does not do. It does not catch an exception the
gateway itself raises (for example ``RecursionError`` on a circular payload
that is otherwise valid): that is the gateway's behaviour, it is not a
``PASS``, and translating it into a verdict would change what the gateway
decided. And the digest is tamper-evidence, not authentication: anyone who
can recompute it can forge it, exactly as the gateway's own integrity
digest can be forged (README section 3).

Because the gateway has only the admission end, ``cns_chain(...).complete()``
is ``False`` by design. That is the honest shape of this repository, not a
defect in the connector; a consumer that wants a complete chain supplies the
``omega`` end from a repository that has one.

Install the extra from a checkout of this repository:
``pip install '.[cns]'``.
"""

from __future__ import annotations

import hashlib
import importlib
from collections.abc import Mapping
from enum import Enum
from math import copysign, isfinite
from operator import itemgetter
from types import ModuleType
from typing import Any

from .gateway import GovernanceGateway
from .models import Artifact, Authority, GateReason, GateResult

__all__ = [
    "CnsGate",
    "CnsNotInstalled",
    "artifact_digest",
    "artifact_subject",
    "cns_available",
    "cns_chain",
    "evaluate_to_cns",
    "judged_content",
    "to_cns_result",
]

#: Run inside a checkout of this repository; no published distribution is assumed.
INSTALL_HINT = "pip install '.[cns]'"

#: The ``gate`` name on every CNS verdict this connector issues.
GATE_NAME = "governance_gateway"

#: What ``subject`` is when the candidate has no usable ``artifact_id``.
DEFAULT_SUBJECT = "artifact"

#: ``reason`` for a native verdict that contradicts itself.
INCONSISTENT_VERDICT = "INCONSISTENT_VERDICT"

#: ``reason`` for a refused native verdict that carries no reason.
NO_REASON_GIVEN = "NO_REASON_GIVEN"

#: The fields the gateway judges, in the model's own order. ``integrity`` is
#: included on purpose: the gateway compares it to the digest it recomputes.
_JUDGED_FIELDS = (
    "artifact_id",
    "payload",
    "provenance",
    "epistemic_status",
    "authority",
    "scope",
    "integrity",
)

#: What the connector needs from ``cns.gate``. ``subject_digest`` arrived in
#: CNS 1.2.0, so an older install is rejected here, at construction, instead
#: of failing on first use.
_REQUIRED_NAMES = ("GateChain", "GateOutcome", "GatePosition", "GateResult", "subject_digest")

#: Containers nested deeper than this are summarized by a digest, not expanded.
#: CNS's encoder recurses, and the gateway accepts payloads far deeper than it
#: can render (measured: a dict nested 200 deep on Python 3.11).
_MAX_DEPTH = 32

#: Values expanded per field before the rest is summarized by a digest. It
#: bounds the work and the size handed to CNS, whatever the structure. Content
#: is walked in a fixed order, so where the bound falls depends on content only.
_MAX_EXPANDED = 10_000

_MISSING = object()

_LEAF_TYPES = (str, int, float, bool, type(None))


class CnsNotInstalled(ImportError):
    """Raised by this module's functions when ``cns.gate`` cannot be used."""


def _cns_gate() -> ModuleType:
    """Import ``cns.gate`` on demand, or say exactly what is wrong with it."""
    try:
        module = importlib.import_module("cns.gate")
    except ModuleNotFoundError as exc:
        if exc.name in ("cns", "cns.gate"):
            raise CnsNotInstalled(
                "governance_gateway.cns_connector needs the CNS package "
                "(cns.gate), which is not installed. Install it with: "
                f"{INSTALL_HINT}, run inside a governance_gateway checkout. "
                "governance_gateway itself works without it."
            ) from exc
        raise _unusable(f"it could not be imported ({exc})") from exc
    except Exception as exc:  # a broken install can raise anything while loading
        raise _unusable(f"it could not be imported ({type(exc).__name__}: {exc})") from exc
    missing = [name for name in _REQUIRED_NAMES if not hasattr(module, name)]
    if missing:
        raise _unusable(
            f"it lacks {', '.join(missing)}; the connector needs CNS v1.4.0 "
            "(subject_digest arrived in 1.2.0)"
        )
    return module


def _unusable(why: str) -> CnsNotInstalled:
    return CnsNotInstalled(
        "governance_gateway.cns_connector found cns.gate but cannot use it: "
        f"{why}. Reinstall it with: {INSTALL_HINT}, run inside a "
        "governance_gateway checkout. governance_gateway itself works without it."
    )


def cns_available() -> bool:
    """Whether the CNS gate contract can be imported and used in this environment."""
    try:
        _cns_gate()
    except CnsNotInstalled:
        return False
    return True


def _type_name(value: object) -> str:
    kind = type(value)
    return f"{kind.__module__}.{kind.__qualname__}"


def _text(value: object) -> str | None:
    """The exact ``str`` a ``str`` instance holds, or None when CNS cannot encode it.

    Read through ``str``'s own method, so a subclass cannot interfere.
    """
    if not isinstance(value, str):
        return None
    text = str.__str__(value)
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return None
    return text


def _scalar(value: object) -> object:
    """A leaf as content CNS digests faithfully: an exact built-in or a tagged stand-in.

    Subclasses of ``int``, ``float`` and ``str`` are read through the built-in
    type's own methods, so a hostile ``__str__``, ``__repr__`` or ``__len__``
    cannot make this raise or change what is digested.
    """
    if value is _MISSING:
        return {"missing": True}
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, Enum):
        return {"enum": f"{_type_name(value)}.{value.name}"}
    if isinstance(value, int):
        number = int.__int__(value)
        try:
            str(number)  # CNS renders ints in decimal; CPython refuses very long ones
        except ValueError:
            return {"huge_int": hex(number)}
        return number
    if isinstance(value, float):
        number = float.__float__(value)
        if not isfinite(number):
            return {"non_finite_float": repr(number)}
        if number == 0.0 and copysign(1.0, number) < 0:
            return {"negative_zero": True}  # CNS digests -0.0 like 0.0; the gateway does not
        return number
    if isinstance(value, str):
        text = _text(value)
        return text if text is not None else {"unencodable_str": ascii(str.__str__(value))}
    return {"opaque": _type_name(value)}


class _Cycle(Exception):
    """A container that contains itself was found while describing a field."""


class _Walk:
    """State for describing one field: the live path, what may still be expanded, hashed nodes."""

    __slots__ = ("budget", "memo", "path")

    def __init__(self) -> None:
        self.budget = _MAX_EXPANDED
        self.path: set[int] = set()
        # id -> (node, digest). Holding the node keeps its id from being reused.
        self.memo: dict[int, tuple[object, bytes]] = {}


def _is_container(value: object) -> bool:
    if type(value) in _LEAF_TYPES:
        return False
    return isinstance(value, (Mapping, list, tuple, Authority))


def _entries(value: object) -> tuple[str, list[Any]]:
    """The kind of a container and its children: ``(key, item)`` pairs, or items."""
    if isinstance(value, Authority):
        return "authority", [
            ("actor", getattr(value, "actor", _MISSING)),
            ("grant", getattr(value, "grant", _MISSING)),
        ]
    if isinstance(value, Mapping):
        return "mapping", list(value.items())
    return "list", list(value)


def _seal(kind: str, parts: list[bytes]) -> bytes:
    if kind == "list":
        count, body = len(parts), b"".join(parts)
    else:  # parts alternate key, item; entries sort by content, never by insertion
        entries = sorted(parts[index] + parts[index + 1] for index in range(0, len(parts), 2))
        count, body = len(entries), b"".join(entries)
    return hashlib.sha256(b"%s:%d:" % (kind.encode(), count) + body).digest()


def _digest_subtree(
    root: object, walk: _Walk, entries: tuple[str, list[Any]] | None = None
) -> str:
    """SHA-256 over everything below ``root``: no recursion, each shared node once.

    Every part is length-prefixed or fixed-width, so distinct content cannot
    render alike. A container met again while it is still being walked is a
    cycle and stops the walk, so a cyclic or shared structure cannot make this
    take more than one visit per distinct node.
    """
    memo, path, frames = walk.memo, set(), []

    def enter(node: object, node_entries: tuple[str, list[Any]] | None = None) -> bytes | None:
        key = id(node)
        known = memo.get(key)
        if known is not None:
            return known[1]
        if key in path:
            raise _Cycle
        kind, children = node_entries if node_entries is not None else _entries(node)
        if kind != "list":
            children = [part for pair in children for part in pair]
        path.add(key)
        frames.append((node, key, kind, iter(children), []))
        return None

    done = enter(root, entries)
    if done is not None:
        return done.hex()
    while True:
        node, key, kind, remaining, parts = frames[-1]
        for child in remaining:
            if _is_container(child):
                known = enter(child)
                if known is None:
                    break  # walk the child first; this loop resumes where it stopped
                parts.append(b"c" + known)
            else:
                token = repr(_scalar(child)).encode("utf-8")
                parts.append(b"s%d:" % len(token) + token)
        else:
            frames.pop()
            path.discard(key)
            digest = _seal(kind, parts)
            memo[key] = (node, digest)
            if not frames:
                return digest.hex()
            frames[-1][4].append(b"c" + digest)


def _describe_key(key: object, walk: _Walk) -> object:
    if _is_container(key):
        return {"subtree_sha256": _digest_subtree(key, walk)}
    return _scalar(key)


def _describe_mapping(items: list[Any], walk: _Walk, depth: int) -> object:
    texts = [_text(key) if not isinstance(key, Enum) else None for key, _ in items]
    if None not in texts and len(set(texts)) == len(texts):
        ordered = sorted(zip(texts, (item for _, item in items)), key=itemgetter(0))
        return {"mapping": {text: _describe(item, walk, depth) for text, item in ordered}}
    keyed = [(_describe_key(key, walk), item) for key, item in items]
    keyed.sort(key=lambda pair: repr(pair[0]))
    return {"mapping_pairs": [[key, _describe(item, walk, depth)] for key, item in keyed]}


def _describe(value: object, walk: _Walk, depth: int = 0) -> object:
    """Render any value as content CNS can digest, without loss for what the gateway accepts.

    Every dict this returns is a tagged form with a fixed key set, except the
    inner dict under ``"mapping"``, so judged content cannot imitate a tag.
    """
    if not _is_container(value):
        return _scalar(value)
    node = id(value)
    if node in walk.path:
        raise _Cycle
    kind, children = _entries(value)
    cost = 1 + len(children)
    if depth >= _MAX_DEPTH or cost > walk.budget:
        return {"subtree_sha256": _digest_subtree(value, walk, (kind, children))}
    walk.budget -= cost
    walk.path.add(node)
    try:
        if kind == "list":
            return [_describe(item, walk, depth + 1) for item in children]
        if kind == "authority":
            return {"authority": {name: _describe(item, walk, depth + 1) for name, item in children}}
        return _describe_mapping(children, walk, depth + 1)
    finally:
        walk.path.discard(node)


def _describe_field(candidate: object, name: str) -> object:
    try:
        return _describe(getattr(candidate, name, _MISSING), _Walk())
    except _Cycle:
        return {"cycle": True}
    except Exception:  # inspecting the value raised: say so, do not fail the verdict
        return {"undescribable": True}


def judged_content(candidate: object) -> dict[str, object]:
    """The canonical mapping of what the gateway judged when it saw ``candidate``.

    Pure Python: needs no CNS. Contains only exact ``str``, ``int``, ``float``,
    ``bool``, ``None``, plain-text-keyed dicts and lists, so
    ``cns.gate.subject_digest`` accepts it. Never raises on an ``Exception``.
    """
    try:
        is_artifact = isinstance(candidate, Artifact)
    except Exception:
        is_artifact = False
    if not is_artifact:
        # The verdict (INVALID_ARTIFACT) does not depend on anything but this.
        try:
            kind = _type_name(candidate)
        except Exception:
            kind = "unknown"
        return {"form": "not_an_artifact", "type": kind}
    content: dict[str, object] = {"form": "artifact"}
    for name in _JUDGED_FIELDS:
        content[name] = _describe_field(candidate, name)
    return content


def artifact_subject(candidate: object) -> str:
    """The ``subject`` label a verdict on ``candidate`` carries by default."""
    try:
        if isinstance(candidate, Artifact):
            text = _text(getattr(candidate, "artifact_id", None))
            if text is not None and text.strip():
                return text
    except Exception:
        pass
    return DEFAULT_SUBJECT


def artifact_digest(candidate: object) -> str:
    """The digest a bound verdict on ``candidate`` carries.

    Pass it, with :func:`artifact_subject`, to ``GateResult.binds`` to check
    that a verdict was issued against exactly this content.
    """
    return _cns_gate().subject_digest(judged_content(candidate))


def _refusal_reason(result: GateResult) -> str:
    if result.accepted is not False:
        return INCONSISTENT_VERDICT  # accepted but incoherent, or not a bool at all
    if isinstance(result.reason, GateReason):
        return result.reason.value
    return str(result.reason) if result.reason else NO_REASON_GIVEN


def to_cns_result(
    result: GateResult, candidate: object, *, subject: str | None = None
) -> Any:
    """Translate the gateway's verdict on ``candidate`` into a ``cns.gate.GateResult``."""
    gate = _cns_gate()
    if not isinstance(result, GateResult):
        raise TypeError(
            f"expected a governance_gateway GateResult, got {type(result).__name__}"
        )
    coherent_accept = (
        result.accepted is True
        and result.reason is None
        and isinstance(candidate, Artifact)  # the gateway refuses anything else first
        and result.artifact is candidate
    )
    if coherent_accept:
        outcome, reason = gate.GateOutcome.PASS, ""
    else:
        outcome, reason = gate.GateOutcome.TERMINAL_BREACH, _refusal_reason(result)
    return gate.GateResult(
        gate=GATE_NAME,
        position=gate.GatePosition.ALPHA,
        outcome=outcome,
        reason=reason,
        subject=artifact_subject(candidate) if subject is None else subject,
        subject_digest=gate.subject_digest(judged_content(candidate)),
    )


class CnsGate:
    """The gateway as a gate that satisfies ``cns.gate.Gate``.

    ``check`` runs the wrapped gateway unchanged and returns its verdict as a
    bound ``cns.gate.GateResult`` at the ALPHA end. Like the gateway, it
    accepts any candidate: a non-artifact is a refusal, not an error.
    """

    def __init__(
        self, inner: GovernanceGateway | None = None, *, subject: str | None = None
    ) -> None:
        _cns_gate()  # fail here, at construction, not on first use
        self._inner = inner if inner is not None else GovernanceGateway()
        self._subject = subject

    @property
    def name(self) -> str:
        return GATE_NAME

    @property
    def position(self) -> Any:
        return _cns_gate().GatePosition.ALPHA

    def check(self, candidate: object) -> Any:
        return to_cns_result(
            self._inner.evaluate(candidate), candidate, subject=self._subject
        )


def cns_chain(
    gateway: GovernanceGateway | None = None, *, subject: str | None = None
) -> Any:
    """A ``cns.gate.GateChain`` holding the gateway in the ``alpha`` slot.

    ``omega`` stays empty: the gateway has no outcome end.
    """
    gate = _cns_gate()
    return gate.GateChain(alpha=(CnsGate(gateway, subject=subject),))


def evaluate_to_cns(
    candidate: object,
    gateway: GovernanceGateway | None = None,
    *,
    subject: str | None = None,
) -> Any:
    """Run the gateway on ``candidate`` and return its verdict as a CNS result.

    Same gateway, same verdict as ``GovernanceGateway().evaluate``; only the
    representation differs. Combine results with ``cns.gate.resolve``.
    """
    _cns_gate()
    gateway = gateway if gateway is not None else GovernanceGateway()
    return to_cns_result(gateway.evaluate(candidate), candidate, subject=subject)
