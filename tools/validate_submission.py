#!/usr/bin/env python3
"""Submission gate: mechanically check every hard constraint before zipping.

    python3 tools/validate_submission.py [marketplace-root]

run_tests.py proves the *logic* is right. This proves the *package* is
submittable: manifest shape, agentskills.io compliance, report conformance
against the published schema, determinism, and packaging limits.

FAIL blocks submission. WARN is advisory — read it, then decide.
Exit code is non-zero only if a FAIL fired.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

# The gate checks for build junk itself: the env var keeps child processes
# clean, the flag keeps our own imports clean.
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

# The marketplace root to check. The gate lives outside it, so it never ships.
REPO = Path(__file__).resolve().parent.parent
ROOT = (Path(sys.argv[1]).resolve() if len(sys.argv) > 1
        else REPO / "brand-ai-readiness-audit-v2.1")
FIXTURE = ROOT / "tests" / "fixtures" / "extraction_tiers.bundle.json"

# agentskills.io frontmatter limits
NAME_MAX = 64
DESC_MAX = 1024
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# Hard limits from the problem statement (Section 5)
ZIP_MAX_BYTES = 50 * 1024 * 1024
RUNTIME_MAX_S = 300

# Things that must never ship inside the zip
JUNK_DIRS = {"__pycache__", ".git", ".pytest_cache", ".mypy_cache", ".venv", "venv"}
JUNK_SUFFIXES = {".pyc", ".pyo", ".DS_Store"}
WEIGHT_SUFFIXES = {".bin", ".pt", ".pth", ".onnx", ".safetensors", ".h5", ".ckpt", ".pkl", ".gguf"}

fails: list[str] = []
warns: list[str] = []


def _section(title: str) -> None:
    print(f"\n{title}")


def ok(label: str) -> None:
    print(f"  ok   {label}")


def fail(label: str, detail: str = "") -> None:
    fails.append(label)
    print(f"  FAIL {label}" + (f" — {detail}" if detail else ""))


def warn(label: str, detail: str = "") -> None:
    warns.append(label)
    print(f"  warn {label}" + (f" — {detail}" if detail else ""))


def require(cond: bool, label: str, detail: str = "") -> bool:
    ok(label) if cond else fail(label, detail)
    return cond


def advise(cond: bool, label: str, detail: str = "") -> bool:
    ok(label) if cond else warn(label, detail)
    return cond


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Minimal YAML-frontmatter reader: scalars + folded (>-) and literal (|) blocks.

    Deliberately dependency-free so the gate runs anywhere the skills do.
    """
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    raw = text[text.find("\n", 3) + 1 : end + 1]
    body = text[end + 4 :]

    meta: dict[str, str] = {}
    key: str | None = None
    buf: list[str] = []
    for line in raw.splitlines():
        if key and (line.startswith((" ", "\t")) or not line.strip()):
            buf.append(line.strip())
            continue
        if key:
            meta[key] = " ".join(p for p in buf if p).strip()
            key, buf = None, []
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        k, v = k.strip(), v.strip()
        if v in {">", ">-", "|", "|-", ""}:
            key, buf = k, []
        else:
            meta[k] = v.strip("'\"")
    if key:
        meta[key] = " ".join(p for p in buf if p).strip()
    return meta, body


# --------------------------------------------------------------------------
_section("Manifest (marketplace.json)")

mf_path = ROOT / "marketplace.json"
manifest: dict = {}
skills: list[dict] = []
if require(mf_path.is_file(), "marketplace.json exists at marketplace root"):
    try:
        manifest = json.loads(mf_path.read_text(encoding="utf-8"))
        ok("marketplace.json is valid JSON")
    except json.JSONDecodeError as e:
        fail("marketplace.json is valid JSON", str(e))

if manifest:
    for field in ("name", "version", "skills"):
        require(field in manifest, f"manifest declares '{field}'")
    advise("description" in manifest, "manifest declares 'description'", "helps a human browsing the marketplace")
    advise("license" in manifest, "manifest declares 'license'")

    skills = manifest.get("skills") or []
    require(isinstance(skills, list) and bool(skills), "manifest lists at least one skill")

    entries = [s for s in skills if s.get("entrypoint") is True]
    require(len(entries) == 1, "exactly one skill marked entrypoint", f"found {len(entries)}")

    ids = [s.get("id") for s in skills]
    require(all(ids), "every skill entry has an 'id'")
    require(len(ids) == len(set(ids)), "skill ids are unique", f"{ids}")
    require(all(s.get("path") for s in skills), "every skill entry has a 'path'")

    missing = [s.get("path") for s in skills if not (ROOT / str(s.get("path", ""))).is_dir()]
    require(not missing, "every listed skill path exists", f"missing: {missing}")

    # Reverse check: a folder on disk that the manifest forgot is invisible to the grader.
    on_disk = {p.name for p in (ROOT / "skills").iterdir() if p.is_dir()} if (ROOT / "skills").is_dir() else set()
    listed = {Path(str(s.get("path", ""))).name for s in skills}
    orphans = sorted(on_disk - listed)
    require(not orphans, "no skill folder is missing from the manifest", f"orphaned: {orphans}")

    for s in skills:
        pid, ppath = s.get("id"), Path(str(s.get("path", ""))).name
        advise(pid == ppath, f"{pid}: id matches folder name", f"folder is '{ppath}'")

