"""Data boundary (CLAUDE.md): no cedant labels or values outside examples/<cedant>/ and reference/; packaging
excludes reference/. The forbidden token list lives in the example folder so tests/ itself stays clean."""
import re
import zipfile

from _util import REPO, load_json, requires, tmpdir

SCANNED = ["pw", "registry", "fixtures", "tests", "tools", "contracts", "specs"]
TEXT = {".py", ".json", ".csv", ".md", ".txt"}


def _texts():
    for top in SCANNED:
        for p in sorted((REPO / top).rglob("*")):
            if not p.is_file() or "__pycache__" in p.parts:
                continue
            if p.suffix in TEXT:
                yield p, p.read_text(encoding="utf-8", errors="replace")
            elif p.suffix == ".xlsx":
                with zipfile.ZipFile(p) as z:
                    yield p, " ".join(z.read(n).decode("utf-8", "replace") for n in z.namelist() if n.endswith(".xml"))


@requires("examples/ufic_2027")
def test_no_cedant_tokens_outside_examples_and_reference():
    tokens = load_json(REPO / "examples" / "ufic_2027" / "expected_structure.json")["forbidden_tokens"]
    pats = [(t, re.compile(r"(?<![A-Za-z0-9])" + re.escape(t) + r"(?![A-Za-z0-9])")) for t in tokens]
    hits = []
    for p, txt in _texts():
        for t, rx in pats:
            if rx.search(txt):
                hits.append(f"{p.relative_to(REPO)}: {t}")
    assert not hits, hits[:20]


def test_package_excludes_reference_and_client_examples():
    import sys
    sys.path.insert(0, str(REPO / "tools"))
    import package
    with tmpdir() as d:
        names = package.build(d / "rel.zip")
        assert names and not [n for n in names if "/reference/" in n or "/examples/ufic_2027/" in n or "/runs/" in n]
        assert any(n.endswith("/pw/evaluator.py") for n in names)
        with zipfile.ZipFile(d / "rel.zip") as z:
            assert len(z.namelist()) == len(names)


@requires("examples/ufic_2027")
def test_check_bundle_has_runner_and_examples_but_no_reference():
    import sys
    sys.path.insert(0, str(REPO / "tools"))
    import package
    with tmpdir() as d:
        names = package.build(d / "check.zip", check_bundle=True)
        assert "RUN_LAPTOP_CHECK.bat" in names
        assert any(n.endswith("/COMMIT.txt") for n in names)
        assert any("/examples/ufic_2027/template_spec.json" in n for n in names)
        assert not [n for n in names if "/reference/" in n or "/runs/" in n]
