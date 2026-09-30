"""A test double for the part of ``cns.gate`` that the connector uses.

CI installs only ``.[test]``, so the real CNS is not there and the connected
suite (``test_cns_connector.py``) skips. This double lets the mapping tests in
``test_cns_mapping_double.py`` run everywhere, so a regression in the mapping
(a refusal turned into ``RETRY``, the wrong end, a self-contradicting verdict
turned into ``PASS``) is caught without CNS.

It is a shape, not a copy: the same field names, enum members and methods the
connector touches, and a digest that is deliberately **no looser** than the
real one. ``subject_digest`` here refuses anything but exact ``str``, ``int``,
``float``, ``bool``, ``None``, plain-text-keyed dicts and lists, so content the
connector hands to it is safe for the real function too. The connected suite
checks both claims against the installed CNS
(``test_the_test_double_is_no_looser_than_the_real_contract``).
"""

from __future__ import annotations

import enum
import hashlib
import json
import math
from dataclasses import dataclass


class GatePosition(enum.Enum):
    ALPHA = "alpha"
    OMEGA = "omega"


class GateOutcome(enum.Enum):
    PASS = "pass"
    RETRY = "retry"
    TERMINAL_BREACH = "terminal_breach"


@dataclass(frozen=True, slots=True)
class GateResult:
    gate: str
    position: GatePosition
    outcome: GateOutcome
    reason: str = ""
    subject: str = ""
    subject_digest: str = ""

    def blocking(self) -> bool:
        return self.outcome is not GateOutcome.PASS

    def bound(self) -> bool:
        return bool(self.subject) and bool(self.subject_digest)

    def binds(self, subject: str, digest: str) -> bool:
        return self.bound() and self.subject == subject and self.subject_digest == digest


@dataclass(frozen=True, slots=True)
class GateChain:
    alpha: tuple = ()
    omega: tuple = ()

    def complete(self) -> bool:
        return bool(self.alpha) and bool(self.omega)


def _strict(value: object) -> None:
    kind = type(value)
    if value is None or kind in (bool, int):
        return
    if kind is float:
        if not math.isfinite(value):
            raise TypeError("non-finite float")
        return
    if kind is str:
        value.encode("utf-8")  # a lone surrogate raises UnicodeEncodeError
        return
    if kind is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise TypeError(f"mapping key of type {type(key).__name__}")
            key.encode("utf-8")
            _strict(item)
        return
    if kind in (list, tuple):
        for item in value:
            _strict(item)
        return
    raise TypeError(f"unsupported content type {kind.__name__}")


def subject_digest(content: object) -> str:
    _strict(content)
    rendered = json.dumps(content, sort_keys=True, allow_nan=False, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()
