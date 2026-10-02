"""Package current working files, never Git history or private runtime data."""
from __future__ import annotations

import hashlib
import argparse
import json
from pathlib import Path
import re
import subprocess
from datetime import datetime, timezone
from zipfile import ZipFile, ZIP_DEFLATED


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "submission"
ARCHIVE = OUTPUT / "Advisor-Console-Project-1-2026-10-02.zip"
EXCLUDED_PARTS = {".git", "node_modules", "venv", ".venv", "__pycache__",
                  ".pytest_cache", "dist", "test-results", "submission"}
SAFE_ENV = {"backend/.env.example", "backend/env.example", "backend/.env.production",
            "frontend/.env.example", "frontend/.env.production"}
SECRET_PATTERNS = [
    rb"sk-or-v1-[A-Za-z0-9]{32,}",
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\r?\n[A-Za-z0-9+/=]{32,}",
    rb"AIza[0-9A-Za-z_-]{30,}",
    rb"gh[pousr]_[A-Za-z0-9]{30,}",
    rb"GOCSPX-[A-Za-z0-9_-]{20,}",
]


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT).decode("utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-demo-access", action="store_true",
                        help="Include Git-ignored submission/DEMO_ACCESS.md in a private reviewer ZIP")
    args = parser.parse_args()
    # Git supplies tracked and non-ignored files; read their CURRENT bytes.
    paths = sorted(set(git("ls-files", "--cached", "--others", "--exclude-standard", "-z").split("\0")) - {""})
    files = {}
    sources = {}
    for name in paths:
        relative = Path(name)
        if EXCLUDED_PARTS.intersection(relative.parts):
            continue
        if (".env" in relative.name or relative.name == "env.example") and name not in SAFE_ENV:
            continue
        if relative.suffix.lower() in {".pem", ".key", ".p12", ".pfx", ".sqlite", ".db", ".dump", ".zip"}:
            continue
        source = ROOT / relative
        if source.is_symlink() or not source.resolve().is_relative_to(ROOT):
            raise RuntimeError(f"Unsafe source path: {name}")
        if not source.is_file():
            continue
        data = source.read_bytes()
        if any(re.search(pattern, data) for pattern in SECRET_PATTERNS):
            raise RuntimeError(f"Credential-like content requires review: {name}")
        if relative.suffix.lower() == ".json" and b'"type": "service_account"' in data:
            raise RuntimeError(f"Service account file excluded from distribution: {name}")
        files[name] = data
        sources[name] = source

    if args.include_demo_access:
        demo = OUTPUT / "DEMO_ACCESS.md"
        if demo.is_symlink() or not demo.resolve().is_relative_to(ROOT) or not demo.is_file():
            raise RuntimeError("Expected local submission/DEMO_ACCESS.md for private reviewer access")
        if subprocess.run(["git", "check-ignore", "-q", str(demo)], cwd=ROOT).returncode != 0:
            raise RuntimeError("Demo access must be Git-ignored before packaging")
        files["DEMO_ACCESS.md"] = demo.read_bytes()
        sources["DEMO_ACCESS.md"] = demo

    required = {"PRD.md", "README.md", "frontend/README.md", "eval/prompts.json",
                "docs/FINAL_VERIFICATION.md", "docs/TIMELINE.md",
                "docs/evidence/submission-backend.xml", "scripts/package_submission.py"}
    if required - files.keys():
        raise RuntimeError(f"Missing deliverables: {sorted(required - files.keys())}")
    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_commit": git("rev-parse", "HEAD").strip(),
        "branch": git("branch", "--show-current").strip(),
        "working_tree_status": git("status", "--short"),
        "snapshot": "Current local working files; not a claim of remote synchronization",
        "excluded": "Secrets/private env, Git history, dependencies, caches, builds, runtime databases and generated archives",
        "file_count": len(files),
        "private_reviewer_demo_access_included": args.include_demo_access,
        "files": {name: {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                  for name, data in files.items()},
    }
    OUTPUT.mkdir(exist_ok=True)
    with ZipFile(ARCHIVE, "w", ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in files.items():
            archive.writestr("Advisor-Console/" + name, data)
        archive.writestr("Advisor-Console/SUBMISSION_MANIFEST.json", json.dumps(manifest, indent=2))
    with ZipFile(ARCHIVE) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ZIP CRC validation failed")
        if len(archive.namelist()) != len(files) + 1:
            raise RuntimeError("ZIP member count mismatch")
        for name, data in files.items():
            if archive.read("Advisor-Console/" + name) != data:
                raise RuntimeError(f"ZIP content mismatch: {name}")
            if sources[name].read_bytes() != data:
                raise RuntimeError(f"File changed during packaging; rerun: {name}")
    digest = hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()
    ARCHIVE.with_suffix(".zip.sha256").write_text(f"{digest}  {ARCHIVE.name}\n", encoding="utf-8")
    print(f"Verified {len(files)} source files plus manifest; {ARCHIVE.stat().st_size:,} bytes")
    print(ARCHIVE)
    print(f"SHA-256: {digest}")


if __name__ == "__main__":
    main()
