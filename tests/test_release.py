"""WS4 release: the zip (tools/package.py) ships no reference/, client example or run folder, carries RELEASE.json,
COMMIT.txt, the install notes and the laptop-check launcher, is byte-reproducible, and an installed copy reports the
repo-only tests as skipped (a repo clone missing the same content fails instead)."""
import json
import subprocess
import sys
import zipfile

from _util import REPO, tmpdir

from pw import __version__


def _package():
    sys.path.insert(0, str(REPO / "tools"))
    import package
    return package


def test_release_zip_contents_and_metadata():
    package = _package()
    with tmpdir() as d:
        names = package.build(d / "rel.zip")
        root = f"pricing-workbench-{__version__}/"
        bad = [n for n in names if any(x in n for x in ("/reference/", "/examples/ufic_2027/", "/runs/", "/out/", "/.git/",
                                                        "__pycache__"))]
        assert not bad, bad[:10]
        for need in ("RELEASE.json", "COMMIT.txt", "docs/INSTALL.md", "requirements-native.txt", "tools/laptop_check.py",
                     "tools/pw.py", "pw/pipeline.py", "contracts/treaty_feed_contract.json", "fixtures/RUN_SYN/run_config.json",
                     "examples/scorecard_weights.json"):
            assert root + need in names, need
        assert "RUN_LAPTOP_CHECK.bat" in names
        with zipfile.ZipFile(d / "rel.zip") as z:
            info = json.loads(z.read(root + "RELEASE.json"))
            assert info["version"] == __version__ and info["mode"] == "release"
            assert "examples/ufic_2027" in info["excluded"] and "reference" in info["excluded"]
            assert b"pricing-workbench-*" in z.read("RUN_LAPTOP_CHECK.bat")        # launcher is not tied to a version
        package.build(d / "rel2.zip")
        assert (d / "rel.zip").read_bytes() == (d / "rel2.zip").read_bytes()


def test_installed_release_skips_repo_only_tests_and_clone_does_not():
    package = _package()
    with tmpdir() as d:
        package.build(d / "rel.zip")
        with zipfile.ZipFile(d / "rel.zip") as z:
            z.extractall(d / "inst")
        root = d / "inst" / f"pricing-workbench-{__version__}"
        assert not (root / "reference").exists() and not (root / "examples" / "ufic_2027").exists()
        run = [sys.executable, str(root / "tests" / "run_all.py"), "-q", "-k", "test_ws5_ufic"]
        p = subprocess.run(run, capture_output=True, text=True, cwd=str(d))
        assert p.returncode == 0 and "0 failed, 2 skipped" in p.stdout and "not in release" in p.stdout, p.stdout
        p = subprocess.run([sys.executable, str(root / "tests" / "run_all.py"), "-q", "-k", "test_release_zip"],
                           capture_output=True, text=True, cwd=str(d))
        assert p.returncode == 0 and "1 passed, 0 failed" in p.stdout, p.stdout + p.stderr  # repackaging from an install
        (root / "RELEASE.json").unlink()                       # not a release any more: missing content is a failure
        p = subprocess.run(run, capture_output=True, text=True, cwd=str(d))
        assert p.returncode == 1 and "missing repo content" in p.stdout, p.stdout


def test_version_follows_the_owner_scheme():
    """Owner, 25 Oct 2026: 0.d.d while in development, no digit above 9 (0.0.9 -> 0.1.0); 1.0.0+ only for official GC
    test releases, which this check then needs updating for."""
    import re
    m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", __version__)
    assert m, __version__
    major, minor, patch = map(int, m.groups())
    assert major == 0 and minor <= 9 and patch <= 9, __version__