# --------------------------------------------------------------------------
_section("SKILL.md compliance (agentskills.io)")

for s in skills:
    sid = s.get("id", "?")
    folder = ROOT / str(s.get("path", ""))
    sm = folder / "SKILL.md"
    if not require(sm.is_file(), f"{sid}: SKILL.md exists"):
        continue

    text = sm.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)

    if not require(bool(meta), f"{sid}: has YAML frontmatter"):
        continue

    name = meta.get("name", "")
    if require(bool(name), f"{sid}: frontmatter has 'name'"):
        require(len(name) <= NAME_MAX, f"{sid}: name <= {NAME_MAX} chars", f"{len(name)}")
        require(bool(NAME_RE.match(name)), f"{sid}: name is lowercase-hyphen", f"got '{name}'")
        require(name == folder.name, f"{sid}: name matches folder name", f"'{name}' vs '{folder.name}'")

    desc = meta.get("description", "")
    if require(bool(desc), f"{sid}: frontmatter has 'description'"):
        require(len(desc) <= DESC_MAX, f"{sid}: description <= {DESC_MAX} chars", f"{len(desc)}")
        advise(len(desc) >= 80, f"{sid}: description is substantive", f"only {len(desc)} chars")

    require(bool(meta.get("license")), f"{sid}: frontmatter has 'license'")
    advise(bool(meta.get("allowed-tools")), f"{sid}: declares allowed-tools")
    require(len(body.strip()) > 0, f"{sid}: SKILL.md has a body")

    lower = body.lower()
    for heading in ("when to use", "input", "procedure", "output"):
        advise(heading in lower, f"{sid}: body covers '{heading}'")

    # Progressive disclosure: detail belongs in references/ and scripts/.
    n_lines = len(text.splitlines())
    advise(n_lines <= 200, f"{sid}: SKILL.md is lean (<=200 lines)", f"{n_lines} lines")
    advise(
        (folder / "references").is_dir() or (folder / "scripts").is_dir(),
        f"{sid}: bundles references/ or scripts/",
    )

# --------------------------------------------------------------------------
_section("Report conformance (replayed, no network)")

schema_path = ROOT / "schema" / "audit-report.schema.json"
report: dict = {}

if require(FIXTURE.is_file(), "replay fixture exists", str(FIXTURE)):
    entry = next((s for s in skills if s.get("entrypoint")), None)
    audit = ROOT / str(entry.get("path", "")) / "scripts" / "audit.py" if entry else None
    if audit and require(audit.is_file(), "entrypoint exposes scripts/audit.py"):
        proc = subprocess.run(
            [sys.executable, str(audit), "--replay", str(FIXTURE)],
            capture_output=True, text=True, cwd=ROOT,
        )
        if require(proc.returncode == 0, "entrypoint replays cleanly", proc.stderr.strip()[-300:]):
            try:
                report = json.loads(proc.stdout)
                ok("entrypoint emits valid JSON on stdout")
            except json.JSONDecodeError as e:
                fail("entrypoint emits valid JSON on stdout", str(e))

