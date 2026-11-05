"""Audit the complete Git index without printing file contents or credential values."""

import json
import re
import subprocess
from io import BytesIO
from pathlib import PurePosixPath

ROOT_FILES = {
    ".gitignore",
    ".gitattributes",
    ".dockerignore",
    ".env.example",
    "Dockerfile",
    "README.md",
    "DEPLOYMENT.md",
    "data_requirements.md",
    "pyproject.toml",
    "requirements.txt",
    "uv.lock",
    "app.py",
    "activity_nav.py",
    "agent2_views.py",
    "agent2_track4_views.py",
    "hybrid_inputs.py",
    "journey_inputs.py",
    "decision_inputs.py",
    "future_inputs.py",
    "pricing_inputs.py",
    "proposal_inputs.py",
    "proposal_journey.py",
    "review_inputs.py",
    "selection_controls.py",
    "ui_drafts.py",
}
EXCLUDED_PROBES = [
    ".env",
    ".env.production",
    ".streamlit/secrets.toml",
    "local_data/plans.db",
    "local_data/private-original.md",
    "uploads/officer.txt",
    "outputs/private.jsonl",
    ".venv/pyvenv.cfg",
    ".uv-cache/cache",
    "__pycache__/cache.pyc",
    "logs/private.log",
    "raw/source.xlsx",
    "data/raw/tender.json",
    "data/unreviewed.json",
    "records.xlsx",
    "records.csv",
    "notebook.ipynb",
    "credentials.json",
    "BUILD_BRIEF.md",
    "HANDOVER.md",
    "IMPLEMENTATION_PLAN.md",
    "VALIDATION.md",
    "evaluation/HYBRID_REVIEW_2026-10-05.md",
]
SECRET = re.compile(
    r"sk-[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
)
PRIVATE = re.compile(
    r"[A-Za-z]:[/\\]" + "Users" + r"[/\\]|/" + "Users" + r"/[^/]+/|/" + "home" + r"/[^/]+/|\bE\d{7}@", re.I
)


def allowed(path):
    p = PurePosixPath(path)
    if path in ROOT_FILES or path in {".streamlit/config.toml", ".streamlit/secrets.example.toml"}:
        return True
    if p.parts[0] in {"services", "scripts", "tests"}:
        return p.suffix in {".py", ".ps1", ".mjs"} and "__pycache__" not in p.parts
    if p.parts[0] == "docs":
        return p.suffix == ".md"
    if p.parts[0] == "contracts":
        return p.name.endswith(".schema.json")
    if path in {
        "evaluation/PLAN.md",
        "evaluation/TOOLS.md",
        "evaluation/cases.json",
        "data/reference/role_titles.json",
        "data/reference/pwm-2026-10-19.json",
    }:
        return True
    return p.parts[:2] == ("data", "sample") and p.suffix in {".json", ".md"}


