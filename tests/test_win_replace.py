"""Windows file-lock tolerance (GC work laptop, 25 Oct 2026): the swap in make_reproducible retries on PermissionError
(an antivirus / indexer briefly holding a just-written file) and re-raises once the retries are used up."""
from pathlib import Path

from _util import raises, tmpdir

import pw.io_excel as io_excel


def test_replace_retries_transient_permission_error():
    calls = {"n": 0}
    real = Path.replace

    def flaky(self, target):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise PermissionError(5, "Access is denied")
        return real(self, target)
    with tmpdir() as d:
        (d / "a.tmp").write_text("new")
        (d / "a").write_text("old")
        Path.replace = flaky
        try:
            io_excel.replace_file(d / "a.tmp", d / "a", delays=(0, 0, 0))
        finally:
            Path.replace = real
        assert calls["n"] == 3 and (d / "a").read_text() == "new" and not (d / "a.tmp").exists()


def test_replace_gives_up_after_the_retries():
    real = Path.replace

    def locked(self, target):
        raise PermissionError(5, "Access is denied")
    with tmpdir() as d:
        (d / "a.tmp").write_text("new")
        Path.replace = locked
        try:
            raises(PermissionError, io_excel.replace_file, d / "a.tmp", d / "a", delays=(0, 0))
        finally:
            Path.replace = real


def test_make_reproducible_uses_the_retrying_swap():
    import inspect
    assert "replace_file(tmp, path)" in inspect.getsource(io_excel.make_reproducible)