if report:
    # The problem statement's required floor, checked literally and independently
    # of our own schema — our schema could itself drift from the spec.
    for field in ("site", "audited_at", "summary", "findings"):
        require(field in report, f"report has required '{field}'")

    summary = report.get("summary") or {}
    for field in ("total_findings", "critical", "high", "medium"):
        require(field in summary, f"summary has required '{field}'")

    try:
        datetime.strptime(str(report.get("audited_at", "")), "%Y-%m-%dT%H:%M:%SZ")
        ok("audited_at is RFC3339 UTC")
    except ValueError:
        fail("audited_at is RFC3339 UTC", f"got '{report.get('audited_at')}'")

    findings = report.get("findings") or []
    require(isinstance(findings, list), "findings is an array")
    bad = [
        f.get("id", "?")
        for f in findings
        if not all(k in f for k in ("id", "title", "severity", "evidence", "suggested_action"))
    ]
    require(not bad, "every finding has the 5 required fields", f"offenders: {bad}")

    no_action = [f.get("id") for f in findings if not (f.get("suggested_action") or {}).get("summary")]
    require(not no_action, "every suggested_action has a summary", f"offenders: {no_action}")
    no_prio = [f.get("id") for f in findings if not (f.get("suggested_action") or {}).get("priority")]
    require(not no_prio, "every suggested_action has a priority", f"offenders: {no_prio}")

    empty_ev = [f.get("id") for f in findings if not str(f.get("evidence", "")).strip()]
    require(not empty_ev, "no finding has empty evidence", f"offenders: {empty_ev}")

    # Counts must agree with the array, or the summary misleads a non-expert reader.
    # Three statuses now: a defect, something unobservable behind a blocker, and
    # something that looks deliberate. Only the first counts as "active".
    active = [f for f in findings if f.get("status", "active") == "active"]
    latent = [f for f in findings if f.get("status") == "latent"]
    confirm = [f for f in findings if f.get("status") == "confirm_intent"]
    require(all(f.get("status", "active") in ("active", "latent", "confirm_intent")
                for f in findings),
            "every finding has a status the schema declares",
            "a sub-skill emitted an undeclared status value")
    require(len(active) + len(latent) + len(confirm) == len(findings),
            "active + latent + confirm_intent accounts for every finding",
            f"{len(active)}+{len(latent)}+{len(confirm)} != {len(findings)}")
    if "confirm_intent_findings" in summary:
        require(summary["confirm_intent_findings"] == len(confirm),
                "summary.confirm_intent_findings matches the array",
                f"summary={summary['confirm_intent_findings']} actual={len(confirm)}")
    if "total_findings" in summary:
        require(
            summary["total_findings"] == len(findings),
            "summary.total_findings matches len(findings)",
            f"summary={summary['total_findings']} actual={len(findings)}",
        )
    if "active_findings" in summary:
        require(
            summary["active_findings"] == len(active),
            "summary.active_findings matches active findings",
            f"summary={summary['active_findings']} actual={len(active)}",
        )
    for sev in ("critical", "high", "medium", "low"):
        if sev in summary:
            actual = sum(1 for f in active if f.get("severity") == sev)
            require(summary[sev] == actual, f"summary.{sev} matches findings", f"summary={summary[sev]} actual={actual}")

    if require(schema_path.is_file(), "audit-report.schema.json exists"):
        try:
            import jsonschema

            jsonschema.validate(report, json.loads(schema_path.read_text(encoding="utf-8")))
            ok("report validates against the published schema")
        except ImportError:
            warn("report validates against the published schema", "jsonschema not installed; skipped")
        except Exception as e:  # ValidationError / SchemaError
            fail("report validates against the published schema", str(e).split("\n")[0][:200])

# --------------------------------------------------------------------------
_section("Determinism")

if FIXTURE.is_file() and report:
    entry = next((s for s in skills if s.get("entrypoint")), None)
    audit = ROOT / str(entry.get("path", "")) / "scripts" / "audit.py"
    runs = []
    for _ in range(2):
        p = subprocess.run(
            [sys.executable, str(audit), "--replay", str(FIXTURE)],
            capture_output=True, text=True, cwd=ROOT,
        )
        try:
            d = json.loads(p.stdout)
            d.pop("audited_at", None)  # wall-clock is expected to differ
            runs.append(json.dumps(d, sort_keys=True))
        except json.JSONDecodeError:
            runs.append(f"<unparseable:{p.returncode}>")
    require(len(runs) == 2 and runs[0] == runs[1], "two replays of one bundle are byte-identical")

# --------------------------------------------------------------------------
_section("Packaging & limits")

readme = ROOT / "README.md"
if require(readme.is_file(), "README.md exists at marketplace root"):
    rtext = readme.read_text(encoding="utf-8")
    unnamed = [s.get("id") for s in skills if str(s.get("id")) not in rtext]
    require(not unnamed, "README names every skill", f"missing: {unnamed}")
    advise(
        any(w in rtext.lower() for w in ("compose", "orchestrat", "entrypoint")),
        "README explains how the entrypoint composes the skills",
    )

junk, weights, big = [], [], []
for path in ROOT.rglob("*"):
    rel = path.relative_to(ROOT)
    if any(part in JUNK_DIRS for part in rel.parts):
        junk.append(str(rel))
        continue
    if path.is_file():
        if path.suffix in JUNK_SUFFIXES:
            junk.append(str(rel))
        if path.suffix in WEIGHT_SUFFIXES:
            weights.append(str(rel))
        if path.stat().st_size > 5 * 1024 * 1024:
            big.append(f"{rel} ({path.stat().st_size // 1024 // 1024} MB)")

