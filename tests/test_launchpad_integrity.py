"""Verify gcp-launchpad structure, scripts, schemas, workflows, and prose hygiene."""

import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent

SKIP_DIRS = frozenset({
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".venv",
})

SKIP_FILES = frozenset({
    ".DS_Store",
    "platform-context.json",
    "00_linked.auto.tfvars.json",
})

REQUIRED_FILES = (
    "LICENSE",
    "CODEOWNERS",
    ".gitignore",
    "Makefile",
    "README.md",
    "QUESTIONNAIRE.md",
    "AGENTS.md",
    "CLAUDE.md",
    "examples/platform-context.greenfield.json",
    "examples/platform-context.brownfield.json",
    "scripts/preflight-check.sh",
    "scripts/generate-brownfield-link.py",
    ".agents/skills/route-architecture/SKILL.md",
    ".agents/skills/brownfield-bridge/SKILL.md",
    ".github/workflows/ci.yml",
    "tests/test_launchpad_integrity.py",
)

LEAKED_IDENTIFIERS = (
    "jacky" + "choo",
    "alto" + "strat",
    "@" + "google.com",
    ".c.googlers." + "com",
    "playground-" + "473704",
    "016" + "D20",
    "C01" + "hil3w1",
)

SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:[A-Z]+ )?" + r"PRIVATE KEY-----"),
    re.compile(r"\bAK" + r"IA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh" + r"p_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAI" + r"za[0-9A-Za-z_-]{35}\b"),
)

TWELVE_DIGIT_RE = re.compile(r"\b\d{12}\b")
BILLING_ID_RE = re.compile(r"\b[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}\b")
DEPRECATED_MODEL_RE = re.compile(
    r"\b(?:gemini[- ]?(?:1\.0|1\.5|2\.0|2\.5)|claude[- ]?3|gemma[- ]?2)\b",
    re.IGNORECASE,
)

MOCK_MARKERS = (
    "mock_" + "success",
    "dummy_" + "payload",
    "fake_" + "output",
)

BANNED_AI_WORDS = (
    "del" + "ve",
    "navi" + "gate",
    "fos" + "ter",
    "cham" + "pion",
    "stream" + "line",
    "ele" + "vate",
    "har" + "ness",
    "orches" + "trate",
    "illu" + "minate",
    "tran" + "scend",
    "demy" + "stify",
    "emb" + "race",
    "un" + "lock",
    "tape" + "stry",
    "testa" + "ment",
    "bea" + "con",
    "re" + "alm",
    "land" + "scape",
    "para" + "digm",
    "syn" + "ergy",
    "fa" + "cet",
    "nua" + "nce",
    "corner" + "stone",
    "jour" + "ney",
    "blue" + "print",
    "para" + "mount",
    "multi" + "faceted",
    "vib" + "rant",
    "piv" + "otal",
    "hol" + "istic",
    "cru" + "cial",
    "compre" + "hensive",
    "meti" + "culous",
    "dyn" + "amic",
    "pro" + "found",
    "intr" + "icate",
    "further" + "more",
    "more" + "over",
    "in " + "conclusion",
    "at its " + "core",
    "it is worth " + "noting",
    "impor" + "tantly",
    "in " + "summary",
    "ulti" + "mately",
)

EMOJI_PATTERN = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F]")
SECTION_SYMBOL = "\u00a7"
BULLET_PREFIX_RE = re.compile(r"^(?:[-*]|\d+\.)\s+")


