"""CLI smoke tests and fixture reproducibility (rebuilding fixtures gives byte-identical files)."""
import hashlib
import subprocess
import sys

from _util import FIX, REPO, tmpdir

PW = [sys.executable, str(REPO / "tools" / "pw.py")]


def _run(*args, ok=True):
    r = subprocess.run(PW + list(args), capture_output=True, text=True, cwd=str(REPO / "docs"))   # cwd is not the repo
    if ok:
        assert r.returncode == 0, r.stderr + r.stdout
    return r


def test_cli_commands():
    with tmpdir() as d:
        _run("catalogue", "parse", str(FIX / "CAT_GAMMA" / "spec.json"), "--out", str(d / "g.json"))
        assert (d / "g.json").exists()
        assert "PASS" in _run("gates", "v1", str(FIX / "CAT_BETA" / "spec.json")).stdout
        assert "5 flagged" in _run("gates", "v2", str(FIX / "CAT_BETA" / "spec.json"), "--out", str(d / "v2.csv")).stdout
        assert '"OK"' in _run("gates", "v0", str(FIX / "EXPO_SYN" / "dim_life.csv"), "--manifest",
                              str(FIX / "EXPO_SYN" / "run_manifest.csv")).stdout
        out = _run("t", "generate", str(REPO / "examples" / "ufic_2027" / "template_spec.json"), "--out", str(d / "u.xlsx")).stdout
        assert "structure hash" in out
        r = _run("exposure", "build", str(FIX / "EXPO_SYN" / "dim_life.csv"), "--maps", str(FIX / "EXPO_SYN" / "maps"),
                 ok=False)
        assert r.returncode == 2 and "MappingRequired" in r.stderr
        r = _run("exposure", "build", str(FIX / "EXPO_SYN" / "dim_life.csv"), "--maps", str(FIX / "EXPO_SYN" / "maps"),
                 "--manifest", str(FIX / "EXPO_SYN" / "run_manifest.csv"), "--catalogue", str(FIX / "CAT_ALPHA" / "spec.json"),
                 "--out", str(d / "x"))
        assert "coverage PASS" in r.stdout


def test_fixtures_rebuild_byte_identical():
    with tmpdir() as d:
        subprocess.run([sys.executable, str(REPO / "tools" / "build_fixtures.py"), "--out", str(d)], check=True, capture_output=True)
        subprocess.run([sys.executable, str(REPO / "tools" / "build_submissions.py"), "--out", str(d)], check=True, capture_output=True)
        committed = sorted(p.relative_to(FIX) for p in FIX.rglob("*") if p.is_file())
        rebuilt = sorted(p.relative_to(d) for p in d.rglob("*") if p.is_file())
        assert committed == rebuilt
        diff = [str(r) for r in committed if _content_hash(FIX / r) != _content_hash(d / r)]
        assert not diff, diff


def _content_hash(p):
    """Bytes for text files; for .xlsx the sorted, uncompressed zip members. Deflate output differs between zlib
    builds (e.g. CPython 3.14 on Windows uses zlib-ng), so compressed bytes are only reproducible on one build;
    the workbook content must be identical everywhere."""
    import zipfile
    if p.suffix != ".xlsx":
        return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    h = hashlib.sha256()
    with zipfile.ZipFile(p) as z:
        for n in sorted(z.namelist()):
            h.update(n.encode())
            h.update(z.read(n))
    return h.hexdigest()


def test_every_cli_command_has_a_laptop_check():
    """SPEC §13: a tool without a laptop check is not complete."""
    src = (REPO / "tools" / "laptop_check.py").read_text(encoding="utf-8")
    cli = (REPO / "tools" / "pw.py").read_text(encoding="utf-8")
    import re
    cmds = re.findall(r'sub\.add_parser\("([a-z]+)"\)', cli)
    assert cmds
    for c in cmds:
        if c == "fixtures":
            continue
        assert f'"{c}"' in src, f"no laptop check for CLI command '{c}'"
    for g in ("v0", "v1", "v2", "v3", "v4"):
        assert f'"{g}"' in src, g
