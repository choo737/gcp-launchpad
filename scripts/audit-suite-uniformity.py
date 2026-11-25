#!/usr/bin/env python3
"""Cross-repository documentation & contract uniformity gate for the 5-repo choo737/gcp-* suite.

Modes:
1. Local sibling mode (default when sibling directories ../gcp-* exist):
   Verifies that all 5 local repositories have a byte-identical `tests/suite_doc_contract.py`
   (matching SHA-256) and zero violations from `validate_repo_suite_contract(...)`.
2. Remote GitHub mode (`--remote` or automatic fallback in single-repo CI when siblings are absent):
   Fetches `tests/suite_doc_contract.py`, `README.md`, `QUESTIONNAIRE.md`, `AGENTS.md`, `CLAUDE.md`,
   and `Makefile` from `https://raw.githubusercontent.com/choo737/<repo>/main/...` and verifies
   cross-repo SHA-256 parity and zero contract violations across the live suite.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import re
import sys
import tempfile
import time
import urllib.error
import urllib.request

LAUNCHPAD_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(LAUNCHPAD_ROOT / "tests"))

import suite_doc_contract as contract  # noqa: E402

REMOTE_CHECK_FILES: tuple[str, ...] = (
    "README.md",
    "QUESTIONNAIRE.md",
    "AGENTS.md",
    "CLAUDE.md",
    "CODEOWNERS",
    "LICENSE",
    "SECURITY.md",
    "Makefile",
    "tests/suite_doc_contract.py",
)
REMOTE_TREE_MD_RE = re.compile(r"^(?:docs/.+\.md|\.agents/skills/[^/]+/SKILL\.md)$")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _github_auth_headers(accept: str | None = None) -> dict[str, str]:
    token = (os.environ.get("SUITE_GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()
    headers = {"User-Agent": "gcp-launchpad-uniformity-audit/1.0"}
    if accept:
        headers["Accept"] = accept
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _urlopen_with_retry(urls: tuple[str, ...], headers: dict[str, str], attempts: int = 5) -> bytes:
    last_exc: Exception | None = None
    for attempt in range(attempts):
        url = urls[attempt % len(urls)]
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code not in (429, 500, 502, 503, 504):
                raise
        except urllib.error.URLError as exc:
            last_exc = exc
        if attempt + 1 < attempts:
            time.sleep((2 ** attempt) + random.uniform(0.1, 0.5))
    assert last_exc is not None
    raise last_exc


def fetch_remote_file_with_retry(repo_slug: str, rel: str, attempts: int = 5) -> bytes:
    urls = (
        f"https://raw.githubusercontent.com/choo737/{repo_slug}/main/{rel}",
        f"https://github.com/choo737/{repo_slug}/raw/main/{rel}",
    )
    return _urlopen_with_retry(urls, _github_auth_headers(), attempts=attempts)


def extract_tree_markdown_paths(tree_payload: dict[str, object]) -> list[str]:
    tree_entries = tree_payload.get("tree")
    if not isinstance(tree_entries, list):
        return []
    matched: set[str] = set()
    for entry in tree_entries:
        if not isinstance(entry, dict):
            continue
        if entry.get("type") != "blob":
            continue
        rel = entry.get("path")
        if not isinstance(rel, str):
            continue
        if ".." in Path(rel).parts or rel.startswith("/"):
            continue
        if REMOTE_TREE_MD_RE.match(rel) and rel not in REMOTE_CHECK_FILES:
            matched.add(rel)
    return sorted(matched)


def fetch_remote_tree_markdown_paths(
    repo_slug: str, owner: str = "choo737", attempts: int = 5
) -> list[str]:
    tree_url = f"https://api.github.com/repos/{owner}/{repo_slug}/git/trees/HEAD?recursive=1"
    raw = _urlopen_with_retry(
        (tree_url,),
        _github_auth_headers(accept="application/vnd.github+json"),
        attempts=attempts,
    )
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        return []
    return extract_tree_markdown_paths(payload)


def audit_local_siblings(repos_parent: Path) -> int:
    canonical_bytes = (LAUNCHPAD_ROOT / "tests" / "suite_doc_contract.py").read_bytes()
    canonical_sha = sha256_bytes(canonical_bytes)
    failures: list[str] = []

    for repo_slug, _, _ in contract.SUITE_REPOS:
        repo_dir = repos_parent / repo_slug
        if not repo_dir.is_dir():
            failures.append(f"[{repo_slug}] Missing sibling directory: {repo_dir}")
            continue
        target_contract = repo_dir / "tests" / "suite_doc_contract.py"
        if not target_contract.is_file():
            failures.append(f"[{repo_slug}] Missing tests/suite_doc_contract.py")
        else:
            repo_sha = sha256_bytes(target_contract.read_bytes())
            if repo_sha != canonical_sha:
                failures.append(
                    f"[{repo_slug}] SHA-256 drift in tests/suite_doc_contract.py "
                    f"(expected {canonical_sha[:12]}, got {repo_sha[:12]})"
                )
        for err in contract.validate_repo_suite_contract(repo_dir, repo_slug):
            failures.append(f"[{repo_slug}] {err}")

    if failures:
        print("SUITE UNIFORMITY AUDIT FAILED:", file=sys.stderr)
        for item in failures:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print(
        f"SUITE UNIFORMITY AUDIT PASSED: all {len(contract.SUITE_REPOS)} local repositories "
        f"match contract SHA-256 {canonical_sha[:12]} with 0 violations."
    )
    return 0


def audit_remote_github() -> int:
    canonical_bytes = (LAUNCHPAD_ROOT / "tests" / "suite_doc_contract.py").read_bytes()
    canonical_sha = sha256_bytes(canonical_bytes)
    failures: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        tmp_parent = Path(tmp)
        for repo_slug, _, _ in contract.SUITE_REPOS:
            if repo_slug == "gcp-launchpad":
                for err in contract.validate_repo_suite_contract(LAUNCHPAD_ROOT, repo_slug):
                    failures.append(f"[{repo_slug}] {err}")
                continue

            repo_tmp = tmp_parent / repo_slug
            repo_tmp.mkdir(parents=True, exist_ok=True)
            try:
                extra_md_files = fetch_remote_tree_markdown_paths(repo_slug)
            except (urllib.error.URLError, json.JSONDecodeError, ValueError) as exc:
                failures.append(f"[{repo_slug}] Failed fetching git tree: {exc}")
                continue

            fetch_ok = True
            for rel in (*REMOTE_CHECK_FILES, *extra_md_files):
                dest = repo_tmp / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                try:
                    dest.write_bytes(fetch_remote_file_with_retry(repo_slug, rel))
                except urllib.error.URLError as exc:
                    failures.append(f"[{repo_slug}] Failed fetching {rel}: {exc}")
                    fetch_ok = False
            if not fetch_ok:
                continue

            remote_sha = sha256_bytes((repo_tmp / "tests" / "suite_doc_contract.py").read_bytes())
            if remote_sha != canonical_sha:
                failures.append(
                    f"[{repo_slug}] Remote SHA-256 drift in tests/suite_doc_contract.py "
                    f"(expected {canonical_sha[:12]}, got {remote_sha[:12]})"
                )
            for err in contract.validate_repo_suite_contract(repo_tmp, repo_slug):
                failures.append(f"[{repo_slug}] {err}")

    if failures:
        print("REMOTE SUITE UNIFORMITY AUDIT FAILED:", file=sys.stderr)
        for item in failures:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print(
        f"REMOTE SUITE UNIFORMITY AUDIT PASSED: all {len(contract.SUITE_REPOS)} GitHub repositories "
        f"match contract SHA-256 {canonical_sha[:12]} with 0 violations."
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify documentation uniformity across all 5 suite repositories.")
    parser.add_argument("--repos-root", type=Path, default=LAUNCHPAD_ROOT.parent, help="Parent directory holding gcp-* sibling checkouts.")
    parser.add_argument("--remote", action="store_true", help="Verify live GitHub main branches via raw.githubusercontent.com.")
    args = parser.parse_args()

    if args.remote:
        return audit_remote_github()

    all_siblings_present = all((args.repos_root / slug).is_dir() for slug, _, _ in contract.SUITE_REPOS)
    if all_siblings_present:
        return audit_local_siblings(args.repos_root)
    return audit_remote_github()


if __name__ == "__main__":
    raise SystemExit(main())