def _iter_repo_files() -> list[Path]:
    files: list[Path] = []
    for path in sorted(REPO_ROOT.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name in SKIP_FILES:
            continue
        if path.name.endswith((".tfstate", ".tfstate.backup")) or ".tfstate." in path.name:
            continue
        files.append(path)
    return files


def _extract_markdown_sentences(text: str) -> list[str]:
    lines = text.splitlines()
    in_code = False
    in_frontmatter = False
    prose_blocks: list[str] = []
    current_para: list[str] = []

    def flush_para() -> None:
        if current_para:
            prose_blocks.append(" ".join(current_para))
            current_para.clear()

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if idx == 0 and stripped == "---":
            in_frontmatter = True
            continue
        if in_frontmatter:
            if stripped == "---":
                in_frontmatter = False
            continue
        if stripped.startswith("```"):
            flush_para()
            in_code = not in_code
            continue
        if in_code:
            continue
        if not stripped or stripped.startswith(("#", "|", "---")):
            flush_para()
            continue
        if BULLET_PREFIX_RE.match(stripped):
            flush_para()
            prose_blocks.append(BULLET_PREFIX_RE.sub("", stripped).strip())
            continue
        current_para.append(stripped)

    flush_para()

    sentences: list[str] = []
    for block in prose_blocks:
        for part in re.split(r"[.!?](?:\s+|$)", block):
            cleaned = part.strip()
            if cleaned:
                sentences.append(cleaned)
    return sentences


class LaunchpadIntegrityTest(unittest.TestCase):
    """Validate structure, agent docs, scripts, examples, CI, and anti-leak rules."""

    def test_required_files_and_no_catalog_yaml(self) -> None:
        for rel in REQUIRED_FILES:
            with self.subTest(file=rel):
                self.assertTrue((REPO_ROOT / rel).is_file(), f"Missing {rel}")
        self.assertFalse(
            (REPO_ROOT / "catalog.yaml").exists(),
            "catalog.yaml must not exist; README.md is the single catalog",
        )

    def test_gitignore_patterns(self) -> None:
        gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        for entry in ("platform-context.json", "*.tfvars", "*.tfvars.json", ".cm_project"):
            with self.subTest(entry=entry):
                self.assertIn(entry, gitignore)

    def test_agent_instructions_align_and_roadmap_naming(self) -> None:
        required_refs = (
            "README.md",
            "QUESTIONNAIRE.md",
            "platform-context.json",
            "scripts/preflight-check.sh",
            "scripts/generate-brownfield-link.py",
            "route-architecture",
            "brownfield-bridge",
            "--private",
            "gcp-foundation",
            "gcp-data-ingestion",
            "gcp-data-medallion",
            "gcp-webapp",
            "gcp-adk-agent",
        )
        for doc_name in ("AGENTS.md", "CLAUDE.md"):
            content = (REPO_ROOT / doc_name).read_text(encoding="utf-8")
            with self.subTest(doc=doc_name):
                for ref in required_refs:
                    self.assertIn(ref, content, f"{doc_name} missing {ref}")
        self.assertFalse((REPO_ROOT / "GEMINI.md").exists(), "GEMINI.md must not exist")

        stale_roadmap_name = "gcp-webapp-" + "ha"
        for path in _iter_repo_files():
            text = path.read_text(encoding="utf-8", errors="ignore")
            self.assertNotIn(
                stale_roadmap_name,
                text,
                f"Use gcp-webapp instead of {stale_roadmap_name} in {path}",
            )

    def test_skills_have_valid_frontmatter(self) -> None:
        for skill_name in ("route-architecture", "brownfield-bridge"):
            skill_path = REPO_ROOT / ".agents" / "skills" / skill_name / "SKILL.md"
            text = skill_path.read_text(encoding="utf-8")
            with self.subTest(skill=skill_name):
                self.assertTrue(text.startswith("---\n"))
                parts = text.split("---\n", 2)
                self.assertGreaterEqual(len(parts), 3)
                frontmatter = parts[1]
                self.assertRegex(
                    frontmatter,
                    rf"(?m)^name:\s*{re.escape(skill_name)}\s*$",
                )
                self.assertRegex(frontmatter, r"(?m)^description:\s*.+$")

    def test_example_contexts_match_schema(self) -> None:
        required_keys = {
            "schema_version",
            "adoption_mode",
            "compliance_profile",
            "selected_templates",
            "primary_region",
            "dr_region",
            "environments",
            "prefix",
            "project_suffix",
            "github_owner",
            "ci_identity_mode",
            "existing_landing_zone",
        }
        for mode, filename in (
            ("greenfield", "examples/platform-context.greenfield.json"),
            ("brownfield", "examples/platform-context.brownfield.json"),
        ):
            payload = json.loads((REPO_ROOT / filename).read_text(encoding="utf-8"))
            with self.subTest(example=filename):
                self.assertEqual(payload["schema_version"], "1.0")
                self.assertEqual(payload["adoption_mode"], mode)
                self.assertTrue(required_keys.issubset(payload.keys()))
                self.assertIsInstance(payload["selected_templates"], list)
                self.assertIsInstance(payload["environments"], list)
                self.assertIsInstance(payload["existing_landing_zone"], dict)

    def test_preflight_script_cli_and_validation(self) -> None:
        script = REPO_ROOT / "scripts" / "preflight-check.sh"
        self.assertTrue(os.access(script, os.X_OK), "preflight-check.sh must be executable")

        help_res = subprocess.run(
            ["bash", str(script), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(help_res.returncode, 0, help_res.stderr)
        self.assertIn("Usage:", help_res.stdout)

        dry_res = subprocess.run(
            ["bash", str(script), "--dry-run", "--project", "example-core-01"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(dry_res.returncode, 0, dry_res.stderr)
        self.assertIn("Dry-run mode enabled", dry_res.stdout)

        for bad_args in (
            ["--dry-run", "--project", "BAD_ID!"],
            ["--dry-run", "--folder", "not-numeric"],
            ["--dry-run", "--org", "123"],
            ["--unknown-flag"],
        ):
            with self.subTest(bad_args=bad_args):
                bad_res = subprocess.run(
                    ["bash", str(script), *bad_args],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertNotEqual(bad_res.returncode, 0)

    def test_generate_brownfield_link_end_to_end_and_filtering(self) -> None:
        script = REPO_ROOT / "scripts" / "generate-brownfield-link.py"
        self.assertTrue(
            os.access(script, os.X_OK),
            "generate-brownfield-link.py must be executable",
        )
        brownfield_ctx = REPO_ROOT / "examples" / "platform-context.brownfield.json"

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            out_file = tmp_root / "00_linked.auto.tfvars.json"
            res = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--context",
                    str(brownfield_ctx),
                    "--output",
                    str(out_file),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertTrue(out_file.is_file())
            mode = stat.S_IMODE(out_file.stat().st_mode)
            self.assertEqual(mode, 0o600)

            linked = json.loads(out_file.read_text(encoding="utf-8"))
            self.assertEqual(linked["core_project_id"], "acme-dev01-data-core")
            self.assertEqual(linked["core_storage_project_id"], "acme-dev01-data-core")
            self.assertEqual(linked["etl_compute_project_id"], "acme-dev01-data-etl")
            self.assertEqual(linked["primary_gold_project_id"], "acme-dev01-data-gold")
            self.assertEqual(linked["primary_gold_dataset_id"], "gold")
            self.assertEqual(linked["kms_key_name"], linked["kms_key_id"])
            self.assertEqual(linked["network_id"], linked["vpc_id"])
            self.assertEqual(
                linked["dataform_service_account_email"],
                linked["dataform_sa_email"],
            )

            # Verify --target-variables-tf filtering strictly trims undeclared keys.
            target_vars = tmp_root / "variables.tf"
            target_vars.write_text(
                'variable "core_storage_project_id" { type = string }\n'
                'variable "bronze_dataset_id" { type = string }\n'
                'variable "landing_bucket_name" { type = string }\n',
                encoding="utf-8",
            )
            filtered_out = tmp_root / "filtered.auto.tfvars.json"
            filt_res = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--context",
                    str(brownfield_ctx),
                    "--target-variables-tf",
                    str(target_vars),
                    "--output",
                    str(filtered_out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(filt_res.returncode, 0, filt_res.stderr)
            filtered = json.loads(filtered_out.read_text(encoding="utf-8"))
            self.assertEqual(
                set(filtered.keys()),
                {"bronze_dataset_id", "core_storage_project_id", "landing_bucket_name"},
            )

            # Verify invalid identifiers and missing required fields fail non-zero.
            for bad_args in (
                ["--core-project-id", "BAD_PROJECT"],
                ["--kms-key-id", "not/a/kms/key"],
                ["--vpc-id", "invalid-vpc"],
                ["--context", str(REPO_ROOT / "examples" / "platform-context.greenfield.json")],
            ):
                with self.subTest(bad_args=bad_args):
                    err_res = subprocess.run(
                        [sys.executable, str(script), *bad_args, "--output", str(out_file)],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertNotEqual(err_res.returncode, 0)

    def test_ci_workflow_security_hardening(self) -> None:
        ci_text = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        self.assertRegex(ci_text, r"(?m)^permissions:\s*\n\s*contents:\s*read\s*$")
        uses_refs = re.findall(r"(?m)^\s*uses:\s*([^\s#]+)", ci_text)
        self.assertGreaterEqual(len(uses_refs), 2)
        for ref in uses_refs:
            with self.subTest(action_ref=ref):
                self.assertRegex(ref, r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}$")

        in_run_block = False
        run_indent = 0
        for line in ci_text.splitlines():
            stripped = line.lstrip()
            indent = len(line) - len(stripped)
            if re.match(r"^(?:-\s*)?run:\s*", stripped):
                self.assertNotIn("${{", stripped, "Expression interpolation inside run:")
                if stripped.endswith("|") or stripped.endswith(">"):
                    in_run_block = True
                    run_indent = indent
                continue
            if in_run_block:
                if stripped and indent <= run_indent:
                    in_run_block = False
                else:
                    self.assertNotIn("${{", line, "Expression interpolation inside run: block")

    def test_no_leaked_identifiers_secrets_or_deprecated_models(self) -> None:
        for path in _iter_repo_files():
            text = path.read_text(encoding="utf-8")
            lowered = text.lower()
            rel = str(path.relative_to(REPO_ROOT))
            with self.subTest(file=rel):
                for ident in LEAKED_IDENTIFIERS:
                    self.assertNotIn(
                        ident.lower(),
                        lowered,
                        f"Leaked identifier '{ident}' found in {rel}",
                    )
                for pat in SECRET_PATTERNS:
                    self.assertIsNone(
                        pat.search(text),
                        f"Secret pattern {pat.pattern} found in {rel}",
                    )
                self.assertIsNone(
                    TWELVE_DIGIT_RE.search(text),
                    f"Literal 12-digit integer found in {rel}",
                )
                self.assertIsNone(
                    BILLING_ID_RE.search(text),
                    f"Hex billing ID pattern found in {rel}",
                )
                self.assertIsNone(
                    DEPRECATED_MODEL_RE.search(text),
                    f"Deprecated model ID found in {rel}",
                )
                for marker in MOCK_MARKERS:
                    self.assertNotIn(
                        marker,
                        lowered,
                        f"Mock marker '{marker}' found in {rel}",
                    )

    def test_no_emojis_section_symbol_or_banned_ai_words(self) -> None:
        word_patterns = {
            w: re.compile(rf"\b{re.escape(w)}\b", re.IGNORECASE)
            for w in BANNED_AI_WORDS
        }
        for path in _iter_repo_files():
            text = path.read_text(encoding="utf-8")
            rel = str(path.relative_to(REPO_ROOT))
            with self.subTest(file=rel):
                self.assertIsNone(
                    EMOJI_PATTERN.search(text),
                    f"Decorative emoji found in {rel}",
                )
                self.assertNotIn(
                    SECTION_SYMBOL,
                    text,
                    f"Forbidden section symbol found in {rel}",
                )
                for word, pat in word_patterns.items():
                    self.assertIsNone(
                        pat.search(text),
                        f"Banned AI word '{word}' found in {rel}",
                    )

    def test_markdown_sentences_are_short(self) -> None:
        for path in _iter_repo_files():
            if path.suffix != ".md":
                continue
            rel = str(path.relative_to(REPO_ROOT))
            sentences = _extract_markdown_sentences(path.read_text(encoding="utf-8"))
            with self.subTest(markdown=rel):
                for sentence in sentences:
                    words = [w for w in sentence.split() if w]
                    self.assertLessEqual(
                        len(words),
                        20,
                        f"Sentence exceeds 20 words ({len(words)}) in {rel}: {sentence}",
                    )


if __name__ == "__main__":
    unittest.main()
