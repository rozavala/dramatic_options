"""#407 — one formatted root handler: every project logger reaches the journal, a library's INFO does not."""

from __future__ import annotations

import io
import logging
from pathlib import Path

import orchestrator
from data.forward_catalysts import ForwardCatalysts

REPO = Path(orchestrator.__file__).resolve().parent


def _handler() -> logging.Handler:
    hs = [h for h in logging.getLogger().handlers if h.get_name() == "dramatic"]
    assert len(hs) == 1, "exactly one project handler on the root logger"
    return hs[0]


def _record(level: int, pathname: str, name: str = "x") -> logging.LogRecord:
    return logging.LogRecord(name, level, pathname, 1, "msg", None, None)


def test_a_project_module_info_line_reaches_the_handler_formatted(tmp_path, monkeypatch):
    h = _handler()
    buf = io.StringIO()
    monkeypatch.setattr(h, "stream", buf)
    ForwardCatalysts(str(tmp_path / "absent.json"))      # real repo code: logs INFO on the data.forward_catalysts logger
    line = buf.getvalue()
    assert " INFO data.forward_catalysts: forward_catalysts: no pin file at " in line


def test_info_passes_only_from_project_files_warning_from_anywhere():
    h = _handler()
    assert h.filter(_record(logging.INFO, str(REPO / "monitor.py"), "monitor"))
    assert h.filter(_record(logging.INFO, str(REPO / "council" / "router.py"), "council.router"))
    site = "/usr/lib/python3/site-packages/httpx/_client.py"          # a library logging a request URL at INFO
    assert not h.filter(_record(logging.INFO, site, "httpx"))
    assert not h.filter(_record(logging.INFO, str(REPO / "venv" / "lib" / "site-packages" / "x.py"), "x"))
    assert h.filter(_record(logging.WARNING, site, "httpx"))           # a library's WARNING still shows, formatted


def test_no_tree_keeps_a_private_handler_so_nothing_prints_twice():
    for name in ("orchestrator", "council", "monitor", "carry", "paper_loop", "broker", "shadow_book"):
        lg = logging.getLogger(name)
        assert lg.propagate and not lg.handlers, name


def test_configuring_again_never_stacks_a_second_handler():
    orchestrator._configure_logging()
    orchestrator._configure_logging()
    _handler()


def test_a_checkout_imported_through_a_symlink_still_logs_project_info(tmp_path):
    # record.pathname keeps the symlinked spelling, the resolved repo dir does not: both must count as project code
    import subprocess
    import sys

    link = tmp_path / "checkout"
    link.symlink_to(REPO, target_is_directory=True)
    code = (f"import sys; sys.path.insert(0, {str(link)!r}); import orchestrator; "
            "from data.forward_catalysts import ForwardCatalysts; ForwardCatalysts('/nonexistent/pins.json')")
    out = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, capture_output=True, text=True, timeout=120)
    assert " INFO data.forward_catalysts: forward_catalysts: no pin file at /nonexistent/pins.json" in out.stderr
