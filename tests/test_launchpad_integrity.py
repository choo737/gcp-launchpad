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

BINARY_EXTENSIONS = frozenset({
    ".webp",
    ".gif",
    ".png",
    ".jpg",
    ".jpeg",
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
    "assets/cloud-city-launchpad.webp",
    "assets/cloud-city-org-scanner.png",
    "docs/01-end-to-end-operational-playbook.md",
    "docs/02-template-documentation-standard.md",
    "docs/03-org-completeness-scanner-design.md",
    "examples/platform-context.greenfield.json",
    "examples/platform-context.brownfield.json",
    "scripts/preflight-check.sh",
    "scripts/generate-brownfield-link.py",
    ".agents/skills/route-architecture/SKILL.md",
    ".agents/skills/brownfield-bridge/SKILL.md",
    ".github/workflows/ci.yml",
    "tests/test_launchpad_integrity.py",
)

CANONICAL_README_H2_SECTIONS = [
    "## Template Suite Overview",
    "## Create Your Private Repository (Do Not Fork Publicly)",
    "## Architecture & Capabilities",
    "## 6-Step Enterprise Operationalization",
    "## AI Coding Agent Quickstart",
    "## CI/CD Workflows",
    "## Repository Layout",
    "## Quick Verification",
    "## Documentation Index",
    "## License",
]

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
MD_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
ABBREV_DOT_RE = re.compile(r"\b(e|i)\.g\.", re.IGNORECASE)
TABLE_SEP_CELL_RE = re.compile(r"^:?-{3,}:?$")


def _strip_md_links(text: str) -> str:
    return MD_LINK_RE.sub(r"\1", text)


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
        if path.suffix.lower() in BINARY_EXTENSIONS:
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
        if not stripped or stripped.startswith(("#", "|", "---", "<picture", "</picture", "<source", "<img", "![")):
            flush_para()
            continue
        if stripped.startswith(">"):
            stripped = stripped.lstrip("> ").strip()
            if not stripped or stripped.startswith("[!"):
                flush_para()
                continue
        stripped = _strip_md_links(stripped)
        if BULLET_PREFIX_RE.match(stripped):
            flush_para()
            current_para.append(BULLET_PREFIX_RE.sub("", stripped).strip())
            continue
        current_para.append(stripped)

    flush_para()

    sentences: list[str] = []
    for block in prose_blocks:
        masked = ABBREV_DOT_RE.sub(lambda m: f"{m.group(1)}<DOT>g<DOT>", block)
        for part in re.split(r"[.!?](?:\s+|$)", masked):
            cleaned = part.replace("<DOT>", ".").strip()
            if cleaned:
                sentences.append(cleaned)
    return sentences


def _extract_markdown_table_cells(text: str) -> list[str]:
    lines = text.splitlines()
    in_code = False
    in_frontmatter = False
    cells: list[str] = []
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
            in_code = not in_code
            continue
        if in_code or not stripped.startswith("|"):
            continue
        raw_cells = [c.strip() for c in stripped.strip("|").split("|")]
        if raw_cells and all(TABLE_SEP_CELL_RE.match(c) for c in raw_cells if c):
            continue
        for cell in raw_cells:
            cleaned = _strip_md_links(cell).strip()
            if cleaned:
                cells.append(cleaned)
    return cells


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
        for entry in (
            "platform-context.json",
            "terraform.tfvars",
            "*.auto.tfvars",
            "*.auto.tfvars.json",
            ".cm_project",
        ):
            with self.subTest(entry=entry):
                self.assertIn(entry, gitignore)
        for forbidden in ("*.tfvars", "*.tfvars.json"):
            self.assertNotIn(forbidden, gitignore)

    def test_readme_canonical_ten_sections(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertTrue(
            readme.startswith("# GCP Launchpad\n"),
            "README.md must start with '# GCP Launchpad'",
        )
        h2_sections = [
            line.strip() for line in readme.splitlines() if line.startswith("## ")
        ]
        self.assertEqual(h2_sections, CANONICAL_README_H2_SECTIONS)
        for required_link in (
            "QUESTIONNAIRE.md",
            "docs/01-end-to-end-operational-playbook.md",
            "docs/02-template-documentation-standard.md",
            "docs/03-org-completeness-scanner-design.md",
            "LICENSE",
        ):
            with self.subTest(link=required_link):
                self.assertIn(required_link, readme)

    def test_agent_instructions_align_and_roadmap_naming(self) -> None:
        required_refs = (
            "README.md",
            "QUESTIONNAIRE.md",
            "docs/01-end-to-end-operational-playbook.md",
            "docs/02-template-documentation-standard.md",
            "docs/03-org-completeness-scanner-design.md",
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
                self.assertRegex(payload["prefix"], r"^[a-z][a-z0-9-]{1,6}[a-z0-9]$")
                self.assertIn(payload["ci_identity_mode"], ("github_oidc_wif", "existing_ci_runner"))
                self.assertIsInstance(payload["selected_templates"], list)
                self.assertIsInstance(payload["environments"], list)
                self.assertIsInstance(payload["existing_landing_zone"], dict)

                finops = payload["finops"]
                self.assertEqual(
                    set(finops.keys()),
                    {
                        "create_dedicated_finops_project",
                        "finops_billing_export_location",
                        "monthly_budget_amount",
                        "environment_budgets",
                        "workload_budgets",
                        "budget_thresholds",
                        "enable_forecasted_threshold",
                        "finops_alert_email_addresses",
                    },
                )
                self.assertIsInstance(finops["create_dedicated_finops_project"], bool)
                self.assertIn(finops["finops_billing_export_location"], ("US", "EU", "asia-southeast1"))
                self.assertIsInstance(finops["monthly_budget_amount"], (int, float))
                self.assertNotIsInstance(finops["monthly_budget_amount"], bool)
                self.assertGreater(finops["monthly_budget_amount"], 0)
                self.assertIsInstance(finops["environment_budgets"], dict)
                self.assertTrue(finops["environment_budgets"])
                for amt in finops["environment_budgets"].values():
                    self.assertIsInstance(amt, (int, float))
                    self.assertNotIsInstance(amt, bool)
                    self.assertGreater(amt, 0)
                self.assertIsInstance(finops["workload_budgets"], dict)
                for wb in finops["workload_budgets"].values():
                    self.assertEqual(set(wb.keys()), {"amount", "projects", "labels", "alert_emails"})
                    self.assertIsInstance(wb["amount"], (int, float))
                    self.assertNotIsInstance(wb["amount"], bool)
                    self.assertGreater(wb["amount"], 0)
                    self.assertIsInstance(wb["projects"], list)
                    self.assertIsInstance(wb["labels"], dict)
                    self.assertIsInstance(wb["alert_emails"], list)
                self.assertIsInstance(finops["budget_thresholds"], list)
                self.assertTrue(finops["budget_thresholds"])
                for ratio in finops["budget_thresholds"]:
                    self.assertIsInstance(ratio, (int, float))
                    self.assertNotIsInstance(ratio, bool)
                    self.assertGreater(ratio, 0)
                    self.assertLessEqual(ratio, 1.0)
                self.assertIsInstance(finops["enable_forecasted_threshold"], bool)
                self.assertIsInstance(finops["finops_alert_email_addresses"], list)
                self.assertLessEqual(len(finops["finops_alert_email_addresses"]), 5)

                bdr = payload["backup_dr"]
                self.assertEqual(
                    set(bdr.keys()),
                    {
                        "enable_backup_dr",
                        "backup_enforced_retention_days",
                        "lock_backup_vault",
                        "soft_delete_retention_seconds",
                        "enable_dual_region_gcs",
                        "gcs_rpo",
                        "cross_border_dual_region_approved",
                        "bq_dr_mode",
                    },
                )
                for bkey in (
                    "enable_backup_dr",
                    "lock_backup_vault",
                    "enable_dual_region_gcs",
                    "cross_border_dual_region_approved",
                ):
                    self.assertIsInstance(bdr[bkey], bool)
                self.assertIn(bdr["backup_enforced_retention_days"], (14, 30))
                self.assertEqual(
                    bdr["soft_delete_retention_seconds"],
                    bdr["backup_enforced_retention_days"] * 86400,
                )
                self.assertIn(bdr["gcs_rpo"], ("DEFAULT", "ASYNC_TURBO"))
                self.assertIn(
                    bdr["bq_dr_mode"],
                    ("time_travel_only", "cross_region_replica", "enterprise_plus_failover"),
                )

                ngfw = payload["ngfw"]
                self.assertEqual(
                    set(ngfw.keys()),
                    {
                        "enable_hierarchical_firewall_policy",
                        "enable_ngfw_standard_rules",
                        "enable_secure_tags",
                        "enable_ngfw_enterprise",
                    },
                )
                for nkey in ngfw:
                    self.assertIsInstance(ngfw[nkey], bool)

                scc = payload["scc"]
                self.assertEqual(
                    set(scc.keys()),
                    {
                        "scc_tier",
                        "scc_scope",
                        "enable_audit_cmek",
                        "scc_alert_email_addresses",
                        "runtime_detectors",
                    },
                )
                self.assertIn(scc["scc_tier"], ("NONE", "STANDARD", "PREMIUM"))
                self.assertIn(scc["scc_scope"], ("FOLDER", "PROJECT"))
                self.assertIsInstance(scc["enable_audit_cmek"], bool)
                self.assertIsInstance(scc["scc_alert_email_addresses"], list)
                self.assertIsInstance(scc["runtime_detectors"], list)
                allowed_detectors = {
                    "EVENT_THREAT_DETECTION",
                    "CONTAINER_THREAT_DETECTION",
                    "VIRTUAL_MACHINE_THREAT_DETECTION",
                    "CLOUD_RUN_THREAT_DETECTION",
                }
                self.assertTrue(set(scc["runtime_detectors"]).issubset(allowed_detectors))

        gf = json.loads(
            (REPO_ROOT / "examples" / "platform-context.greenfield.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(gf["compliance_profile"], "regulated_fsi_rmit")
        self.assertTrue(gf["finops"]["create_dedicated_finops_project"])
        self.assertEqual(gf["backup_dr"]["backup_enforced_retention_days"], 30)
        self.assertFalse(gf["backup_dr"]["lock_backup_vault"])
        self.assertEqual(gf["backup_dr"]["soft_delete_retention_seconds"], 2592000)
        self.assertTrue(gf["backup_dr"]["enable_dual_region_gcs"])
        self.assertTrue(gf["ngfw"]["enable_ngfw_enterprise"])
        self.assertEqual(gf["scc"]["scc_tier"], "PREMIUM")
        self.assertIn("VIRTUAL_MACHINE_THREAT_DETECTION", gf["scc"]["runtime_detectors"])

        bf = json.loads(
            (REPO_ROOT / "examples" / "platform-context.brownfield.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(bf["compliance_profile"], "enterprise_standard")
        self.assertTrue(bf["finops"]["create_dedicated_finops_project"])
        self.assertEqual(bf["backup_dr"]["backup_enforced_retention_days"], 14)
        self.assertFalse(bf["backup_dr"]["lock_backup_vault"])
        self.assertEqual(bf["backup_dr"]["soft_delete_retention_seconds"], 1209600)
        self.assertFalse(bf["backup_dr"]["enable_dual_region_gcs"])
        self.assertFalse(bf["ngfw"]["enable_ngfw_enterprise"])
        self.assertEqual(bf["scc"]["scc_tier"], "STANDARD")
        for key in ("finops_project_id", "backup_project_id", "backup_vault_id", "by_environment"):
            self.assertIn(key, bf["existing_landing_zone"])
        self.assertEqual(set(bf["existing_landing_zone"]["by_environment"].keys()), {"dev", "staging", "prod"})

    def test_questionnaire_four_pillars_and_official_links(self) -> None:
        questionnaire = (REPO_ROOT / "QUESTIONNAIRE.md").read_text(encoding="utf-8")
        expected_tokens = (
            "### Pillar 1: FinOps Governance & Billing Export",
            "### Pillar 2: Backup & Disaster Recovery",
            "### Pillar 3: Cloud NGFW & Network Security",
            "### Pillar 4: Security Command Center (SCC)",
            "<prefix>-cmn-finops",
            "finops_billing_export_location",
            "enable_backup_dr",
            "lock_backup_vault",
            "soft_delete_policy",
            "soft_delete_retention_seconds",
            "ASYNC_TURBO",
            "BNM RMiT",
            "ALTER SCHEMA ... ADD REPLICA",
            "GCE_FIREWALL",
            "enable_ngfw_enterprise",
            "SCC Enterprise",
            "May 21, 2027",
            "scc_scope",
            "VIRTUAL_MACHINE_THREAT_DETECTION",
            "<prefix>_scc_findings",
            "^[a-z][a-z0-9-]{1,6}[a-z0-9]$",
            "https://docs.cloud.google.com/billing/docs/how-to/export-data-bigquery-setup",
            "https://docs.cloud.google.com/docs/migration/plan/landing-zones",
            "https://docs.cloud.google.com/billing/docs/how-to/export-data-bigquery",
            "https://cloud.google.com/storage/sla",
            "https://cloud.google.com/security/products/firewall",
            "https://cloud.google.com/firewall/pricing",
        )
        for token in expected_tokens:
            with self.subTest(token=token):
                self.assertIn(token, questionnaire)

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

        for empty_or_missing in (
            ["--dry-run", "--project", ""],
            ["--dry-run", "--org-id", ""],
            ["--dry-run", "--region", ""],
            ["--dry-run", "--project"],
            ["--project", "--dry-run"],
            ["--dry-run", "--project="],
            ["--dry-run", "--org-id="],
            ["--dry-run", "--region="],
        ):
            with self.subTest(empty_or_missing=empty_or_missing):
                usage_res = subprocess.run(
                    ["bash", str(script), *empty_or_missing],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(usage_res.returncode, 2, usage_res.stderr)

        with tempfile.TemporaryDirectory() as tmp_dir:
            bin_dir = Path(tmp_dir) / "bin"
            bin_dir.mkdir()
            for tool_name, body in (
                ("gcloud", "#!/usr/bin/env bash\necho '(unset)'\n"),
                ("gh", "#!/usr/bin/env bash\nexit 0\n"),
                ("terraform", "#!/usr/bin/env bash\nexit 0\n"),
            ):
                tool_path = bin_dir / tool_name
                tool_path.write_text(body, encoding="utf-8")
                tool_path.chmod(0o755)

            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}:{env['PATH']}"
            unset_res = subprocess.run(
                ["bash", str(script)],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(unset_res.returncode, 1)
            self.assertIn("No active gcloud account", unset_res.stderr)

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
            self.assertEqual(linked["bi_project_id"], "acme-dev01-data-bi")
            self.assertNotIn("bi_compute_project_id", linked)
            self.assertNotIn("finops_project_id", linked)
            self.assertNotIn("backup_project_id", linked)
            self.assertNotIn("backup_vault_id", linked)
            self.assertEqual(linked["dataform_release_config_name"], "dev-main")
            self.assertEqual(linked["dataform_release_config_id"], "dev-main")
            self.assertEqual(linked["primary_gold_dataset_id"], "gold")
            self.assertEqual(linked["kms_key_name"], linked["kms_key_id"])
            self.assertEqual(linked["network_id"], linked["vpc_id"])
            self.assertEqual(
                linked["dataform_service_account_email"],
                linked["dataform_sa_email"],
            )

            # Verify unfiltered keys match gcp-data-ingestion/stages/enterprise/variables.tf when present on disk.
            committed_expected_keys = {
                "core_project_id",
                "core_storage_project_id",
                "compute_project_id",
                "etl_compute_project_id",
                "analytics_project_id",
                "primary_gold_project_id",
                "bi_project_id",
                "governance_project_id",
                "bronze_dataset_id",
                "silver_dataset_id",
                "gold_dataset_id",
                "primary_gold_dataset_id",
                "quarantine_dataset_id",
                "assertions_dataset_id",
                "ops_telemetry_dataset_id",
                "landing_bucket_name",
                "dataform_repository_name",
                "dataform_release_config_name",
                "dataform_release_config_id",
                "dataform_sa_email",
                "dataform_service_account_email",
                "batch_loader_sa_email",
                "pubsub_writer_sa_email",
                "kms_key_id",
                "kms_key_name",
                "pii_restricted_policy_tag_id",
                "pii_masked_policy_tag_id",
                "vpc_id",
                "network_id",
                "subnet_id",
                "artifact_registry_repository_uri",
                "region",
                "environment",
                "prefix",
            }
            self.assertEqual(set(linked.keys()), committed_expected_keys)

            ingestion_vars_tf = (
                REPO_ROOT.parent / "gcp-data-ingestion" / "stages" / "enterprise" / "variables.tf"
            )
            if ingestion_vars_tf.is_file():
                declared_vars = set(
                    re.findall(
                        r'^\s*variable\s+"([A-Za-z0-9_]+)"\s*\{',
                        ingestion_vars_tf.read_text(encoding="utf-8"),
                        re.MULTILINE,
                    )
                )
                self.assertTrue(
                    set(linked.keys()).issubset(declared_vars),
                    f"Undeclared keys for gcp-data-ingestion: {sorted(set(linked.keys()) - declared_vars)}",
                )

            # Verify --env staging and --env prod resolution from by_environment.
            for target_env, expected_suffix in (("staging", "stg01"), ("prod", "prd01")):
                env_out = tmp_root / f"{target_env}.auto.tfvars.json"
                env_res = subprocess.run(
                    [
                        sys.executable,
                        str(script),
                        "--context",
                        str(brownfield_ctx),
                        "--env",
                        target_env,
                        "--output",
                        str(env_out),
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(env_res.returncode, 0, env_res.stderr)
                env_linked = json.loads(env_out.read_text(encoding="utf-8"))
                self.assertEqual(env_linked["environment"], target_env)
                self.assertEqual(env_linked["core_project_id"], f"acme-{expected_suffix}-data-core")
                self.assertEqual(env_linked["dataform_release_config_id"], f"{target_env}-main")

            # Verify RHS alias normalization works and unknown/conflicting keys fail closed.
            alias_ctx = tmp_root / "alias-context.json"
            alias_payload = json.loads(brownfield_ctx.read_text(encoding="utf-8"))
            alias_payload["existing_landing_zone"] = {
                "core_storage_project_id": "acme-dev01-data-core",
                "etl_compute_project_id": "acme-dev01-data-etl",
                "bronze_dataset_id": "bronze",
                "landing_bucket_name": "acme-dev01-raw-landing",
                "dataform_repository_name": "medallion-repo",
            }
            alias_ctx.write_text(json.dumps(alias_payload), encoding="utf-8")
            alias_out = tmp_root / "alias.auto.tfvars.json"
            alias_res = subprocess.run(
                [sys.executable, str(script), "--context", str(alias_ctx), "--output", str(alias_out)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(alias_res.returncode, 0, alias_res.stderr)
            self.assertEqual(
                json.loads(alias_out.read_text(encoding="utf-8"))["core_project_id"],
                "acme-dev01-data-core",
            )

            unknown_ctx = tmp_root / "unknown-key-context.json"
            unknown_payload = json.loads(brownfield_ctx.read_text(encoding="utf-8"))
            unknown_payload["existing_landing_zone"]["unexpected_typo_key"] = "oops"
            unknown_ctx.write_text(json.dumps(unknown_payload), encoding="utf-8")
            unknown_res = subprocess.run(
                [sys.executable, str(script), "--context", str(unknown_ctx), "--output", str(out_file)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(unknown_res.returncode, 0)
            self.assertIn("ERROR:", unknown_res.stderr)

            unknown_env_ctx = tmp_root / "unknown-env-key-context.json"
            unknown_env_payload = json.loads(brownfield_ctx.read_text(encoding="utf-8"))
            unknown_env_payload["existing_landing_zone"]["by_environment"]["prod"]["bad_key"] = "x"
            unknown_env_ctx.write_text(json.dumps(unknown_env_payload), encoding="utf-8")
            unknown_env_res = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--context",
                    str(unknown_env_ctx),
                    "--env",
                    "dev",
                    "--output",
                    str(out_file),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(unknown_env_res.returncode, 0)
            self.assertIn("ERROR:", unknown_env_res.stderr)

            # Verify optional Dataform, Dataplex, and Datastream fields pass validation and filter cleanly.
            ext_out = tmp_root / "extended.auto.tfvars.json"
            target_vars = tmp_root / "variables.tf"
            target_vars.write_text(
                'variable "core_storage_project_id" { type = string }\n'
                'variable "bronze_dataset_id" { type = string }\n'
                'variable "landing_bucket_name" { type = string }\n'
                'variable "dataform_release_config_name" { type = string }\n'
                'variable "dataplex_profile_scan_id" { type = string }\n'
                'variable "dataplex_quality_scan_id" { type = string }\n'
                'variable "datastream_network_attachment_id" { type = string }\n',
                encoding="utf-8",
            )
            ext_res = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--context",
                    str(brownfield_ctx),
                    "--dataform-release-config-name",
                    "prod-release",
                    "--dataplex-profile-scan-id",
                    "silver-orders-profile",
                    "--dataplex-quality-scan-id",
                    "silver-orders-dq",
                    "--datastream-network-attachment-id",
                    "projects/acme-dev01-network/regions/asia-southeast1/networkAttachments/ds-psc",
                    "--target-variables-tf",
                    str(target_vars),
                    "--output",
                    str(ext_out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(ext_res.returncode, 0, ext_res.stderr)
            filtered = json.loads(ext_out.read_text(encoding="utf-8"))
            self.assertEqual(
                set(filtered.keys()),
                {
                    "bronze_dataset_id",
                    "core_storage_project_id",
                    "dataform_release_config_name",
                    "dataplex_profile_scan_id",
                    "dataplex_quality_scan_id",
                    "datastream_network_attachment_id",
                    "landing_bucket_name",
                },
            )

            # Verify full Dataform releaseConfig and Dataplex dataScans resource paths are accepted.
            full_path_out = tmp_root / "full-paths.auto.tfvars.json"
            full_rc = "projects/acme-dev01-data-etl/locations/asia-southeast1/repositories/medallion-repo/releaseConfigs/prod-main"
            full_prof = "projects/acme-dev01-data-gold/locations/asia-southeast1/dataScans/silver-orders-profile"
            full_qual = "projects/acme-dev01-data-gold/locations/asia-southeast1/dataScans/silver-orders-dq"
            full_res = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--context",
                    str(brownfield_ctx),
                    "--dataform-release-config-name",
                    full_rc,
                    "--dataplex-profile-scan-id",
                    full_prof,
                    "--dataplex-quality-scan-id",
                    full_qual,
                    "--output",
                    str(full_path_out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(full_res.returncode, 0, full_res.stderr)
            full_linked = json.loads(full_path_out.read_text(encoding="utf-8"))
            self.assertEqual(full_linked["dataform_release_config_name"], full_rc)
            self.assertEqual(full_linked["dataform_release_config_id"], full_rc)
            self.assertEqual(full_linked["dataplex_profile_scan_id"], full_prof)
            self.assertEqual(full_linked["dataplex_quality_scan_id"], full_qual)

            # Verify conflicting LHS/RHS alias keys fail closed.
            conflict_ctx = tmp_root / "conflict-alias.json"
            conflict_payload = json.loads(brownfield_ctx.read_text(encoding="utf-8"))
            conflict_payload["existing_landing_zone"]["core_storage_project_id"] = "acme-other-core"
            conflict_ctx.write_text(json.dumps(conflict_payload), encoding="utf-8")
            conflict_res = subprocess.run(
                [sys.executable, str(script), "--context", str(conflict_ctx), "--output", str(out_file)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(conflict_res.returncode, 0)
            self.assertIn("Conflicting values", conflict_res.stderr)

            # Verify invalid identifiers, non-numeric policy tags, metacharacters, and missing fields fail cleanly.
            for bad_args in (
                ["--core-project-id", "BAD_PROJECT"],
                ["--bronze-dataset-id", "1bad_dataset"],
                ["--kms-key-id", "not/a/kms/key"],
                ["--kms-key-id", 'projects/acme-dev01-gov/locations/asia-southeast1/keyRings/ring"/cryptoKeys/key'],
                ["--vpc-id", "invalid-vpc"],
                ["--vpc-id", "projects/acme-dev01-net/global/networks/vpc;rm"],
                ["--subnet-id", "projects/acme-dev01-net/regions/asia-southeast1/subnetworks/sub$x"],
                ["--dataform-repository-name", "projects/acme-dev01-etl/locations/asia-southeast1/repositories/repo'x"],
                ["--dataform-repository-name", "projects/acme-dev01-etl/locations/asia-southeast1/repositories/repo.dot"],
                ["--context", str(brownfield_ctx), "--dataform-release-config-name", "projects/acme-dev01-etl/locations/asia-southeast1/repositories/medallion-repo/bad/prod"],
                ["--context", str(brownfield_ctx), "--dataplex-profile-scan-id", "BAD_SCAN"],
                ["--context", str(brownfield_ctx), "--dataplex-quality-scan-id", "BAD_SCAN"],
                ["--context", str(brownfield_ctx), "--env", "qa"],
                ["--pii-restricted-policy-tag-id", "projects/acme-dev01-data-gov/locations/asia-southeast1/taxonomies/example-tax-id/policyTags/12345678"],
                ["--pii-masked-policy-tag-id", "projects/acme-dev01-data-gov/locations/asia-southeast1/taxonomies/1000000001/policyTags/non-numeric"],
                ["--datastream-network-attachment-id", "projects/bad/global/networkAttachments/ds"],
                ["--prefix", "a-"],
                ["--prefix", "a"],
                ["--prefix", "ab"],
                ["--prefix", "toolongprefix"],
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

            # Verify non-string values in existing_landing_zone are rejected.
            bad_ctx = tmp_root / "bad-type-context.json"
            ctx_payload = json.loads(brownfield_ctx.read_text(encoding="utf-8"))
            ctx_payload["existing_landing_zone"]["bronze_dataset_id"] = 12345
            bad_ctx.write_text(json.dumps(ctx_payload), encoding="utf-8")
            type_res = subprocess.run(
                [sys.executable, str(script), "--context", str(bad_ctx), "--output", str(out_file)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(type_res.returncode, 0)
            self.assertIn("ERROR:", type_res.stderr)

            # Verify OSError (IsADirectoryError) exits cleanly without a Python traceback.
            dir_out = tmp_root / "existing_dir"
            dir_out.mkdir()
            os_res = subprocess.run(
                [sys.executable, str(script), "--context", str(brownfield_ctx), "--output", str(dir_out)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(os_res.returncode, 0)
            self.assertIn("ERROR:", os_res.stderr)
            self.assertNotIn("Traceback", os_res.stderr)

    def test_generate_brownfield_link_four_pillar_validation(self) -> None:
        script = REPO_ROOT / "scripts" / "generate-brownfield-link.py"
        brownfield_ctx = REPO_ROOT / "examples" / "platform-context.brownfield.json"

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            out_file = tmp_root / "pillar_linked.auto.tfvars.json"
            target_vars = tmp_root / "variables.tf"
            target_vars.write_text(
                'variable "finops_project_id" { type = string }\n'
                'variable "backup_project_id" { type = string }\n'
                'variable "backup_vault_id" { type = string }\n',
                encoding="utf-8",
            )
            override_vault = (
                "projects/acme-prod-cmn-backup/locations/asia-southeast1/backupVaults/prod-vault-02"
            )
            res = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--context",
                    str(brownfield_ctx),
                    "--finops-project-id",
                    "acme-prod-cmn-finops",
                    "--backup-project-id",
                    "acme-prod-cmn-backup",
                    "--backup-vault-id",
                    override_vault,
                    "--target-variables-tf",
                    str(target_vars),
                    "--output",
                    str(out_file),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertEqual(stat.S_IMODE(out_file.stat().st_mode), 0o600)
            linked = json.loads(out_file.read_text(encoding="utf-8"))
            self.assertEqual(
                linked,
                {
                    "backup_project_id": "acme-prod-cmn-backup",
                    "backup_vault_id": override_vault,
                    "finops_project_id": "acme-prod-cmn-finops",
                },
            )

            for bad_args in (
                ["--context", str(brownfield_ctx), "--finops-project-id", "BAD_FINOPS"],
                ["--context", str(brownfield_ctx), "--finops-project-id", "ab"],
                ["--context", str(brownfield_ctx), "--backup-project-id", "BAD_BACKUP"],
                ["--context", str(brownfield_ctx), "--backup-vault-id", "not/a/vault"],
                [
                    "--context",
                    str(brownfield_ctx),
                    "--backup-vault-id",
                    "projects/acme-dev01-cmn-backup/locations/asia-southeast1/backupVaults/UPPER_BAD",
                ],
                [
                    "--context",
                    str(brownfield_ctx),
                    "--backup-vault-id",
                    "projects/acme-dev01-cmn-backup/locations/asia-southeast1/backupVaults/v",
                ],
            ):
                with self.subTest(bad_args=bad_args):
                    err_res = subprocess.run(
                        [sys.executable, str(script), *bad_args, "--output", str(out_file)],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertNotEqual(err_res.returncode, 0)
                    self.assertIn("ERROR:", err_res.stderr)

            for field in ("finops_project_id", "backup_project_id", "backup_vault_id"):
                for bad_val in (True, 42):
                    with self.subTest(field=field, bad_val=bad_val):
                        bad_ctx = tmp_root / f"bad-{field}-{type(bad_val).__name__}.json"
                        payload = json.loads(brownfield_ctx.read_text(encoding="utf-8"))
                        payload["existing_landing_zone"][field] = bad_val
                        bad_ctx.write_text(json.dumps(payload), encoding="utf-8")
                        type_res = subprocess.run(
                            [
                                sys.executable,
                                str(script),
                                "--context",
                                str(bad_ctx),
                                "--output",
                                str(out_file),
                            ],
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                        self.assertNotEqual(type_res.returncode, 0)
                        self.assertIn("ERROR:", type_res.stderr)

    def test_org_scanner_design_covers_d00_through_d15(self) -> None:
        scanner_doc = (
            REPO_ROOT / "docs" / "03-org-completeness-scanner-design.md"
        ).read_text(encoding="utf-8")
        self.assertIn("sixteen platform areas (`D00` through `D15`)", scanner_doc)
        self.assertIn("## 16-Area Control-Plane Checks", scanner_doc)
        for idx in range(16):
            check_id = f"`D{idx:02d}`"
            with self.subTest(check_id=check_id):
                self.assertIn(check_id, scanner_doc)
        for expected in (
            "<prefix>-cmn-finops",
            "BackupVault",
            "soft_delete_policy",
            "GCE_FIREWALL",
            "<prefix>_scc_findings",
            "roles/billing.viewer",
            "roles/backupdr.viewer",
            "roles/compute.networkViewer",
            "roles/compute.orgFirewallPolicyUser",
            "roles/resourcemanager.tagViewer",
            "roles/monitoring.viewer",
            "roles/securitycenter.adminViewer",
            "Cloud Billing Account",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, scanner_doc)

    def test_playbook_contains_complete_commands_and_variables(self) -> None:
        playbook = (REPO_ROOT / "docs" / "01-end-to-end-operational-playbook.md").read_text(
            encoding="utf-8"
        )
        for expected in (
            "foundation/01-org-governance foundation/02-security-network",
            "foundation/02-security-network data/enterprise/01-platform data/enterprise/02-governance-ops",
            "--from-gcs gs://<iac-outputs-bucket>/foundation-outputs.json",
            "--env dev",
            "stages/enterprise",
            "GCP_WIF_PROVIDER",
            "GCP_WIF_SERVICE_ACCOUNT",
            "<prefix>_ops_telemetry.pipeline_runs",
            "make plan STAGE=<stage> ENV=<env> TFSTATE_BUCKET=<bucket>",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, playbook)

    def test_ci_workflow_security_hardening(self) -> None:
        workflow_files = sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml"))
        self.assertGreaterEqual(len(workflow_files), 1)
        for wf_path in workflow_files:
            ci_text = wf_path.read_text(encoding="utf-8")
            with self.subTest(workflow=wf_path.name):
                self.assertRegex(ci_text, r"(?m)^permissions:\s*\n\s*contents:\s*read\s*$")
                self.assertNotIn("write-all", ci_text)
                uses_refs = re.findall(r"(?m)^\s*uses:\s*([^\s#]+)", ci_text)
                self.assertGreaterEqual(len(uses_refs), 2)
                for ref in uses_refs:
                    with self.subTest(action_ref=ref):
                        self.assertRegex(ref, r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}$")

                in_perms_block = False
                perms_indent = 0
                in_run_block = False
                run_indent = 0
                for line in ci_text.splitlines():
                    stripped = line.lstrip()
                    indent = len(line) - len(stripped)
                    if in_perms_block:
                        if stripped and indent <= perms_indent:
                            in_perms_block = False
                        elif stripped and not stripped.startswith("#"):
                            self.assertNotRegex(
                                stripped,
                                r":\s*write\b",
                                f"{wf_path.name}: Unapproved write permission in permissions: {stripped}",
                            )
                    if re.match(r"^permissions\s*:", stripped):
                        self.assertNotRegex(
                            stripped,
                            r":\s*(?:write-all|write)\b",
                            f"{wf_path.name}: Write scope on permissions line: {stripped}",
                        )
                        in_perms_block = True
                        perms_indent = indent
                        continue

                    run_match = re.match(r"^(?:-\s*)?run\s*:\s*(.*)$", stripped)
                    if run_match:
                        self.assertNotIn("${{", stripped, f"{wf_path.name}: Expression interpolation inside run:")
                        run_rhs = re.sub(r"\s+#.*$", "", run_match.group(1)).strip()
                        if run_rhs in ("|", ">", "|-", ">-", "|+", ">+"):
                            in_run_block = True
                            run_indent = indent
                        continue
                    if in_run_block:
                        if stripped and indent <= run_indent:
                            in_run_block = False
                        else:
                            self.assertNotIn("${{", line, f"{wf_path.name}: Expression interpolation inside run: block")

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
            content = path.read_text(encoding="utf-8")
            sentences = _extract_markdown_sentences(content)
            table_cells = _extract_markdown_table_cells(content)
            with self.subTest(markdown=rel):
                for sentence in sentences:
                    words = [w for w in sentence.split() if w]
                    self.assertLessEqual(
                        len(words),
                        20,
                        f"Sentence exceeds 20 words ({len(words)}) in {rel}: {sentence}",
                    )
                for cell in table_cells:
                    words = [w for w in cell.split() if w]
                    self.assertLessEqual(
                        len(words),
                        20,
                        f"Table cell exceeds 20 words ({len(words)}) in {rel}: {cell}",
                    )

    def test_visual_assets_have_valid_headers(self) -> None:
        webp_path = REPO_ROOT / "assets" / "cloud-city-launchpad.webp"
        gif_path = REPO_ROOT / "assets" / "cloud-city-launchpad.gif"
        png_path = REPO_ROOT / "assets" / "cloud-city-org-scanner.png"

        for asset_path in (webp_path, png_path):
            with self.subTest(asset=str(asset_path.relative_to(REPO_ROOT))):
                self.assertTrue(asset_path.is_file(), f"Missing {asset_path}")
                self.assertGreater(asset_path.stat().st_size, 100_000)

        webp_head = webp_path.read_bytes()[:12]
        self.assertEqual(webp_head[:4], b"RIFF")
        self.assertEqual(webp_head[8:12], b"WEBP")

        self.assertFalse(gif_path.exists(), f"Duplicate GIF asset must not exist: {gif_path}")

        png_head = png_path.read_bytes()[:8]
        self.assertEqual(png_head, b"\x89PNG\r\n\x1a\n")


if __name__ == "__main__":
    unittest.main()