def issues_for(path, content):
    if path in {
        "data/templates/track2-blank-template.xlsx",
        "data/templates/track2-example-proposal.xlsx",
        "data/templates/track2-preplanned-budget-sample.xlsx",
    }:
        import zipfile

        try:
            with zipfile.ZipFile(BytesIO(content)) as archive:
                if sum(item.file_size for item in archive.infolist()) > 500000:
                    return ["unexpected proposal-template size"]
                if any(
                    "externalLink" in name or "vbaProject" in name or "connections" in name
                    for name in archive.namelist()
                ):
                    return ["proposal template contains external links or macros"]
                value = "\n".join(
                    archive.read(name).decode("utf-8") for name in archive.namelist() if name.endswith(".xml")
                )
                return (
                    ["private or credential-shaped value in proposal template"]
                    if SECRET.search(value) or PRIVATE.search(value)
                    else []
                )
        except (ValueError, zipfile.BadZipFile, UnicodeDecodeError):
            return ["invalid proposal workbook template"]
    issues = []
    if not allowed(path):
        issues.append("outside reviewed shareable file categories")
    try:
        value = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return [*issues, "unexpected binary/non-UTF-8 file"]
    if SECRET.search(value):
        issues.append("credential-shaped value")
    if PRIVATE.search(value):
        issues.append("private identifier or local path")
    if path.startswith("data/sample/") and path.endswith(".json"):
        try:
            payload = json.loads(value)
            synthetic = (
                isinstance(payload, list)
                and bool(payload)
                and all(r.get("data_origin") == "synthetic" for r in payload)
            ) or (
                isinstance(payload, dict)
                and payload.get("synthetic") is True
                and "synthetic" in payload.get("label", "").casefold()
            )
            if not synthetic:
                issues.append("dataset lacks explicit synthetic provenance")
        except (ValueError, AttributeError):
            issues.append("invalid synthetic JSON fixture")
    if path == "data/reference/pwm-2026-10-19.json":
        payload = json.loads(value)
        schedules = payload.get("schedules", [])
        if not schedules or any(
            not r.get("source", "").startswith("https://www.mom.gov.sg/")
            or not r.get("verified_on")
            or not r.get("valid_until")
            or not r.get("points")
            for r in schedules
        ):
            issues.append("official policy snapshot lacks MOM source/date/wage provenance")
    if path == "data/reference/role_titles.json":
        payload = json.loads(value)
        if (
            set(payload) != {"source", "titles", "not_benchmark_evidence"}
            or payload["not_benchmark_evidence"] is not True
        ):
            issues.append("title inventory includes unexpected evidence fields")
    if path in {".env.example", ".streamlit/secrets.example.toml"}:
        for line in value.splitlines():
            if re.match(
                r"\s*(OPENAI_API_KEY|client_secret|cookie_secret|password|access_token)\s*=", line, re.I
            ):
                if line.split("=", 1)[1].strip().strip("\"'"):
                    issues.append("non-empty credential in example configuration")
    return issues


def git(*args, input_data=None):
    return subprocess.run(["git", *args], input=input_data, capture_output=True, check=False)


def audit():
    listed = git("ls-files", "--stage", "-z")
    if listed.returncode:
        raise ValueError("Run inside the prepared Git repository")
    findings, entries = [], []
    for entry in listed.stdout.split(b"\0"):
        if not entry:
            continue
        meta, raw_path = entry.split(b"\t", 1)
        mode, oid, stage = meta.split()
        entries.append((mode, oid, stage, raw_path.decode("utf-8")))
    # Read exactly the indexed blobs in one Git operation, not the mutable working tree.
    result = git("cat-file", "--batch", input_data=b"\n".join(e[1] for e in entries) + b"\n")
    stream = BytesIO(result.stdout)
    for mode, _oid, stage, path in entries:
        header = stream.readline().split()
        if len(header) != 3 or header[1] != b"blob":
            findings.append({"file": path, "issues": ["indexed content unavailable"]})
            continue
        content = stream.read(int(header[2]))
        stream.read(1)
        if mode not in (b"100644", b"100755") or stage != b"0":
            findings.append(
                {"file": path, "issues": ["symlink/submodule/conflicted index entry is not allowed"]}
            )
            continue
        problems = issues_for(path, content)
        if problems:
            findings.append({"file": path, "issues": problems})
    ignored = git(
        "check-ignore",
        "--no-index",
        "-z",
        "--stdin",
        input_data=b"\0".join(p.encode() for p in EXCLUDED_PROBES) + b"\0",
    )
    ignored_paths = set(ignored.stdout.decode("utf-8").split("\0"))
    for path in EXCLUDED_PROBES:
        if path not in ignored_paths:
            findings.append({"file": path, "issues": ["private/raw/generated exclusion is missing"]})
    if not entries:
        findings.append({"file": "index", "issues": ["nothing has been staged"]})
    return {
        "indexed_files_scanned": len(entries),
        "exclusion_probes": len(EXCLUDED_PROBES),
        "findings": findings,
        "secret_values_printed": False,
    }


def main():
    result = audit()
    print(json.dumps(result, indent=2))
    if result["findings"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
