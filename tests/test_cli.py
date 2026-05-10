"""Smoke tests for the ``tm-spec`` console-script dispatcher.

We don't spawn a subprocess — we call ``cli.main(argv)`` directly so
that the test runs in-process and counts toward coverage.
"""
from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from tm_spec import cli


def test_help_runs() -> None:
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cli.main([])
    assert rc == 0
    assert "tm-spec" in buf.getvalue().lower()


def test_version_reports_package_version() -> None:
    import tm_spec

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cli.main(["version"])
    assert rc == 0
    assert tm_spec.__version__ in buf.getvalue()


def test_unknown_command_returns_2() -> None:
    err = io.StringIO()
    out = io.StringIO()
    with redirect_stderr(err), redirect_stdout(out):
        rc = cli.main(["this-is-not-a-command"])
    assert rc == 2
    assert "unknown command" in err.getvalue()


def test_validate_dispatch(examples_dir: Path) -> None:
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cli.main(["validate", str(examples_dir / "pyr_smoke.tm.yaml")])
    assert rc == 0
    assert "PASS" in buf.getvalue()


def test_validate_all_dispatch(examples_dir: Path) -> None:
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cli.main(["validate", "--all", str(examples_dir)])
    assert rc == 0
    out = buf.getvalue()
    assert "Summary:" in out
    # The summary line ALWAYS contains a "0 FAIL" / "N FAIL" component, so check
    # the count explicitly rather than substring presence of the word "FAIL".
    assert "0 FAIL" in out, f"expected '0 FAIL' in summary, got:\n{out}"