require(not weights, "no pretrained model weights bundled", f"{weights[:5]}")
advise(not big, "no unexpectedly large files", f"{big[:5]}")
# A hard failure, not advice: this tree starts clean and every script the gate
# runs sets PYTHONDONTWRITEBYTECODE, so junk here means something escaped that.
require(
    not junk,
    "no build junk in the tree",
    f"{len(junk)} path(s), e.g. {sorted(set(junk))[:3]} — exclude these when zipping",
)

# Size the zip the way we would actually build it: junk excluded.
tmp = Path(os.environ.get("TMPDIR", "/tmp")) / "_submission_probe.zip"
try:
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(ROOT.rglob("*")):
            rel = path.relative_to(ROOT)
            if any(part in JUNK_DIRS for part in rel.parts) or path.suffix in JUNK_SUFFIXES:
                continue
            if path.is_file():
                z.write(path, Path(ROOT.name) / rel)
    size = tmp.stat().st_size
    require(size <= ZIP_MAX_BYTES, f"zip <= 50 MB ({size / 1024:.0f} KB)")
finally:
    tmp.unlink(missing_ok=True)

# Portability: an absolute path from this machine breaks on the grader's.
leaks = []
for py in ROOT.rglob("*.py"):
    if any(part in JUNK_DIRS for part in py.relative_to(ROOT).parts):
        continue
    for n, line in enumerate(py.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if re.search(r"['\"](?:/home/|/Users/|[A-Z]:\\\\)", line):
            leaks.append(f"{py.relative_to(ROOT)}:{n}")
require(not leaks, "no absolute machine paths hardcoded", f"{leaks[:5]}")

# Third-party deps are allowed, but every one must be declared somewhere the
# grader will read before running, or the unzip-and-run path dies on ImportError.
STDLIB_OK = set(sys.stdlib_module_names) | {"__future__"}
# import name -> distribution name, where they differ
DIST_ALIAS = {"bs4": "beautifulsoup4", "yaml": "pyyaml", "PIL": "pillow"}

third_party: dict[str, set[str]] = {}
for py in ROOT.rglob("*.py"):
    rel = py.relative_to(ROOT)
    if any(part in JUNK_DIRS for part in rel.parts) or rel.parts[0] == "tests":
        continue
    # Strip docstrings/comments first: prose like "from markup, never observed"
    # otherwise scans as an import.
    src = re.sub(r'""".*?"""|\'\'\'.*?\'\'\'', "", py.read_text(encoding="utf-8", errors="replace"), flags=re.S)
    for line in src.splitlines():
        m = re.match(r"\s*(?:import|from)\s+([a-zA-Z_][\w]*)(?=\s*(?:import|as|,|$))", line)
        if not m or m.group(1) in STDLIB_OK:
            continue
        mod = m.group(1)
        if (py.parent / f"{mod}.py").is_file():  # same-folder sibling module
            continue
        third_party.setdefault(mod, set()).add(str(rel))

if third_party:
    declared = ""
    for f in ("README.md", "requirements.txt", "pyproject.toml"):
        if (ROOT / f).is_file():
            declared += (ROOT / f).read_text(encoding="utf-8").lower()
    undeclared = sorted(
        m for m in third_party
        if m.lower() not in declared and DIST_ALIAS.get(m, m).lower() not in declared
    )
    require(not undeclared, "every third-party dependency is declared", f"{undeclared}")
    advise(
        (ROOT / "requirements.txt").is_file(),
        "requirements.txt at marketplace root",
        f"deps ({', '.join(sorted(DIST_ALIAS.get(m, m) for m in third_party))}) are prose-only; "
        "a pinned file makes unzip-and-run reproducible",
    )
    advise(
        False,
        "skill scripts are stdlib-only",
        f"uses {', '.join(sorted(third_party))} — fine, but each is a way the grader's run can fail",
    )
else:
    ok("skill scripts are stdlib-only")

# --------------------------------------------------------------------------
_section("Manual checks this gate cannot make")
for item in (
    f"Runtime < {RUNTIME_MAX_S}s on a real site (this gate replays a fixture; time a live run)",
    "Generalization: run against >=3 sites never used in research, hunt false positives",
    "Rubric #1-#3: detection accuracy, action quality, output legibility to a non-expert",
    "Rubric #5: decomposition is genuine separation of concerns, not padding",
):
    print(f"  --   {item}")

# --------------------------------------------------------------------------
print("\n" + "=" * 58)
if fails:
    print(f"  BLOCKED — {len(fails)} hard failure(s), {len(warns)} warning(s)")
    for f in fails:
        print(f"    x {f}")
else:
    print(f"  SUBMITTABLE — 0 hard failures, {len(warns)} warning(s)")
print("=" * 58)

sys.exit(1 if fails else 0)
