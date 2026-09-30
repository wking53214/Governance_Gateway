"""governance_gateway is independent of CNS, and these tests hold whether or
not CNS is installed. They never skip. Each subprocess test runs in a fresh
interpreter in which ``cns`` is blocked outright (``sys.modules['cns'] =
None`` makes any import of it fail), so the result does not depend on what
the test environment happens to contain.

The connected half, which needs CNS, is in ``test_cns_connector.py``.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
import textwrap
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

BLOCK = "import sys; sys.modules['cns'] = None; sys.modules['cns.gate'] = None\n"

CNS_PIN = "3b465dbcc1a6a4ab6f1040f93d44483196abd737"


def _run(
    code: str, *, block: bool = True, extra_path: Path | None = None
) -> subprocess.CompletedProcess[str]:
    path = os.pathsep.join([str(SRC)] + ([str(extra_path)] if extra_path else []))
    return subprocess.run(
        [sys.executable, "-c", (BLOCK if block else "") + textwrap.dedent(code)],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": path, "PATH": ""},
        timeout=60,
    )


def _ok(done: subprocess.CompletedProcess[str]) -> None:
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "ok"


def test_the_package_and_its_connector_import_with_cns_blocked():
    _ok(_run("import governance_gateway, governance_gateway.cns_connector; print('ok')"))


def test_importing_the_package_loads_nothing_from_cns():
    """Not blocked: if CNS is installed, importing still must not touch it."""
    _ok(
        _run(
            """
            import sys
            import governance_gateway, governance_gateway.cns_connector
            loaded = sorted(m for m in sys.modules if m == 'cns' or m.startswith('cns.'))
            assert loaded == [], loaded
            print('ok')
            """,
            block=False,
        )
    )


def test_importing_the_package_does_not_import_the_connector():
    """The connector is opt-in: only importing it by name loads it."""
    _ok(
        _run(
            """
            import sys
            import governance_gateway
            assert 'governance_gateway.cns_connector' not in sys.modules
            assert not hasattr(governance_gateway, 'cns_connector')
            import governance_gateway.cns_connector
            assert 'governance_gateway.cns_connector' in sys.modules
            print('ok')
            """,
            block=False,
        )
    )


def test_no_module_in_the_package_imports_cns_by_statement():
    """The only door to CNS is the importlib call inside ``_cns_gate``."""
    offenders = []
    for path in sorted((SRC / "governance_gateway").glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            offenders += [
                f"{path.name}:{node.lineno} {name}"
                for name in names
                if name == "cns" or name.startswith("cns.")
            ]
    assert offenders == []


def test_the_gateway_still_judges_artifacts_with_cns_blocked():
    _ok(
        _run(
            """
            from governance_gateway import (
                Artifact, Authority, EpistemicStatus, GateReason, GovernanceGateway, Scope,
            )
            artifact = Artifact.create(
                artifact_id="a-1", payload={"x": 1}, provenance={"s": "h"},
                epistemic_status=EpistemicStatus.INFERENCE,
                authority=Authority(actor="alice", grant="review"), scope=Scope.READ_ONLY,
            )
            gateway = GovernanceGateway()
            assert gateway.evaluate(artifact).accepted
            object.__setattr__(artifact, "payload", {"x": 2})
            verdict = gateway.evaluate(artifact)
            assert not verdict.accepted and verdict.reason is GateReason.INTEGRITY_FAILURE
            assert gateway.evaluate(None).reason is GateReason.INVALID_ARTIFACT
            print('ok')
            """
        )
    )


def test_the_connector_says_what_is_missing_when_cns_is_blocked():
    _ok(
        _run(
            """
            from governance_gateway.cns_connector import (
                CnsNotInstalled, artifact_digest, cns_available, cns_chain, evaluate_to_cns,
            )
            assert cns_available() is False
            for call in (
                lambda: evaluate_to_cns(None),
                lambda: artifact_digest(None),
                lambda: cns_chain(),
            ):
                try:
                    call()
                except CnsNotInstalled as exc:
                    assert "pip install '.[cns]'" in str(exc)
                    assert "checkout" in str(exc)
                    assert "governance-gateway[cns]" not in str(exc)  # no such PyPI distribution
                    assert isinstance(exc, ImportError)
                else:
                    raise AssertionError('expected CnsNotInstalled')
            print('ok')
            """
        )
    )


def test_constructing_a_cns_gate_fails_at_construction_not_first_use():
    _ok(
        _run(
            """
            from governance_gateway.cns_connector import CnsGate, CnsNotInstalled
            try:
                CnsGate()
            except CnsNotInstalled:
                print('ok')
            """
        )
    )


def test_judged_content_needs_no_cns_and_holds_only_digestible_types():
    """The content is computed without CNS and is expressible as CNS content."""
    _ok(
        _run(
            """
            import json
            from governance_gateway import (
                Artifact, Authority, EpistemicStatus, Scope,
            )
            from governance_gateway.cns_connector import judged_content

            def digestible(value):
                # exact built-ins only: an enum or a str subclass is not what CNS can digest
                kind = type(value)
                if value is None or kind in (bool, int):
                    return True
                if kind is str:
                    try:
                        value.encode('utf-8')
                    except UnicodeEncodeError:
                        return False
                    return True
                if kind is float:
                    return value == value and value not in (float('inf'), float('-inf'))
                if kind is dict:
                    return all(type(k) is str and digestible(k) and digestible(v)
                               for k, v in value.items())
                if kind is list:
                    return all(digestible(v) for v in value)
                return False

            def artifact(**forced):
                made = Artifact.create(
                    artifact_id="a-1", payload={"x": [1, 2.5, None, True]},
                    provenance={"s": "h"}, epistemic_status=EpistemicStatus.INFERENCE,
                    authority=Authority(actor="alice", grant="review"), scope=Scope.READ_ONLY,
                )
                for name, value in forced.items():
                    object.__setattr__(made, name, value)
                return made

            cyclic = {}
            cyclic['self'] = cyclic
            deep = 'leaf'
            for _ in range(5000):
                deep = {'k': deep}
            candidates = [
                artifact(), None, 1, '', object(), {}, [],
                artifact(payload=float('nan')),
                artifact(payload={1, 2}),
                artifact(payload=cyclic),
                artifact(payload=deep),
                artifact(payload='\\ud800'),
                artifact(payload=10 ** 5000),
                artifact(payload={1: 'a'}),
                artifact(payload={Scope.EXECUTE: 1}),
                artifact(payload=json.loads('{"\\\\ud800": 1}')),
                artifact(provenance=json.loads('{"\\\\ud800": 1}')),
                artifact(authority=None, scope='EXECUTE'),
            ]
            for candidate in candidates:
                assert digestible(judged_content(candidate)), candidate
            assert judged_content(artifact())['form'] == 'artifact'
            print('ok')
            """
        )
    )


def _fake_cns(tmp_path: Path, gate_source: str) -> Path:
    package = tmp_path / "cns"
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "gate.py").write_text(gate_source)
    return tmp_path


def test_a_cns_that_is_too_old_is_refused_at_construction_not_on_first_use(tmp_path):
    """CNS before 1.2.0 has no subject_digest: say so now, not on the first verdict."""
    old = _fake_cns(
        tmp_path,
        "GatePosition = GateOutcome = GateResult = GateChain = object\n",
    )
    _ok(
        _run(
            """
            from governance_gateway.cns_connector import (
                CnsGate, CnsNotInstalled, cns_available, cns_chain, evaluate_to_cns,
            )

            class Spy:
                def evaluate(self, candidate):
                    raise AssertionError('the gateway ran before CNS was checked')

            assert cns_available() is False
            for call in (
                lambda: CnsGate(),
                lambda: cns_chain(),
                lambda: evaluate_to_cns(None, Spy()),
            ):
                try:
                    call()
                except CnsNotInstalled as exc:
                    assert 'subject_digest' in str(exc), str(exc)
                    assert 'not installed' not in str(exc), str(exc)
                else:
                    raise AssertionError('expected CnsNotInstalled')
            print('ok')
            """,
            block=False,
            extra_path=old,
        )
    )


def test_a_cns_that_fails_to_import_is_reported_as_broken_not_as_missing(tmp_path):
    broken = _fake_cns(tmp_path, "import a_module_that_does_not_exist_anywhere\n")
    _ok(
        _run(
            """
            from governance_gateway.cns_connector import CnsGate, CnsNotInstalled, cns_available
            assert cns_available() is False
            try:
                CnsGate()
            except CnsNotInstalled as exc:
                assert 'a_module_that_does_not_exist_anywhere' in str(exc), str(exc)
                assert 'which is not installed' not in str(exc), str(exc)
                assert isinstance(exc.__cause__, ImportError)
            else:
                raise AssertionError('expected CnsNotInstalled')
            print('ok')
            """,
            block=False,
            extra_path=broken,
        )
    )


def test_a_cns_that_cannot_even_be_parsed_does_not_escape_cns_available(tmp_path):
    unparsable = _fake_cns(tmp_path, "def (:\n")
    _ok(
        _run(
            """
            from governance_gateway.cns_connector import CnsGate, CnsNotInstalled, cns_available
            assert cns_available() is False
            try:
                CnsGate()
            except CnsNotInstalled as exc:
                assert isinstance(exc.__cause__, SyntaxError)
            else:
                raise AssertionError('expected CnsNotInstalled')
            print('ok')
            """,
            block=False,
            extra_path=unparsable,
        )
    )


def test_a_cns_with_the_names_the_connector_needs_is_available(tmp_path):
    complete = _fake_cns(
        tmp_path,
        "GatePosition = GateOutcome = GateResult = GateChain = object\n"
        "def subject_digest(content):\n    return 'digest'\n",
    )
    _ok(
        _run(
            """
            from governance_gateway.cns_connector import CnsGate, cns_available
            assert cns_available() is True
            CnsGate()
            print('ok')
            """,
            block=False,
            extra_path=complete,
        )
    )


def test_the_package_declares_no_runtime_dependency_and_pins_the_cns_extra():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert data["project"]["dependencies"] == []
    extras = data["project"]["optional-dependencies"]
    assert extras["test"] == ["pytest>=8"]
    (requirement,) = extras["cns"]
    assert requirement.startswith("cns @ git+")
    assert requirement.endswith(f"@{CNS_PIN}")
